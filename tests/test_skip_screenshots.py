import base64
import logging
from typing import Any, Dict
from unittest import TestCase

from icloudpd.base import where_builder
from icloudpd.cli import parse
from pyicloud_ipd.services.photos import PhotoAsset


def asset(asset_fields: Dict[str, Any]) -> PhotoAsset:
    master: Dict[str, Any] = {
        "recordName": "M1",
        "fields": {
            "itemType": {"value": "public.png"},
            "filenameEnc": {
                "type": "ENCRYPTED_BYTES",
                "value": base64.b64encode(b"IMG_0001.PNG").decode(),
            },
        },
    }
    return PhotoAsset(master, {"recordName": "A1", "fields": asset_fields})


SCREENSHOT = {"assetSubtypeV2": {"type": "INT64", "value": 3}}
PHOTO = {"assetSubtypeV2": {"type": "INT64", "value": 0}}


def passes(photo: PhotoAsset, skip_screenshots: bool) -> bool:
    return where_builder(
        logging.getLogger("test"),
        False,
        None,
        None,
        False,
        lambda _: "IMG_0001.PNG",
        photo,
        skip_screenshots=skip_screenshots,
    )


class SkipScreenshotsTestCase(TestCase):
    def test_is_screenshot(self) -> None:
        self.assertTrue(asset(SCREENSHOT).is_screenshot)
        self.assertFalse(asset(PHOTO).is_screenshot)
        self.assertFalse(asset({}).is_screenshot)
        self.assertFalse(asset({"assetSubtypeV2": {"value": "x"}}).is_screenshot)

    def test_skip_screenshots(self) -> None:
        """--skip-screenshots leaves out screenshots and keeps other photos (#1386)"""
        self.assertFalse(passes(asset(SCREENSHOT), skip_screenshots=True))
        self.assertTrue(passes(asset(PHOTO), skip_screenshots=True))
        self.assertTrue(passes(asset({}), skip_screenshots=True))

    def test_screenshots_are_kept_by_default(self) -> None:
        self.assertTrue(passes(asset(SCREENSHOT), skip_screenshots=False))

    def test_parse_skip_screenshots(self) -> None:
        _, user_configs = parse(["--username", "u", "--directory", "d", "--skip-screenshots"])
        self.assertTrue(user_configs[0].skip_screenshots)
        _, user_configs = parse(["--username", "u", "--directory", "d"])
        self.assertFalse(user_configs[0].skip_screenshots)
