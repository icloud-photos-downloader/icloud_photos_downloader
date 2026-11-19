import inspect
import json
import os
from unittest import TestCase, mock

from icloudpd.base import apple_sign_in_error
from pyicloud_ipd.exceptions import PyiCloudAPIResponseException, PyiCloudFailedLoginException
from tests.helpers import path_from_project_root, recreate_path, run_cassette

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


class SignInErrorOutputTestCase(TestCase):
    def test_wrong_password_is_reported_as_one_error_line(self) -> None:
        root_path = path_from_project_root(__file__)
        base_dir = os.path.join(root_path, "fixtures", inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        recreate_path(base_dir)
        recreate_path(cookie_dir)

        with mock.patch("icloudpd.base.get_password_from_keyring", return_value="old-password"):
            result = run_cassette(
                os.path.join(root_path, "vcr_cassettes", "failed_auth.yml"),
                [
                    "--username",
                    "bad_username",
                    "--password",
                    "bad_password",
                    "--cookie-directory",
                    cookie_dir,
                    "--auth-only",
                    "--no-progress-bar",
                ],
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            'Invalid email/password combination. Apple says: "Enter the email or phone '
            'number and password for your Apple Account." (-20101)',
            result.output,
        )
        self.assertNotIn("('Invalid email/password combination.'", result.output)
        self.assertIn("is stored in the keyring and may be out of date", result.output)
        self.assertIn(f"deleting the saved session in {cookie_dir}", result.output)
        self.assertIn("Sign-in requests and responses (for a bug report):", result.output)
