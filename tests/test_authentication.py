import inspect
import os
import shutil
from typing import Any, NamedTuple, NoReturn
from unittest import TestCase, mock

import pytest
from click.testing import CliRunner
from requests import Timeout
from requests.exceptions import ConnectionError
from vcr import VCR

# import vcr
import pyicloud_ipd
from foundation.core import constant, identity
from icloudpd.authentication import authenticator
from icloudpd.base import dummy_password_writter, lp_filename_concatinator, main
from icloudpd.logger import setup_logger
from icloudpd.mfa_provider import MFAProvider
from icloudpd.status import StatusExchange
from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.raw_policy import RawTreatmentPolicy
from pyicloud_ipd.session import PyiCloudSession
from pyicloud_ipd.sms import parse_trusted_phone_numbers_payload
from tests.helpers import path_from_project_root, recreate_path

vcr = VCR(decode_compressed_response=True, record_mode="none")


class AuthenticationTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog: pytest.LogCaptureFixture) -> None:
        self._caplog = caplog
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
                    identity,
                    lp_filename_concatinator,
                    RawTreatmentPolicy.AS_IS,
                    FileMatchPolicy.NAME_SIZE_DEDUP_WITH_SUFFIX,
                    {"test": (constant("dummy"), dummy_password_writter)},
                    MFAProvider.CONSOLE,
                    StatusExchange(),
                    "bad_username",
                    lambda: None,
                    None,
                    cookie_dir,
                    "EC5646DE-9423-11E8-BF21-14109FE0B321",
                )

        self.assertIn(
            "ERROR    Failed to login with srp, falling back to old raw password authentication.",
            self._caplog.text,
        )
        self.assertTrue("Invalid email/password combination." in str(context.exception))

    def test_fallback_raw_password(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        with vcr.use_cassette(os.path.join(self.vcr_path, "fallback_raw_password.yml")):  # noqa: SIM117
            runner = CliRunner(env={"CLIENT_ID": "EC5646DE-9423-11E8-BF21-14109FE0B321"})
            result = runner.invoke(
                main,
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
                "ERROR    Failed to login with srp, falling back to old raw password authentication.",
                self._caplog.text,
            )
            self.assertIn("INFO     Authentication completed successfully", self._caplog.text)
            assert result.exit_code == 0

    def test_successful_token_validation(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        cookie_master_path = os.path.join(self.root_path, "cookie")

        recreate_path(base_dir)

        shutil.copytree(cookie_master_path, cookie_dir)

        with vcr.use_cassette(os.path.join(self.vcr_path, "successful_auth.yml")):
            runner = CliRunner(env={"CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"})
            result = runner.invoke(
                main,
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
            self.assertIn("INFO     Authentication completed successfully", self._caplog.text)
            assert result.exit_code == 0

    def test_password_prompt_2sa(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        with vcr.use_cassette(os.path.join(self.vcr_path, "2sa_flow_valid_code.yml")):
            runner = CliRunner(env={"CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"})
            result = runner.invoke(
                main,
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
            self.assertIn("DEBUG    Authenticating...", self._caplog.text)
            self.assertIn(
                "INFO     Two-step authentication is required",
                self._caplog.text,
            )
            self.assertIn("  0: SMS to *******03", result.output)
            self.assertIn("Please choose an option: [0]: 0", result.output)
            self.assertIn("Please enter two-step authentication code: 654321", result.output)
            self.assertIn(
                "INFO     Great, you're all set up. The script can now be run without "
                "user interaction until 2SA expires.",
                self._caplog.text,
            )
            assert result.exit_code == 0

    def test_password_prompt_2fa(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        with vcr.use_cassette(os.path.join(self.vcr_path, "2fa_flow_valid_code.yml")):
            runner = CliRunner(env={"CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"})
            result = runner.invoke(
                main,
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
            self.assertIn("DEBUG    Authenticating...", self._caplog.text)
            self.assertIn(
                "INFO     Two-factor authentication is required",
                self._caplog.text,
            )
            self.assertIn("  a: (***) ***-**81", result.output)
            self.assertIn(
                "Please enter two-factor authentication code or device index (a) to send SMS with a code: 654321",
                result.output,
            )
            self.assertIn(
                "INFO     Great, you're all set up. The script can now be run without "
                "user interaction until 2FA expires.",
                self._caplog.text,
            )
            self.assertNotIn("Failed to parse response with JSON mimetype", self._caplog.text)
            assert result.exit_code == 0

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
                identity,
                lp_filename_concatinator,
                RawTreatmentPolicy.AS_IS,
                FileMatchPolicy.NAME_SIZE_DEDUP_WITH_SUFFIX,
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

        with vcr.use_cassette(os.path.join(self.vcr_path, "failed_auth_503.yml")):  # noqa: SIM117
            runner = CliRunner(env={"CLIENT_ID": "EC5646DE-9423-11E8-BF21-14109FE0B321"})
            result = runner.invoke(
                main,
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
                "ERROR    Failed to login with srp, falling back to old raw password authentication.",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     Apple iCloud is temporary refusing to serve icloudpd", self._caplog.text
            )
            assert result.exit_code == 1

    def test_failed_auth_503_watch(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        with vcr.use_cassette(os.path.join(self.vcr_path, "failed_auth_503.yml")):  # noqa: SIM117
            # errors.CannotOverwriteExistingCassetteException
            runner = CliRunner(env={"CLIENT_ID": "EC5646DE-9423-11E8-BF21-14109FE0B321"})
            result = runner.invoke(
                main,
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
                "ERROR    Failed to login with srp, falling back to old raw password authentication.",
                self._caplog.text,
            )
            self.assertEqual(
                2,
                self._caplog.text.count(
                    "INFO     Apple iCloud is temporary refusing to serve icloudpd"
                ),
            )
            self.assertEqual(2, self._caplog.text.count("INFO     Waiting for 1 sec..."))
            # self.assertTrue("Can't overwrite existing cassette" in str(context.exception))
            assert result.exit_code == 1  # should error for vcr

    def test_connection_error(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        def mock_raise_response_error(_a1: Any, _a2: Any, _a3: Any, **kwargs) -> NoReturn:  # type: ignore [no-untyped-def]
            raise ConnectionError("Simulated Connection Error")

        with (
            mock.patch.object(
                PyiCloudSession, "request", side_effect=mock_raise_response_error, autospec=True
            ) as pa_request,
            vcr.use_cassette(os.path.join(self.vcr_path, "failed_auth_503.yml")),
        ):  # noqa: SIM117
            # errors.CannotOverwriteExistingCassetteException
            runner = CliRunner(env={"CLIENT_ID": "EC5646DE-9423-11E8-BF21-14109FE0B321"})
            result = runner.invoke(
                main,
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
                self._caplog.text,
            )
            self.assertIn(
                "INFO     Cannot connect to Apple iCloud service",
                self._caplog.text,
            )
            assert result.exit_code == 1  # should error for vcr

    def test_timeout_error(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        def mock_raise_response_error(_a1: Any, _a2: Any, _a3: Any, **kwargs) -> NoReturn:  # type: ignore [no-untyped-def]
            raise TimeoutError("Simulated TimeoutError")

        with (
            mock.patch.object(
                PyiCloudSession, "request", side_effect=mock_raise_response_error, autospec=True
            ) as pa_request,
            vcr.use_cassette(os.path.join(self.vcr_path, "failed_auth_503.yml")),
        ):  # noqa: SIM117
            # errors.CannotOverwriteExistingCassetteException
            runner = CliRunner(env={"CLIENT_ID": "EC5646DE-9423-11E8-BF21-14109FE0B321"})
            result = runner.invoke(
                main,
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
                self._caplog.text,
            )
            self.assertIn(
                "INFO     Cannot connect to Apple iCloud service",
                self._caplog.text,
            )
            assert result.exit_code == 1  # should error for vcr

    def test_timeout(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        def mock_raise_response_error(_a1: Any, _a2: Any, _a3: Any, **kwargs) -> NoReturn:  # type: ignore [no-untyped-def]
            raise Timeout("Simulated Timeout")

        with (
            mock.patch.object(
                PyiCloudSession, "request", side_effect=mock_raise_response_error, autospec=True
            ) as pa_request,
            vcr.use_cassette(os.path.join(self.vcr_path, "failed_auth_503.yml")),
        ):  # noqa: SIM117
            # errors.CannotOverwriteExistingCassetteException
            runner = CliRunner(env={"CLIENT_ID": "EC5646DE-9423-11E8-BF21-14109FE0B321"})
            result = runner.invoke(
                main,
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
                self._caplog.text,
            )
            self.assertIn(
                "INFO     Cannot connect to Apple iCloud service",
                self._caplog.text,
            )
            assert result.exit_code == 1  # should error for vcr


class _TrustedDevice(NamedTuple):
    id: int
    obfuscated_number: str
