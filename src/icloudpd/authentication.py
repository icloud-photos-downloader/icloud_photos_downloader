"""Handles username/password authentication and two-step authentication"""

import logging
import time
from functools import partial
from typing import Any, Callable, Dict, List, Mapping, Tuple

from icloudpd.mfa_provider import MFAProvider
from icloudpd.status import Status, StatusExchange
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.exceptions import (
    PyiCloudConnectionException,
)
from pyicloud_ipd.response_types import (
    AuthDomainMismatchError,
    AuthenticationFailed,
    AuthenticationSuccessWithService,
    AuthenticatorConnectionError,
    AuthenticatorMFAError,
    AuthenticatorResult,
    AuthenticatorSuccess,
    AuthenticatorTwoSAExit,
    AuthRequires2SAWithService,
    TwoFactorAuthFailed,
    TwoFactorAuthResult,
    TwoFactorAuthSuccess,
)


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
) -> AuthenticatorResult:
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

    auth_result = PyiCloudService.create_pyicloud_service_adt(
        domain=domain,
        apple_id=username,
        password_provider=partial(password_provider, username, valid_password),
        response_observer=response_observer,
        cookie_directory=cookie_directory,
        client_id=client_id,
    )

    # Handle authentication result and extract service
    icloud: PyiCloudService
    match auth_result:
        case AuthenticationSuccessWithService(service):
            icloud = service
        case AuthenticationFailed(error):
            return AuthenticatorConnectionError(error)
        case AuthRequires2SAWithService(service, _):
            # 2SA is handled below, service is available
            icloud = service
        case AuthDomainMismatchError(domain_to_use):
            msg = f"Apple insists on using {domain_to_use} for your request. Please use --domain parameter"
            return AuthenticatorConnectionError(PyiCloudConnectionException(msg))

    if valid_password:
        # save valid password to all providers
        for _, _pair in password_providers.items():
            _, writer = _pair
            writer(username, valid_password[0])

    if icloud.requires_2fa:
        logger.info("Two-factor authentication is required (2fa)")
        notificator()
        if mfa_provider == MFAProvider.WEBUI:
            result = request_2fa_web(icloud, logger, status_exchange)
        else:
            result = request_2fa(icloud, logger)

        match result:
            case TwoFactorAuthSuccess():
                pass  # Success, continue
            case TwoFactorAuthFailed(error_msg):
                return AuthenticatorMFAError(error_msg)

    elif icloud.requires_2sa:
        logger.info("Two-step authentication is required (2sa)")
        notificator()
        result = request_2sa(icloud, logger)

        match result:
            case TwoFactorAuthSuccess():
                pass  # Success, continue
            case TwoFactorAuthFailed(_):
                # For 2SA, need to exit with code 1 for backward compatibility
                return AuthenticatorTwoSAExit()

    return AuthenticatorSuccess(icloud)


def request_2sa(icloud: PyiCloudService, logger: logging.Logger) -> TwoFactorAuthResult:
    """Request two-step authentication. Prompts for SMS or device"""
    from pyicloud_ipd.response_types import (
        Response2SARequired,
        ResponseAPIError,
        ResponseServiceNotActivated,
        ResponseServiceUnavailable,
        TrustedDevicesSuccess,
    )

    devices_result = icloud.get_trusted_devices()
    match devices_result:
        case TrustedDevicesSuccess(devices):
            pass  # Continue with devices
        case (
            Response2SARequired(_)
            | ResponseServiceNotActivated(_, _)
            | ResponseAPIError(_, _)
            | ResponseServiceUnavailable(_)
        ):
            return TwoFactorAuthFailed("Failed to get trusted devices")

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
    from pyicloud_ipd.response_types import (
        SendVerificationCodeSuccess,
        ValidateVerificationCodeSuccess,
    )

    send_result = icloud.send_verification_code(device)
    match send_result:
        case SendVerificationCodeSuccess(success):
            if not success:
                logger.error("Failed to send two-step authentication code")
                return TwoFactorAuthFailed("Failed to send two-step authentication code")
        case _:
            logger.error("Failed to send two-step authentication code")
            return TwoFactorAuthFailed("Failed to send two-step authentication code")

    code = prompt_string("Please enter two-step authentication code")
    validate_result = icloud.validate_verification_code(device, code)
    match validate_result:
        case ValidateVerificationCodeSuccess(success):
            if not success:
                logger.error("Failed to verify two-step authentication code")
                return TwoFactorAuthFailed("Failed to verify two-step authentication code")
        case _:
            logger.error("Failed to verify two-step authentication code")
            return TwoFactorAuthFailed("Failed to verify two-step authentication code")
    logger.info(
        "Great, you're all set up. The script can now be run without "
        "user interaction until 2SA expires.\n"
        "You can set up email notifications for when "
        "the two-step authentication expires.\n"
        "(Use --help to view information about SMTP options.)"
    )
    return TwoFactorAuthSuccess()


