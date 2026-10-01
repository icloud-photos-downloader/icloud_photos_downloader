import inspect
import logging
import os
import shutil
import time
from functools import partial
from threading import Thread
from typing import Callable, Generic, NamedTuple, NoReturn, TypeVar, cast
from unittest import TestCase, mock

import pytest
from requests import Timeout
from requests.exceptions import ConnectionError
from vcr import VCR

import pyicloud_ipd
from foundation.core import constant
from icloudpd.authentication import authenticator
from icloudpd.base import dummy_password_writter
from icloudpd.logger import setup_logger
from icloudpd.login_confirmation import LoginConfirmation
from icloudpd.mfa_provider import MFAProvider
from icloudpd.server import serve_app
from icloudpd.status import Status, StatusExchange
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.exceptions import PyiCloudAPIResponseException, PyiCloudFailedLoginException
from pyicloud_ipd.sms import parse_trusted_phone_numbers_payload
from tests.helpers import path_from_project_root, recreate_path, run_cassette

vcr = VCR(decode_compressed_response=True, record_mode="none")


class AuthenticationTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")
        self.vcr_path = os.path.join(self.root_path, "vcr_cassettes")
        self.data_path = os.path.join(self.root_path, "data")

    def test_failed_auth(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        with vcr.use_cassette(os.path.join(self.vcr_path, "failed_auth.yml")):  # noqa: SIM117
            with self.assertRaises(pyicloud_ipd.exceptions.PyiCloudFailedLoginException) as context:
                authenticator(
                    setup_logger(),
                    "com",
                    {"test": (constant("dummy"), dummy_password_writter)},
                    MFAProvider.CONSOLE,
                    StatusExchange(),
                    "bad_username",
                    lambda: None,
                    None,
                    cookie_dir,
                    "EC5646DE-9423-11E8-BF21-14109FE0B321",
                )

        # self.assertIn(
        #     "Failed to login with srp, falling back to old raw password authentication.",
        #     result.output,
        # )
        self.assertTrue("Invalid email/password combination." in str(context.exception))

    @pytest.mark.skip(reason="No longer support fallback to raw")
    def test_fallback_raw_password(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        result = run_cassette(
            os.path.join(self.vcr_path, "fallback_raw_password.yml"),
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--no-progress-bar",
                "--cookie-directory",
                cookie_dir,
                "--auth-only",
            ],
        )
        self.assertIn(
            "Failed to login with srp, falling back to old raw password authentication.",
            result.output,
        )
        self.assertIn("Authentication completed successfully", result.output)
        self.assertEqual(result.exit_code, 0, "exit code")

    def test_successful_token_validation(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        cookie_master_path = os.path.join(self.root_path, "cookie")

        recreate_path(base_dir)

        shutil.copytree(cookie_master_path, cookie_dir)

        result = run_cassette(
            os.path.join(self.vcr_path, "successful_auth.yml"),
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--no-progress-bar",
                "--cookie-directory",
                cookie_dir,
                "--auth-only",
            ],
        )
        self.assertIn("Authentication completed successfully", result.output)
        self.assertEqual(result.exit_code, 0, "exit code")

    def test_password_prompt_2sa(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        result = run_cassette(
            os.path.join(self.vcr_path, "2sa_flow_valid_code.yml"),
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--no-progress-bar",
                "--cookie-directory",
                cookie_dir,
                "--auth-only",
            ],
            input="0\n654321\n",
        )
        self.assertIn("Authenticating...", result.output)
        self.assertIn(
            "Two-step authentication is required",
            result.output,
        )
        self.assertIn("  0: SMS to *******03", result.output)
        self.assertIn("Please choose an option: [0]: 0", result.output)
        self.assertIn("Please enter two-step authentication code: 654321", result.output)
        self.assertIn(
            "Great, you're all set up. The script can now be run without "
            "user interaction until 2SA expires.",
            result.output,
        )
        self.assertEqual(result.exit_code, 0, "exit code")

    def test_password_prompt_2fa(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        result = run_cassette(
            os.path.join(self.vcr_path, "2fa_flow_valid_code.yml"),
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--no-progress-bar",
                "--cookie-directory",
                cookie_dir,
                "--auth-only",
            ],
            input="654321\n",
        )
        self.assertIn("Authenticating...", result.output)
        self.assertIn(
            "Two-factor authentication is required",
            result.output,
        )
        self.assertIn("  a: (***) ***-**81", result.output)
        self.assertIn(
            "Please enter two-factor authentication code or device index (a) to send SMS with a code: 654321",
            result.output,
        )
        self.assertIn(
            "Great, you're all set up. The script can now be run without "
            "user interaction until 2FA expires.",
            result.output,
        )
        self.assertNotIn("Failed to parse response with JSON mimetype", result.output)
        self.assertEqual(result.exit_code, 0, "exit code")

    def test_parse_trusted_phone_numbers_payload_valid(self) -> None:
        html_path = os.path.join(self.data_path, "parse_trusted_phone_numbers_payload_valid.html")
        with open(html_path, encoding="UTF-8") as file:
            html = file.read()
        expected = _TrustedDevice(id=1, obfuscated_number="(***) ***-**81")
        result = parse_trusted_phone_numbers_payload(html)
        self.assertEqual(1, len(result), "number of numbers parsed")
        self.assertEqual(expected, result[0], "parsed number")

    def test_parse_trusted_phone_numbers_payload_minimal(self) -> None:
        html = '<script type="application/json" class="boot_args">{"direct":{"twoSV":{"phoneNumberVerification":{"trustedPhoneNumbers":[{"numberWithDialCode":"+1 (•••) •••-••81","pushMode":"sms","obfuscatedNumber":"(•••) •••-••81","lastTwoDigits":"81","id":1}]},"authInitialRoute":"auth/verify/phone"}}}</script>'  # noqa: E501
        expected = _TrustedDevice(id=1, obfuscated_number="(***) ***-**81")
        result = parse_trusted_phone_numbers_payload(html)
        self.assertEqual(1, len(result), "number of numbers parsed")
        self.assertEqual(expected, result[0], "parsed number")

    def test_parse_trusted_phone_numbers_payload_bridge_initiate_fallback(self) -> None:
        html = '<script type="application/json" class="boot_args">{"direct":{"twoSV":{"bridgeInitiateData":{"phoneNumberVerification":{"trustedPhoneNumbers":[{"numberWithDialCode":"+1 (•••) •••-••81","pushMode":"sms","obfuscatedNumber":"(•••) •••-••81","lastTwoDigits":"81","id":1}]}},"authInitialRoute":"auth/verify/phone"}}}</script>'  # noqa: E501
        expected = _TrustedDevice(id=1, obfuscated_number="(***) ***-**81")
        result = parse_trusted_phone_numbers_payload(html)
        self.assertEqual(1, len(result), "number of numbers parsed")
        self.assertEqual(expected, result[0], "parsed number")

    def test_parse_trusted_phone_numbers_payload_missing_node0(self) -> None:
        html = '<script type="application/json" class="boot_args">{"MISSINGdirect":{"twoSV":{"phoneNumberVerification":{"trustedPhoneNumbers":[{"numberWithDialCode":"+1 (•••) •••-••81","pushMode":"sms","obfuscatedNumber":"(•••) •••-••81","lastTwoDigits":"81","id":1}]},"authInitialRoute":"auth/verify/phone"}}}</script>'  # noqa: E501
        result = parse_trusted_phone_numbers_payload(html)
        self.assertEqual(0, len(result), "number of numbers parsed")

    def test_parse_trusted_phone_numbers_payload_missing_node1(self) -> None:
        html = '<script type="application/json" class="boot_args">{"direct":{"MISSINGtwoSV":{"phoneNumberVerification":{"trustedPhoneNumbers":[{"numberWithDialCode":"+1 (•••) •••-••81","pushMode":"sms","obfuscatedNumber":"(•••) •••-••81","lastTwoDigits":"81","id":1}]},"authInitialRoute":"auth/verify/phone"}}}</script>'  # noqa: E501
        result = parse_trusted_phone_numbers_payload(html)
        self.assertEqual(0, len(result), "number of numbers parsed")

    def test_parse_trusted_phone_numbers_payload_missing_node2(self) -> None:
        html = '<script type="application/json" class="boot_args">{"direct":{"twoSV":{"MISSINGphoneNumberVerification":{"trustedPhoneNumbers":[{"numberWithDialCode":"+1 (•••) •••-••81","pushMode":"sms","obfuscatedNumber":"(•••) •••-••81","lastTwoDigits":"81","id":1}]},"authInitialRoute":"auth/verify/phone"}}}</script>'  # noqa: E501
        result = parse_trusted_phone_numbers_payload(html)
        self.assertEqual(0, len(result), "number of numbers parsed")

    def test_parse_trusted_phone_numbers_payload_missing_node3(self) -> None:
        html = '<script type="application/json" class="boot_args">{"direct":{"twoSV":{"phoneNumberVerification":{"MISSINGtrustedPhoneNumbers":[{"numberWithDialCode":"+1 (•••) •••-••81","pushMode":"sms","obfuscatedNumber":"(•••) •••-••81","lastTwoDigits":"81","id":1}]},"authInitialRoute":"auth/verify/phone"}}}</script>'  # noqa: E501
        result = parse_trusted_phone_numbers_payload(html)
        self.assertEqual(0, len(result), "number of numbers parsed")

    def test_parse_trusted_phone_numbers_payload_empty_list(self) -> None:
        html = '<script type="application/json" class="boot_args">{"direct":{"twoSV":{"phoneNumberVerification":{"trustedPhoneNumbers":[]},"authInitialRoute":"auth/verify/phone"}}}</script>'  # noqa: E501
        result = parse_trusted_phone_numbers_payload(html)
        self.assertEqual(0, len(result), "number of numbers parsed")

    def test_parse_trusted_phone_numbers_payload_invalid_missing_id(self) -> None:
        html = '<script type="application/json" class="boot_args">{"direct":{"twoSV":{"phoneNumberVerification":{"trustedPhoneNumbers":[{"numberWithDialCode":"+1 (•••) •••-••81","pushMode":"sms","obfuscatedNumber":"(•••) •••-••81","lastTwoDigits":"81","MISSINGid":1}]},"authInitialRoute":"auth/verify/phone"}}}</script>'  # noqa: E501
        result = parse_trusted_phone_numbers_payload(html)
        self.assertEqual(0, len(result), "number of numbers parsed")

    def test_parse_trusted_phone_numbers_payload_invalid_missing_number(self) -> None:
        html = '<script type="application/json" class="boot_args">{"direct":{"twoSV":{"phoneNumberVerification":{"trustedPhoneNumbers":[{"numberWithDialCode":"+1 (•••) •••-••81","pushMode":"sms","MISSINGobfuscatedNumber":"(•••) •••-••81","lastTwoDigits":"81","id":1}]},"authInitialRoute":"auth/verify/phone"}}}</script>'  # noqa: E501
        result = parse_trusted_phone_numbers_payload(html)
        self.assertEqual(0, len(result), "number of numbers parsed")

    def test_non_2fa(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        with vcr.use_cassette(os.path.join(self.vcr_path, "auth_non_2fa.yml")) as cass:
            # To re-record this HTTP request,
            # delete ./tests/vcr_cassettes/auth_requires_2fa.yml,
            # put your actual credentials in here, run the test,
            # and then replace with dummy credentials.
            authenticator(
                setup_logger(),
                "com",
                {"test": (constant("dummy"), dummy_password_writter)},
                MFAProvider.CONSOLE,
                StatusExchange(),
                "jdoe@gmail.com",
                lambda: None,
                None,
                cookie_dir,
                "EC5646DE-9423-11E8-BF21-14109FE0B321",
            )

            self.assertTrue(cass.all_played)

    def test_failed_auth_503(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        result = run_cassette(
            os.path.join(self.vcr_path, "failed_auth_503.yml"),
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--no-progress-bar",
                "--cookie-directory",
                cookie_dir,
                "--auth-only",
            ],
        )
        self.assertNotIn(
            "Failed to login with srp, falling back to old raw password authentication.",
            result.output,
        )
        self.assertIn("Apple iCloud is temporary refusing to serve icloudpd", result.output)
        self.assertEqual(result.exit_code, 1, "exit code")

    def test_failed_auth_503_watch(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        result = run_cassette(
            os.path.join(self.vcr_path, "failed_auth_503.yml"),
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--no-progress-bar",
                "--directory",
                base_dir,
                "--cookie-directory",
                cookie_dir,
                "--watch-with-interval",
                "1",
            ],
        )
        self.assertNotIn(
            "Failed to login with srp, falling back to old raw password authentication.",
            result.output,
        )
        self.assertEqual(
            2,
            result.output.count("Apple iCloud is temporary refusing to serve icloudpd"),
        )
        self.assertEqual(2, result.output.count("Waiting for 1 sec..."))
        # self.assertTrue("Can't overwrite existing cassette" in str(context.exception))
        self.assertEqual(result.exit_code, 1, "exit code")

    def test_connection_error(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        def mock_raise_response_error(*args, **kwargs) -> NoReturn:  # type: ignore [no-untyped-def]
            raise ConnectionError("Simulated Connection Error")

        with mock.patch(
            "requests.Session.request", side_effect=mock_raise_response_error
        ) as pa_request:
            result = run_cassette(
                os.path.join(self.vcr_path, "failed_auth_503.yml"),
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--no-progress-bar",
                    "--directory",
                    base_dir,
                    "--cookie-directory",
                    cookie_dir,
                    # "--watch-with-interval",
                    # "1",
                ],
            )
            pa_request.assert_called_once()
            self.assertIn(
                "Authenticating...",
                result.output,
            )
            self.assertIn(
                "Cannot connect to Apple iCloud service",
                result.output,
            )
            self.assertEqual(result.exit_code, 1, "exit code")

    def test_timeout_error(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        def mock_raise_response_error(*args, **kwargs) -> NoReturn:  # type: ignore [no-untyped-def]
            raise TimeoutError("Simulated TimeoutError")

        with mock.patch(
            "requests.Session.request", side_effect=mock_raise_response_error
        ) as pa_request:
            result = run_cassette(
                os.path.join(self.vcr_path, "failed_auth_503.yml"),
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--no-progress-bar",
                    "--directory",
                    base_dir,
                    "--cookie-directory",
                    cookie_dir,
                    # "--watch-with-interval",
                    # "1",
                ],
            )
            pa_request.assert_called_once()
            self.assertIn(
                "Authenticating...",
                result.output,
            )
            self.assertIn(
                "Cannot connect to Apple iCloud service",
                result.output,
            )
            self.assertEqual(result.exit_code, 1, "exit code")

    def test_timeout(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        def mock_raise_response_error(*args, **kwargs) -> NoReturn:  # type: ignore [no-untyped-def]
            raise Timeout("Simulated Timeout")

        with mock.patch(
            "requests.Session.request", side_effect=mock_raise_response_error
        ) as pa_request:
            result = run_cassette(
                os.path.join(self.vcr_path, "failed_auth_503.yml"),
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--no-progress-bar",
                    "--directory",
                    base_dir,
                    "--cookie-directory",
                    cookie_dir,
                    # "--watch-with-interval",
                    # "1",
                ],
            )
            pa_request.assert_called_once()
            self.assertIn(
                "Authenticating...",
                result.output,
            )
            self.assertIn(
                "Cannot connect to Apple iCloud service",
                result.output,
            )
            self.assertEqual(result.exit_code, 1, "exit code")

    def _login_confirmation_authenticator(
        self,
        logger: logging.Logger,
        status_exchange: StatusExchange,
        password_reader: Callable[[str], str | None],
        notificator: Callable[[], None],
        cookie_dir: str,
    ) -> "_BackgroundCall[PyiCloudService]":
        return _BackgroundCall(
            partial(
                authenticator,
                logger,
                "com",
                {"test": (password_reader, dummy_password_writter)},
                MFAProvider.CONSOLE,
                status_exchange,
                "jdoe@gmail.com",
                notificator,
                None,
                cookie_dir,
                "EC5646DE-9423-11E8-BF21-14109FE0B321",
                LoginConfirmation.WEBUI,
            )
        )

    def test_login_confirmation_webui_absent_session(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        logger = logging.getLogger("icloudpd.test_login_confirmation")
        status_exchange = StatusExchange()
        password_reader = mock.Mock(return_value="dummy")
        notificator = mock.Mock()

        with (
            vcr.use_cassette(os.path.join(self.vcr_path, "auth_non_2fa.yml")) as cass,
            self.assertLogs(logger, level="INFO") as logs,
        ):
            background = self._login_confirmation_authenticator(
                logger, status_exchange, password_reader, notificator, cookie_dir
            )
            background.wait_for_status(status_exchange, Status.NEED_LOGIN_CONFIRMATION)

            # nothing is sent to Apple and no password is read until the user confirms
            self.assertEqual(0, cass.play_count, "requests before confirmation")
            password_reader.assert_not_called()
            notificator.assert_called_once()

            self.assertTrue(status_exchange.confirm_login())
            background.join()

            password_reader.assert_called_once_with("jdoe@gmail.com")
            self.assertTrue(cass.all_played)
            self.assertEqual(Status.NO_INPUT_NEEDED, status_exchange.get_status())

        self.assertIn(
            "INFO:icloudpd.test_login_confirmation:Session expired for jdoe@gmail.com, "
            "waiting for sign-in confirmation in WebUI",
            logs.output,
        )

    def test_login_confirmation_webui_invalid_session(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        cookie_master_path = os.path.join(self.root_path, "cookie")

        recreate_path(base_dir)

        shutil.copytree(cookie_master_path, cookie_dir)

        status_exchange = StatusExchange()
        password_reader = mock.Mock(return_value="dummy")
        notificator = mock.Mock()

        with (
            mock.patch.object(
                PyiCloudService,
                "_validate_token",
                side_effect=PyiCloudAPIResponseException("Invalid authentication token", "421"),
            ) as validate_token,
            vcr.use_cassette(os.path.join(self.vcr_path, "auth_non_2fa.yml")) as cass,
        ):
            background = self._login_confirmation_authenticator(
                setup_logger(), status_exchange, password_reader, notificator, cookie_dir
            )
            background.wait_for_status(status_exchange, Status.NEED_LOGIN_CONFIRMATION)

            validate_token.assert_called_once()
            self.assertEqual(0, cass.play_count, "requests before confirmation")
            password_reader.assert_not_called()
            notificator.assert_called_once()

            self.assertTrue(status_exchange.confirm_login())
            background.join()

            password_reader.assert_called_once_with("jdoe@gmail.com")
            self.assertTrue(cass.all_played)
            self.assertEqual(Status.NO_INPUT_NEEDED, status_exchange.get_status())

    def test_login_confirmation_webui_valid_session(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        cookie_master_path = os.path.join(self.root_path, "cookie")

        recreate_path(base_dir)

        shutil.copytree(cookie_master_path, cookie_dir)

        status_exchange = StatusExchange()
        password_reader = mock.Mock(return_value="dummy")
        notificator = mock.Mock()

        with vcr.use_cassette(os.path.join(self.vcr_path, "successful_auth.yml")) as cass:
            self._login_confirmation_authenticator(
                setup_logger(), status_exchange, password_reader, notificator, cookie_dir
            ).join()

            self.assertTrue(cass.all_played)

        # valid session does not need sign-in, so confirmation is not requested
        password_reader.assert_not_called()
        notificator.assert_not_called()
        self.assertEqual(Status.NO_INPUT_NEEDED, status_exchange.get_status())

    def test_login_confirmation_webui_unexpected_status(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        status_exchange = StatusExchange()
        status_exchange.replace_status(Status.NO_INPUT_NEEDED, Status.NEED_MFA)
        password_reader = mock.Mock(return_value="dummy")
        notificator = mock.Mock()

        with vcr.use_cassette(os.path.join(self.vcr_path, "auth_non_2fa.yml")) as cass:
            background = self._login_confirmation_authenticator(
                setup_logger(), status_exchange, password_reader, notificator, cookie_dir
            )
            with self.assertRaises(PyiCloudFailedLoginException) as context:
                background.join()

            self.assertEqual(0, cass.play_count, "requests to Apple")

        self.assertIn("Expected NO_INPUT_NEEDED, but got NEED_MFA", str(context.exception))
        password_reader.assert_not_called()
        notificator.assert_not_called()

    def _assert_login_confirmation_notifies_once(self, cassette: str, mfa_request: str) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[1][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        status_exchange = StatusExchange()
        password_reader = mock.Mock(return_value="dummy")
        notificator = mock.Mock()

        with (
            mock.patch(f"icloudpd.authentication.{mfa_request}") as request_mfa,
            vcr.use_cassette(os.path.join(self.vcr_path, cassette)),
        ):
            background = self._login_confirmation_authenticator(
                setup_logger(), status_exchange, password_reader, notificator, cookie_dir
            )
            background.wait_for_status(status_exchange, Status.NEED_LOGIN_CONFIRMATION)
            notificator.assert_called_once()

            self.assertTrue(status_exchange.confirm_login())
            background.join()

        # MFA is requested right after the user confirmed sign-in, so there is no second notification
        request_mfa.assert_called_once()
        notificator.assert_called_once()

    def test_login_confirmation_webui_notifies_once_for_2fa(self) -> None:
        self._assert_login_confirmation_notifies_once("auth_requires_2fa.yml", "request_2fa")

    def test_login_confirmation_webui_notifies_once_for_2sa(self) -> None:
        self._assert_login_confirmation_notifies_once("2sa_flow_valid_code.yml", "request_2sa")

    def test_login_confirmation_webui_cli_absent_session(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        with (
            mock.patch("icloudpd.base.Thread") as thread,
            mock.patch("icloudpd.authentication.request_login_confirmation_web") as confirmation,
        ):
            result = run_cassette(
                os.path.join(self.vcr_path, "auth_non_2fa.yml"),
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--no-progress-bar",
                    "--cookie-directory",
                    cookie_dir,
                    "--auth-only",
                    "--login-confirmation",
                    "webui",
                ],
            )
        self.assertIs(serve_app, thread.call_args.kwargs["target"])
        confirmation.assert_called_once_with(mock.ANY, mock.ANY, "jdoe@gmail.com", mock.ANY)
        self.assertIn("Starting web server for WebUI authentication...", result.output)
        self.assertIn("Authentication completed successfully", result.output)
        self.assertEqual(result.exit_code, 0, "exit code")

    def test_login_confirmation_webui_cli_valid_session(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        cookie_master_path = os.path.join(self.root_path, "cookie")

        recreate_path(base_dir)

        shutil.copytree(cookie_master_path, cookie_dir)

        with (
            mock.patch("icloudpd.base.Thread") as thread,
            mock.patch("icloudpd.authentication.request_login_confirmation_web") as confirmation,
        ):
            result = run_cassette(
                os.path.join(self.vcr_path, "successful_auth.yml"),
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--no-progress-bar",
                    "--cookie-directory",
                    cookie_dir,
                    "--auth-only",
                    "--login-confirmation",
                    "webui",
                ],
            )
        self.assertIs(serve_app, thread.call_args.kwargs["target"])
        confirmation.assert_not_called()
        self.assertIn("Authentication completed successfully", result.output)
        self.assertEqual(result.exit_code, 0, "exit code")

    def test_login_confirmation_none_cli(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        with (
            mock.patch("icloudpd.base.Thread") as thread,
            mock.patch("icloudpd.authentication.request_login_confirmation_web") as confirmation,
        ):
            result = run_cassette(
                os.path.join(self.vcr_path, "auth_non_2fa.yml"),
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--no-progress-bar",
                    "--cookie-directory",
                    cookie_dir,
                    "--auth-only",
                ],
            )
        thread.assert_not_called()
        confirmation.assert_not_called()
        self.assertIn("Authentication completed successfully", result.output)
        self.assertEqual(result.exit_code, 0, "exit code")


class _TrustedDevice(NamedTuple):
    id: int
    obfuscated_number: str


_T = TypeVar("_T")


class _BackgroundCall(Generic[_T]):
    """Runs a blocking call in a daemon thread, so a test can interact with it while it waits"""

    def __init__(self, func: Callable[[], _T]) -> None:
        self.result: _T | None = None
        self.error: BaseException | None = None

        def _run() -> None:
            try:
                self.result = func()
            except BaseException as error:
                self.error = error

        self.thread = Thread(target=_run, daemon=True)
        self.thread.start()

    def join(self, timeout: float = 10) -> _T:
        self.thread.join(timeout)
        if self.thread.is_alive():
            raise TimeoutError("Background call did not finish in time")
        if self.error is not None:
            raise self.error
        return cast(_T, self.result)

    def wait_for_status(
        self, status_exchange: StatusExchange, expected: Status, timeout: float = 10
    ) -> None:
        deadline = time.monotonic() + timeout
        while status_exchange.get_status() != expected:
            if not self.thread.is_alive():
                self.join(0)  # surfaces the error of the finished call
                raise AssertionError(f"Finished without reaching {expected}")
            if time.monotonic() > deadline:
                raise TimeoutError(f"Expected {expected}, but got {status_exchange.get_status()}")
            time.sleep(0.01)
