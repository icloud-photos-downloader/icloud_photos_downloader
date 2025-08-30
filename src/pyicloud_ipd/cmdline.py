#! /usr/bin/env python
"""
A Command Line Wrapper to allow easy use of pyicloud for
command line scripts, and related.
"""

import argparse
import getpass
import sys
from typing import NoReturn, Sequence

from foundation import version_info_formatted
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.exceptions import PyiCloudFailedLoginException

from . import utils





def main(args: Sequence[str] | None = None) -> NoReturn:
    """Main commandline entrypoint."""
    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser(description="Find My iPhone CommandLine Tool")

    parser.add_argument(
        "--username",
        action="store",
        dest="username",
        default="",
        help="Apple ID to Use",
    )
    parser.add_argument(
        "--password",
        action="store",
        dest="password",
        default="",
        help=(
            "Apple ID Password to Use; if unspecified, password will be "
            "fetched from the system keyring."
        ),
    )
    parser.add_argument(
        "-n",
        "--non-interactive",
        action="store_false",
        dest="interactive",
        default=True,
        help="Disable interactive prompts.",
    )
    parser.add_argument(
        "--delete-from-keyring",
        action="store_true",
        dest="delete_from_keyring",
        default=False,
        help="Delete stored password in system keyring for this username.",
    )







    parser.add_argument(
        "--domain",
        action="store",
        dest="domain",
        default="com",
        help="Root domain for requests to iCloud. com or cn",
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

    username: str | None = command_line.username.strip() or None
    password: str | None = command_line.password.strip() or None
    domain = command_line.domain

    if username is not None and command_line.delete_from_keyring:
        utils.delete_password_in_keyring(username)
        print("Password delete from keyring")

    failure_count = 0
    while True:
        # Which password we use is determined by your username, so we
        # do need to check for this first and separately.
        if username is None:
            parser.error("No username supplied")

        got_from_keyring = False

        if password is None:
            password = utils.get_password_from_keyring(username)
            got_from_keyring = password is not None

        if password is None:
            password = getpass.getpass(f"Enter iCloud password for {username}: ").strip() or None

        if password is None:
            parser.error("No password supplied")

        try:
            api = PyiCloudService(
                domain,
                username,
                lambda: password,
                lambda _: None,
            )
            if (
                not got_from_keyring
                and command_line.interactive
                and input("Save password in keyring? [y/N] ").strip().lower() in ("y", "yes")
            ):
                utils.store_password_in_keyring(username, password)

            if api.requires_2fa:
                # fmt: off
                print(
                    "\nTwo-step authentication required.",
                    "\nPlease enter validation code"
                )
                # fmt: on

                code = input("(string) --> ")
                if not api.validate_2fa_code(code):
                    print("Failed to verify verification code")
                    sys.exit(1)

                print("")

            elif api.requires_2sa:
                # fmt: off
                print(
                    "\nTwo-step authentication required.",
                    "\nYour trusted devices are:"
                )
                # fmt: on

                devices = api.trusted_devices
                for i, device in enumerate(devices):
                    print(
                        "    %s: %s"
                        % (
                            i,
                            device.get("deviceName", "SMS to %s" % device.get("phoneNumber")),
                        )
                    )

                print("\nWhich device would you like to use?")
                device_index = int(input("(number) --> "))
                device = devices[device_index]
                if not api.send_verification_code(device):
                    print("Failed to send verification code")
                    sys.exit(1)

                print("\nPlease enter validation code")
                code = input("(string) --> ")
                if not api.validate_verification_code(device, code):
                    print("Failed to verify verification code")
                    sys.exit(1)

                print("")
            break
        except PyiCloudFailedLoginException as err:
            # If they have a stored password; we just used it and
            # it did not work; let's delete it if there is one.
            if utils.password_exists_in_keyring(username):
                utils.delete_password_in_keyring(username)

            message = f"Bad username or password for {username}"
            password = None

            failure_count += 1
            if failure_count >= 3:
                raise RuntimeError(message) from err

            print(message, file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
