"""icloudpd uses the local time zone for date folders and --skip-created-*; the rest of the
suite runs in UTC (see conftest.py), these tests switch to other zones on purpose."""

import inspect
import os
import time
from contextlib import contextmanager
from typing import Iterator
from unittest import TestCase

import pytest
import tzlocal

from tests.helpers import path_from_project_root, run_icloudpd_test


@contextmanager
def local_time_zone(name: str) -> Iterator[None]:
    previous = os.environ.get("TZ")
    os.environ["TZ"] = name
    if hasattr(time, "tzset"):
        time.tzset()
    tzlocal.reload_localzone()
    try:
        yield
    finally:
        if previous is None:
            del os.environ["TZ"]
        else:
            os.environ["TZ"] = previous
        if hasattr(time, "tzset"):
            time.tzset()
        tzlocal.reload_localzone()


# In listing_photos.yml, IMG_7409 was taken 2018-07-31 07:22 UTC and IMG_7407 2018-07-30 11:44 UTC
class LocalTimeZoneTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

    def list_photos(self, time_zone: str, extra_params: list[str]) -> list[str]:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[1][3])
        with local_time_zone(time_zone):
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
                    "--skip-videos",
                    "--skip-live-photos",
                    "--only-print-filenames",
                    "--no-progress-bar",
                    "--threads-num",
                    "1",
                    *extra_params,
                ],
            )
        self.assertEqual(result.exit_code, 0, "exit code")
        return [
            os.path.relpath(line, data_dir).replace(os.sep, "/")
            for line in result.output.splitlines()
        ]

    def test_date_folders_use_local_date_west(self) -> None:
        """At UTC-12, IMG_7409 was taken on July 30 local time"""
        filenames = self.list_photos("Etc/GMT+12", [])

        self.assertIn("2018/07/30/IMG_7409.JPG", filenames)
        self.assertIn("2018/07/29/IMG_7407.JPG", filenames)

    def test_date_folders_use_local_date_east(self) -> None:
        """At UTC+14, IMG_7407 was taken on July 31 local time"""
        filenames = self.list_photos("Pacific/Kiritimati", [])

        self.assertIn("2018/07/31/IMG_7409.JPG", filenames)
        self.assertIn("2018/07/31/IMG_7407.JPG", filenames)

    def test_skip_created_before_is_local_midnight(self) -> None:
        """2018-07-31 means midnight local time: 2018-07-31 12:00 UTC at UTC-12, after IMG_7409"""
        filenames = self.list_photos("Etc/GMT+12", ["--skip-created-before", "2018-07-31"])

        self.assertEqual([], filenames)

    def test_skip_created_after_is_local_midnight(self) -> None:
        """2018-07-31 means midnight local time: 2018-07-30 10:00 UTC at UTC+14, before IMG_7407"""
        filenames = self.list_photos("Pacific/Kiritimati", ["--skip-created-after", "2018-07-31"])

        self.assertEqual([], filenames)
