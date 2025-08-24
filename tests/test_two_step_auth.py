import inspect
import os
from unittest import TestCase, mock

import pytest

from pyicloud_ipd.base import PyiCloudService
from tests.helpers import (
    calc_cookie_dir,
    calc_vcr_dir,
    path_from_project_root,
    recreate_path,
    run_cassette,
)


class TwoStepAuthTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")
        self.vcr_path = calc_vcr_dir(self.root_path)

    def test_2sa_flow_invalid_code(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = calc_cookie_dir(base_dir)

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        result = run_cassette(
            os.path.join(self.vcr_path, "2sa_flow_invalid_code.yml"),
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
            input="0\n901431\n",
        )
        self.assertIn(
            "Failed to verify two-step authentication code",
            result.output,
        )

        self.assertEqual(result.exit_code, 1, "exit code")

    def test_2sa_flow_valid_code(self) -> None:
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

    def test_2sa_flow_failed_send_code(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        with mock.patch.object(PyiCloudService, "send_verification_code") as svc_mocked:
            svc_mocked.return_value = False
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
                input="0\n",
            )
            self.assertIn("Authenticating...", result.output)
            self.assertIn(
                "Two-step authentication is required",
                result.output,
            )
            self.assertIn("  0: SMS to *******03", result.output)
            self.assertIn("Please choose an option: [0]: 0", result.output)
            self.assertIn(
                "Failed to send two-step authentication code",
                result.output,
            )
            self.assertEqual(result.exit_code, 1, "exit code")

    def test_2fa_flow_invalid_code(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        result = run_cassette(
            os.path.join(self.vcr_path, "2fa_flow_invalid_code.yml"),
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
            input="901431\n",
        )
        self.assertIn(
            "Failed to verify two-factor authentication code",
            result.output,
        )

        self.assertEqual(result.exit_code, 1, "exit code")

    def test_2fa_flow_valid_code(self) -> None:
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
        self.assertIn(
            "Please enter two-factor authentication code or device index (a) to send SMS with a code: 654321",
            result.output,
        )
        self.assertIn(
            "Great, you're all set up. The script can now be run without "
            "user interaction until 2FA expires.",
            result.output,
        )
        self.assertEqual(result.exit_code, 0, "exit code")

    def test_2fa_flow_valid_code_zero_lead(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        result = run_cassette(
            os.path.join(self.vcr_path, "2fa_flow_valid_code_zero_lead.yml"),
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
            input="054321\n",
        )
        self.assertIn("Authenticating...", result.output)
        self.assertIn(
            "Two-factor authentication is required",
            result.output,
        )
        self.assertIn(
            "Please enter two-factor authentication code or device index (a) to send SMS with a code: 054321",
            result.output,
        )
        self.assertIn(
            "Great, you're all set up. The script can now be run without "
            "user interaction until 2FA expires.",
            result.output,
        )
        self.assertEqual(result.exit_code, 0, "exit code")
