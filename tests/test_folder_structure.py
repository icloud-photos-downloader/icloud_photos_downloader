import glob
import inspect
import os
import shutil
import sys
from typing import List, Tuple
from unittest import TestCase

import pytest
from click.testing import CliRunner
from vcr import VCR

from icloudpd.base import main
from tests.helpers import (
    path_from_project_root,
    print_result_exception,
    recreate_path,
    run_icloudpd_test,
)

vcr = VCR(decode_compressed_response=True, record_mode="none")


class FolderStructureTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog: pytest.LogCaptureFixture) -> None:
        self._caplog = caplog
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")
        self.vcr_path = os.path.join(self.root_path, "vcr_cassettes")

    # This is basically a copy of the listing_recent_photos test #
    def test_default_folder_structure(self) -> None:
        """Tests if the default directory structure is constructed correctly"""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create: List[Tuple[str, str, int]] = []
        files_to_download: List[Tuple[str, str]] = []

        # Note - This test uses the same cassette as test_download_photos.py
        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos.yml",
            files_to_create,
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "5",
                "--only-print-filenames",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        assert result.exit_code == 0

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

    def test_folder_structure_none(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create: List[Tuple[str, str, int]] = []
        files_to_download: List[Tuple[str, str]] = []

        # Note - This test uses the same cassette as test_download_photos.py
        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos.yml",
            files_to_create,
            files_to_download,
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
                "--threads-num",
                "1",
            ],
        )

        assert result.exit_code == 0

        filenames = result.output.splitlines()

        self.assertEqual(len(filenames), 8)
        self.assertEqual(os.path.join(data_dir, os.path.normpath("IMG_7409.JPG")), filenames[0])
        self.assertEqual(os.path.join(data_dir, os.path.normpath("IMG_7409.MOV")), filenames[1])
        self.assertEqual(os.path.join(data_dir, os.path.normpath("IMG_7408.JPG")), filenames[2])
        self.assertEqual(os.path.join(data_dir, os.path.normpath("IMG_7408.MOV")), filenames[3])
        self.assertEqual(os.path.join(data_dir, os.path.normpath("IMG_7407.JPG")), filenames[4])
        self.assertEqual(os.path.join(data_dir, os.path.normpath("IMG_7407.MOV")), filenames[5])
        self.assertEqual(os.path.join(data_dir, os.path.normpath("IMG_7405.MOV")), filenames[6])
        self.assertEqual(os.path.join(data_dir, os.path.normpath("IMG_7404.MOV")), filenames[7])

    @pytest.mark.skipif(sys.platform == "win32", reason="local strings are not working on windows")
    def test_folder_structure_de_posix(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")
        cookie_master_path = os.path.join(self.root_path, "cookie")

        for dir in [base_dir, data_dir]:
            recreate_path(dir)

        shutil.copytree(cookie_master_path, cookie_dir)

        files_to_download: List[str] = []

        # Note - This test uses the same cassette as test_download_photos.py
        with vcr.use_cassette(os.path.join(self.vcr_path, "listing_photos.yml")):
            # Pass fixed client ID via environment variable
            runner = CliRunner(
                env={
                    "CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321",
                    "LC_ALL": "de_DE.UTF-8",
                }
            )
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
                    "--folder-structure={:%Y/%B}",
                    "--no-progress-bar",
                    "--use-os-locale",
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
                os.path.join(data_dir, os.path.normpath("2018/Juli/IMG_7409.JPG")), filenames[0]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/Juli/IMG_7409.MOV")), filenames[1]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/Juli/IMG_7408.JPG")), filenames[2]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/Juli/IMG_7408.MOV")), filenames[3]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/Juli/IMG_7407.JPG")), filenames[4]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/Juli/IMG_7407.MOV")), filenames[5]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/Juli/IMG_7405.MOV")), filenames[6]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/Juli/IMG_7404.MOV")), filenames[7]
            )

            assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_download)

        for file_name in files_to_download:
            assert os.path.exists(os.path.join(data_dir, os.path.normpath(file_name))), (
                f"File {file_name} expected, but does not exist"
            )

    def test_folder_structure_bad_format(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create: List[Tuple[str, str, int]] = []
        files_to_download: List[Tuple[str, str]] = []

        # Note - This test uses the same cassette as test_download_photos.py
        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos.yml",
            files_to_create,
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "5",
                "--only-print-filenames",
                "--folder-structure={%Y}{%Y}",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        assert result.exit_code == 2

        messages = result.output.splitlines()

        self.assertTrue("Format specified in --folder-structure is incorrect" in messages)
