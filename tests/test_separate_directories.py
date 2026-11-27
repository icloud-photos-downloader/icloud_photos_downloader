import base64
import contextlib
import datetime
import io
import logging
import os
from typing import Any, Dict
from unittest import TestCase, mock

from icloudpd.autodelete import autodelete_photos
from icloudpd.base import download_builder
from icloudpd.cli import cli, parse
from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.raw_policy import RawTreatmentPolicy
from pyicloud_ipd.services.photos import AssetItemType, PhotoAsset
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize


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
        """download_builder routes screenshots to --screenshot-directory and videos to --video-directory (#1494)"""
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

        def run_inspect(asset: PhotoAsset) -> list[str]:
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
        self.assertTrue(any(p.startswith(os.path.normpath("/screenshots")) for p in screenshot_paths))
        self.assertFalse(any(p.startswith(os.path.normpath("/base")) for p in screenshot_paths))

        # Video goes to /videos
        video_paths = run_inspect(video)
        self.assertTrue(any(p.startswith(os.path.normpath("/videos")) for p in video_paths))
        self.assertFalse(any(p.startswith(os.path.normpath("/base")) for p in video_paths))

    def test_autodelete_photos_checks_separate_directories(self) -> None:
        """autodelete_photos checks screenshot and video directories for recently deleted assets (#1494)"""
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

        with mock.patch("os.path.exists", return_value=True), mock.patch(
            "icloudpd.autodelete.delete_file", side_effect=lambda _, path: deleted_paths.append(path)
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
