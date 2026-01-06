#! /usr/bin/env python
"""
A Command Line Tool for managing iCloud keyring credentials.
"""

import argparse
import getpass
import sys
from typing import NoReturn, Sequence

from foundation import version_info_formatted
from foundation.predicates import in_pred
from foundation.string_utils import strip_and_lower

from . import utils


def main(args: Sequence[str] | None = None) -> NoReturn:
    """Main commandline entrypoint for iCloud keyring management."""
    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser(description="iCloud Keyring Management Tool")

    parser.add_argument(
        "--username",
        action="store",
        dest="username",
        help="Apple ID username",
    )
    parser.add_argument(
        "--delete-from-keyring",
        action="store_true",
        dest="delete_from_keyring",
        default=False,
        help="Delete stored password from system keyring for this username",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        dest="version",
        help="Show the version, commit hash and timestamp",
    )

    command_line = parser.parse_args(args)

    if command_line.version:
        print(version_info_formatted())
        sys.exit(0)

    username: str | None = strip_and_lower(command_line.username) if command_line.username else None

    if username is None:
        parser.error("--username is required")

    if command_line.delete_from_keyring:
        # Delete password from keyring
        if utils.password_exists_in_keyring(username):
            user_response = strip_and_lower(
                input(f"Delete password for {username} from keyring? [y/N] ")
            )
            is_affirmative = in_pred(["y", "yes"])

            if is_affirmative(user_response):
                utils.delete_password_in_keyring(username)
                print(f"Password for {username} deleted from keyring")
            else:
                print("Operation cancelled")
        else:
            print(f"No password found in keyring for {username}")
    else:
        # Store password in keyring
        password = getpass.getpass(f"Enter iCloud password for {username}: ")

        if not password:
            print("No password provided", file=sys.stderr)
            sys.exit(1)

        user_response = strip_and_lower(input(f"Save password for {username} to keyring? [y/N] "))
        is_affirmative = in_pred(["y", "yes"])

        if is_affirmative(user_response):
            utils.store_password_in_keyring(username, password)
            print(f"Password for {username} saved to keyring")
        else:
            print("Password not saved")

    sys.exit(0)


if __name__ == "__main__":
    main()
