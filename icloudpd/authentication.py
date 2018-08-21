"""Handles username/password authentication and two-step authentication"""

import sys
import click
import pyicloud_ipd
from icloudpd.logger import setup_logger


class TwoStepAuthRequiredError(Exception):
    """
    Raised when 2SA is required. base.py catches this exception
    and sends an email notification.
    """


def authenticate(
        username,
        password,
        cookie_directory=None,
        raise_error_on_2sa=False,
        client_id=None
):
    """Authenticate with iCloud username and password"""
    logger = setup_logger()
    logger.debug("Authenticating...")
    try:
        # If password not provided on command line variable will be set to None
        # and PyiCloud will attempt to retrieve from it's keyring
        icloud = pyicloud_ipd.PyiCloudService(
            username, password,
            cookie_directory=cookie_directory,
            client_id=client_id)
    except pyicloud_ipd.exceptions.NoStoredPasswordAvailable:
        # Prompt for password if not stored in PyiCloud's keyring
        password = click.prompt("iCloud Password", hide_input=True)
        icloud = pyicloud_ipd.PyiCloudService(
            username, password,
            cookie_directory=cookie_directory,
            client_id=client_id)

    if icloud.requires_2sa:
        if raise_error_on_2sa:
            raise TwoStepAuthRequiredError(
                "Two-step/two-factor authentication is required!"
            )
        logger.info("Two-step/two-factor authentication is required!")
        request_2sa(icloud, logger)
    return icloud


def request_2sa(icloud, logger):
    """Request two-step authentication. Prompts for SMS or device"""
    devices = icloud.trusted_devices
    devices_count = len(devices)
    device_index = 0
    if devices_count > 0:
        for i, device in enumerate(devices):
            print(
                "  %s: %s" %
                (i, device.get(
                    "deviceName", "SMS to %s" %
                    device.get("phoneNumber"))))

        # pylint: disable-msg=superfluous-parens
        print("  %s: Enter two-factor authentication code" % devices_count)
        # pylint: enable-msg=superfluous-parens
        device_index = click.prompt(
            "Please choose an option:",
            default=0,
            type=click.IntRange(
                0,
                devices_count))

    if device_index == devices_count:
        # We're using the 2FA code that was automatically sent to the user's device,
        # so can just use an empty dict()
        device = dict()
    else:
        device = devices[device_index]
        if not icloud.send_verification_code(device):
            logger.error("Failed to send two-factor authentication code")
            sys.exit(1)

    code = click.prompt("Please enter two-factor authentication code")
    if not icloud.validate_verification_code(device, code):
        logger.error("Failed to verify two-factor authentication code")
        sys.exit(1)
    logger.info(
        "Great, you're all set up. The script can now be run without "
        "user interaction until 2SA expires.\n"
        "You can set up email notifications for when "
        "the two-step authentication expires.\n"
        "(Use --help to view information about SMTP options.)"
    )
