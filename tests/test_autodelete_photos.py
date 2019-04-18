from unittest import TestCase
from vcr import VCR
import os
import shutil
import click
import pytest
import mock
from click.testing import CliRunner
import piexif
from icloudpd.base import main
import icloudpd.exif_datetime

vcr = VCR(decode_compressed_response=True, record_mode="new_episodes")


class AutodeletePhotosTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    def test_autodelete_photos(self):
        if os.path.exists("tests/fixtures/Photos"):
            shutil.rmtree("tests/fixtures/Photos")
        os.makedirs("tests/fixtures/Photos")

        # create some empty files that should be deleted
        os.makedirs("tests/fixtures/Photos/2018/07/30/")
        open("tests/fixtures/Photos/2018/07/30/IMG_7406.MOV", "a").close()
        os.makedirs("tests/fixtures/Photos/2018/07/26/")
        open("tests/fixtures/Photos/2018/07/26/IMG_7383.PNG", "a").close()
        os.makedirs("tests/fixtures/Photos/2018/07/12/")
        open("tests/fixtures/Photos/2018/07/12/IMG_7190.JPG", "a").close()
        open("tests/fixtures/Photos/2018/07/12/IMG_7190-medium.JPG", "a").close()

        # Should not be deleted
        open("tests/fixtures/Photos/2018/07/30/IMG_7407.JPG", "a").close()
        open("tests/fixtures/Photos/2018/07/30/IMG_7407-original.JPG", "a").close()

        with vcr.use_cassette("tests/vcr_cassettes/autodelete_photos.yml"):
            # Pass fixed client ID via environment variable
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
                    "--skip-videos",
                    "--auto-delete",
                    "-d",
                    "tests/fixtures/Photos",
                ],
            )
            self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
            self.assertIn(
                "INFO     Downloading 0 original photos to tests/fixtures/Photos/ ...",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     All photos have been downloaded!", self._caplog.text
            )
            self.assertIn(
                "INFO     Deleting any files found in 'Recently Deleted'...",
                self._caplog.text,
            )

            self.assertIn(
                "INFO     Deleting any files found in 'Recently Deleted'...",
                self._caplog.text,
            )

            self.assertIn(
                "INFO     Deleting tests/fixtures/Photos/2018/07/30/IMG_7406.MOV",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     Deleting tests/fixtures/Photos/2018/07/26/IMG_7383.PNG",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     Deleting tests/fixtures/Photos/2018/07/12/IMG_7190.JPG",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     Deleting tests/fixtures/Photos/2018/07/12/IMG_7190-medium.JPG",
                self._caplog.text,
            )

            self.assertNotIn("IMG_7407.JPG", self._caplog.text)
            self.assertNotIn("IMG_7407-original.JPG", self._caplog.text)

            assert result.exit_code == 0
