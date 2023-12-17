from unittest import TestCase
import os
from vcr import VCR
import pytest
from click.testing import CliRunner
from icloudpd.logger import setup_logger
import pyicloud_ipd
from icloudpd.base import main
from icloudpd.authentication import authenticator, TwoStepAuthRequiredError
import inspect
import glob

from tests.helpers import path_from_project_root, recreate_path

vcr = VCR(decode_compressed_response=True)


class AuthenticationTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")
        self.vcr_path = os.path.join(self.root_path, "vcr_cassettes")

    def test_failed_auth(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        with vcr.use_cassette(os.path.join(self.vcr_path, "failed_auth.yml")):
            with self.assertRaises(
                pyicloud_ipd.exceptions.PyiCloudFailedLoginException
            ) as context:
                authenticator(setup_logger(), "com")(
                    "bad_username",
                    "bad_password",
                    cookie_directory=cookie_dir,
                    client_id="EC5646DE-9423-11E8-BF21-14109FE0B321",
                )

        self.assertTrue(
            "Invalid email/password combination." in str(context.exception))

    def test_2sa_required(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        with vcr.use_cassette(os.path.join(self.vcr_path, "2sa_flow_valid_code.yml")):
            with self.assertRaises(TwoStepAuthRequiredError) as context:
                # To re-record this HTTP request,
                # delete ./tests/vcr_cassettes/auth_requires_2sa.yml,
                # put your actual credentials in here, run the test,
                # and then replace with dummy credentials.
                authenticator(setup_logger(), "com")(
                    "jdoe@gmail.com",
                    "password1",
                    raise_error_on_2sa=True,
                    cookie_directory=cookie_dir,
                    client_id="DE309E26-942E-11E8-92F5-14109FE0B321",
                )

            self.assertTrue(
                "Two-step/two-factor authentication is required"
                in str(context.exception)
            )

    def test_2fa_required(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        with vcr.use_cassette(os.path.join(self.vcr_path, "auth_requires_2fa.yml")):
            with self.assertRaises(TwoStepAuthRequiredError) as context:
                # To re-record this HTTP request,
                # delete ./tests/vcr_cassettes/auth_requires_2fa.yml,
                # put your actual credentials in here, run the test,
                # and then replace with dummy credentials.
                authenticator(setup_logger(), "com")(
                    "jdoe@gmail.com",
                    "password1",
                    raise_error_on_2sa=True,
                    cookie_directory=cookie_dir,
                    client_id="EC5646DE-9423-11E8-BF21-14109FE0B321",
                )

            self.assertTrue(
                "Two-step/two-factor authentication is required"
                in str(context.exception)
            )

    def test_successful_token_validation(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        # We need to create a session file first before we test the auth token validation
        with vcr.use_cassette(os.path.join(self.vcr_path, "2sa_flow_valid_code.yml")):
            runner = CliRunner(env={
                "CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"
            })
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
            assert result.exit_code ==0

        with vcr.use_cassette(os.path.join(self.vcr_path, "successful_auth.yml")):
            runner = CliRunner(env={
                "CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"
            })
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

    def test_password_prompt(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        with vcr.use_cassette(os.path.join(self.vcr_path, "2sa_flow_valid_code.yml")):
            runner = CliRunner(env={
                "CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"
            })
            result = runner.invoke(
                main,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--no-progress-bar",
                    "--cookie-directory",
                    cookie_dir,
                    "--auth-only",
                ],
                input="password1\n0\n654321\n",
            )
            self.assertIn("DEBUG    Authenticating...", self._caplog.text)
            self.assertIn(
                "INFO     Two-step/two-factor authentication is required",
                self._caplog.text,
            )
            self.assertIn("  0: SMS to *******03", result.output)
            self.assertIn("Please choose an option: [0]: 0", result.output)
            self.assertIn(
                "Please enter two-factor authentication code: 654321", result.output
            )
            self.assertIn(
                "INFO     Great, you're all set up. The script can now be run without "
                "user interaction until 2SA expires.",
                self._caplog.text,
            )
            assert result.exit_code == 0
