"""Utils."""
import getpass
import keyring
import sys

from .exceptions import PyiCloudNoStoredPasswordAvailableException


KEYRING_SYSTEM = "pyicloud://icloud-password"


def get_password(username, interactive=sys.stdout.isatty()):
    """Get the password from a username."""
    try:
        return get_password_from_keyring(username)
    except PyiCloudNoStoredPasswordAvailableException:
        if not interactive:
            raise

        return getpass.getpass(
            "Enter iCloud password for {username}: ".format(
                username=username,
            )
        )


def password_exists_in_keyring(username):
    """Return true if the password of a username exists in the keyring."""
    try:
        get_password_from_keyring(username)
    except PyiCloudNoStoredPasswordAvailableException:
        return False

    return True


def get_password_from_keyring(username):
    """Get the password from a username."""
    result = keyring.get_password(KEYRING_SYSTEM, username)
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


def store_password_in_keyring(username, password):
    """Store the password of a username."""
    return keyring.set_password(
        KEYRING_SYSTEM,
        username,
        password,
    )


def delete_password_in_keyring(username):
    """Delete the password of a username."""
    return keyring.delete_password(
        KEYRING_SYSTEM,
        username,
    )


def underscore_to_camelcase(word, initial_capital=False):
    """Transform a word to camelCase."""
    words = [x.capitalize() or "_" for x in word.split("_")]
    if not initial_capital:
        words[0] = words[0].lower()

    return "".join(words)
