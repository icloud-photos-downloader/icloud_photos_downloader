import base64
import logging
from typing import Sequence
from unittest import TestCase

from icloudpd.base import where_builder
from icloudpd.cli import parse
from pyicloud_ipd.services.photos import PhotoAsset


def asset(filename: str) -> PhotoAsset:
    master = {
        "recordName": "M1",
        "fields": {
            "itemType": {"value": "public.jpeg"},
            "filenameEnc": {
                "type": "ENCRYPTED_BYTES",
                "value": base64.b64encode(filename.encode()).decode(),
            },
        },
    }
    return PhotoAsset(master, {"recordName": "A1", "fields": {}})


def passes(filename: str, patterns: Sequence[str]) -> bool:
    return where_builder(
        logging.getLogger("test"),
        False,
        None,
        None,
        False,
        lambda photo: filename,
        asset(filename),
        exclude_filenames=patterns,
    )


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
