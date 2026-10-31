"""Regression test for issue #1355."""

import inspect
import os
from unittest import TestCase

import pytest

from tests.helpers import path_from_project_root, run_icloudpd_test


class Issue1355XmpOnlyPrintFilenamesTest(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

    def test_only_print_filenames_skips_xmp_sidecar(self) -> None:
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
                "jdoe" + "@gmail.com",
                "--password",
                "password1",
                "--recent",
                "1",
                "--xmp-sidecar",
                "--only-print-filenames",
                "--skip-live-photos",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        assert result.exit_code == 0
        self.assertIn("IMG_7409.JPG", result.output)
        self.assertEqual([], os.listdir(data_dir))
