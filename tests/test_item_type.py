import base64
from typing import Any, Dict
from unittest import TestCase

from pyicloud_ipd.item_type import AssetItemType
from pyicloud_ipd.services.photos import PhotoAsset


def asset(item_type: str, filename: str) -> PhotoAsset:
    master: Dict[str, Any] = {
        "recordName": "M1",
        "fields": {
            "itemType": {"value": item_type},
            "filenameEnc": {
                "type": "ENCRYPTED_BYTES",
                "value": base64.b64encode(filename.encode()).decode(),
            },
        },
    }
    return PhotoAsset(master, {"recordName": "A1", "fields": {}})


class ItemTypeTestCase(TestCase):
    def test_jpeg_xl_is_an_image(self) -> None:
        """JPEG XL photos were treated as videos, e.g. skipped by --skip-videos (#1385)"""
        self.assertEqual(AssetItemType.IMAGE, asset("public.jpeg-xl", "IMG_0001.JXL").item_type)
        self.assertEqual("JXL", asset("public.jpeg-xl", "IMG_0001.JXL").item_type_extension)

    def test_unknown_type_with_image_extension_is_an_image(self) -> None:
        for filename in ["a.jxl", "a.webp", "a.GIF", "a.tiff", "a.avif", "a.dng"]:
            with self.subTest(filename=filename):
                self.assertEqual(AssetItemType.IMAGE, asset("public.unknown", filename).item_type)

    def test_unknown_type_with_other_extension_is_a_movie(self) -> None:
        for filename in ["a.mp4", "a.MOV", "a.m4v"]:
            with self.subTest(filename=filename):
                self.assertEqual(AssetItemType.MOVIE, asset("public.unknown", filename).item_type)
