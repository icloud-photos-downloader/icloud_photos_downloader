import base64
import logging
from typing import Any, Callable, Dict, Sequence
from unittest import TestCase

from icloudpd.base import build_filename_cleaner, where_builder
from icloudpd.cli import parse
from icloudpd.filename_policies import create_filename_builder
from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.services.photos import PhotoAsset


def asset(filename: str, item_type: str = "public.jpeg", **fields: Any) -> PhotoAsset:
    master_fields: Dict[str, Any] = {
        "itemType": {"value": item_type},
        "filenameEnc": {
            "type": "ENCRYPTED_BYTES",
            "value": base64.b64encode(filename.encode()).decode(),
        },
    }
    master_fields.update(fields)
    master = {"recordName": "AY6c+BsE0jjaXx9tmVGJM1D2VcEO", "fields": master_fields}
    return PhotoAsset(master, {"recordName": "A1", "fields": {}})


def builder(policy: FileMatchPolicy) -> Callable[[PhotoAsset], str]:
    return create_filename_builder(policy, build_filename_cleaner(False))


NAME_SIZE = builder(FileMatchPolicy.NAME_SIZE_DEDUP_WITH_SUFFIX)


def passes_asset(
    photo: PhotoAsset,
    patterns: Sequence[str],
    filename_builder: Callable[[PhotoAsset], str] = NAME_SIZE,
) -> bool:
    return where_builder(
        logging.getLogger("test"),
        False,
        None,
        None,
        False,
        filename_builder,
        photo,
        exclude_filenames=patterns,
    )


def passes(filename: str, patterns: Sequence[str]) -> bool:
    return passes_asset(asset(filename), patterns)


def resource(filename: str) -> Dict[str, Any]:
    return {
        "value": {
            "size": 1,
            "downloadURL": f"https://example.com/{filename}",
            "fileChecksum": "x",
        }
    }


class ExcludeFilenameTestCase(TestCase):
    def test_pattern_matches(self) -> None:
        """Assets with a matching filename are left out (#1259)"""
        self.assertFalse(passes("IMG_1234.JPG", ["IMG_12*.JPG"]))
        self.assertFalse(passes("IMG_1234.JPG", ["img_1234.jpg"]))
        self.assertFalse(passes("20241215_wedding_001_IMG_1234.jpg", ["*_wedding_*"]))

    def test_other_filenames_pass(self) -> None:
        self.assertTrue(passes("IMG_9999.JPG", ["IMG_12*.JPG"]))
        self.assertTrue(passes("IMG_1234.JPG", ["IMG_1234"]))

    def test_one_matching_pattern_is_enough(self) -> None:
        self.assertFalse(passes("IMG_1234.JPG", ["*.PNG", "IMG_1*"]))

    def test_nothing_is_excluded_by_default(self) -> None:
        self.assertTrue(passes("IMG_1234.JPG", []))

    def test_character_ranges_ignore_case(self) -> None:
        self.assertFalse(passes("IMG_1234.JPG", ["[a-z]MG_*"]))
        self.assertTrue(passes("IMG_1234.JPG", ["[!a-z]MG_*"]))
        self.assertFalse(passes("1MG_1234.JPG", ["[!a-z]MG_*"]))

    def test_name_id7_matches_the_name_with_the_id(self) -> None:
        """With name-id7 the pattern sees the filename that has the id in it"""
        name_id7 = builder(FileMatchPolicy.NAME_ID7)
        photo = asset("IMG_1234.JPG")
        self.assertRegex(name_id7(photo), r"^IMG_1234_.{7}\.JPG$")
        self.assertTrue(passes_asset(photo, ["IMG_1234.JPG"], name_id7))
        self.assertFalse(passes_asset(photo, ["IMG_1234*.JPG"], name_id7))

    def test_live_photo_is_matched_by_its_photo(self) -> None:
        """A match skips the whole Live Photo, its video isn't matched on its own"""
        live_photo = asset(
            "IMG_1234.HEIC",
            item_type="public.heic",
            resOriginalRes=resource("IMG_1234.HEIC"),
            resOriginalVidComplRes=resource("IMG_1234.MOV"),
        )
        self.assertFalse(passes_asset(live_photo, ["*.HEIC"]))
        self.assertTrue(passes_asset(live_photo, ["*.MOV"]))

    def test_parse_exclude_filename(self) -> None:
        _, user_configs = parse(
            [
                "--username",
                "u",
                "--directory",
                "d",
                "--exclude-filename",
                "*.PNG",
                "--exclude-filename",
                "IMG_1*",
            ]
        )
        self.assertEqual(("*.PNG", "IMG_1*"), tuple(user_configs[0].exclude_filenames))
        _, user_configs = parse(["--username", "u", "--directory", "d"])
        self.assertEqual((), tuple(user_configs[0].exclude_filenames))

    def test_default_patterns_are_combined_with_the_user_patterns(self) -> None:
        _, user_configs = parse(
            [
                "--exclude-filename",
                "*.PNG",
                "--username",
                "u1",
                "--directory",
                "d",
                "--exclude-filename",
                "IMG_1*",
                "--username",
                "u2",
                "--directory",
                "d",
            ]
        )
        self.assertEqual(("*.PNG", "IMG_1*"), tuple(user_configs[0].exclude_filenames))
        self.assertEqual(("*.PNG",), tuple(user_configs[1].exclude_filenames))
