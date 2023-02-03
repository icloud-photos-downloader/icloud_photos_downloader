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
import inspect
import glob

vcr = VCR(decode_compressed_response=True)

class ListingAlbumsTestCase(TestCase):

    def test_listing_albums(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        with vcr.use_cassette("tests/vcr_cassettes/listing_albums.yml"):
            # Pass fixed client ID via environment variable
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
                    "--list-albums",
                    "--no-progress-bar",
                ],
            )

            print_result_exception(result)
            albums = result.output.splitlines()

            self.assertIn("All Photos", albums)
            self.assertIn("WhatsApp", albums)
            self.assertIn("Time-lapse", albums)
            self.assertIn("Recently Deleted", albums)
            self.assertIn("Favorites", albums)

            assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 0