def request_2fa(icloud: PyiCloudService, logger: logging.Logger) -> TwoFactorAuthResult:
    """Request two-factor authentication."""
    from pyicloud_ipd.response_types import (
        Response2SARequired,
        ResponseAPIError,
        ResponseServiceNotActivated,
        ResponseServiceUnavailable,
        TrustedPhoneNumbersSuccess,
    )

    devices_result = icloud.get_trusted_phone_numbers()
    match devices_result:
        case TrustedPhoneNumbersSuccess(devices):
            pass  # Continue with devices
        case (
            Response2SARequired(_)
            | ResponseServiceNotActivated(_, _)
            | ResponseAPIError(_, _)
            | ResponseServiceUnavailable(_)
        ):
            return TwoFactorAuthFailed("Failed to get trusted phone numbers")

    devices_count = len(devices)
    device_index_alphabet = "abcdefghijklmnopqrstuvwxyz"
    if devices_count > 0:
        if devices_count > len(device_index_alphabet):
            return TwoFactorAuthFailed("Too many trusted devices for authentication")

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
            from pyicloud_ipd.response_types import Send2FACodeSMSSuccess

            send_result = icloud.send_2fa_code_sms(device.id)
            match send_result:
                case Send2FACodeSMSSuccess(success):
                    if not success:
                        return TwoFactorAuthFailed("Failed to send two-factor authentication code")
                case _:
                    return TwoFactorAuthFailed("Failed to send two-factor authentication code")
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

            from pyicloud_ipd.response_types import Validate2FACodeSMSSuccess

            validate_result = icloud.validate_2fa_code_sms(device.id, code)
            match validate_result:
                case Validate2FACodeSMSSuccess(success):
                    if not success:
                        return TwoFactorAuthFailed(
                            "Failed to verify two-factor authentication code"
                        )
                case _:
                    return TwoFactorAuthFailed("Failed to verify two-factor authentication code")
        else:
            from pyicloud_ipd.response_types import Validate2FACodeSuccess

            validate_2fa_result = icloud.validate_2fa_code(index_or_code)
            match validate_2fa_result:
                case Validate2FACodeSuccess(success):
                    if not success:
                        return TwoFactorAuthFailed(
                            "Failed to verify two-factor authentication code"
                        )
                case _:
                    return TwoFactorAuthFailed("Failed to verify two-factor authentication code")
    else:
        while True:
            from foundation.string_utils import strip

            code = strip(prompt_string("Please enter two-factor authentication code"))
            if len(code) == 6 and code.isdigit():
                break
            echo("Invalid code, should be six digits. Try again")
        from pyicloud_ipd.response_types import Validate2FACodeSuccess

        validate_2fa_result = icloud.validate_2fa_code(code)
        match validate_2fa_result:
            case Validate2FACodeSuccess(success):
                if not success:
                    return TwoFactorAuthFailed("Failed to verify two-factor authentication code")
            case _:
                return TwoFactorAuthFailed("Failed to verify two-factor authentication code")
    logger.info(
        "Great, you're all set up. The script can now be run without "
        "user interaction until 2FA expires.\n"
        "You can set up email notifications for when "
        "the two-factor authentication expires.\n"
        "(Use --help to view information about SMTP options.)"
    )
    return TwoFactorAuthSuccess()


def request_2fa_web(
    icloud: PyiCloudService, logger: logging.Logger, status_exchange: StatusExchange
) -> TwoFactorAuthResult:
    """Request two-factor authentication through Webui."""
    if not status_exchange.replace_status(Status.NO_INPUT_NEEDED, Status.NEED_MFA):
        return TwoFactorAuthFailed(
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
                return TwoFactorAuthFailed(
                    "Internal error: did not get code for SUPPLIED_MFA status"
                )

            if not icloud.validate_2fa_code(code):
                if status_exchange.set_error("Failed to verify two-factor authentication code"):
                    # that will loop forever
                    # TODO give user an option to restart auth in case they missed code
                    continue
                else:
                    return TwoFactorAuthFailed("Failed to change status of invalid code")
            else:
                status_exchange.replace_status(Status.CHECKING_MFA, Status.NO_INPUT_NEEDED)  # done

                logger.info(
                    "Great, you're all set up. The script can now be run without "
                    "user interaction until 2FA expires.\n"
                    "You can set up email notifications for when "
                    "the two-factor authentication expires.\n"
                    "(Use --help to view information about SMTP options.)"
                )
                return TwoFactorAuthSuccess()
        else:
            return TwoFactorAuthFailed("Failed to change status")
