"""A listing that ends before the count iCloud reported is not a complete download (#1390)

The photo listing stops at the first empty page. When iCloud returned an empty page too
early, the run still ended with "All photos and videos have been downloaded". The run now
compares the number of listed items with the count iCloud gave for the album.
"""

import inspect
import os
from typing import List
from unittest import TestCase, mock

from pyicloud_ipd.services.photos import PhotoAlbum
from tests.helpers import path_from_project_root, run_icloudpd_test

# the shared library in listing_photos.yml holds one asset, and iCloud reports a count of 1
SHARED_LIBRARY = "SharedSync-00000000-1111-2222-3333-444444444444"


class IncompleteListingTestCase(TestCase):
    def setUp(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

    def run_shared_library(self, test_name: str, extra: List[str]) -> tuple[int, str]:
        _, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            os.path.join(self.fixtures_path, test_name),
            "listing_photos.yml",
            [],
            [],
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--library",
                SHARED_LIBRARY,
                "--dry-run",
                "--no-progress-bar",
                *extra,
            ],
        )
        return result.exit_code, result.output

    def test_complete_listing_is_reported_as_downloaded(self) -> None:
        exit_code, output = self.run_shared_library(inspect.stack()[0][3], [])
        self.assertEqual(0, exit_code)
        self.assertIn("All photos and videos have been downloaded", output)
        self.assertNotIn("iCloud listed only", output)

    def test_listing_that_ends_early_is_an_error(self) -> None:
        with mock.patch.object(PhotoAlbum, "__len__", return_value=3):
            exit_code, output = self.run_shared_library(inspect.stack()[0][3], [])
        self.assertEqual(1, exit_code)
        self.assertIn(
            "iCloud listed only 1 of 3 items in the library; the listing ended early, so not everything "
            "was downloaded. Run icloudpd again to download the rest",
            output,
        )
        self.assertNotIn("have been downloaded", output)

    def test_recent_lists_fewer_on_purpose(self) -> None:
        with mock.patch.object(PhotoAlbum, "__len__", return_value=3):
            exit_code, output = self.run_shared_library(inspect.stack()[0][3], ["--recent", "1"])
        self.assertEqual(0, exit_code)
        self.assertNotIn("iCloud listed only", output)
