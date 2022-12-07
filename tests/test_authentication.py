from unittest import TestCase
import os
from vcr import VCR
import pytest
from click.testing import CliRunner
import pyicloud
from icloudpd.base import main
from icloudpd.authentication import authenticate, TwoStepAuthRequiredError
import inspect

vcr = VCR(decode_compressed_response=True)


class AuthenticationTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    def test_failed_auth(self):
        with vcr.use_cassette("tests/vcr_cassettes/failed_auth.yml"):
            with self.assertRaises(
                pyicloud.exceptions.PyiCloudFailedLoginException
            ) as context:
                authenticate(
                    "bad_username",
                    "bad_password",
                    client_id="EC5646DE-9423-11E8-BF21-14109FE0B321",
                )

        self.assertTrue("Invalid email/password combination." in str(context.exception))

    def test_2sa_required(self):
        with vcr.use_cassette("tests/vcr_cassettes/auth_requires_2sa.yml"):
            with self.assertRaises(TwoStepAuthRequiredError) as context:
                # To re-record this HTTP request,
                # delete ./tests/vcr_cassettes/auth_requires_2sa.yml,
                # put your actual credentials in here, run the test,
                # and then replace with dummy credentials.
                authenticate(
                    "jdoe@gmail.com",
                    "password1",
                    raise_error_on_2sa=True,
                    client_id="EC5646DE-9423-11E8-BF21-14109FE0B321",
                )

            self.assertTrue(
                "Two-step/two-factor authentication is required!"
                in str(context.exception)
            )

    def test_successful_auth(self):
        with vcr.use_cassette("tests/vcr_cassettes/successful_auth.yml"):
            authenticate(
                "jdoe@gmail.com",
                "password1",
                client_id="EC5646DE-9423-11E8-BF21-14109FE0B321",
            )

    def test_password_prompt(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
            runner = CliRunner(env={
                "CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"
            })
            result = runner.invoke(
                main,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--recent",
                    "0",
                    "--no-progress-bar",
                    "-d",
                    base_dir,
                ],
                input="password1\n",
            )
            self.assertIn("DEBUG    Authenticating...", self._caplog.text)
            self.assertIn(
                "DEBUG    Looking up all photos and videos from album All Photos...",
                self._caplog.text
            )
            self.assertIn(
                "INFO     All photos have been downloaded!", self._caplog.text
            )
            assert result.exit_code == 0
