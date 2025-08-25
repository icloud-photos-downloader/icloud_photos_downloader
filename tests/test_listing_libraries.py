import inspect
import os
from unittest import TestCase

import pytest

from tests.helpers import (
    path_from_project_root,
    run_icloudpd_test,
)


class ListingLibraryTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

    def test_listing_library(self) -> None:
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
                "--list-libraries",
                "--no-progress-bar",
            ],
        )
        self.assertEqual(result.exit_code, 0, "exit code")
        albums = result.output.splitlines()

        self.assertIn("PrimarySync", albums)
        self.assertIn("SharedSync-00000000-1111-2222-3333-444444444444", albums)

    def test_listing_library_error(self) -> None:
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
                "--library",
                "doesnotexist",
                "--no-progress-bar",
            ],
        )
        self.assertEqual(result.exit_code, 1, "exit code")
        self.assertIn(
            "Unknown library: doesnotexist",
            result.output,
        )
