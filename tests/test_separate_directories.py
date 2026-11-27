import base64
import contextlib
import inspect
import io
import logging
import os
import shutil
from typing import Any, Dict, List, Tuple
from unittest import TestCase, mock

import pytest

from icloudpd.autodelete import autodelete_photos
from icloudpd.base import download_builder
from icloudpd.cli import cli, parse
from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.raw_policy import RawTreatmentPolicy
from pyicloud_ipd.services.photos import PhotoAsset
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize
from tests.helpers import (
    path_from_project_root,
    recreate_path,
    run_cassette,
    run_icloudpd_test,
)


def files_in(directory: str) -> List[str]:
    return sorted(
        os.path.relpath(os.path.join(root, name), directory).replace(os.sep, "/")
        for root, _, names in os.walk(directory)
        for name in names
    )


def make_asset(
    record_name: str,
    item_type: str,
    filename: str,
    file_type_val: str,
    asset_fields: Dict[str, Any] | None = None,
) -> PhotoAsset:
    master: Dict[str, Any] = {
        "recordName": f"M_{record_name}",
        "fields": {
            "itemType": {"value": item_type},
            "filenameEnc": {
                "type": "ENCRYPTED_BYTES",
                "value": base64.b64encode(filename.encode()).decode(),
            },
            "dataClass": {"value": "com.apple.Dataclass.Photos"},
        },
    }
    asset_record: Dict[str, Any] = {
        "recordName": record_name,
        "fields": {
            "assetDate": {"value": 1683720000000},
            "resOriginalRes": {
                "value": {
                    "size": 1000,
                    "downloadURL": "http://example.com/download",
                    "fileChecksum": "dummychecksum",
                }
            },
            "resOriginalFileType": {"value": file_type_val},
            **(asset_fields or {}),
        },
    }
    return PhotoAsset(master, asset_record)


class SeparateDirectoriesTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")
        self.vcr_path = os.path.join(self.root_path, "vcr_cassettes")

    def test_parse_screenshot_and_video_directories(self) -> None:
        """--screenshot-directory and --video-directory are parsed into UserConfig (#1494)"""
        _, user_configs = parse(
            [
                "--username",
                "u",
                "--directory",
                "/base",
                "--screenshot-directory",
                "/screenshots",
                "--video-directory",
                "/videos",
            ]
        )
        self.assertEqual(user_configs[0].screenshot_directory, "/screenshots")
        self.assertEqual(user_configs[0].video_directory, "/videos")

    def test_validation_rejects_conflicting_options(self) -> None:
        """Conflicting directory and skip options exit with code 2 (#1494)"""
        output = io.StringIO()
        with (
            mock.patch(
                "sys.argv",
                [
                    "icloudpd",
                    "--username",
                    "u",
                    "--directory",
                    "/base",
                    "--screenshot-directory",
                    "/screenshots",
                    "--skip-screenshots",
                ],
            ),
            contextlib.redirect_stdout(output),
        ):
            code = cli()
        self.assertEqual(code, 2)
        self.assertIn(
            "--screenshot-directory can't be combined with --skip-screenshots or --prune-orphans",
            output.getvalue(),
        )

        output = io.StringIO()
        with (
            mock.patch(
                "sys.argv",
                [
                    "icloudpd",
                    "--username",
                    "u",
                    "--directory",
                    "/base",
                    "--screenshot-directory",
                    "/screenshots",
                    "--prune-orphans",
                ],
            ),
            contextlib.redirect_stdout(output),
        ):
            code = cli()
        self.assertEqual(code, 2)
        self.assertIn(
            "--screenshot-directory can't be combined with --skip-screenshots or --prune-orphans",
            output.getvalue(),
        )

        output = io.StringIO()
        with (
            mock.patch(
                "sys.argv",
                [
                    "icloudpd",
                    "--username",
                    "u",
                    "--directory",
                    "/base",
                    "--video-directory",
                    "/videos",
                    "--skip-videos",
                ],
            ),
            contextlib.redirect_stdout(output),
        ):
            code = cli()
        self.assertEqual(code, 2)
        self.assertIn(
            "--video-directory can't be combined with --skip-videos or --prune-orphans",
            output.getvalue(),
        )

        output = io.StringIO()
        with (
            mock.patch(
                "sys.argv",
                [
                    "icloudpd",
                    "--username",
                    "u",
                    "--directory",
                    "/base",
                    "--video-directory",
                    "/videos",
                    "--prune-orphans",
                ],
            ),
            contextlib.redirect_stdout(output),
        ):
            code = cli()
        self.assertEqual(code, 2)
        self.assertIn(
            "--video-directory can't be combined with --skip-videos or --prune-orphans",
            output.getvalue(),
        )

    def test_download_builder_routes_screenshots_and_videos(self) -> None:
        """download_builder routes screenshots to --screenshot-directory and videos (#1494)"""
        photo = make_asset("P1", "public.jpeg", "photo.jpg", "public.jpeg")
        screenshot = make_asset(
            "S1",
            "public.png",
            "screen.png",
            "public.png",
            {"assetSubtypeV2": {"type": "INT64", "value": 3}},
        )
        video = make_asset(
            "V1",
            "com.apple.quicktime-movie",
            "movie.mov",
            "com.apple.quicktime-movie",
        )

        def run_inspect(asset: PhotoAsset) -> Tuple[str, ...]:
            res = download_builder(
                logging.getLogger("test"),
                "none",
                "/base",
                [AssetVersionSize.ORIGINAL],
                False,
                False,
                False,
                True,
                LivePhotoVersionSize.ORIGINAL,
                True,
                FileMatchPolicy.NAME_SIZE_DEDUP_WITH_SUFFIX,
                False,
                lambda f: f,
                lambda a: a.filename,
                RawTreatmentPolicy.AS_IS,
                mock.MagicMock(),
                mock.MagicMock(),
                asset,
                inspect_only=True,
                screenshot_directory="/screenshots",
                video_directory="/videos",
            )
            return res.expected_paths

        # Photo goes to /base
        photo_paths = run_inspect(photo)
        self.assertTrue(any(p.startswith(os.path.normpath("/base")) for p in photo_paths))

        # Screenshot goes to /screenshots
        screenshot_paths = run_inspect(screenshot)
        self.assertTrue(
            any(p.startswith(os.path.normpath("/screenshots")) for p in screenshot_paths)
        )
        self.assertFalse(any(p.startswith(os.path.normpath("/base")) for p in screenshot_paths))

        # Video goes to /videos
        video_paths = run_inspect(video)
        self.assertTrue(any(p.startswith(os.path.normpath("/videos")) for p in video_paths))
        self.assertFalse(any(p.startswith(os.path.normpath("/base")) for p in video_paths))

    def test_autodelete_photos_checks_separate_directories(self) -> None:
        """autodelete_photos checks screenshot and video directories for deletions (#1494)"""
        photo = make_asset("P1", "public.jpeg", "photo.jpg", "public.jpeg")
        screenshot = make_asset(
            "S1",
            "public.png",
            "screen.png",
            "public.png",
            {"assetSubtypeV2": {"type": "INT64", "value": 3}},
        )
        video = make_asset(
            "V1",
            "com.apple.quicktime-movie",
            "movie.mov",
            "com.apple.quicktime-movie",
        )

        library = mock.MagicMock()
        library.recently_deleted = [photo, screenshot, video]

        deleted_paths: list[str] = []

        with (
            mock.patch("os.path.exists", return_value=True),
            mock.patch(
                "icloudpd.autodelete.delete_file",
                side_effect=lambda _, path: deleted_paths.append(path),
            ),
        ):
            autodelete_photos(
                logging.getLogger("test"),
                False,
                library,
                "none",
                "/base",
                [AssetVersionSize.ORIGINAL],
                lambda f: f,
                RawTreatmentPolicy.AS_IS,
                lambda a: a.filename,
                screenshot_directory="/screenshots",
                video_directory="/videos",
            )

        self.assertTrue(any(p.startswith(os.path.normpath("/base")) for p in deleted_paths))
        self.assertTrue(any(p.startswith(os.path.normpath("/screenshots")) for p in deleted_paths))
        self.assertTrue(any(p.startswith(os.path.normpath("/videos")) for p in deleted_paths))

    def test_cassette_video_directory_downloads_and_skips_existing(self) -> None:
        """Standalone videos download into --video-directory and skip on second run (#1494)"""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        video_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3] + "_videos")
        for directory in [base_dir, video_dir]:
            recreate_path(directory)

        # First run: downloads IMG_7405.MOV into video_dir; data_dir has no files
        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_videos.yml",
            [],
            [],
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "4",
                "--skip-photos",
                "--set-exif-datetime",
                "--no-progress-bar",
                "--threads-num",
                "1",
                "--video-directory",
                video_dir,
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(["2018/07/30/IMG_7405.MOV"], files_in(video_dir))
        self.assertEqual([], files_in(data_dir))

        # Adjust downloaded file size to match remote record (36491351 bytes)
        video_file = os.path.join(video_dir, "2018", "07", "30", "IMG_7405.MOV")
        with open(video_file, "r+b") as f:
            f.truncate(36491351)

        # Second run: file already exists in video_dir with matching size, no re-download
        _, result2 = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_videos.yml",
            [],
            [],
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "4",
                "--skip-photos",
                "--set-exif-datetime",
                "--no-progress-bar",
                "--threads-num",
                "1",
                "--video-directory",
                video_dir,
            ],
        )
        self.assertEqual(result2.exit_code, 0)
        self.assertIn("already exists", result2.output)

    def test_cassette_live_photo_video_does_not_go_to_video_directory(self) -> None:
        """Live Photo videos do not go to --video-directory (#1494)"""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        video_dir = os.path.join(base_dir, "videos")
        for directory in [base_dir, video_dir]:
            recreate_path(directory)

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "download_live_photos.yml",
            [],
            [
                ("2020/11/04", "IMG_0516.HEIC"),
                ("2020/11/04", "IMG_0514.HEIC"),
                ("2020/11/04", "IMG_0514_HEVC.MOV"),
                ("2020/11/04", "IMG_0512.HEIC"),
                ("2020/11/04", "IMG_0512_HEVC.MOV"),
            ],
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "3",
                "--no-progress-bar",
                "--threads-num",
                "1",
                "--video-directory",
                video_dir,
            ],
        )
        self.assertEqual(result.exit_code, 0)
        # Video directory remains empty because Live Photos are images
        self.assertEqual([], files_in(video_dir))

    def test_cassette_all_three_directories_together(self) -> None:
        """--directory, --live-photo-directory, and --video-directory together (#1494)"""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        live_dir = os.path.join(base_dir, "live")
        video_dir = os.path.join(base_dir, "videos")
        screen_dir = os.path.join(base_dir, "screenshots")
        for directory in [base_dir, live_dir, video_dir, screen_dir]:
            recreate_path(directory)

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "download_live_photos.yml",
            [],
            [
                ("2020/11/04", "IMG_0516.HEIC"),
                ("2020/11/04", "IMG_0514.HEIC"),
                ("2020/11/04", "IMG_0512.HEIC"),
            ],
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "3",
                "--no-progress-bar",
                "--threads-num",
                "1",
                "--live-photo-directory",
                live_dir,
                "--video-directory",
                video_dir,
                "--screenshot-directory",
                screen_dir,
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertEqual([], files_in(video_dir))
        self.assertEqual([], files_in(screen_dir))
        self.assertEqual(
            ["2020/11/04/IMG_0512_HEVC.MOV", "2020/11/04/IMG_0514_HEVC.MOV"],
            files_in(live_dir),
        )

    def test_cassette_auto_delete_with_separate_directories(self) -> None:
        """--auto-delete deletes from screenshot and video directories (#1494)"""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")
        live_dir = os.path.join(base_dir, "live")
        screen_dir = os.path.join(base_dir, "screenshots")
        video_dir = os.path.join(base_dir, "videos")
        for directory in [base_dir, data_dir, live_dir, screen_dir, video_dir]:
            recreate_path(directory)
        shutil.copytree(os.path.join(self.root_path, "cookie"), cookie_dir)

        # In autodelete_photos.yml:
        # - IMG_7190.JPG and IMG_7190.MOV (Live Photo) are in Recently Deleted
        # - IMG_7383.PNG (Screenshot) is in Recently Deleted
        # - IMG_7406.MOV (Movie) is in Recently Deleted
        # - IMG_7407.JPG and IMG_7407.MOV are NOT in Recently Deleted
        for directory, name in [
            (data_dir, "2018/07/12/IMG_7190.JPG"),
            (live_dir, "2018/07/12/IMG_7190.MOV"),
            (screen_dir, "2018/07/26/IMG_7383.PNG"),
            (video_dir, "2018/07/30/IMG_7406.MOV"),
            (data_dir, "2018/07/30/IMG_7407.JPG"),
            (live_dir, "2018/07/30/IMG_7407.MOV"),
        ]:
            os.makedirs(os.path.dirname(os.path.join(directory, name)), exist_ok=True)
            open(os.path.join(directory, name), "a").close()

        result = run_cassette(
            os.path.join(self.vcr_path, "autodelete_photos.yml"),
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "0",
                "--auto-delete",
                "-d",
                data_dir,
                "--live-photo-directory",
                live_dir,
                "--screenshot-directory",
                screen_dir,
                "--video-directory",
                video_dir,
                "--cookie-directory",
                cookie_dir,
            ],
        )

        self.assertEqual(0, result.exit_code)
        # Screenshots and videos are deleted from their directories
        self.assertIn("Deleted", result.output)
        self.assertEqual([], files_in(screen_dir))
        self.assertEqual([], files_in(video_dir))
        # Non-deleted photo and live-photo video remain
        self.assertEqual(["2018/07/30/IMG_7407.JPG"], files_in(data_dir))
        self.assertEqual(["2018/07/30/IMG_7407.MOV"], files_in(live_dir))
