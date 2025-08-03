"""Handles username/password authentication and two-step authentication"""

import logging
import sys
import time
from functools import partial
from typing import Any, Callable, Dict, List, Mapping, Tuple

import click

from icloudpd.mfa_provider import MFAProvider
from icloudpd.status import Status, StatusExchange
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.raw_policy import RawTreatmentPolicy


def authenticator(
    logger: logging.Logger,
    domain: str,
    filename_cleaner: Callable[[str], str],
    lp_filename_generator: Callable[[str], str],
    raw_policy: RawTreatmentPolicy,
    file_match_policy: FileMatchPolicy,
    password_providers: Dict[str, Tuple[Callable[[str], str | None], Callable[[str, str], None]]],
    mfa_provider: MFAProvider,
    status_exchange: StatusExchange,
    username: str,
    notificator: Callable[[], None],
    response_observer: Callable[[Mapping[str, Any]], None] | None = None,
    cookie_directory: str | None = None,
    client_id: str | None = None,
) -> PyiCloudService:
    """Authenticate with iCloud username and password"""
    logger.debug("Authenticating...")
    valid_password: List[str] = []

    def password_provider(username: str, valid_password: List[str]) -> str | None:
        for _, _pair in password_providers.items():
            reader, _ = _pair
            password = reader(username)
            if password:
                valid_password.append(password)
                return password
        return None

    icloud = PyiCloudService(
        filename_cleaner,
        lp_filename_generator,
        domain,
        raw_policy,
        file_match_policy,
        username,
        partial(password_provider, username, valid_password),
        response_observer,
        cookie_directory=cookie_directory,
        client_id=client_id,
    )

    if not icloud:
        raise NotImplementedError("None of providers gave password")

    if valid_password:
        # save valid password to all providers
        for _, _pair in password_providers.items():
            _, writer = _pair
            writer(username, valid_password[0])

    if icloud.requires_2fa:
        logger.info("Two-factor authentication is required (2fa)")
        notificator()
        if mfa_provider == MFAProvider.WEBUI:
            request_2fa_web(icloud, logger, status_exchange)
        else:
            request_2fa(icloud, logger)

    elif icloud.requires_2sa:
        logger.info("Two-step authentication is required (2sa)")
        notificator()
        request_2sa(icloud, logger)

    return icloud


def request_2sa(icloud: PyiCloudService, logger: logging.Logger) -> None:
    """Request two-step authentication. Prompts for SMS or device"""
    devices = icloud.trusted_devices
    devices_count = len(devices)
    device_index: int = 0
    if devices_count > 0:
        for i, device in enumerate(devices):
            number = device["phoneNumber"]
            alt_name = f"SMS to {number}"
            name = device.get("deviceName", alt_name)
            click.echo(f"  {i}: {name}")

        device_index = click.prompt(
            "Please choose an option:", default="0", type=click.IntRange(0, devices_count - 1)
        )

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
    device_index_alphabet = "abcdefghijklmnopqrstuvwxyz"
    if devices_count > 0:
        if devices_count > len(device_index_alphabet):
            logger.error("Too many trusted devices for authentication")
            sys.exit(1)

        for i, device in enumerate(devices):
            click.echo(f"  {device_index_alphabet[i]}: {device.obfuscated_number}")

        index_str = f"..{device_index_alphabet[devices_count - 1]}" if devices_count > 1 else ""
        index_or_code: str = ""
        while True:
            index_or_code = (
                click.prompt(
                    f"Please enter two-factor authentication code or device index ({device_index_alphabet[0]}{index_str}) to send SMS with a code",
                )
                .strip()
                .lower()
            )

            if index_or_code == "":
                click.echo("Empty string. Try again")
                continue

            if len(index_or_code) == 1:
                if index_or_code in device_index_alphabet:
                    if device_index_alphabet.index(index_or_code) > devices_count - 1:
                        click.echo(
                            f"Invalid index, should be ({device_index_alphabet[0]}{index_str}). Try again",
                        )
                        continue
                    else:
                        break
                else:
                    click.echo(
                        f"Invalid index, should be ({device_index_alphabet[0]}{index_str}). Try again",
                    )
                    continue

            if len(index_or_code) == 6:
                if index_or_code.isdigit():
                    break
                else:
                    click.echo("Invalid code, should be six digits. Try again")
                    continue

            click.echo(
                f"Should be index ({device_index_alphabet[0]}{index_str}) or six-digit code. Try again",
            )

        if index_or_code in device_index_alphabet:
            # need to send code
            device_index = device_index_alphabet.index(index_or_code)
            device = devices[device_index]
            if not icloud.send_2fa_code_sms(device.id):
                logger.error("Failed to send two-factor authentication code")
                sys.exit(1)
            while True:
                code: str = click.prompt(
                    "Please enter two-factor authentication code that you received over SMS",
                ).strip()
                if len(code) == 6 and code.isdigit():
                    break
                click.echo("Invalid code, should be six digits. Try again")

            if not icloud.validate_2fa_code_sms(device.id, code):
                logger.error("Failed to verify two-factor authentication code")
                sys.exit(1)
        else:
            if not icloud.validate_2fa_code(index_or_code):
                logger.error("Failed to verify two-factor authentication code")
                sys.exit(1)
    else:
        while True:
            code = click.prompt(
                "Please enter two-factor authentication code",
            ).strip()
            if len(code) == 6 and code.isdigit():
                break
            click.echo("Invalid code, should be six digits. Try again")
        if not icloud.validate_2fa_code(code):
            logger.error("Failed to verify two-factor authentication code")
            sys.exit(1)
    logger.info(
        "Great, you're all set up. The script can now be run without "
        "user interaction until 2FA expires.\n"
        "You can set up email notifications for when "
        "the two-factor authentication expires.\n"
        "(Use --help to view information about SMTP options.)"
    )


def request_2fa_web(
    icloud: PyiCloudService, logger: logging.Logger, status_exchange: StatusExchange
) -> None:
    """Request two-factor authentication through Webui."""
    if not status_exchange.replace_status(Status.NO_INPUT_NEEDED, Status.NEED_MFA):
        logger.error("Expected NO_INPUT_NEEDED, but got something else")
        return

    # wait for input
    while True:
        status = status_exchange.get_status()
        if status == Status.NEED_MFA:
            time.sleep(1)
        else:
            break

    if status_exchange.replace_status(Status.SUPPLIED_MFA, Status.CHECKING_MFA):
        code = status_exchange.get_payload()
        if not code:
            logger.error("Internal error: did not get code for SUPPLIED_MFA status")
            status_exchange.replace_status(
                Status.CHECKING_MFA, Status.NO_INPUT_NEEDED
            )  # TODO Error
            return

        if not icloud.validate_2fa_code(code):
            logger.error("Failed to verify two-factor authentication code")
            status_exchange.replace_status(
                Status.CHECKING_MFA, Status.NO_INPUT_NEEDED
            )  # TODO Error
            return
        status_exchange.replace_status(Status.CHECKING_MFA, Status.NO_INPUT_NEEDED)  # done

        logger.info(
            "Great, you're all set up. The script can now be run without "
            "user interaction until 2FA expires.\n"
            "You can set up email notifications for when "
            "the two-factor authentication expires.\n"
            "(Use --help to view information about SMTP options.)"
        )
    else:
        logger.error("Failed to change status")
