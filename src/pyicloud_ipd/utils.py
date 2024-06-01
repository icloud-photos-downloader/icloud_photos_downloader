import getpass
import os
from typing import Any, Callable, Dict, Optional, Sequence, TypeVar
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

def disambiguate_filenames(_versions: Dict[str, Dict[str, Any]], _sizes:Sequence[str]) -> Dict[str, Dict[str, Any]]:
    _results: Dict[ str, Dict[str, Any]] = {}
    # add those that were requested
    for _size in _sizes:
        _version = _versions.get(_size)
        if _version:
            _results[_size] = _version.copy()

    # adjusted
    if "adjusted" in _sizes:
        if "original" not in _sizes:
            if "adjusted" not in _results:
                # clone
                _results["adjusted"] = _versions["original"].copy()
        else:
            if "adjusted" in _results and _results["original"]["filename"] == _results["adjusted"]["filename"]:
                _n, _e = os.path.splitext(_results["adjusted"]["filename"])
                _results["adjusted"]["filename"] = _n + "-adjusted" + _e

    # alternative
    if "alternative" in _sizes:
        if "original" not in _sizes and "adjusted" not in _results:
            if "alternative" not in _results:
                # clone
                _results["alternative"] = _versions["original"].copy()
        else:
            if "adjusted" in _results and _results["adjusted"]["filename"] == _results["alternative"]["filename"] or "original" in _results and _results["original"]["filename"] == _results["alternative"]["filename"]:
                _n, _e = os.path.splitext(_results["alternative"]["filename"])
                _results["alternative"]["filename"] = _n + "-alternative" + _e

    for _size in _sizes:
        if _size not in ["original", "adjusted", "alternative"]:
            if _size not in _results:
                # ensure original is downloaded - mimic existing behavior
                if "original" not in _sizes:
                    _results["original"] = _versions["original"].copy()
            # else:
            #     _n, _e = os.path.splitext(_results[_size]["filename"])
            #     _results[_size]["filename"] = f"{_n}-{_size}{_e}"

    return _results

