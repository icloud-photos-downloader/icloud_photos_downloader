"""Test for issue #1220: --only-print-filenames downloads live photo video files during deduplication

https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/1220

Bug Description:
- When using --only-print-filenames, no files should be downloaded
- However, during live photo deduplication, the MOV file gets downloaded
- This happens because the deduplication logic changes the filename and resets file_exists to False
- The download then proceeds despite only_print_filenames being True
"""

import inspect
import os
from typing import List, Tuple
from unittest import TestCase

import pytest

from tests.helpers import (
    path_from_project_root,
    run_icloudpd_test,
)


class Issue1220OnlyPrintFilenamesDeduplicationBugTest(TestCase):
    """Test case to reproduce the bug where --only-print-filenames downloads files during deduplication"""

    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

    def test_only_print_filenames_should_not_download_during_deduplication(self) -> None:
        """
        Test that --only-print-filenames works correctly with deduplication.

        This test reproduces issue #1220 and verifies the fix.
        """
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        # Create files that will trigger deduplication scenarios
        # We create files with different sizes than what the mock will return
        files_to_create: List[Tuple[str, str, int]] = [
            (
                os.path.join("2018", "07", "31"),
                "IMG_7409.MOV",
                100,
            ),  # Small size to trigger deduplication
        ]

        # With --only-print-filenames, NO files should be downloaded
        files_to_download: List[Tuple[str, str]] = []

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "download_live_photos.yml",  # Use a VCR cassette that has live photos
            files_to_create,
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "3",
                "--only-print-filenames",  # This should prevent ALL downloads
                "--file-match-policy",
                "name-size-dedup-with-suffix",  # Enable deduplication
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        # The command should succeed
        assert result.exit_code == 0

        # Filenames should be printed to stdout
        filenames = result.output.splitlines()
        self.assertGreater(len(filenames), 0, "Some filenames should be printed")

        # Check that the directory contains only the files we created (no downloads)
        actual_files = []
        for root, _dirs, files in os.walk(data_dir):
            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), data_dir)
                actual_files.append(rel_path)

        # Only the file we created should exist (no downloads should have happened)
        expected_files = [os.path.join("2018", "07", "31", "IMG_7409.MOV")]

        # After the fix, this should pass
        self.assertEqual(
            sorted(actual_files),
            sorted(expected_files),
            "Only pre-created files should exist. No files should be downloaded "
            "when --only-print-filenames is used, even during deduplication.",
        )
