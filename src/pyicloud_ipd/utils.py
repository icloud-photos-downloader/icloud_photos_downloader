import copy
from typing import TYPE_CHECKING, Any, Callable, Dict, Sequence, Tuple, TypeVar

import keyring
from requests import Response, Timeout
from requests.exceptions import ConnectionError
from urllib3.exceptions import NewConnectionError

from pyicloud_ipd.asset_version import AssetVersion, add_suffix_to_filename
from pyicloud_ipd.version_size import AssetVersionSize, VersionSize

from .exceptions import (
    PyiCloudConnectionErrorException,
    PyiCloudNoStoredPasswordAvailableException,
    PyiCloudServiceUnavailableException,
)

if TYPE_CHECKING:
    from pyicloud_ipd.services.photos import PhotoAsset

KEYRING_SYSTEM = "pyicloud://icloud-password"


# def get_password(username:str, interactive:bool=sys.stdout.isatty()) -> str:
#     try:
#         return get_password_from_keyring(username)
#     except PyiCloudNoStoredPasswordAvailableException:
#         if not interactive:
#             raise

#         return getpass.getpass(
#             'Enter iCloud password for {username}: '.format(
#                 username=username,
#             )
#         )


def password_exists_in_keyring(username: str) -> bool:
    try:
        return get_password_from_keyring(username) is not None
    except PyiCloudNoStoredPasswordAvailableException:
        return False


def get_password_from_keyring(username: str) -> str | None:
    result = keyring.get_password(KEYRING_SYSTEM, username)
    # if result is None:
    #     raise PyiCloudNoStoredPasswordAvailableException(
    #         "No pyicloud password for {username} could be found "
    #         "in the system keychain.  Use the `--store-in-keyring` "
    #         "command-line option for storing a password for this "
    #         "username.".format(
    #             username=username,
    #         )
    #     )

    return result


def store_password_in_keyring(username: str, password: str) -> None:
    # if get_password_from_keyring(username) is not None:
    #     # Apple can save only into empty keyring
    #     return delete_password_in_keyring(username)
    return keyring.set_password(
        KEYRING_SYSTEM,
        username,
        password,
    )


def delete_password_in_keyring(username: str) -> None:
    return keyring.delete_password(
        KEYRING_SYSTEM,
        username,
    )


def underscore_to_camelcase(word: str, initial_capital: bool = False) -> str:
    words = [x.capitalize() or "_" for x in word.split("_")]
    if not initial_capital:
        words[0] = words[0].lower()

    return "".join(words)


# def filename_with_size(filename: str, size: str, original: Optional[Dict[str, Any]]) -> str:
#     """Returns the filename with size, e.g. IMG1234.jpg, IMG1234-small.jpg"""
#     if size == 'original' or size == 'alternative':
#         # TODO what if alternative ext matches original?
#         return filename
#     # for adjustments we add size only if extension matches original (alternative
#     if size == "adjusted" and original != None and original["filename"] != filename:
#         return filename
#     return (f"-{size}.").join(filename.rsplit(".", 1))


def size_to_suffix(size: VersionSize) -> str:
    return f"-{size}".lower()


