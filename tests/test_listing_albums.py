from unittest import TestCase
from vcr import VCR
import os
import shutil
import click
from click.testing import CliRunner
import json
import mock
from icloudpd.base import main
from tests.helpers.print_result_exception import print_result_exception

vcr = VCR(decode_compressed_response=True)

class ListingAlbumsTestCase(TestCase):

    def test_listing_albums(self):
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
                    "--list-albums",
                    "--no-progress-bar",
                    "-d",
                    "tests/fixtures/Photos",
                ],
            )

            print_result_exception(result)
            albums = result.output.splitlines()

            self.assertEqual(len(albums), 40)
            self.assertEqual(
                "All Photos", albums[1]
            )
            self.assertEqual(
                "Time-lapse", albums[2]
            )
            self.assertEqual(
                "WhatsApp", albums[40]
            )

            assert result.exit_code == 0