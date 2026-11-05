import logging
import os
import struct
import tempfile
from unittest import TestCase

import piexif

from icloudpd.exif_datetime import get_photo_exif, set_photo_exif


def jpeg_with_truncated_exif() -> bytes:
    """A JPEG whose EXIF block is cut short by one byte; piexif.load raises struct.error on it"""
    exif: bytes = piexif.dump(
        {
            "0th": {piexif.ImageIFD.DateTime: b"2018:07:31 07:22:24"},
            "Exif": {piexif.ExifIFD.DateTimeOriginal: b"2018:07:31 07:22:24"},
            "1st": {piexif.ImageIFD.XResolution: (72, 1)},
        }
    )
    app1 = b"Exif\x00\x00" + exif[:-1]
    return b"\xff\xd8\xff\xe1" + struct.pack(">H", len(app1) + 2) + app1 + b"\xff\xd9"


def jpeg(exif: bytes | None = None) -> bytes:
    """A JPEG piexif can read and write, with the given EXIF block (from piexif.dump)"""
    data = b"\xff\xd8"
    if exif is not None:
        data += b"\xff\xe1" + struct.pack(">H", len(exif) + 2) + exif
    return data + b"\xff\xda\x00\x02" + b"\xff\xd9"


class SetExifDatetimeTestCase(TestCase):
    """--set-exif-datetime writes DateTime in the main IFD and both date tags in the Exif IFD"""

    def setUp(self) -> None:
        handle, self.path = tempfile.mkstemp(suffix=".JPG")
        os.close(handle)
        self.logger = logging.getLogger("icloudpd-test-set-exif-datetime")

    def tearDown(self) -> None:
        os.remove(self.path)

    def check_dates_written(self, data: bytes) -> None:
        with open(self.path, "wb") as file:
            file.write(data)
        set_photo_exif(self.logger, self.path, "2018:07:31 07:22:24")
        exif = piexif.load(self.path)
        self.assertEqual(b"2018:07:31 07:22:24", exif["0th"].get(piexif.ImageIFD.DateTime))
        self.assertEqual(b"2018:07:31 07:22:24", exif["Exif"].get(piexif.ExifIFD.DateTimeOriginal))
        self.assertEqual(b"2018:07:31 07:22:24", exif["Exif"].get(piexif.ExifIFD.DateTimeDigitized))
        self.assertEqual(b"2018:07:31 07:22:24", get_photo_exif(self.logger, self.path))

    def test_jpeg_without_exif(self) -> None:
        self.check_dates_written(jpeg())

    def test_jpeg_with_exif_without_dates(self) -> None:
        exif: bytes = piexif.dump({"0th": {piexif.ImageIFD.Make: b"Apple"}})
        self.check_dates_written(jpeg(exif))
        self.assertEqual(b"Apple", piexif.load(self.path)["0th"].get(piexif.ImageIFD.Make))


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
