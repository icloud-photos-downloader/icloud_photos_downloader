"""Unit tests for icloudpd.exif_datetime — get/set EXIF dates on real JPEGs."""

import logging
import os
import shutil
import tempfile
from unittest import TestCase

import piexif

from icloudpd.exif_datetime import get_photo_exif, set_photo_exif

_test_logger = logging.getLogger("test_exif_datetime")

# Minimal valid 1x1 JPEG that piexif can load/modify
_MINIMAL_JPEG = bytes(
    [
        0xFF, 0xD8,  # SOI
        0xFF, 0xE0, 0x00, 0x10,  # APP0 marker + length
        0x4A, 0x46, 0x49, 0x46, 0x00,  # JFIF\0
        0x01, 0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00,  # Version, density, no thumb
        0xFF, 0xDB, 0x00, 0x43, 0x00,  # DQT marker
    ]
    + [0x01] * 64  # Quantisation table
    + [
        0xFF, 0xC0, 0x00, 0x0B, 0x08,  # SOF0
        0x00, 0x01, 0x00, 0x01,  # 1x1
        0x01, 0x01, 0x11, 0x00,  # 1 component
        0xFF, 0xC4, 0x00, 0x1F, 0x00,  # DHT
        0x00, 0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01,
        0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
        0x08, 0x09, 0x0A, 0x0B,
        0xFF, 0xDA, 0x00, 0x08,  # SOS
        0x01, 0x01, 0x00, 0x00, 0x3F, 0x00,
        0x7B, 0x40,  # Compressed data
        0xFF, 0xD9,  # EOI
    ]
)


def _create_jpeg(path: str, exif_date: str | None = None) -> None:
    """Write a minimal JPEG, optionally with an EXIF date already set."""
    with open(path, "wb") as f:
        f.write(_MINIMAL_JPEG)
    if exif_date:
        exif_dict = piexif.load(path)
        exif_dict["Exif"][36867] = exif_date.encode()
        exif_dict["Exif"][36868] = exif_date.encode()
        exif_dict["0th"][306] = exif_date.encode()
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, path)


class TestPiexifAssumptions(TestCase):
    """Document and verify our assumptions about piexif behaviour."""

    def test_piexif_load_always_returns_dicts_for_ifds(self) -> None:
        """piexif.load() returns empty dicts for IFDs, never None.

        This validates our removal of the None guards that were dead code.
        """
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(_MINIMAL_JPEG)
            path = f.name
        try:
            exif_dict = piexif.load(path)
            for ifd_name in ["0th", "Exif", "GPS", "1st", "Interop"]:
                ifd = exif_dict.get(ifd_name)
                self.assertIsInstance(
                    ifd, dict, f"piexif IFD '{ifd_name}' should be dict, got {type(ifd)}"
                )
        finally:
            os.unlink(path)


class TestGetPhotoExif(TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir)

    def test_returns_date_string_when_exif_present(self) -> None:
        path = os.path.join(self._tmpdir, "with_exif.jpg")
        _create_jpeg(path, "2025:03:15 10:30:00")
        result = get_photo_exif(_test_logger, path)
        self.assertEqual(result, "2025:03:15 10:30:00")

    def test_returns_none_when_no_exif_datetime(self) -> None:
        path = os.path.join(self._tmpdir, "no_exif.jpg")
        _create_jpeg(path)
        result = get_photo_exif(_test_logger, path)
        self.assertIsNone(result)

    def test_returns_none_for_corrupt_file(self) -> None:
        path = os.path.join(self._tmpdir, "corrupt.jpg")
        with open(path, "wb") as f:
            f.write(b"not a jpeg")
        result = get_photo_exif(_test_logger, path)
        self.assertIsNone(result)


class TestSetPhotoExif(TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir)

    def test_sets_exif_date_on_jpeg_without_existing_exif(self) -> None:
        path = os.path.join(self._tmpdir, "no_exif.jpg")
        _create_jpeg(path)
        set_photo_exif(_test_logger, path, "2025:06:01 12:00:00")
        # Verify the date was written
        result = get_photo_exif(_test_logger, path)
        self.assertEqual(result, "2025:06:01 12:00:00")

    def test_overwrites_existing_exif_date(self) -> None:
        path = os.path.join(self._tmpdir, "with_exif.jpg")
        _create_jpeg(path, "2020:01:01 00:00:00")
        set_photo_exif(_test_logger, path, "2025:12:25 18:00:00")
        result = get_photo_exif(_test_logger, path)
        self.assertEqual(result, "2025:12:25 18:00:00")

    def test_noop_on_corrupt_file(self) -> None:
        path = os.path.join(self._tmpdir, "corrupt.jpg")
        with open(path, "wb") as f:
            f.write(b"not a jpeg")
        with open(path, "rb") as f:
            original_content = f.read()
        set_photo_exif(_test_logger, path, "2025:01:01 00:00:00")
        # File should be unchanged
        with open(path, "rb") as f:
            self.assertEqual(f.read(), original_content)

    def test_piexif_roundtrip_is_idempotent(self) -> None:
        """After one set_photo_exif, subsequent round-trips don't change size."""
        path = os.path.join(self._tmpdir, "idempotent.jpg")
        _create_jpeg(path)
        set_photo_exif(_test_logger, path, "2025:01:01 00:00:00")
        size_after_first = os.path.getsize(path)
        set_photo_exif(_test_logger, path, "2025:01:01 00:00:00")
        size_after_second = os.path.getsize(path)
        self.assertEqual(size_after_first, size_after_second)
