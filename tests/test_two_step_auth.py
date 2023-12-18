from unittest import TestCase
from vcr import VCR
import mock
import pytest
import os
import click
from click.testing import CliRunner
from icloudpd.base import main
from pyicloud_ipd import PyiCloudService
import inspect
import shutil
import glob

from tests.helpers import path_from_project_root, recreate_path

vcr = VCR(decode_compressed_response=True)


class TwoStepAuthTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")
        self.vcr_path = os.path.join(self.root_path, "vcr_cassettes")

    def test_2sa_flow_invalid_code(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        with vcr.use_cassette(os.path.join(self.vcr_path, "2sa_flow_invalid_code.yml")):
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
                    "--auth-only"
                ],
                input="0\n901431\n",
            )
            self.assertIn(
                "ERROR    Failed to verify two-factor authentication code",
                self._caplog.text,
            )

            assert result.exit_code == 1

    def test_2sa_flow_valid_code(self):
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

    def test_2sa_flow_failed_send_code(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        with vcr.use_cassette(os.path.join(self.vcr_path, "2sa_flow_valid_code.yml")):
            with mock.patch.object(
                PyiCloudService, "send_verification_code"
            ) as svc_mocked:
                svc_mocked.return_value = False
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
                        "--auth-only"
                    ],
                    input="0\n",
                )
                self.assertIn("DEBUG    Authenticating...", self._caplog.text)
                self.assertIn(
                    "INFO     Two-step/two-factor authentication is required",
                    self._caplog.text,
                )
                self.assertIn("  0: SMS to *******03", result.output)
                self.assertIn("Please choose an option: [0]: 0", result.output)
                self.assertIn(
                    "ERROR    Failed to send two-factor authentication code",
                    self._caplog.text,
                )
                assert result.exit_code == 1

    def test_2fa_flow_invalid_code(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        with vcr.use_cassette(os.path.join(self.vcr_path, "2fa_flow_invalid_code.yml")):
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
                    "--auth-only"
                ],
                input="901431\n",
            )
            self.assertIn(
                "ERROR    Failed to verify two-factor authentication code",
                self._caplog.text,
            )

            assert result.exit_code == 1

    def test_2fa_flow_valid_code(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")

        for dir in [base_dir, cookie_dir]:
            recreate_path(dir)

        with vcr.use_cassette(os.path.join(self.vcr_path, "2fa_flow_valid_code.yml")):
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
                input="654321\n",
            )
            self.assertIn("DEBUG    Authenticating...", self._caplog.text)
            self.assertIn(
                "INFO     Two-step/two-factor authentication is required",
                self._caplog.text,
            )
            self.assertIn(
                "Please enter two-factor authentication code: 654321", result.output
            )
            self.assertIn(
                "INFO     Great, you're all set up. The script can now be run without "
                "user interaction until 2SA expires.",
                self._caplog.text,
            )
            assert result.exit_code == 0
