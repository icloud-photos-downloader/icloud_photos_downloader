import datetime
import inspect
import os
from types import SimpleNamespace
from typing import Any, List, Tuple
from unittest import TestCase, mock

import pytest

from icloudpd.base import keep_icloud_recent_days_warnings
from pyicloud_ipd.asset_version import AssetVersion
from pyicloud_ipd.services.photos import PhotoAsset
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize
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
            mock_now = datetime.datetime(2018, 7, 31, tzinfo=datetime.UTC)
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

            self.assertIn(
                "--keep-icloud-recent-days is used with --recent 1: only the first 1 assets are checked, older assets are not deleted from iCloud",
                result.output,
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
            mock_now = datetime.datetime(2018, 8, 1, tzinfo=datetime.UTC)
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
            mock_now = datetime.datetime(2018, 7, 31, tzinfo=datetime.UTC)
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
            mock_now = datetime.datetime(2018, 7, 31, 23, 59, 59, tzinfo=datetime.UTC)
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
            mock_now = datetime.datetime(2018, 7, 31, tzinfo=datetime.UTC)
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
            mock_now = datetime.datetime(2018, 7, 31, tzinfo=datetime.UTC)
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
            mock_now = datetime.datetime(2018, 7, 31, tzinfo=datetime.UTC)
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
            mock_now = datetime.datetime(2018, 7, 31, tzinfo=datetime.UTC)
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

    def _run_keep_recent_days_0(
        self,
        base_dir: str,
        files_to_create: List[Tuple[str, str, int]],
        extra_params: List[str],
        files_to_download: List[Tuple[str, str]] | None = None,
        skip_live_photos: bool = True,
    ) -> Tuple[str, Any]:
        with mock.patch("datetime.datetime", wraps=datetime.datetime) as dt_mock:
            mock_now = datetime.datetime(2018, 7, 31, tzinfo=datetime.UTC)
            dt_mock.now.return_value = mock_now + datetime.timedelta(days=10)
            return run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos_keep_icloud_recent_days.yml",
                files_to_create,
                files_to_download or [],
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "3",
                    "--skip-videos",
                    *(["--skip-live-photos"] if skip_live_photos else []),
                    "--no-progress-bar",
                    "--threads-num",
                    "1",
                    "--keep-icloud-recent-days",
                    "0",
                    *extra_params,
                ],
            )

    def test_keep_icloud_recent_days_keeps_photos_that_failed_to_download(self) -> None:
        """A photo is only deleted from iCloud when it is present locally (#1312)"""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        with mock.patch("icloudpd.download.download_media", return_value=False):
            _, result = self._run_keep_recent_days_0(base_dir, [], [])

        self.assertNotIn("in iCloud", result.output)
        self.assertEqual(result.exit_code, 0)

    def test_keep_icloud_recent_days_deletes_only_photos_present_locally(self) -> None:
        """Already downloaded photos are still deleted; ones that failed to download are kept"""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        with mock.patch("icloudpd.download.download_media", return_value=False):
            _, result = self._run_keep_recent_days_0(
                base_dir, [("2018/07/31", "IMG_7409.JPG", 1884695)], []
            )

        self.assertIn("Deleted IMG_7409.JPG in iCloud", result.output)
        self.assertNotIn("Deleted IMG_7408.JPG in iCloud", result.output)
        self.assertNotIn("Deleted IMG_7407.JPG in iCloud", result.output)
        self.assertIn(
            "Not deleting IMG_7408.JPG from iCloud: it is not present locally", result.output
        )
        self.assertEqual(result.exit_code, 0)

    def test_keep_icloud_recent_days_does_not_delete_when_only_printing_filenames(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        # logging is off in this mode, so check the delete call itself
        with mock.patch("icloudpd.base.delete_photo") as delete_photo:
            _, result = self._run_keep_recent_days_0(base_dir, [], ["--only-print-filenames"])

        delete_photo.assert_not_called()
        self.assertEqual(result.exit_code, 0)

    def test_keep_icloud_recent_days_keeps_photos_without_the_forced_size(self) -> None:
        """--force-size skips photos without that size; nothing is on disk, so keep them"""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        with (
            mock.patch.object(PhotoAsset, "versions", new_callable=mock.PropertyMock) as versions,
            mock.patch("icloudpd.base.delete_photo") as delete_photo,
        ):
            versions.return_value = {
                AssetVersionSize.ORIGINAL: AssetVersion(
                    1, "https://example.com", "public.jpeg", "x"
                )
            }
            _, result = self._run_keep_recent_days_0(
                base_dir, [], ["--size", "medium", "--force-size"]
            )

        self.assertIn("medium size does not exist for IMG_7409.JPG. Skipping...", result.output)
        delete_photo.assert_not_called()
        self.assertEqual(result.exit_code, 0)

    def test_keep_icloud_recent_days_keeps_live_photo_without_the_video_size(self) -> None:
        """The still is on disk but the live photo video size is missing: keep it in iCloud"""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        def fake_download(*args: Any) -> bool:
            path = args[4]
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "wb").close()
            return True

        with (
            mock.patch.object(PhotoAsset, "versions", new_callable=mock.PropertyMock) as versions,
            mock.patch("icloudpd.download.download_media", side_effect=fake_download),
            mock.patch("icloudpd.base.delete_photo") as delete_photo,
        ):
            versions.return_value = {
                AssetVersionSize.ORIGINAL: AssetVersion(
                    1, "https://example.com", "public.jpeg", "x"
                ),
                LivePhotoVersionSize.ORIGINAL: AssetVersion(
                    2, "https://example.com", "com.apple.quicktime-movie", "y"
                ),
            }
            _, result = self._run_keep_recent_days_0(
                base_dir,
                [],
                ["--live-photo-size", "medium"],
                files_to_download=[
                    ("2018/07/31", "IMG_7409.JPG"),
                    ("2018/07/30", "IMG_7408.JPG"),
                    ("2018/07/30", "IMG_7407.JPG"),
                ],
                skip_live_photos=False,
            )

        delete_photo.assert_not_called()
        self.assertEqual(result.exit_code, 0)


class KeepICloudRecentDaysWarningsTestCase(TestCase):
    def warnings(self, keep: int | None, recent: int | None, until_found: int | None) -> List[str]:
        config = SimpleNamespace(
            keep_icloud_recent_days=keep, recent=recent, until_found=until_found
        )
        return keep_icloud_recent_days_warnings(config)  # type: ignore[arg-type]

    def test_no_warning_without_keep_icloud_recent_days(self) -> None:
        self.assertEqual([], self.warnings(None, 10, 5))

    def test_no_warning_without_recent_or_until_found(self) -> None:
        self.assertEqual([], self.warnings(0, None, None))

    def test_warns_for_recent_and_until_found(self) -> None:
        self.assertEqual(
            [
                "--keep-icloud-recent-days is used with --recent 10: only the first 10 assets are checked, older assets are not deleted from iCloud",
                "--keep-icloud-recent-days is used with --until-found 5: assets after the point where the run stops are not deleted from iCloud",
            ],
            self.warnings(0, 10, 5),
        )
