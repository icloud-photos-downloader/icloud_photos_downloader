import inspect
import os
import sys
from typing import List, Tuple
from unittest import TestCase

import pytest

from tests.helpers import (
    path_from_project_root,
    run_icloudpd_test,
)


class FolderStructureTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

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

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos.yml",
            [],
            [],
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
            ],
            {
                "LC_ALL": "de_DE.UTF-8",
            },
        )
        self.assertEqual(0, result.exit_code, "exit code")

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

        # Check if the error message about folder structure format is present
        found_error = any(
            "Format" in msg and "specified in --folder-structure is incorrect" in msg
            for msg in messages
        )
        self.assertTrue(found_error)
