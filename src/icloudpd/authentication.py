"""Handles username/password authentication and two-step authentication"""

import logging
import sys
import time
from functools import partial
from typing import Any, Callable, Dict, List, Mapping, Tuple

from icloudpd.mfa_provider import MFAProvider
from icloudpd.status import Status, StatusExchange
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.exceptions import PyiCloudFailedMFAException


def prompt_int_range(message: str, default: str, min_val: int, max_val: int) -> int:
    """Prompt user for integer input within a range, similar to click.IntRange"""
    while True:
        try:
            from foundation.string_utils import strip

            response = strip(input(f"{message} [{default}]: ")) or default
            value = int(response)
            if min_val <= value <= max_val:
                return value
            else:
                print(f"Invalid input: {value} is not in the range {min_val}-{max_val}")
        except ValueError:
            print(f"Invalid input: '{response}' is not a valid integer")


def prompt_string(message: str) -> str:
    """Prompt user for string input"""
    return input(f"{message}: ")


# Pure validation functions for 2FA input
def is_empty_string(input: str) -> bool:
    """Check if input is empty string"""
    return input == ""


def is_valid_device_index(input: str, device_count: int, alphabet: str) -> bool:
    """Check if input is a valid device index"""
    is_single_char = len(input) == 1
    is_in_alphabet = input in alphabet
    is_valid_index = alphabet.index(input) <= device_count - 1 if input in alphabet else False

    return is_single_char and is_in_alphabet and is_valid_index


def is_valid_six_digit_code(input: str) -> bool:
    """Check if input is a valid six-digit code"""
    return len(input) == 6 and input.isdigit()


def echo(message: str) -> None:
    """Print message to stdout, similar to click.echo"""
    print(message)


