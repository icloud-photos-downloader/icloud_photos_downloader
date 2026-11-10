import datetime
from argparse import ArgumentError
from pathlib import Path
from unittest import TestCase, mock

from icloudpd.base import download_builder
from icloudpd.cli import parse
from icloudpd.counter import Counter
from pyicloud_ipd.asset_version import AssetVersion
from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.item_type import AssetItemType
from pyicloud_ipd.raw_policy import RawTreatmentPolicy
from pyicloud_ipd.services.photos import PhotoAsset
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize


class TempSuffixOptionTestCase(TestCase):
    def test_default_and_custom_suffix(self) -> None:
        _, user_configs = parse(["--username", "u", "--directory", "d"])
        self.assertEqual(".part", user_configs[0].temp_suffix)
        _, user_configs = parse(
            ["--username", "u", "--directory", "d", "--temp-suffix", ".icloudpd"]
        )
        self.assertEqual(".icloudpd", user_configs[0].temp_suffix)

    def test_suffix_with_a_path_separator_is_rejected(self) -> None:
        for suffix in ("", "a/b", "a\b"):
            with self.assertRaises(ArgumentError):
                parse(["--username", "u", "--directory", "d", "--temp-suffix", suffix])

    def test_suffix_that_looks_like_media_is_rejected(self) -> None:
        """A leftover temporary file must not be mistaken for a photo or sidecar"""
        for suffix in (".jpg", ".HEIC", ".mov", ".xmp", ".tmp.jpg"):
            with self.assertRaises(ArgumentError):
                parse(["--username", "u", "--directory", "d", "--temp-suffix", suffix])


def test_live_photo_video_uses_the_temp_suffix(tmp_path: Path) -> None:
    media = mock.MagicMock(spec=PhotoAsset)
    media.created = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    media.filename = "IMG-2024.HEIC"
    media.item_type = AssetItemType.IMAGE
    media._asset_record = {"fields": {}}
    media.versions_with_raw_policy.return_value = {
        AssetVersionSize.ORIGINAL: AssetVersion(
            5, "https://example.invalid/photo", "public.heic", ""
        ),
        LivePhotoVersionSize.ORIGINAL: AssetVersion(
            5, "https://example.invalid/video", "com.apple.quicktime-movie", ""
        ),
    }

    def write_media(*args: object) -> bool:
        Path(str(args[4])).write_bytes(b"media")
        return True

    with mock.patch(
        "icloudpd.base.download.download_media", side_effect=write_media
    ) as download_media:
        download_builder(
            mock.MagicMock(),
            "none",
            str(tmp_path),
            [AssetVersionSize.ORIGINAL],
            False,
            False,
            False,
            False,
            LivePhotoVersionSize.ORIGINAL,
            False,
            FileMatchPolicy.NAME_SIZE_DEDUP_WITH_SUFFIX,
            False,
            lambda filename: str(Path(filename).with_suffix(".MOV")),
            lambda item: item.filename,
            RawTreatmentPolicy.AS_IS,
            mock.MagicMock(),
            Counter(),
            media,
            temp_suffix=".icloudpd",
        )

    targets = {Path(call.args[4]).name: call.args[-1] for call in download_media.call_args_list}
    assert targets == {"IMG-2024.HEIC": ".icloudpd", "IMG-2024.MOV": ".icloudpd"}
