import copy
import os
from typing import Dict, Optional, Sequence
import typing
import keyring

from pyicloud_ipd.asset_version import AssetVersion
from pyicloud_ipd.version_size import AssetVersionSize, VersionSize

from .exceptions import PyiCloudNoStoredPasswordAvailableException

KEYRING_SYSTEM = 'pyicloud://icloud-password'


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


def password_exists_in_keyring(username:str) -> bool:
    try:
        return get_password_from_keyring(username) is not None
    except PyiCloudNoStoredPasswordAvailableException:
        return False


def get_password_from_keyring(username:str) -> Optional[str]:
    result = keyring.get_password(
        KEYRING_SYSTEM,
        username
    )
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


def store_password_in_keyring(username: str, password:str) -> None:
    # if get_password_from_keyring(username) is not None:
    #     # Apple can save only into empty keyring
    #     return delete_password_in_keyring(username)
    return keyring.set_password(
        KEYRING_SYSTEM,
        username,
        password,
    )


def delete_password_in_keyring(username:str) -> None:
    return keyring.delete_password(
        KEYRING_SYSTEM,
        username,
    )


def underscore_to_camelcase(word:str , initial_capital: bool=False) -> str:
    words = [x.capitalize() or '_' for x in word.split('_')]
    if not initial_capital:
        words[0] = words[0].lower()

    return ''.join(words)


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

def add_suffix_to_filename(suffix: str, filename: str) -> str:
    _n, _e = os.path.splitext(filename)
    return _n + suffix + _e

def disambiguate_filenames(_versions: Dict[VersionSize, AssetVersion], _sizes:Sequence[AssetVersionSize]) -> Dict[AssetVersionSize, AssetVersion]:
    _results: Dict[AssetVersionSize, AssetVersion] = {}
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
                _results[AssetVersionSize.ADJUSTED] = copy.copy(_versions[AssetVersionSize.ORIGINAL])
        else:
            if AssetVersionSize.ADJUSTED in _results and _results[AssetVersionSize.ORIGINAL].filename == _results[AssetVersionSize.ADJUSTED].filename:
                _results[AssetVersionSize.ADJUSTED].filename = add_suffix_to_filename("-adjusted", _results[AssetVersionSize.ADJUSTED].filename)

    # alternative
    if AssetVersionSize.ALTERNATIVE in _sizes:
        if AssetVersionSize.ORIGINAL not in _sizes and AssetVersionSize.ADJUSTED not in _results:
            if AssetVersionSize.ALTERNATIVE not in _results:
                # clone
                _results[AssetVersionSize.ALTERNATIVE] = copy.copy(_versions[AssetVersionSize.ORIGINAL])
        else:
            if AssetVersionSize.ALTERNATIVE in _results:
                if AssetVersionSize.ADJUSTED in _results and _results[AssetVersionSize.ADJUSTED].filename == _results[AssetVersionSize.ALTERNATIVE].filename or AssetVersionSize.ORIGINAL in _results and _results[AssetVersionSize.ORIGINAL].filename == _results[AssetVersionSize.ALTERNATIVE].filename:
                    _results[AssetVersionSize.ALTERNATIVE].filename = add_suffix_to_filename("-alternative", _results[AssetVersionSize.ALTERNATIVE].filename)

    for _size in _sizes:
        if _size not in [AssetVersionSize.ORIGINAL, AssetVersionSize.ADJUSTED, AssetVersionSize.ALTERNATIVE]:
            if _size not in _results:
                # ensure original is downloaded - mimic existing behavior
                if AssetVersionSize.ORIGINAL not in _sizes:
                    _results[AssetVersionSize.ORIGINAL] = copy.copy(_versions[AssetVersionSize.ORIGINAL])
            # else:
            #     _n, _e = os.path.splitext(_results[_size]["filename"])
            #     _results[_size]["filename"] = f"{_n}-{_size}{_e}"


    return _results
