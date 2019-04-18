from unittest import TestCase
from vcr import VCR
import mock
import pytest
import os
import click
from click.testing import CliRunner
from icloudpd.base import main
from pyicloud_ipd import PyiCloudService

vcr = VCR(decode_compressed_response=True)


class TwoStepAuthTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    def test_2sa_flow_invalid_device_2fa(self):
        with vcr.use_cassette("tests/vcr_cassettes/2sa_flow_invalid_device.yml"):
            os.environ["CLIENT_ID"] = "DE309E26-942E-11E8-92F5-14109FE0B321"
            runner = CliRunner()
            result = runner.invoke(
                main,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "0",
                    "--no-progress-bar",
                    "-d",
                    "tests/fixtures/Photos",
                ],
                input="1\n901431\n",
            )
            self.assertIn(
                "ERROR    Failed to verify two-factor authentication code",
                self._caplog.text,
            )
            assert result.exit_code == 1

    def test_2sa_flow_device_2fa(self):
        with vcr.use_cassette("tests/vcr_cassettes/2sa_flow_valid_device.yml"):
            os.environ["CLIENT_ID"] = "DE309E26-942E-11E8-92F5-14109FE0B321"
            runner = CliRunner()
            result = runner.invoke(
                main,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "0",
                    "--no-progress-bar",
                    "-d",
                    "tests/fixtures/Photos",
                ],
                input="1\n654321\n",
            )
            self.assertIn("DEBUG    Authenticating...", self._caplog.text)
            self.assertIn(
                "INFO     Two-step/two-factor authentication is required!",
                self._caplog.text,
            )
            self.assertIn("  0: SMS to *******03", result.output)
            self.assertIn("  1: Enter two-factor authentication code", result.output)
            self.assertIn("Please choose an option: [0]: 1", result.output)
            self.assertIn(
                "Please enter two-factor authentication code: 654321", result.output
            )
            self.assertIn(
                "INFO     Great, you're all set up. The script can now be run without "
                "user interaction until 2SA expires.",
                self._caplog.text,
            )
            self.assertIn(
                "DEBUG    Looking up all photos and videos from album All Photos...", self._caplog.text
            )
            self.assertIn(
                "INFO     All photos have been downloaded!", self._caplog.text
            )
            assert result.exit_code == 0

    def test_2sa_flow_sms(self):
        with vcr.use_cassette("tests/vcr_cassettes/2sa_flow_valid_sms.yml"):
            os.environ["CLIENT_ID"] = "DE309E26-942E-11E8-92F5-14109FE0B321"
            runner = CliRunner()
            result = runner.invoke(
                main,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "0",
                    "--no-progress-bar",
                    "-d",
                    "tests/fixtures/Photos",
                ],
                input="0\n123456\n",
            )
            self.assertIn("DEBUG    Authenticating...", self._caplog.text)
            self.assertIn(
                "INFO     Two-step/two-factor authentication is required!",
                self._caplog.text,
            )
            self.assertIn("  0: SMS to *******03", result.output)
            self.assertIn("  1: Enter two-factor authentication code", result.output)
            self.assertIn("Please choose an option: [0]: 0", result.output)
            self.assertIn(
                "Please enter two-factor authentication code: 123456", result.output
            )
            self.assertIn(
                "INFO     Great, you're all set up. The script can now be run without "
                "user interaction until 2SA expires.",
                self._caplog.text,
            )
            self.assertIn(
                "DEBUG    Looking up all photos and videos from album All Photos...", self._caplog.text
            )
            self.assertIn(
                "INFO     All photos have been downloaded!", self._caplog.text
            )
            assert result.exit_code == 0

    def test_2sa_flow_sms_failed(self):
        with vcr.use_cassette("tests/vcr_cassettes/2sa_flow_valid_sms.yml"):
            with mock.patch.object(
                PyiCloudService, "send_verification_code"
            ) as svc_mocked:
                svc_mocked.return_value = False
                os.environ["CLIENT_ID"] = "DE309E26-942E-11E8-92F5-14109FE0B321"
                runner = CliRunner()
                result = runner.invoke(
                    main,
                    [
                        "--username",
                        "jdoe@gmail.com",
                        "--password",
                        "password1",
                        "--recent",
                        "0",
                        "--no-progress-bar",
                        "-d",
                        "tests/fixtures/Photos",
                    ],
                    input="0\n",
                )
                self.assertIn("DEBUG    Authenticating...", self._caplog.text)
                self.assertIn(
                    "INFO     Two-step/two-factor authentication is required!",
                    self._caplog.text,
                )
                self.assertIn("  0: SMS to *******03", result.output)
                self.assertIn(
                    "  1: Enter two-factor authentication code", result.output
                )
                self.assertIn("Please choose an option: [0]: 0", result.output)
                self.assertIn(
                    "ERROR    Failed to send two-factor authentication code",
                    self._caplog.text,
                )
                assert result.exit_code == 1
