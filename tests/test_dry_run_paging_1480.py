import datetime
import inspect
import os
from typing import Any, Callable, Dict, List, Tuple
from unittest import TestCase, mock

import pytest

from icloudpd.base import delete_photo as real_delete_photo
from pyicloud_ipd.services.photos import PhotoAlbum, PhotoAsset, PhotoLibrary
from tests.helpers import path_from_project_root, run_icloudpd_test


class FakeResponse:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self.payload = payload

    def json(self) -> Dict[str, Any]:
        return self.payload


FILES_THREE_PHOTOS: List[Tuple[str, str, int]] = [
    ("2018/07/31", "IMG_7409.JPG", 1884695),
    ("2018/07/30", "IMG_7408.JPG", 1151066),
    ("2018/07/30", "IMG_7407.JPG", 656257),
]


def make_paged_photos_request(
    page_size: int,
    n_assets: int = 3,
    max_requests: int = 6,
) -> Tuple[Callable[[PhotoAlbum], Any], List[int], List[Dict[str, Any]]]:
    """Build a PhotoAlbum.photos_request replacement that slices the first real VCR response into small pages."""
    original_photos_request = PhotoAlbum.photos_request
    assets: List[Dict[str, Any]] = []
    masters: Dict[str, Dict[str, Any]] = {}
    requested_offsets: List[int] = []
    loaded = False

    def paged_photos_request(album: PhotoAlbum) -> Any:
        nonlocal loaded
        if not loaded:
            raw_records = original_photos_request(album).json()["records"]
            for rec in raw_records:
                if rec["recordType"] == "CPLAsset" and len(assets) < n_assets:
                    assets.append(rec)
                elif rec["recordType"] == "CPLMaster":
                    masters[rec["recordName"]] = rec
            loaded = True

        requested_offsets.append(album.offset)
        if len(requested_offsets) > max_requests:
            raise RuntimeError(
                f"Infinite paging loop detected: photos_request called {len(requested_offsets)} "
                f"times with offsets {requested_offsets}"
            )

        page_assets = assets[album.offset : album.offset + page_size]
        page_masters: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for asset in page_assets:
            master_name = asset["fields"]["masterRef"]["value"]["recordName"]
            if master_name not in seen and master_name in masters:
                seen.add(master_name)
                page_masters.append(masters[master_name])
        return FakeResponse({"records": page_masters + page_assets})

    return paged_photos_request, requested_offsets, assets


class DryRunPaging1480TestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

    def test_keep_icloud_recent_days_dry_run_pages_advance_without_repeating(self) -> None:
        """Dry run with --keep-icloud-recent-days across multiple pages must not repeat offsets (#1480)."""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        paged_request, requested_offsets, _ = make_paged_photos_request(
            page_size=1, n_assets=3, max_requests=6
        )

        with (
            mock.patch("datetime.datetime", wraps=datetime.datetime) as dt_mock,
            mock.patch.object(PhotoAlbum, "photos_request", paged_request),
        ):
            mock_now = datetime.datetime(2018, 7, 31, tzinfo=datetime.UTC)
            dt_mock.now.return_value = mock_now + datetime.timedelta(days=10)
            _, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos_keep_icloud_recent_days.yml",
                FILES_THREE_PHOTOS,
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
                    "--no-progress-bar",
                    "--threads-num",
                    "1",
                    "--keep-icloud-recent-days",
                    "0",
                    "--dry-run",
                ],
            )

        self.assertIsNone(result.exception)
        self.assertEqual(result.exit_code, 0)
        # 3 single-asset pages at offsets 0, 1, 2 followed by empty page at offset 3
        self.assertEqual(requested_offsets, [0, 1, 2, 3])
        self.assertEqual(len(requested_offsets), len(set(requested_offsets)))
        for _, filename, _ in FILES_THREE_PHOTOS:
            msg = f"[DRY RUN] Would delete {filename} in iCloud library PrimarySync"
            self.assertEqual(result.output.count(msg), 1, f"Expected {filename} processed once")

    def test_delete_after_download_dry_run_pages_advance_without_repeating(self) -> None:
        """Dry run with --delete-after-download across multiple pages must not repeat offsets (#1480)."""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        paged_request, requested_offsets, _ = make_paged_photos_request(
            page_size=2, n_assets=3, max_requests=6
        )

        with (
            mock.patch.object(PhotoAlbum, "photos_request", paged_request),
            mock.patch("icloudpd.download.download_media", return_value=True),
        ):
            _, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos_keep_icloud_recent_days.yml",
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
                    "--no-progress-bar",
                    "--threads-num",
                    "1",
                    "--delete-after-download",
                    "--dry-run",
                ],
            )

        self.assertIsNone(result.exception)
        self.assertEqual(result.exit_code, 0)
        # Page 1 at offset 0 (2 assets), page 2 at offset 2 (1 asset), empty page at offset 3
        self.assertEqual(requested_offsets, [0, 2, 3])
        self.assertEqual(len(requested_offsets), len(set(requested_offsets)))
        for _, filename, _ in FILES_THREE_PHOTOS:
            msg = f"[DRY RUN] Would delete {filename} in iCloud library PrimarySync"
            self.assertEqual(result.output.count(msg), 1, f"Expected {filename} processed once")

    def test_real_delete_steps_offset_back_keeping_pages_aligned(self) -> None:
        """Non-dry-run delete removes the asset from iCloud and steps offset back so paging stays aligned."""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        paged_request, requested_offsets, assets = make_paged_photos_request(
            page_size=1, n_assets=3, max_requests=6
        )

        def delete_and_remove_from_server(
            logger: Any,
            library_object: PhotoLibrary,
            photo: PhotoAsset,
            filename_builder: Callable[[PhotoAsset], str],
        ) -> bool:
            deleted = real_delete_photo(logger, library_object, photo, filename_builder)
            if deleted:
                record_name = photo._asset_record["recordName"]
                assets[:] = [a for a in assets if a["recordName"] != record_name]
            return deleted

        with (
            mock.patch("datetime.datetime", wraps=datetime.datetime) as dt_mock,
            mock.patch.object(PhotoAlbum, "photos_request", paged_request),
            mock.patch("icloudpd.base.delete_photo", side_effect=delete_and_remove_from_server),
        ):
            # 1 day later: IMG_7409.JPG (0 days old) is kept; IMG_7408.JPG and IMG_7407.JPG (1 day old) are deleted
            mock_now = datetime.datetime(2018, 7, 31, tzinfo=datetime.UTC)
            dt_mock.now.return_value = mock_now + datetime.timedelta(days=1)
            _, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos_keep_icloud_recent_days.yml",
                FILES_THREE_PHOTOS,
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
                    "--no-progress-bar",
                    "--threads-num",
                    "1",
                    "--keep-icloud-recent-days",
                    "1",
                ],
            )

        self.assertIsNone(result.exception)
        self.assertEqual(result.exit_code, 0)
        # Offset 0 kept -> advances to 1; offset 1 (IMG_7408) deleted -> steps back to 1 for IMG_7407;
        # offset 1 (IMG_7407) deleted -> steps back to 1 which is now past the remaining 1-asset list
        self.assertEqual(requested_offsets, [0, 1, 1, 1])
        self.assertNotIn("Deleted IMG_7409.JPG in iCloud", result.output)
        self.assertEqual(result.output.count("Deleted IMG_7408.JPG in iCloud"), 1)
        self.assertEqual(result.output.count("Deleted IMG_7407.JPG in iCloud"), 1)