def authenticator(
    logger: logging.Logger,
    domain: str,
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
        domain,
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
        elif mfa_provider == MFAProvider.TELEGRAM:
            request_2fa_telegram(icloud, logger, status_exchange)
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
            echo(f"  {i}: {name}")

        device_index = prompt_int_range("Please choose an option:", "0", 0, devices_count - 1)

    device = devices[device_index]
    if not icloud.send_verification_code(device):
        logger.error("Failed to send two-step authentication code")
        sys.exit(1)

    code = prompt_string("Please enter two-step authentication code")
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
            raise PyiCloudFailedMFAException("Too many trusted devices for authentication")

        for i, device in enumerate(devices):
            echo(f"  {device_index_alphabet[i]}: {device.obfuscated_number}")

        index_str = f"..{device_index_alphabet[devices_count - 1]}" if devices_count > 1 else ""
        index_or_code: str = ""
        while True:
            from foundation.string_utils import strip_and_lower

            index_or_code = strip_and_lower(
                prompt_string(
                    f"Please enter two-factor authentication code or device index ({device_index_alphabet[0]}{index_str}) to send SMS with a code"
                )
            )

            # Use pure validation functions
            if is_empty_string(index_or_code):
                echo("Empty string. Try again")
                continue

            if is_valid_device_index(index_or_code, devices_count, device_index_alphabet):
                break

            if is_valid_six_digit_code(index_or_code):
                break

            # Handle invalid input cases
            if len(index_or_code) == 1:
                echo(f"Invalid index, should be ({device_index_alphabet[0]}{index_str}). Try again")
                continue
            elif len(index_or_code) == 6:
                echo("Invalid code, should be six digits. Try again")
                continue

            echo(
                f"Should be index ({device_index_alphabet[0]}{index_str}) or six-digit code. Try again"
            )

        if index_or_code in device_index_alphabet:
            # need to send code
            device_index = device_index_alphabet.index(index_or_code)
            device = devices[device_index]
            if not icloud.send_2fa_code_sms(device.id):
                raise PyiCloudFailedMFAException("Failed to send two-factor authentication code")
            while True:
                from foundation.string_utils import strip

                code: str = strip(
                    prompt_string(
                        "Please enter two-factor authentication code that you received over SMS"
                    )
                )
                if len(code) == 6 and code.isdigit():
                    break
                echo("Invalid code, should be six digits. Try again")

            if not icloud.validate_2fa_code_sms(device.id, code):
                raise PyiCloudFailedMFAException("Failed to verify two-factor authentication code")
        else:
            if not icloud.validate_2fa_code(index_or_code):
                raise PyiCloudFailedMFAException("Failed to verify two-factor authentication code")
    else:
        while True:
            from foundation.string_utils import strip

            code = strip(prompt_string("Please enter two-factor authentication code"))
            if len(code) == 6 and code.isdigit():
                break
            echo("Invalid code, should be six digits. Try again")
        if not icloud.validate_2fa_code(code):
            raise PyiCloudFailedMFAException("Failed to verify two-factor authentication code")
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
        raise PyiCloudFailedMFAException(
            f"Expected NO_INPUT_NEEDED, but got {status_exchange.get_status()}"
        )

    # wait for input
    while True:
        status = status_exchange.get_status()
        if status == Status.NEED_MFA:
            time.sleep(1)
            continue
        else:
            pass

        if status_exchange.replace_status(Status.SUPPLIED_MFA, Status.CHECKING_MFA):
            code = status_exchange.get_payload()
            if not code:
                raise PyiCloudFailedMFAException(
                    "Internal error: did not get code for SUPPLIED_MFA status"
                )

            if not icloud.validate_2fa_code(code):
                if status_exchange.set_error("Failed to verify two-factor authentication code"):
                    # that will loop forever
                    # TODO give user an option to restart auth in case they missed code
                    continue
                else:
                    raise PyiCloudFailedMFAException("Failed to chage status of invalid code")
            else:
                status_exchange.replace_status(Status.CHECKING_MFA, Status.NO_INPUT_NEEDED)  # done

                logger.info(
                    "Great, you're all set up. The script can now be run without "
                    "user interaction until 2FA expires.\n"
                    "You can set up email notifications for when "
                    "the two-factor authentication expires.\n"
                    "(Use --help to view information about SMTP options.)"
                )
        else:
            raise PyiCloudFailedMFAException("Failed to change status")


def request_2fa_telegram(
    icloud: PyiCloudService, logger: logging.Logger, status_exchange: StatusExchange
) -> None:
    """Request two-factor authentication through Telegram."""
    if not status_exchange.replace_status(Status.NO_INPUT_NEEDED, Status.NEED_MFA):
        raise PyiCloudFailedMFAException(
            f"Expected NO_INPUT_NEEDED, but got {status_exchange.get_status()}"
        )

    # Get telegram bot from status_exchange if available
    telegram_bot = status_exchange.get_telegram_bot()
    if telegram_bot:
        username = status_exchange.get_current_user() or "user"
        telegram_bot.request_auth_code(username)
    else:
        logger.warning("Telegram bot not available, falling back to console")
        # Fallback to console if Telegram bot not available
        request_2fa(icloud, logger)
        return

    # wait for input
    while True:
        status = status_exchange.get_status()
        if status == Status.NEED_MFA:
            time.sleep(1)
            continue
        else:
            pass

        if status_exchange.replace_status(Status.SUPPLIED_MFA, Status.CHECKING_MFA):
            code = status_exchange.get_payload()
            if not code:
                raise PyiCloudFailedMFAException(
                    "Internal error: did not get code for SUPPLIED_MFA status"
                )

            if not icloud.validate_2fa_code(code):
                if status_exchange.set_error("Failed to verify two-factor authentication code"):
                    # Reset waiting flag and request code again
                    if telegram_bot:
                        telegram_bot.request_auth_code(username)
                    continue
                else:
                    raise PyiCloudFailedMFAException("Failed to change status of invalid code")
            else:
                status_exchange.replace_status(Status.CHECKING_MFA, Status.NO_INPUT_NEEDED)  # done
                if telegram_bot:
                    telegram_bot.send_message("✅ Authentication completed successfully")
                logger.info(
                    "Great, you're all set up. The script can now be run without "
                    "user interaction until 2FA expires.\n"
                    "You can set up email notifications for when "
                    "the two-factor authentication expires.\n"
                    "(Use --help to view information about SMTP options.)"
                )
                break
        else:
            raise PyiCloudFailedMFAException("Failed to change status")
