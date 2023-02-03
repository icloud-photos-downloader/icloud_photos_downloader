from unittest import TestCase
import os
from os.path import normpath
import shutil
from click.testing import CliRunner
from vcr import VCR
from icloudpd.base import main
from tests.helpers.print_result_exception import print_result_exception
import inspect
import glob

vcr = VCR(decode_compressed_response=True)

class FolderStructureTestCase(TestCase):

    # This is basically a copy of the listing_recent_photos test #
    def test_default_folder_structure(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        ### Tests if the default directory structure is constructed correctly ###
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        files_to_download = [
        ]

        # Note - This test uses the same cassette as test_download_photos.py
        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
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
                    base_dir,
                ],
            )
            print_result_exception(result)
            filenames = result.output.splitlines()

            self.assertEqual(len(filenames), 8)
            self.assertEqual(
                os.path.join(base_dir, os.path.normpath("2018/07/31/IMG_7409.JPG")), filenames[0]
            )
            self.assertEqual(
                os.path.join(base_dir, os.path.normpath("2018/07/31/IMG_7409.MOV")), filenames[1]
            )
            self.assertEqual(
                os.path.join(base_dir, os.path.normpath("2018/07/30/IMG_7408.JPG")), filenames[2]
            )
            self.assertEqual(
                os.path.join(base_dir, os.path.normpath("2018/07/30/IMG_7408.MOV")), filenames[3]
            )
            self.assertEqual(
                os.path.join(base_dir, os.path.normpath("2018/07/30/IMG_7407.JPG")), filenames[4]
            )
            self.assertEqual(
                os.path.join(base_dir, os.path.normpath("2018/07/30/IMG_7407.MOV")), filenames[5]
            )
            self.assertEqual(
                os.path.join(base_dir, os.path.normpath("2018/07/30/IMG_7405.MOV")), filenames[6]
            )
            self.assertEqual(
                os.path.join(base_dir, os.path.normpath("2018/07/30/IMG_7404.MOV")), filenames[7]
            )

            assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_download)

        for file_name in files_to_download:
            assert os.path.exists(os.path.join(base_dir, os.path.normpath(file_name))), f"File {file_name} expected, but does not exist"


    def test_folder_structure_none(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        files_to_download = []

        # Note - This test uses the same cassette as test_download_photos.py
        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
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
                    base_dir,
                ],
            )
            print_result_exception(result)
            filenames = result.output.splitlines()

            self.assertEqual(len(filenames), 8)
            self.assertEqual(
                os.path.join(base_dir, os.path.normpath("IMG_7409.JPG")), filenames[0]
            )
            self.assertEqual(
                os.path.join(base_dir, os.path.normpath("IMG_7409.MOV")), filenames[1]
            )
            self.assertEqual(
                os.path.join(base_dir, os.path.normpath("IMG_7408.JPG")), filenames[2]
            )
            self.assertEqual(
                os.path.join(base_dir, os.path.normpath("IMG_7408.MOV")), filenames[3]
            )
            self.assertEqual(
                os.path.join(base_dir, os.path.normpath("IMG_7407.JPG")), filenames[4]
            )
            self.assertEqual(
                os.path.join(base_dir, os.path.normpath("IMG_7407.MOV")), filenames[5]
            )
            self.assertEqual(
                os.path.join(base_dir, os.path.normpath("IMG_7405.MOV")), filenames[6]
            )
            self.assertEqual(
                os.path.join(base_dir, os.path.normpath("IMG_7404.MOV")), filenames[7]
            )

            assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_download)

        for file_name in files_to_download:
            assert os.path.exists(os.path.join(base_dir, os.path.normpath(file_name))), f"File {file_name} expected, but does not exist"

