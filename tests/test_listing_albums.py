from unittest import TestCase
import pytest
from vcr import VCR
import os
import shutil
import click
from click.testing import CliRunner
import json
import mock
from icloudpd.base import main
from tests.helpers import path_from_project_root, print_result_exception, recreate_path
import inspect
import glob

vcr = VCR(decode_compressed_response=True)

class ListingAlbumsTestCase(TestCase):

    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")
        self.vcr_path = os.path.join(self.root_path, "vcr_cassettes")

    def test_listing_albums(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)

        with vcr.use_cassette(os.path.join(self.vcr_path, "listing_albums.yml")):
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
                    "--cookie-directory",
                    cookie_dir,
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

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 0
