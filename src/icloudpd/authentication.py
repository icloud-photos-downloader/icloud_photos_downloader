"""Handles username/password authentication and two-step authentication"""

import logging
import sys
import click
import pyicloud_ipd


class TwoStepAuthRequiredError(Exception):
    """
    Raised when 2SA is required. base.py catches this exception
    and sends an email notification.
    """


def authenticator(logger: logging.Logger, domain: str):
    """Wraping authentication with domain context"""
    def authenticate_(
            username,
            password,
            cookie_directory=None,
            raise_error_on_2sa=False,
            client_id=None,
    ) -> pyicloud_ipd.PyiCloudService:
        """Authenticate with iCloud username and password"""
        logger.debug("Authenticating...")
        while True:
            try:
                # If password not provided on command line variable will be set to None
                # and PyiCloud will attempt to retrieve from its keyring
                icloud = pyicloud_ipd.PyiCloudService(
                    domain,
                    username, password,
                    cookie_directory=cookie_directory,
                    client_id=client_id,
                )
                break
            except pyicloud_ipd.exceptions.PyiCloudNoStoredPasswordAvailableException:
                # Prompt for password if not stored in PyiCloud's keyring
                password = click.prompt("iCloud Password", hide_input=True)

        if icloud.requires_2fa:
            if raise_error_on_2sa:
                raise TwoStepAuthRequiredError(
                    "Two-step/two-factor authentication is required"
                )
            logger.info("Two-step/two-factor authentication is required (2fa)")
            request_2fa(icloud, logger)

        elif icloud.requires_2sa:
            if raise_error_on_2sa:
                raise TwoStepAuthRequiredError(
                    "Two-step/two-factor authentication is required"
                )
            logger.info("Two-step/two-factor authentication is required (2sa)")
            request_2sa(icloud, logger)

        return icloud
    return authenticate_


def request_2sa(icloud: pyicloud_ipd.PyiCloudService, logger: logging.Logger):
    """Request two-step authentication. Prompts for SMS or device"""
    devices = icloud.trusted_devices
    devices_count = len(devices)
    device_index = 0
    if devices_count > 0:
        for i, device in enumerate(devices):
            # pylint: disable-msg=consider-using-f-string
            print(
                "  %s: %s" %
                (i, device.get(
                    "deviceName", "SMS to %s" %
                    device.get("phoneNumber"))))
            # pylint: enable-msg=consider-using-f-string

        device_index = click.prompt(
            "Please choose an option:",
            default=0,
            type=click.IntRange(
                0,
                devices_count - 1))

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


def request_2fa(icloud: pyicloud_ipd.PyiCloudService, logger: logging.Logger):
    """Request two-factor authentication."""
    code = click.prompt("Please enter two-factor authentication code")
    if not icloud.validate_2fa_code(code):
        logger.error("Failed to verify two-factor authentication code")
        sys.exit(1)
    logger.info(
        "Great, you're all set up. The script can now be run without "
        "user interaction until 2SA expires.\n"
        "You can set up email notifications for when "
        "the two-step authentication expires.\n"
        "(Use --help to view information about SMTP options.)"
    )
