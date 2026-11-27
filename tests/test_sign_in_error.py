import inspect
import json
import os
from contextlib import nullcontext
from types import SimpleNamespace
from typing import Any, List
from unittest import TestCase, mock

from icloudpd.base import apple_sign_in_error
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.exceptions import PyiCloudAPIResponseException, PyiCloudFailedLoginException
from tests.helpers import path_from_project_root, recreate_path, run_cassette, run_main

WRONG_PASSWORD_BODY = json.dumps(
    {
        "serviceErrors": [
            {
                "code": "-20101",
                "message": "Check the account information you entered and try again.",
                "suppressDismissal": False,
            }
        ]
    },
    indent=2,
)


class AppleSignInErrorTestCase(TestCase):
    """A failed sign-in is one readable line with Apple's message, not a tuple with raw JSON (#1348)"""

    def test_apple_message_and_code(self) -> None:
        error = PyiCloudFailedLoginException(
            "Invalid email/password combination.",
            PyiCloudAPIResponseException(WRONG_PASSWORD_BODY, "401"),
        )
        self.assertEqual(
            apple_sign_in_error(error),
            'Invalid email/password combination. Apple says: "Check the account information '
            'you entered and try again." (-20101)',
        )

    def test_answer_that_is_not_json(self) -> None:
        error = PyiCloudFailedLoginException(
            "Invalid email/password combination.",
            PyiCloudAPIResponseException("Service Temporarily Unavailable", "503"),
        )
        self.assertEqual(
            apple_sign_in_error(error),
            "Invalid email/password combination. Apple's answer: "
            "Service Temporarily Unavailable (503)",
        )

    def test_error_without_apple_answer(self) -> None:
        error = PyiCloudFailedLoginException("Timed out waiting for the iCloud web access approval")
        self.assertEqual(
            apple_sign_in_error(error), "Timed out waiting for the iCloud web access approval"
        )

    def test_empty_message_from_apple(self) -> None:
        body = json.dumps({"serviceErrors": [{"code": "-20101", "message": None}]})
        error = PyiCloudFailedLoginException(
            "Invalid email/password combination.", PyiCloudAPIResponseException(body, "401")
        )
        self.assertEqual(
            apple_sign_in_error(error),
            f"Invalid email/password combination. Apple's answer: {body} (401)",
        )

    def test_missing_code_uses_the_http_status(self) -> None:
        body = json.dumps({"serviceErrors": [{"code": None, "message": "Try again later."}]})
        error = PyiCloudFailedLoginException(
            "Invalid email/password combination.", PyiCloudAPIResponseException(body, "503")
        )
        self.assertEqual(
            apple_sign_in_error(error),
            'Invalid email/password combination. Apple says: "Try again later." (503)',
        )


class SrpInitRefusedTestCase(TestCase):
    """Apple refusing signin/init is a failed sign-in with its message, not KeyError 'salt' (#1499)"""

    def init(self, status_code: int, text: str) -> PyiCloudFailedLoginException:
        response = mock.Mock(status_code=status_code, ok=status_code < 400, text=text)
        response.json.side_effect = lambda: json.loads(text)
        service = SimpleNamespace(
            apple_id="jdoe@gmail.com",
            AUTH_ENDPOINT="https://idmsa.apple.com/appleauth/auth",
            AUTH_ROOT_ENDPOINT="https://idmsa.apple.com",
            response_observer=None,
            use_rules=lambda rules: nullcontext(rules),
            _get_auth_headers=lambda overrides=None: dict(overrides or {}),
            session=mock.Mock(**{"post.return_value": response}),
        )
        with self.assertRaises(PyiCloudFailedLoginException) as context:
            PyiCloudService._authenticate_srp(service, "password1")  # type: ignore[arg-type]
        service.session.post.assert_called_once()
        return context.exception

    def test_refused_with_400(self) -> None:
        body = json.dumps(
            {
                "serviceErrors": [
                    {"code": "-900007", "message": "Your request could not be completed."}
                ]
            }
        )
        error = self.init(400, body)

        self.assertEqual(
            apple_sign_in_error(error),
            'Failed to initiate srp authentication. Apple says: "Your request could not be '
            'completed." (-900007)',
        )

    def test_refused_with_401(self) -> None:
        error = self.init(401, WRONG_PASSWORD_BODY)

        self.assertIn("Apple says:", apple_sign_in_error(error))
        self.assertIn("(-20101)", apple_sign_in_error(error))

    def test_answer_without_salt(self) -> None:
        for text in ['{"protocol": "s2k"}', "<html>maintenance</html>", "[]"]:
            with self.subTest(text=text):
                error = self.init(200, text)

                self.assertEqual(
                    apple_sign_in_error(error),
                    f"Failed to initiate srp authentication. Apple's answer: {text} (200)",
                )


class SignInErrorOutputTestCase(TestCase):
    def run_wrong_password(self, params: List[str]) -> Any:
        root_path = path_from_project_root(__file__)
        base_dir = os.path.join(root_path, "fixtures", inspect.stack()[1][3])
        self.cookie_dir = os.path.join(base_dir, "cookie")
        recreate_path(base_dir)
        recreate_path(self.cookie_dir)

        # an older password is stored in the keyring in both cases
        with mock.patch("icloudpd.base.get_password_from_keyring", return_value="old-password"):
            return run_cassette(
                os.path.join(root_path, "vcr_cassettes", "failed_auth.yml"),
                [
                    "--username",
                    "bad_username",
                    *params,
                    "--cookie-directory",
                    self.cookie_dir,
                    "--auth-only",
                    "--no-progress-bar",
                ],
            )

    def test_wrong_password_is_reported_as_one_error_line(self) -> None:
        result = self.run_wrong_password(["--password", "bad_password"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            'ERROR    Invalid email/password combination. Apple says: "Enter the email or phone '
            'number and password for your Apple Account." (-20101)',
            result.raw_output,
        )
        self.assertNotIn("('Invalid email/password combination.'", result.output)
        self.assertIn(f"deleting the saved session in {self.cookie_dir}", result.output)
        self.assertIn("Sign-in requests and responses (for a bug report):", result.output)
        # the refused password came from --password, so the keyring isn't to blame
        self.assertNotIn("keyring", result.output)

    def test_keyring_hint_when_the_keyring_gave_the_password(self) -> None:
        result = self.run_wrong_password(["--password-provider", "keyring"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("The password came from the keyring and may be out of date", result.output)
        self.assertIn("`icloud --username bad_username --delete-from-keyring`", result.output)

    def test_no_hints_for_other_sign_in_errors(self) -> None:
        """e.g. the session isn't accepted after the password was: not a password problem"""
        error = PyiCloudFailedLoginException(
            "Invalid authentication token.", PyiCloudAPIResponseException("Misdirected", "421")
        )
        with mock.patch("icloudpd.base.authenticator", side_effect=error):
            result = run_main(
                ["--username", "jdoe@gmail.com", "--password", "password1", "--auth-only"]
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "Invalid authentication token. Apple's answer: Misdirected (421)", result.output
        )
        self.assertNotIn("If the password is right", result.output)
        self.assertNotIn("keyring", result.output)
