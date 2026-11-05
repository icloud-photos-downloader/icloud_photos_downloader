import datetime
import inspect
import os
from types import SimpleNamespace
from typing import Any, List, Tuple
from unittest import TestCase, mock

import pytest

from icloudpd.base import keep_icloud_recent_days_warnings
from pyicloud_ipd.asset_version import AssetVersion
from pyicloud_ipd.exceptions import PyiCloudAPIResponseException
from pyicloud_ipd.services.photos import PhotoAsset
from pyicloud_ipd.session import PyiCloudSession
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize
from tests.helpers import path_from_project_root, run_icloudpd_test

# the first three assets in the cassette are Live Photos; with their videos (.MOV, sizes from
# resOriginalVidComplRes) on disk they count as present locally
IMG_7409 = [("2018/07/31", "IMG_7409.JPG", 1884695), ("2018/07/31", "IMG_7409.MOV", 3294075)]
IMG_7408 = [("2018/07/30", "IMG_7408.JPG", 1151066), ("2018/07/30", "IMG_7408.MOV", 1606512)]
IMG_7407 = [("2018/07/30", "IMG_7407.JPG", 656257), ("2018/07/30", "IMG_7407.MOV", 2910572)]
LIVE_PHOTOS_ON_DISK = IMG_7409 + IMG_7408 + IMG_7407


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

        files_to_create = [("2018/07/31", "IMG_7409.MOV", 3294075)]
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
                files_to_create,
                files_to_download,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "1",
                    "--skip-videos",
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

    def test_keep_icloud_recent_days_keeps_asset_without_date(self) -> None:
        """An asset without a creation date would count as taken in 1970, and be deleted"""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        # without a date the asset goes into the 1970/01/01 folder
        files_to_download = [("1970/01/01", "IMG_7409.JPG")]

        original_init = PhotoAsset.__init__

        def init_without_asset_date(
            self: PhotoAsset, master_record: Any, asset_record: Any
        ) -> None:
            original_init(self, master_record, asset_record)
            self._asset_record["fields"].pop("assetDate", None)

        with (
            mock.patch("datetime.datetime", wraps=datetime.datetime) as dt_mock,
            mock.patch.object(PhotoAsset, "__init__", init_without_asset_date),
        ):
            dt_mock.now.return_value = datetime.datetime(2018, 8, 10, tzinfo=datetime.UTC)
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
                    "30",
                ],
            )

            self.assertNotIn("Deleted IMG_7409.JPG in iCloud", result.output)
            self.assertIn(
                "Not deleting IMG_7409.JPG from iCloud: it has no creation date", result.output
            )
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

        files_to_create = LIVE_PHOTOS_ON_DISK
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

        files_to_create = (
            IMG_7409  # 0 days old, should be kept
            + IMG_7408  # 1 days old, should be deleted
            + IMG_7407  # 1 days old, should be deleted
        )
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

        files_to_create = IMG_7409

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

        files_to_create = (
            IMG_7409  # 0 days old, should be kept
            + IMG_7408  # 1 days old, should be deleted
            + IMG_7407  # 1 days old, should be deleted
        )
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
        skip_live_photos: bool = False,
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
            _, result = self._run_keep_recent_days_0(base_dir, IMG_7409, [])

        self.assertIn("Deleted IMG_7409.JPG in iCloud", result.output)
        self.assertNotIn("Deleted IMG_7408.JPG in iCloud", result.output)
        self.assertNotIn("Deleted IMG_7407.JPG in iCloud", result.output)
        self.assertIn(
            "Not deleting IMG_7408.JPG from iCloud: it is not present locally", result.output
        )
        self.assertEqual(result.exit_code, 0)

    @staticmethod
    def _fail_first_delete(error: Exception, modify_calls: List[str]) -> Any:
        """A session request that raises error for the first delete (records/modify) only"""
        original_request = PyiCloudSession.request

        def request(self_: PyiCloudSession, method: str, url: str, **kwargs: Any) -> Any:
            if "/records/modify" in url:
                modify_calls.append(url)
                if len(modify_calls) == 1:
                    raise error
            return original_request(self_, method, url, **kwargs)

        return mock.patch.object(PyiCloudSession, "request", request)

    def test_keep_icloud_recent_days_try_again_later_skips_only_that_photo(self) -> None:
        """iCloud can refuse a delete with TRY_AGAIN_LATER (#1283); the run goes on"""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        files = LIVE_PHOTOS_ON_DISK
        # what the session raises for the response in #1283
        error = PyiCloudAPIResponseException(
            "Sync zone CAS Op-Lock failed. There was a concurrent write and this "
            "operation was rejected. Retry request...",
            "TRY_AGAIN_LATER",
        )
        modify_calls: List[str] = []

        with self._fail_first_delete(error, modify_calls):
            _, result = self._run_keep_recent_days_0(base_dir, files, [])

        self.assertIn(
            "Could not delete IMG_7409.JPG in iCloud: Sync zone CAS Op-Lock failed. There was a "
            "concurrent write and this operation was rejected. Retry request... (TRY_AGAIN_LATER)",
            result.output,
        )
        self.assertNotIn("Deleted IMG_7409.JPG in iCloud", result.output)
        self.assertIn("Deleted IMG_7408.JPG in iCloud", result.output)
        self.assertIn("Deleted IMG_7407.JPG in iCloud", result.output)
        self.assertEqual(len(modify_calls), 3)
        self.assertIn("All photos have been downloaded", result.output)
        self.assertEqual(result.exit_code, 0)

    def test_keep_icloud_recent_days_other_delete_errors_end_the_run(self) -> None:
        """Only TRY_AGAIN_LATER is skipped; other delete errors still end the run"""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        files = LIVE_PHOTOS_ON_DISK
        error = PyiCloudAPIResponseException("Internal error", "INTERNAL_ERROR")
        modify_calls: List[str] = []

        with self._fail_first_delete(error, modify_calls):
            _, result = self._run_keep_recent_days_0(base_dir, files, [])

        self.assertIn("Internal error (INTERNAL_ERROR)", result.output)
        self.assertNotIn("Could not delete", result.output)
        self.assertNotIn("Deleted IMG_", result.output)
        self.assertEqual(len(modify_calls), 1)
        self.assertNotIn("All photos have been downloaded", result.output)
        self.assertEqual(result.exit_code, 1)

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
            )

        delete_photo.assert_not_called()
        self.assertEqual(result.exit_code, 0)

    def test_keep_icloud_recent_days_keeps_live_photos_with_skip_live_photos(self) -> None:
        """--skip-live-photos does not download the video, so deleting a Live Photo loses it"""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        # only the stills are on disk; the videos were never downloaded
        files = [IMG_7409[0], IMG_7408[0], IMG_7407[0]]
        versions_property: property = PhotoAsset.__dict__["versions"]
        original_versions = versions_property.fget
        assert original_versions is not None

        def versions(self_: PhotoAsset) -> Any:
            """IMG_7408 without its video, so the run also has a photo that is not a Live Photo"""
            result = original_versions(self_)
            if self_.filename == "IMG_7408.JPG":
                return {
                    size: version
                    for size, version in result.items()
                    if not isinstance(size, LivePhotoVersionSize)
                }
            return result

        modify_calls: List[str] = []
        original_request = PyiCloudSession.request

        def request(self_: PyiCloudSession, method: str, url: str, **kwargs: Any) -> Any:
            if "/records/modify" in url:
                modify_calls.append(url)
            return original_request(self_, method, url, **kwargs)

        with (
            mock.patch.object(PhotoAsset, "versions", property(versions)),
            mock.patch.object(PyiCloudSession, "request", request),
        ):
            _, result = self._run_keep_recent_days_0(base_dir, files, [], skip_live_photos=True)

        self.assertIn(
            "--keep-icloud-recent-days is used with --skip-live-photos: Live Photos are not "
            "deleted from iCloud, since their video is not downloaded",
            result.output,
        )
        for name in ["IMG_7409.JPG", "IMG_7407.JPG"]:
            self.assertNotIn(f"Deleted {name} in iCloud", result.output)
            self.assertIn(
                f"Not deleting {name} from iCloud: it is a Live Photo and --skip-live-photos "
                "did not download its video",
                result.output,
            )
        self.assertIn("Deleted IMG_7408.JPG in iCloud", result.output)
        self.assertEqual(len(modify_calls), 1)
        self.assertIn("All photos have been downloaded", result.output)
        self.assertEqual(result.exit_code, 0)


