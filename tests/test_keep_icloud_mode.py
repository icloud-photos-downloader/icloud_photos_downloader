import datetime
import inspect
import os
from unittest import TestCase, mock

import pytest

from tests.helpers import path_from_project_root, run_icloudpd_test


class KeepICloudModeTestCases(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

    def test_wide_range_keep_icloud_recent_days(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [("2018/07/31", "IMG_7409.JPG")]

        with mock.patch("datetime.datetime", wraps=datetime.datetime) as dt_mock:
            # 90 days in the future
            mock_now = datetime.datetime(2018, 7, 31, tzinfo=datetime.timezone.utc)
            dt_mock.now.return_value = mock_now + datetime.timedelta(days=90)
            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos_keep_icloud_recent_days.yml",
                [],
                files_to_download,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "1",
                    "--skip-videos",
                    "--skip-live-photos",
                    "--no-progress-bar",
                    "--threads-num",
                    "1",
                    "--keep-icloud-recent-days",
                    "100",
                ],
            )

            self.assertIn("Looking up all photos...", result.output)
            self.assertIn(
                f"Downloading the first original photo to {data_dir} ...",
                result.output,
            )
            self.assertIn(
                "Skipping deletion of IMG_7409.JPG as it is within the keep_icloud_recent_days period (89 days old)",
                result.output,
            )
            self.assertIn("All photos have been downloaded", result.output)
            assert result.exit_code == 0

    def test_narrow_range_keep_icloud_recent_days(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [("2018/07/31", "IMG_7409.JPG")]

        with mock.patch("datetime.datetime", wraps=datetime.datetime) as dt_mock:
            mock_now = datetime.datetime(2018, 8, 1, tzinfo=datetime.timezone.utc)
            dt_mock.now.return_value = mock_now
            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos_keep_icloud_recent_days.yml",
                [],
                files_to_download,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "1",
                    "--skip-videos",
                    "--skip-live-photos",
                    "--no-progress-bar",
                    "--threads-num",
                    "1",
                    "--keep-icloud-recent-days",
                    "1",
                ],
            )

            self.assertIn("Looking up all photos...", result.output)
            self.assertIn(
                f"Downloading the first original photo to {data_dir} ...",
                result.output,
            )
            self.assertIn(
                "Skipping deletion of IMG_7409.JPG as it is within the keep_icloud_recent_days period (0 days old)",
                result.output,
            )
            self.assertIn("All photos have been downloaded", result.output)
            assert result.exit_code == 0

    def test_keep_icloud_recent_days_delete_all(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [("2018/07/31", "IMG_7409.JPG")]

        with mock.patch("datetime.datetime", wraps=datetime.datetime) as dt_mock:
            days_old = 10
            mock_now = datetime.datetime(2018, 7, 31, tzinfo=datetime.timezone.utc)
            dt_mock.now.return_value = mock_now + datetime.timedelta(days=days_old)
            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos_keep_icloud_recent_days.yml",
                [],
                files_to_download,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "1",
                    "--skip-videos",
                    "--skip-live-photos",
                    "--no-progress-bar",
                    "--threads-num",
                    "1",
                    "--keep-icloud-recent-days",
                    "0",
                ],
            )

            self.assertIn("Looking up all photos...", result.output)
            self.assertIn(
                f"Downloading the first original photo to {data_dir} ...",
                result.output,
            )
            self.assertIn(
                "Deleted IMG_7409.JPG in iCloud",
                result.output,
            )
            self.assertIn("All photos have been downloaded", result.output)
            assert result.exit_code == 0

    def test_keep_icloud_recent_days_1_keeps_today(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [("2018/07/31", "IMG_7409.JPG")]

        with mock.patch("datetime.datetime", wraps=datetime.datetime) as dt_mock:
            mock_now = datetime.datetime(2018, 7, 31, 23, 59, 59, tzinfo=datetime.timezone.utc)
            dt_mock.now.return_value = mock_now
            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos_keep_icloud_recent_days.yml",
                [],
                files_to_download,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "1",
                    "--skip-videos",
                    "--skip-live-photos",
                    "--no-progress-bar",
                    "--threads-num",
                    "1",
                    "--keep-icloud-recent-days",
                    "1",
                ],
            )

            self.assertIn("Looking up all photos...", result.output)
            self.assertIn(
                f"Downloading the first original photo to {data_dir} ...",
                result.output,
            )
            self.assertIn(
                "Skipping deletion of IMG_7409.JPG as it is within the keep_icloud_recent_days period (0 days old)",
                result.output,
            )
            self.assertIn("All photos have been downloaded", result.output)
            assert result.exit_code == 0

    def test_keep_icloud_recent_days_delete_existing(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2018/07/31", "IMG_7409.JPG", 1884695),
            ("2018/07/30", "IMG_7408.JPG", 1151066),
            ("2018/07/30", "IMG_7407.JPG", 656257),
        ]
        with mock.patch("datetime.datetime", wraps=datetime.datetime) as dt_mock:
            days_old = 10
            mock_now = datetime.datetime(2018, 7, 31, tzinfo=datetime.timezone.utc)
            dt_mock.now.return_value = mock_now + datetime.timedelta(days=days_old)
            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos_keep_icloud_recent_days.yml",
                files_to_create,
                [],
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "3",
                    "--skip-videos",
                    "--skip-live-photos",
                    "--no-progress-bar",
                    "--threads-num",
                    "1",
                    "--keep-icloud-recent-days",
                    "0",
                ],
            )

            self.assertIn("Looking up all photos...", result.output)
            self.assertIn(
                f"Downloading 3 original photos to {data_dir} ...",
                result.output,
            )
            self.assertIn(
                "Deleted IMG_7409.JPG in iCloud",
                result.output,
            )
            self.assertIn(
                "Deleted IMG_7408.JPG in iCloud",
                result.output,
            )
            self.assertIn(
                "Deleted IMG_7407.JPG in iCloud",
                result.output,
            )
            self.assertIn("All photos have been downloaded", result.output)
            assert result.exit_code == 0

    def test_keep_icloud_recent_days_keeps_some(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2018/07/31", "IMG_7409.JPG", 1884695),  # 0 days old, should be kept
            ("2018/07/30", "IMG_7408.JPG", 1151066),  # 1 days old, should be deleted
            ("2018/07/30", "IMG_7407.JPG", 656257),  # 1 days old, should be deleted
        ]
        with mock.patch("datetime.datetime", wraps=datetime.datetime) as dt_mock:
            days_old = 1
            mock_now = datetime.datetime(2018, 7, 31, tzinfo=datetime.timezone.utc)
            dt_mock.now.return_value = mock_now + datetime.timedelta(days=days_old)
            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos_keep_icloud_recent_days.yml",
                files_to_create,
                [],
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "3",
                    "--skip-videos",
                    "--skip-live-photos",
                    "--no-progress-bar",
                    "--threads-num",
                    "1",
                    "--keep-icloud-recent-days",
                    "1",
                ],
            )

            self.assertIn("Looking up all photos...", result.output)
            self.assertIn(
                f"Downloading 3 original photos to {data_dir} ...",
                result.output,
            )
            self.assertNotIn(
                "Deleted IMG_7409.JPG in iCloud",
                result.output,
            )
            self.assertIn(
                "Deleted IMG_7408.JPG in iCloud",
                result.output,
            )
            self.assertIn(
                "Deleted IMG_7407.JPG in iCloud",
                result.output,
            )
            self.assertIn("All photos have been downloaded", result.output)
            assert result.exit_code == 0

    def test_keep_icloud_recent_days_delete_existing_dry_run(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [("2018/07/31", "IMG_7409.JPG", 1884695)]

        with mock.patch("datetime.datetime", wraps=datetime.datetime) as dt_mock:
            days_old = 10
            mock_now = datetime.datetime(2018, 7, 31, tzinfo=datetime.timezone.utc)
            dt_mock.now.return_value = mock_now + datetime.timedelta(days=days_old)
            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos_keep_icloud_recent_days.yml",
                files_to_create,
                [],
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "1",
                    "--skip-videos",
                    "--skip-live-photos",
                    "--no-progress-bar",
                    "--threads-num",
                    "1",
                    "--keep-icloud-recent-days",
                    "0",
                    "--dry-run",
                ],
            )

            self.assertIn("Looking up all photos...", result.output)
            self.assertIn(
                f"Downloading the first original photo to {data_dir} ...",
                result.output,
            )
            self.assertIn(
                "[DRY RUN] Would delete IMG_7409.JPG in iCloud library PrimarySync",
                result.output,
            )
            self.assertIn("All photos have been downloaded", result.output)
            assert result.exit_code == 0

    def test_keep_icloud_recent_days_with_skip_videos(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2018/07/31", "IMG_7409.JPG", 1884695),  # 0 days old, should be kept
            ("2018/07/30", "IMG_7408.JPG", 1151066),  # 1 days old, should be deleted
            ("2018/07/30", "IMG_7407.JPG", 656257),  # 1 days old, should be deleted
        ]
        with mock.patch("datetime.datetime", side_effect=datetime.datetime) as dt_mock:
            days_old = 1
            mock_now = datetime.datetime(2018, 7, 31, tzinfo=datetime.timezone.utc)
            dt_mock.now.return_value = mock_now + datetime.timedelta(days=days_old)
            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos_keep_icloud_recent_days.yml",
                files_to_create,
                [],
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "4",
                    "--skip-videos",
                    "--skip-live-photos",
                    "--no-progress-bar",
                    "--threads-num",
                    "1",
                    "--keep-icloud-recent-days",
                    "1",
                ],
            )

            self.assertIn("Looking up all photos...", result.output)
            self.assertIn(
                f"Downloading 4 original photos to {data_dir} ...",
                result.output,
            )
            self.assertNotIn(
                "Deleted IMG_7409.JPG in iCloud",
                result.output,
            )
            self.assertIn(
                "Deleted IMG_7408.JPG in iCloud",
                result.output,
            )
            self.assertIn(
                "Deleted IMG_7407.JPG in iCloud",
                result.output,
            )
            self.assertNotIn(
                "Deleted IMG_7405.MOV in iCloud",
                result.output,
            )
            self.assertIn("All photos have been downloaded", result.output)
            assert result.exit_code == 0
