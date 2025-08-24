import inspect
import os
from unittest import TestCase

import pytest

from tests.helpers import (
    path_from_project_root,
    run_icloudpd_test,
)


class ListingAlbumsTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

    def test_listing_albums(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        _, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_albums.yml",
            [],
            [],
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--list-albums",
                "--no-progress-bar",
            ],
        )
        albums = result.output.splitlines()

        self.assertIn("WhatsApp", albums)
        self.assertIn("Time-lapse", albums)
        self.assertIn("Recently Deleted", albums)
        self.assertIn("Favorites", albums)

        self.assertEqual(result.exit_code, 0, "exit code")