class KeepICloudRecentDaysWarningsTestCase(TestCase):
    def warnings(
        self,
        keep: int | None,
        recent: int | None,
        until_found: int | None,
        skip_live_photos: bool = False,
    ) -> List[str]:
        config = SimpleNamespace(
            keep_icloud_recent_days=keep,
            recent=recent,
            until_found=until_found,
            skip_live_photos=skip_live_photos,
        )
        return keep_icloud_recent_days_warnings(config)  # type: ignore[arg-type]

    def test_no_warning_without_keep_icloud_recent_days(self) -> None:
        self.assertEqual([], self.warnings(None, 10, 5, skip_live_photos=True))

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

    def test_warns_for_skip_live_photos(self) -> None:
        self.assertEqual(
            [
                "--keep-icloud-recent-days is used with --skip-live-photos: Live Photos are not deleted from iCloud, since their video is not downloaded",
            ],
            self.warnings(0, None, None, skip_live_photos=True),
        )


class HasAssetDateTestCase(TestCase):
    def test_has_asset_date(self) -> None:
        for fields, expected in [
            ({"assetDate": {"value": 1533021744816}}, True),
            # a real date before 1970, e.g. a scanned photo
            ({"assetDate": {"value": -315619200000}}, True),
            ({}, False),
            ({"assetDate": {}}, False),
            ({"assetDate": {"value": None}}, False),
        ]:
            with self.subTest(fields=fields):
                asset = PhotoAsset({"fields": {}}, {"fields": fields})
                self.assertEqual(expected, asset.has_asset_date)
