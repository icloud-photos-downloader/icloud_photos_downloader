import logging
import os
import struct
import tempfile
from unittest import TestCase

import piexif

from icloudpd.exif_datetime import get_photo_exif, set_photo_exif


def jpeg_with_truncated_exif() -> bytes:
    """A JPEG whose EXIF block is cut short by one byte; piexif.load raises struct.error on it"""
    exif = piexif.dump(
        {
            "0th": {piexif.ImageIFD.DateTime: b"2018:07:31 07:22:24"},
            "Exif": {piexif.ExifIFD.DateTimeOriginal: b"2018:07:31 07:22:24"},
            "1st": {piexif.ImageIFD.XResolution: (72, 1)},
        }
    )
    app1 = b"Exif\x00\x00" + exif[:-1]
    return b"\xff\xd8\xff\xe1" + struct.pack(">H", len(app1) + 2) + app1 + b"\xff\xd9"


class ExifDatetimeTestCase(TestCase):
    def setUp(self) -> None:
        handle, self.path = tempfile.mkstemp(suffix=".JPG")
        with os.fdopen(handle, "wb") as file:
            file.write(jpeg_with_truncated_exif())
        self.logger = logging.getLogger("icloudpd-test-exif-datetime")

    def tearDown(self) -> None:
        os.remove(self.path)

    def test_truncated_exif_is_really_broken(self) -> None:
        with self.assertRaises(struct.error):
            piexif.load(self.path)

    def test_get_photo_exif_with_truncated_exif(self) -> None:
        """Damaged EXIF is logged and skipped instead of ending the run (#1431)"""
        with self.assertLogs(self.logger, level="DEBUG") as logs:
            self.assertIsNone(get_photo_exif(self.logger, self.path))
        self.assertIn(f"Error fetching EXIF data for {self.path}", logs.output[0])

    def test_set_photo_exif_with_truncated_exif(self) -> None:
        with open(self.path, "rb") as file:
            before = file.read()
        with self.assertLogs(self.logger, level="DEBUG") as logs:
            set_photo_exif(self.logger, self.path, "2018:07:31 07:22:24")
        self.assertIn(f"Error setting EXIF data for {self.path}", logs.output[0])
        with open(self.path, "rb") as file:
            self.assertEqual(before, file.read())
