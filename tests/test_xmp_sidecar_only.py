import inspect
import os
from unittest import TestCase

import pytest

from icloudpd.cli import parse
from tests.helpers import path_from_project_root, run_icloudpd_test


class XmpSidecarOnlyTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

    def test_writes_only_the_sidecar(self) -> None:
        """--xmp-sidecar-only writes the sidecar without downloading the photo (#1265)"""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        # the cassette has no download or delete requests, so any of them would fail the run
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
                "--delete-after-download",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        self.assertEqual(0, result.exit_code, result.output)

    def test_parse_implies_xmp_sidecar(self) -> None:
        _, user_configs = parse(["--username", "u", "--directory", "d", "--xmp-sidecar-only"])
        self.assertTrue(user_configs[0].xmp_sidecar_only)
        self.assertTrue(user_configs[0].xmp_sidecar)
        _, user_configs = parse(["--username", "u", "--directory", "d"])
        self.assertFalse(user_configs[0].xmp_sidecar_only)
        self.assertFalse(user_configs[0].xmp_sidecar)
