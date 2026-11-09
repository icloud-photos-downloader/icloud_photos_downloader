import inspect
import os
from typing import List
from unittest import TestCase

import pytest

from icloudpd.cli import parse
from tests.helpers import path_from_project_root, run_icloudpd_test, run_main


class XmpSidecarOnlyTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

    def test_writes_only_the_sidecar(self) -> None:
        """--xmp-sidecar-only writes the sidecar without downloading the photo (#1265)"""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        _, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos.yml",
            [],
            [("2018/07/31", "IMG_7409.JPG.xmp")],
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "1",
                "--xmp-sidecar-only",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        self.assertEqual(0, result.exit_code, result.output)

    def test_adds_sidecar_next_to_existing_photo(self) -> None:
        """An existing photo file is left alone and only gets its sidecar"""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos.yml",
            [("2018/07/31", "IMG_7409.JPG", 1884695)],
            [("2018/07/31", "IMG_7409.JPG.xmp")],
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "1",
                "--xmp-sidecar-only",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        self.assertEqual(0, result.exit_code, result.output)
        self.assertEqual(
            1884695,
            os.path.getsize(os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409.JPG"))),
        )

    def test_rejects_options_that_delete_or_need_media(self) -> None:
        for extra in [
            ["--delete-after-download"],
            ["--keep-icloud-recent-days", "0"],
            ["--prune-orphans", "--library", "SharedSync-0"],
            ["--until-found", "3"],
            ["--only-print-filenames"],
        ]:
            with self.subTest(extra=extra):
                params: List[str] = [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "-d",
                    "unused",
                    "--xmp-sidecar-only",
                    *extra,
                ]
                result = run_main(params)
                self.assertEqual(2, result.exit_code, result.output)
                self.assertIn("--xmp-sidecar-only cannot be combined", result.output)

    def test_parse_implies_xmp_sidecar(self) -> None:
        _, user_configs = parse(["--username", "u", "--directory", "d", "--xmp-sidecar-only"])
        self.assertTrue(user_configs[0].xmp_sidecar_only)
        self.assertTrue(user_configs[0].xmp_sidecar)
        _, user_configs = parse(["--username", "u", "--directory", "d"])
        self.assertFalse(user_configs[0].xmp_sidecar_only)
        self.assertFalse(user_configs[0].xmp_sidecar)
