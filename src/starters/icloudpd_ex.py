""" Experimental code """

from multiprocessing import freeze_support
freeze_support() # fixing tqdm on macos

import sys
from icloudpd.base import main as icloudpd_main
from pyicloud_ipd.cmdline import main as icloud_main

import click

# goal0 -- allow experimental flow from cli
# goal1 -- compose auth flow for icloud auth apis that supports 2fa, fido,
# and works from China

# print("Experimenting with authentication")

# def make_requestor():
#     """ make_requestor :: IO (Request -> Response) """

# def make_request_builder():
#     """ make_request_builder :: State (a -> Request) """

# def make_response_parser():
#     """ make_response_parser :: State (Response -> a) """


@click.group()
def commands():
    pass


@commands.command()
@click.option(
    "--username",
    default="",
    help="Apple ID to Use"
)
@click.option(
    "--password",
    default="",
    help=(
        "Apple ID Password to Use; if unspecified, password will be "
        "fetched from the system keyring."
    )
)
@click.option(
    "-n", "--non-interactive",
    default=True,
    help="Disable interactive prompts."
)
@click.option(
    "--delete-from-keyring",
    default=False,
    help="Delete stored password in system keyring for this username.",
)
@click.option(
    "--domain",
    default="com",
    help="Root Domain for requests to iCloud. com or cn",
)
def icloud(username, password, non_interactive, delete_from_keyring, domain):
    """Legacy iCloud utils (keyring)"""
    # raise Exception("blah")
    icloud_main(sys.argv[2:])


@commands.command()
@click.argument('appleid')  # , help="AppleID of the account to use")
@click.argument('target')  # , help="Target path template")
def copy(appleid, target):
    """Copy assets from iCloud to local storage"""


@commands.command()
def move():
    """Move assets from iCloud to local storage"""


@commands.group()
def auth():
    """Manages persistant credentials"""


@auth.command()
@click.argument('appleid')  # , help="AppleID of the account to use")
def add(appleid):
    """Add credentials to keyring"""


@auth.command()
@click.argument('appleid')  # , help="AppleID of the account to use")
def delete(appleid):
    """Delete credentials from keyring"""


@commands.group()
def watch():
    """Watch for iCloud changes"""


def main():
    commands.add_command(icloudpd_main, name="icloudpd")
    watch.add_command(copy)
    watch.add_command(move)
    commands()


if __name__ == "__main__":
    main()
