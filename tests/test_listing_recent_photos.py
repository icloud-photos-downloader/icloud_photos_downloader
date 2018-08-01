from unittest import TestCase
from vcr import VCR
import os
import shutil
import click
from click.testing import CliRunner
from icloudpd.base import main

vcr = VCR(decode_compressed_response=True)


class ListingRecentPhotosTestCase(TestCase):
    def test_listing_recent_photos(self):
        if os.path.exists("tests/fixtures/Photos"):
            shutil.rmtree("tests/fixtures/Photos")
        os.makedirs("tests/fixtures/Photos")

        # Note - This test uses the same cassette as test_download_photos.py
        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
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
                    "5",
                    "--only-print-filenames",
                    "--no-progress-bar",
                    "tests/fixtures/Photos",
                ],
            )
            filenames = result.output.splitlines()
            self.assertEqual(len(filenames), 5)
            self.assertEqual(
                "tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG", filenames[0]
            )
            self.assertEqual(
                "tests/fixtures/Photos/2018/07/30/IMG_7408-original.JPG", filenames[1]
            )
            self.assertEqual(
                "tests/fixtures/Photos/2018/07/30/IMG_7407-original.JPG", filenames[2]
            )
            self.assertEqual(
                "tests/fixtures/Photos/2018/07/30/IMG_7405-original.MOV", filenames[3]
            )
            self.assertEqual(
                "tests/fixtures/Photos/2018/07/30/IMG_7404-original.MOV", filenames[4]
            )

            assert result.exit_code == 0
