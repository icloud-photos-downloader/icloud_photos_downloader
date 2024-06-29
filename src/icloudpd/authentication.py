"""Handles username/password authentication and two-step authentication"""

import logging
import sys
from typing import Callable, Dict, Optional, Sequence, Tuple
import click
import pyicloud_ipd
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.raw_policy import RawTreatmentPolicy


class TwoStepAuthRequiredError(Exception):
    """
    Raised when 2SA is required. base.py catches this exception
    and sends an email notification.
    """


def authenticator(
        logger: logging.Logger, 
        domain: str, 
        filename_cleaner: Callable[[str], str], 
        lp_filename_generator: Callable[[str], str], 
        raw_policy:RawTreatmentPolicy, 
        file_match_policy: FileMatchPolicy,
        password_providers: Dict[str, Tuple[Callable[[str], Optional[str]], Callable[[str, str], None]]]) -> Callable[[str, Optional[str], bool, Optional[str]], PyiCloudService]:
    """Wraping authentication with domain context"""
    def authenticate_(
            username:str,
            cookie_directory:Optional[str]=None,
            raise_error_on_2sa:bool=False,
            client_id:Optional[str]=None,
    ) -> PyiCloudService:
        """Authenticate with iCloud username and password"""
        logger.debug("Authenticating...")
        icloud: Optional[PyiCloudService] = None
        _valid_password: Optional[str] = None
        for _, _pair in password_providers.items():
            _reader, _ = _pair
            _password = _reader(username)
            if _password:
                icloud = PyiCloudService(
                    filename_cleaner,
                    lp_filename_generator,
                    domain,
                    raw_policy,
                    file_match_policy,
                    username, _password,
                    cookie_directory=cookie_directory,
                    client_id=client_id,
                )
                _valid_password = _password
                break

        if not icloud:
            raise NotImplementedError("None of providers gave password")
        
        if _valid_password:
            # save valid password to all providers
            for _, _pair in password_providers.items():
                _, _writer = _pair
                _writer(username, _valid_password)

        if icloud.requires_2fa:
            if raise_error_on_2sa:
                raise TwoStepAuthRequiredError(
                    "Two-factor authentication is required"
                )
            logger.info("Two-factor authentication is required (2fa)")
            request_2fa(icloud, logger)

        elif icloud.requires_2sa:
            if raise_error_on_2sa:
                raise TwoStepAuthRequiredError(
                    "Two-step authentication is required"
                )
            logger.info("Two-step authentication is required (2sa)")
            request_2sa(icloud, logger)

        return icloud
    return authenticate_


def request_2sa(icloud: PyiCloudService, logger: logging.Logger) -> None:
    """Request two-step authentication. Prompts for SMS or device"""
    devices = icloud.trusted_devices
    devices_count = len(devices)
    device_index: int = 0
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
            default="0",
            type=click.IntRange(
                0,
                devices_count - 1))

    device = devices[device_index]
    if not icloud.send_verification_code(device):
        logger.error("Failed to send two-step authentication code")
        sys.exit(1)

    code = click.prompt("Please enter two-step authentication code")
    if not icloud.validate_verification_code(device, code):
        logger.error("Failed to verify two-step authentication code")
        sys.exit(1)
    logger.info(
        "Great, you're all set up. The script can now be run without "
        "user interaction until 2SA expires.\n"
        "You can set up email notifications for when "
        "the two-step authentication expires.\n"
        "(Use --help to view information about SMTP options.)"
    )


def request_2fa(icloud: PyiCloudService, logger: logging.Logger) -> None:
    """Request two-factor authentication."""
    devices = icloud.get_trusted_phone_numbers()
    devices_count = len(devices)
    if devices_count > 0:
        if devices_count > 99:
            logger.error("Too many trusted devices for authentication")
            sys.exit(1)

        for i, device in enumerate(devices):
            print(f"  {i}: {device.obfuscated_number}")

        index_str = f"..{devices_count - 1}" if devices_count > 1 else ""
        code:int = click.prompt(
            f"Please enter two-factor authentication code or device index (0{index_str}) to send SMS with a code",
            type=click.IntRange(
                0,
                999999))

        if code < devices_count:
            # need to send code
            device = devices[code]
            if not icloud.send_2fa_code_sms(device.id):
                logger.error("Failed to send two-factor authentication code")
                sys.exit(1)
            code = click.prompt(
                "Please enter two-factor authentication code that you received over SMS",
                type=click.IntRange(
                    100000,
                    999999))
            if not icloud.validate_2fa_code_sms(device.id, code):
                logger.error("Failed to verify two-factor authentication code")
                sys.exit(1)
        else:
            if not icloud.validate_2fa_code(str(code)):
                logger.error("Failed to verify two-factor authentication code")
                sys.exit(1)
    else:
        code = click.prompt(
            "Please enter two-factor authentication code",
            type=click.IntRange(
                100000,
                999999))
        if not icloud.validate_2fa_code(str(code)):
            logger.error("Failed to verify two-factor authentication code")
            sys.exit(1)
    logger.info(
        "Great, you're all set up. The script can now be run without "
        "user interaction until 2FA expires.\n"
        "You can set up email notifications for when "
        "the two-factor authentication expires.\n"
        "(Use --help to view information about SMTP options.)"
    )