def disambiguate_filenames(
    _versions: Dict[VersionSize, AssetVersion],
    _sizes: Sequence[AssetVersionSize],
    photo_asset: "PhotoAsset",
    lp_filename_generator: Callable[[str], str],
) -> Tuple[Dict[AssetVersionSize, AssetVersion], Dict[AssetVersionSize, str]]:
    _results: Dict[AssetVersionSize, AssetVersion] = {}
    _filename_overrides: Dict[AssetVersionSize, str] = {}

    # add those that were requested
    for _size in _sizes:
        _version = _versions.get(_size)
        if _version:
            _results[_size] = copy.copy(_version)

    # adjusted
    if AssetVersionSize.ADJUSTED in _sizes:
        if AssetVersionSize.ORIGINAL not in _sizes:
            if AssetVersionSize.ADJUSTED not in _results:
                # clone
                _results[AssetVersionSize.ADJUSTED] = copy.copy(
                    _versions[AssetVersionSize.ORIGINAL]
                )
        else:
            if AssetVersionSize.ADJUSTED in _results:
                original_filename = photo_asset.calculate_version_filename(
                    _results[AssetVersionSize.ORIGINAL],
                    AssetVersionSize.ORIGINAL,
                    lp_filename_generator,
                )
                adjusted_filename = photo_asset.calculate_version_filename(
                    _results[AssetVersionSize.ADJUSTED],
                    AssetVersionSize.ADJUSTED,
                    lp_filename_generator,
                )
                if original_filename == adjusted_filename:
                    # Store filename override for adjusted version
                    _filename_overrides[AssetVersionSize.ADJUSTED] = add_suffix_to_filename(
                        "-adjusted", adjusted_filename
                    )

    # alternative
    if AssetVersionSize.ALTERNATIVE in _sizes:
        if AssetVersionSize.ALTERNATIVE not in _results:
            # Only clone from original when alternative is missing AND original is not requested
            if AssetVersionSize.ORIGINAL not in _sizes:
                _results[AssetVersionSize.ALTERNATIVE] = copy.copy(
                    _versions[AssetVersionSize.ORIGINAL]
                )
        else:
            # Check for filename conflicts and add disambiguating suffix if needed
            alternative_filename = photo_asset.calculate_version_filename(
                _results[AssetVersionSize.ALTERNATIVE],
                AssetVersionSize.ALTERNATIVE,
                lp_filename_generator,
            )
            alt_adjusted_filename: str | None = None
            alt_original_filename: str | None = None

            if AssetVersionSize.ADJUSTED in _results:
                alt_adjusted_filename = photo_asset.calculate_version_filename(
                    _results[AssetVersionSize.ADJUSTED],
                    AssetVersionSize.ADJUSTED,
                    lp_filename_generator,
                )
            if AssetVersionSize.ORIGINAL in _results:
                alt_original_filename = photo_asset.calculate_version_filename(
                    _results[AssetVersionSize.ORIGINAL],
                    AssetVersionSize.ORIGINAL,
                    lp_filename_generator,
                )

            if (alt_adjusted_filename and alternative_filename == alt_adjusted_filename) or (
                alt_original_filename and alternative_filename == alt_original_filename
            ):
                # Store filename override for alternative version
                _filename_overrides[AssetVersionSize.ALTERNATIVE] = add_suffix_to_filename(
                    "-alternative", alternative_filename
                )

    for _size in _sizes:
        if (
            _size
            not in [
                AssetVersionSize.ORIGINAL,
                AssetVersionSize.ADJUSTED,
                AssetVersionSize.ALTERNATIVE,
            ]
            and _size not in _results
            and AssetVersionSize.ORIGINAL not in _sizes
        ):
            # ensure original is downloaded - mimic existing behavior
            _results[AssetVersionSize.ORIGINAL] = copy.copy(_versions[AssetVersionSize.ORIGINAL])
            # else:
            #     _n, _e = os.path.splitext(_results[_size]["filename"])
            #     _results[_size]["filename"] = f"{_n}-{_size}{_e}"

    return _results, _filename_overrides


def throw_on_503(response: Response) -> Response:
    if response.status_code == 503:
        raise PyiCloudServiceUnavailableException(
            "Apple iCloud is temporary refusing to serve icloudpd"
        )
    else:
        return response


F = TypeVar("F", bound=Callable[..., Any])


def handle_connection_error(func: F) -> F:
    """Decorator to catch connection errors and raise PyiCloudConnectionErrorException."""

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except (ConnectionError, TimeoutError, Timeout, NewConnectionError) as error:
            raise PyiCloudConnectionErrorException(
                "Cannot connect to Apple iCloud service"
            ) from error

    return wrapper  # type: ignore[return-value]
