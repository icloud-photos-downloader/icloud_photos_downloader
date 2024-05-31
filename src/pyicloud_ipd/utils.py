import getpass
import os
from typing import Any, Callable, Dict, Optional, TypeVar
import keyring
import sys

from .exceptions import PyiCloudNoStoredPasswordAvailableException

KEYRING_SYSTEM = 'pyicloud://icloud-password'


def get_password(username:str, interactive:bool=sys.stdout.isatty()) -> str:
    try:
        return get_password_from_keyring(username)
    except PyiCloudNoStoredPasswordAvailableException:
        if not interactive:
            raise

        return getpass.getpass(
            'Enter iCloud password for {username}: '.format(
                username=username,
            )
        )


def password_exists_in_keyring(username:str) -> bool:
    try:
        get_password_from_keyring(username)
    except PyiCloudNoStoredPasswordAvailableException:
        return False

    return True


def get_password_from_keyring(username:str) -> str:
    result = keyring.get_password(
        KEYRING_SYSTEM,
        username
    )
    if result is None:
        raise PyiCloudNoStoredPasswordAvailableException(
            "No pyicloud password for {username} could be found "
            "in the system keychain.  Use the `--store-in-keyring` "
            "command-line option for storing a password for this "
            "username.".format(
                username=username,
            )
        )

    return result


def store_password_in_keyring(username: str, password:str) -> None:
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

_Tin = TypeVar('_Tin')
_Tout = TypeVar('_Tout')
_Tinter = TypeVar('_Tinter')
def compose(f:Callable[[_Tinter], _Tout], g: Callable[[_Tin], _Tinter]) -> Callable[[_Tin], _Tout]:
    """f after g composition of functions"""
    def inter_(value: _Tin) -> _Tout:
        return f(g(value))
    return inter_

def identity(value: _Tin) -> _Tin:
    """identity function"""
    return value

# def filename_with_size(filename: str, size: str, original: Optional[Dict[str, Any]]) -> str:
#     """Returns the filename with size, e.g. IMG1234.jpg, IMG1234-small.jpg"""
#     if size == 'original' or size == 'alternative':
#         # TODO what if alternative ext matches original?
#         return filename
#     # for adjustments we add size only if extension matches original (alternative
#     if size == "adjusted" and original != None and original["filename"] != filename:
#         return filename
#     return (f"-{size}.").join(filename.rsplit(".", 1))

def disambiguate_filenames(_versions: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    _results: Dict[ str, Dict[str, Any]] = {}
    for _size, _version in _versions.items():
        _results[_size] = _version.copy()
        if _size in ["original", "originalVideo"]:
            # never adjust
            continue
        elif _size in ["alternative"]:
            if not (_results[_size]["filename"] == _versions["original"]["filename"] or ("adjusted" in _versions and _results[_size]["filename"] == _versions["adjusted"]["filename"])):
                # if different from original or adjusted, then do not need to change
                continue
        elif _size in ["adjusted"]:
            if _results[_size]["filename"] != _versions["original"]["filename"]:
                # if different from original, then do not need to change
                continue

        # otherwise add size
        if "Video" in _size:
            _size_cleaned = _size[:-5]
        else:
            _size_cleaned = _size
        _n, _e = os.path.splitext(_results[_size]["filename"])
        _results[_size]["filename"] = f"{_n}-{_size_cleaned}{_e}"

    return _results

