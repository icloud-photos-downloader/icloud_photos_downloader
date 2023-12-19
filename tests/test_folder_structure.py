from unittest import TestCase
import os
from os.path import normpath
import shutil
from click.testing import CliRunner
import pytest
from vcr import VCR
from icloudpd.base import main
from tests.helpers import path_from_project_root, print_result_exception, recreate_path
import inspect
import glob

vcr = VCR(decode_compressed_response=True)

class FolderStructureTestCase(TestCase):

    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")
        self.vcr_path = os.path.join(self.root_path, "vcr_cassettes")

    # This is basically a copy of the listing_recent_photos test #
    def test_default_folder_structure(self):
        ### Tests if the default directory structure is constructed correctly ###
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)

        files_to_download = [
        ]

        # Note - This test uses the same cassette as test_download_photos.py
        with vcr.use_cassette(os.path.join(self.vcr_path, "listing_photos.yml")):
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
                    "--recent",
                    "5",
                    "--only-print-filenames",
                    "--no-progress-bar",
                    "-d",
                    data_dir,
                    "--cookie-directory",
                    cookie_dir,
                ],
            )
            print_result_exception(result)
            filenames = result.output.splitlines()

            self.assertEqual(len(filenames), 8)
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409.JPG")), filenames[0]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409.MOV")), filenames[1]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7408.JPG")), filenames[2]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7408.MOV")), filenames[3]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7407.JPG")), filenames[4]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7407.MOV")), filenames[5]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7405.MOV")), filenames[6]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7404.MOV")), filenames[7]
            )

            assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_download)

        for file_name in files_to_download:
            assert os.path.exists(os.path.join(data_dir, os.path.normpath(file_name))), f"File {file_name} expected, but does not exist"


    def test_folder_structure_none(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)

        files_to_download = []

        # Note - This test uses the same cassette as test_download_photos.py
        with vcr.use_cassette(os.path.join(self.vcr_path, "listing_photos.yml")):
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
                    "--recent",
                    "5",
                    "--only-print-filenames",
                    "--folder-structure=none",
                    "--no-progress-bar",
                    "-d",
                    data_dir,
                    "--cookie-directory",
                    cookie_dir,
                ],
            )
            print_result_exception(result)
            filenames = result.output.splitlines()

            self.assertEqual(len(filenames), 8)
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("IMG_7409.JPG")), filenames[0]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("IMG_7409.MOV")), filenames[1]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("IMG_7408.JPG")), filenames[2]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("IMG_7408.MOV")), filenames[3]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("IMG_7407.JPG")), filenames[4]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("IMG_7407.MOV")), filenames[5]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("IMG_7405.MOV")), filenames[6]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("IMG_7404.MOV")), filenames[7]
            )

            assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_download)

        for file_name in files_to_download:
            assert os.path.exists(os.path.join(data_dir, os.path.normpath(file_name))), f"File {file_name} expected, but does not exist"

