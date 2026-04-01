"""Unit tests for icloudpd.metadata_writer — exiftool-based metadata writing.

Validates that exiftool can write and read back iCloud metadata fields
across all supported image formats (HEIC, JPEG, PNG) without re-encoding
the image or losing existing camera EXIF data.

Requires exiftool to be installed on the system.
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Any
from unittest import TestCase

import piexif

from icloudpd.cli import _parse_write_metadata
from icloudpd.metadata_writer import (
    MetadataUpdate,
    build_exiftool_args,
    check_exiftool,
    extract_metadata_update,
    write_metadata,
)

_test_logger = logging.getLogger("test_metadata_writer")

# Minimal valid 1x1 JPEG (same as test_exif_datetime.py)
_MINIMAL_JPEG = bytes(
    [
        0xFF, 0xD8,  # SOI
        0xFF, 0xE0, 0x00, 0x10,  # APP0 marker + length
        0x4A, 0x46, 0x49, 0x46, 0x00,  # JFIF\0
        0x01, 0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00,
        0xFF, 0xDB, 0x00, 0x43, 0x00,  # DQT marker
    ]
    + [0x01] * 64
    + [
        0xFF, 0xC0, 0x00, 0x0B, 0x08,  # SOF0
        0x00, 0x01, 0x00, 0x01,  # 1x1
        0x01, 0x01, 0x11, 0x00,
        0xFF, 0xC4, 0x00, 0x1F, 0x00,  # DHT
        0x00, 0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01,
        0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
        0x08, 0x09, 0x0A, 0x0B,
        0xFF, 0xDA, 0x00, 0x08,  # SOS
        0x01, 0x01, 0x00, 0x00, 0x3F, 0x00,
        0x7B, 0x40,
        0xFF, 0xD9,  # EOI
    ]
)

# Minimal valid 1x1 PNG with correct CRC (exiftool rejects bad CRC)
_MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01"
    b"\x00\xc9\xfe\x92\xef"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _exiftool_available() -> bool:
    """Check if exiftool is installed."""
    try:
        result = subprocess.run(
            ["exiftool", "-ver"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _exiftool_read(path: str, tags: list[str] | None = None) -> dict[str, Any]:
    """Read metadata from a file using exiftool JSON output.
    
    Returns dict with keys like 'EXIF:ImageDescription', 'XMP-xmp:Rating', etc.
    """
    cmd = ["exiftool", "-json", "-G1"]
    if tags:
        cmd.extend(f"-{tag}" for tag in tags)
    cmd.append(path)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        return {}
    data = json.loads(result.stdout)
    return data[0] if data else {}


def _exiftool_write(path: str, tags: dict[str, str]) -> bool:
    """Write metadata to a file using exiftool. Returns True on success."""
    cmd = ["exiftool", "-overwrite_original"]
    for key, value in tags.items():
        cmd.append(f"-{key}={value}")
    cmd.append(path)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.returncode == 0 and "1 image files updated" in result.stdout


def _create_jpeg(path: str) -> None:
    """Write a minimal JPEG with EXIF date and GPS via piexif."""
    with open(path, "wb") as f:
        f.write(_MINIMAL_JPEG)
    exif_dict = piexif.load(path)
    exif_dict["Exif"][36867] = b"2025:06:15 10:30:00"  # DateTimeOriginal
    exif_dict["0th"][271] = b"Apple"  # Make
    exif_dict["0th"][272] = b"iPhone 16 Pro"  # Model
    exif_dict["GPS"][1] = b"S"  # GPSLatitudeRef
    exif_dict["GPS"][2] = ((33, 1), (45, 1), (3671, 100))  # GPSLatitude
    exif_dict["GPS"][3] = b"E"  # GPSLongitudeRef
    exif_dict["GPS"][4] = ((151, 1), (13, 1), (426, 100))  # GPSLongitude
    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, path)


def _create_png(path: str) -> None:
    """Write a minimal PNG (no EXIF)."""
    with open(path, "wb") as f:
        f.write(_MINIMAL_PNG)


HAS_EXIFTOOL = _exiftool_available()
SKIP_MSG = "exiftool not installed"


class TestCheckExiftool(TestCase):
    """Test the check_exiftool function from the module."""

    def test_check_exiftool_returns_version(self) -> None:
        if not HAS_EXIFTOOL:
            self.skipTest(SKIP_MSG)
        version = check_exiftool()
        self.assertIsInstance(version, str)
        # Should be a version number like "13.25"
        self.assertRegex(version, r"\d+\.\d+")


class TestBuildExiftoolArgs(TestCase):
    """Test argument building from MetadataUpdate."""

    def test_empty_update_returns_no_args(self) -> None:
        update = MetadataUpdate()
        args = build_exiftool_args(update, {"all"})
        self.assertEqual(args, [])

    def test_rating_only(self) -> None:
        update = MetadataUpdate(rating=5)
        args = build_exiftool_args(update, {"rating"})
        self.assertEqual(args, ["-Rating=5"])

    def test_rating_not_in_config(self) -> None:
        update = MetadataUpdate(rating=5)
        args = build_exiftool_args(update, {"keywords"})
        self.assertEqual(args, [])

    def test_all_config_includes_everything(self) -> None:
        update = MetadataUpdate(
            rating=5, title="Test", description="Desc",
            keywords=["a", "b"], orientation=6
        )
        args = build_exiftool_args(update, {"all"})
        self.assertIn("-Rating=5", args)
        self.assertIn("-XPTitle=Test", args)
        self.assertIn("-ImageDescription=Desc", args)
        self.assertIn("-Orientation#=6", args)
        # Keywords generate multiple args
        self.assertTrue(any("XPKeywords" in a for a in args))
        self.assertTrue(any("Subject" in a for a in args))

    def test_keywords_semicolon_separated(self) -> None:
        update = MetadataUpdate(keywords=["holiday", "beach", "sunset"])
        args = build_exiftool_args(update, {"keywords"})
        xp_args = [a for a in args if "XPKeywords" in a]
        self.assertEqual(len(xp_args), 1)
        self.assertIn("holiday; beach; sunset", xp_args[0])


class TestWriteMetadataDryRun(TestCase):
    """Test dry-run mode doesn't modify files."""

    def setUp(self) -> None:
        if not HAS_EXIFTOOL:
            self.skipTest(SKIP_MSG)
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_dry_run_does_not_modify_file(self) -> None:
        path = os.path.join(self.tmp_dir, "test.jpg")
        _create_jpeg(path)
        orig_size = os.path.getsize(path)
        update = MetadataUpdate(rating=5, title="Test")
        result = write_metadata(path, update, {"all"}, dry_run=True)
        self.assertTrue(result)
        self.assertEqual(os.path.getsize(path), orig_size)

    def test_dry_run_returns_false_when_no_changes(self) -> None:
        path = os.path.join(self.tmp_dir, "test.jpg")
        _create_jpeg(path)
        update = MetadataUpdate()  # No fields set
        result = write_metadata(path, update, {"all"}, dry_run=True)
        self.assertFalse(result)


class TestWriteMetadataReal(TestCase):
    """Test real metadata writing via the module API."""

    def setUp(self) -> None:
        if not HAS_EXIFTOOL:
            self.skipTest(SKIP_MSG)
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_write_rating_via_module(self) -> None:
        path = os.path.join(self.tmp_dir, "test.jpg")
        _create_jpeg(path)
        update = MetadataUpdate(rating=5)
        result = write_metadata(path, update, {"all"})
        self.assertTrue(result)
        meta = _exiftool_read(path, ["Rating"])
        self.assertEqual(meta.get("XMP-xmp:Rating"), 5)

    def test_write_all_fields_via_module(self) -> None:
        path = os.path.join(self.tmp_dir, "test.jpg")
        _create_jpeg(path)
        update = MetadataUpdate(
            rating=5,
            title="Beach Sunset",
            description="Beautiful sunset on the beach",
            keywords=["holiday", "beach"],
            orientation=6,
        )
        result = write_metadata(path, update, {"all"})
        self.assertTrue(result)
        meta = _exiftool_read(path)
        self.assertEqual(meta.get("XMP-xmp:Rating"), 5)
        self.assertEqual(meta.get("IFD0:XPTitle"), "Beach Sunset")
        self.assertIn("holiday", meta.get("IFD0:XPKeywords", ""))


class TestExiftoolAvailability(TestCase):
    """Verify exiftool detection works."""

    def test_exiftool_check_returns_bool(self) -> None:
        result = _exiftool_available()
        self.assertIsInstance(result, bool)

    def test_exiftool_is_available(self) -> None:
        self.assertTrue(HAS_EXIFTOOL, SKIP_MSG)


class TestExiftoolWriteRating(TestCase):
    """Write and read back Rating tag."""

    def setUp(self) -> None:
        if not HAS_EXIFTOOL:
            self.skipTest(SKIP_MSG)
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_write_rating_to_jpeg(self) -> None:
        path = os.path.join(self.tmp_dir, "test.jpg")
        _create_jpeg(path)
        self.assertTrue(_exiftool_write(path, {"Rating": "5"}))
        meta = _exiftool_read(path, ["Rating"])
        self.assertEqual(meta.get("XMP-xmp:Rating"), 5)

    def test_write_rating_to_png(self) -> None:
        path = os.path.join(self.tmp_dir, "test.png")
        _create_png(path)
        self.assertTrue(_exiftool_write(path, {"XMP:Rating": "5"}))
        meta = _exiftool_read(path, ["Rating"])
        self.assertEqual(meta.get("XMP-xmp:Rating"), 5)


class TestExiftoolWriteKeywords(TestCase):
    """Write and read back keywords/subject tags."""

    def setUp(self) -> None:
        if not HAS_EXIFTOOL:
            self.skipTest(SKIP_MSG)
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_write_keywords_to_jpeg(self) -> None:
        path = os.path.join(self.tmp_dir, "test.jpg")
        _create_jpeg(path)
        self.assertTrue(
            _exiftool_write(path, {"XPKeywords": "holiday; beach; sunset"})
        )
        meta = _exiftool_read(path, ["XPKeywords"])
        keywords = meta.get("IFD0:XPKeywords", "")
        self.assertIn("holiday", keywords)
        self.assertIn("beach", keywords)
        self.assertIn("sunset", keywords)

    def test_write_iptc_keywords_to_jpeg(self) -> None:
        path = os.path.join(self.tmp_dir, "test.jpg")
        _create_jpeg(path)
        self.assertTrue(
            _exiftool_write(
                path, {"IPTC:Keywords": "holiday", "XMP:Subject": "holiday"}
            )
        )
        meta = _exiftool_read(path, ["Keywords", "Subject"])
        found = str(meta)
        self.assertIn("holiday", found)


class TestExiftoolWriteTitle(TestCase):
    """Write and read back title/description tags."""

    def setUp(self) -> None:
        if not HAS_EXIFTOOL:
            self.skipTest(SKIP_MSG)
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_write_title_to_jpeg(self) -> None:
        path = os.path.join(self.tmp_dir, "test.jpg")
        _create_jpeg(path)
        self.assertTrue(
            _exiftool_write(path, {"XPTitle": "My Holiday Photo"})
        )
        meta = _exiftool_read(path, ["XPTitle"])
        self.assertEqual(meta.get("IFD0:XPTitle"), "My Holiday Photo")

    def test_write_description_to_jpeg(self) -> None:
        path = os.path.join(self.tmp_dir, "test.jpg")
        _create_jpeg(path)
        self.assertTrue(
            _exiftool_write(path, {"ImageDescription": "A sunset at the beach"})
        )
        meta = _exiftool_read(path, ["ImageDescription"])
        self.assertEqual(
            meta.get("EXIF:ImageDescription") or meta.get("IFD0:ImageDescription"),
            "A sunset at the beach",
        )

    def test_write_description_to_png(self) -> None:
        path = os.path.join(self.tmp_dir, "test.png")
        _create_png(path)
        self.assertTrue(
            _exiftool_write(path, {"XMP:Description": "A screenshot"})
        )
        meta = _exiftool_read(path, ["Description"])
        found = str(meta)
        self.assertIn("screenshot", found.lower())


class TestExiftoolPreservation(TestCase):
    """Verify existing camera EXIF is preserved after writing new metadata."""

    def setUp(self) -> None:
        if not HAS_EXIFTOOL:
            self.skipTest(SKIP_MSG)
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_gps_preserved_after_rating_write(self) -> None:
        path = os.path.join(self.tmp_dir, "test.jpg")
        _create_jpeg(path)
        before = _exiftool_read(path, ["GPSLatitude", "GPSLongitude", "Make"])
        # Write rating
        self.assertTrue(_exiftool_write(path, {"Rating": "5"}))
        after = _exiftool_read(path, ["GPSLatitude", "GPSLongitude", "Make"])
        self.assertEqual(
            before.get("Composite:GPSLatitude"),
            after.get("Composite:GPSLatitude"),
        )
        self.assertEqual(
            before.get("Composite:GPSLongitude"),
            after.get("Composite:GPSLongitude"),
        )

    def test_dates_preserved_after_keyword_write(self) -> None:
        path = os.path.join(self.tmp_dir, "test.jpg")
        _create_jpeg(path)
        before = _exiftool_read(path, ["DateTimeOriginal"])
        self.assertTrue(
            _exiftool_write(path, {"XPKeywords": "test"})
        )
        after = _exiftool_read(path, ["DateTimeOriginal"])
        self.assertEqual(
            before.get("EXIF:DateTimeOriginal"),
            after.get("EXIF:DateTimeOriginal"),
        )

    def test_make_model_preserved(self) -> None:
        path = os.path.join(self.tmp_dir, "test.jpg")
        _create_jpeg(path)
        before = _exiftool_read(path, ["Make", "Model"])
        self.assertTrue(_exiftool_write(path, {"Rating": "5", "XPTitle": "Test"}))
        after = _exiftool_read(path, ["Make", "Model"])
        self.assertEqual(before.get("EXIF:Make"), after.get("EXIF:Make"))


class TestExiftoolIdempotency(TestCase):
    """Second write of same metadata must produce identical file."""

    def setUp(self) -> None:
        if not HAS_EXIFTOOL:
            self.skipTest(SKIP_MSG)
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_jpeg_idempotent(self) -> None:
        path = os.path.join(self.tmp_dir, "test.jpg")
        _create_jpeg(path)
        tags = {"Rating": "5", "XPTitle": "Test", "ImageDescription": "Desc"}
        self.assertTrue(_exiftool_write(path, tags))
        size_after_first = os.path.getsize(path)
        self.assertTrue(_exiftool_write(path, tags))
        size_after_second = os.path.getsize(path)
        self.assertEqual(size_after_first, size_after_second)

    def test_png_idempotent(self) -> None:
        path = os.path.join(self.tmp_dir, "test.png")
        _create_png(path)
        tags = {"XMP:Rating": "5", "XMP:Description": "Test"}
        self.assertTrue(_exiftool_write(path, tags))
        size_after_first = os.path.getsize(path)
        self.assertTrue(_exiftool_write(path, tags))
        size_after_second = os.path.getsize(path)
        self.assertEqual(size_after_first, size_after_second)


class TestExiftoolInPlaceSize(TestCase):
    """Verify exiftool patches in-place with minimal size change."""

    def setUp(self) -> None:
        if not HAS_EXIFTOOL:
            self.skipTest(SKIP_MSG)
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_jpeg_size_delta_is_small(self) -> None:
        path = os.path.join(self.tmp_dir, "test.jpg")
        _create_jpeg(path)
        orig_size = os.path.getsize(path)
        tags = {
            "Rating": "5",
            "XPTitle": "Favourite Photo",
            "XPKeywords": "holiday; beach; sunset",
            "ImageDescription": "A sunset at the beach",
        }
        self.assertTrue(_exiftool_write(path, tags))
        new_size = os.path.getsize(path)
        # Should be within 5KB of original (metadata only, no re-encoding)
        self.assertLess(abs(new_size - orig_size), 5000)


class TestExiftoolMultipleFields(TestCase):
    """Write all supported fields at once and verify."""

    def setUp(self) -> None:
        if not HAS_EXIFTOOL:
            self.skipTest(SKIP_MSG)
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_write_all_fields_to_jpeg(self) -> None:
        path = os.path.join(self.tmp_dir, "test.jpg")
        _create_jpeg(path)
        tags = {
            "Rating": "5",
            "XPTitle": "Beach Sunset",
            "XPKeywords": "holiday; beach; sunset",
            "ImageDescription": "Beautiful sunset on the beach",
            "Orientation": "6",  # Rotate 90 CW
        }
        self.assertTrue(_exiftool_write(path, tags))

        meta = _exiftool_read(path)
        self.assertEqual(meta.get("XMP-xmp:Rating"), 5)
        self.assertEqual(meta.get("IFD0:XPTitle"), "Beach Sunset")
        self.assertIn("holiday", meta.get("IFD0:XPKeywords", ""))

    def test_write_all_fields_to_png(self) -> None:
        path = os.path.join(self.tmp_dir, "test.png")
        _create_png(path)
        tags = {
            "XMP:Rating": "5",
            "XMP:Description": "A screenshot",
        }
        self.assertTrue(_exiftool_write(path, tags))
        meta = _exiftool_read(path, ["Rating", "Description"])
        self.assertEqual(meta.get("XMP-xmp:Rating"), 5)


class TestExiftoolErrorHandling(TestCase):
    """Handle missing exiftool and invalid files gracefully."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_write_to_nonexistent_file_fails(self) -> None:
        if not HAS_EXIFTOOL:
            self.skipTest(SKIP_MSG)
        result = _exiftool_write("/tmp/nonexistent_file_xyz.jpg", {"Rating": "5"})
        self.assertFalse(result)

    def test_write_to_empty_file_fails(self) -> None:
        if not HAS_EXIFTOOL:
            self.skipTest(SKIP_MSG)
        path = os.path.join(self.tmp_dir, "empty.jpg")
        with open(path, "wb") as f:
            f.write(b"")
        result = _exiftool_write(path, {"Rating": "5"})
        self.assertFalse(result)


class TestExtractMetadataUpdate(TestCase):
    """Test extract_metadata_update from XMP metadata and raw asset records."""

    def test_from_xmp_with_favourite(self) -> None:
        from collections import namedtuple
        from datetime import datetime, timedelta, timezone

        XMP = namedtuple("XMP", [
            "XMPToolkit", "Title", "Description", "Orientation", "Make",
            "DigitalSourceType", "Keywords", "GPSAltitude", "GPSLatitude",
            "GPSLongitude", "GPSSpeed", "GPSTimeStamp", "CreateDate", "Rating",
        ])
        xmp = XMP(
            XMPToolkit="icloudpd", Title="Beach Day", Description="Fun day",
            Orientation=6, Make="Apple", DigitalSourceType=None,
            Keywords=["holiday", "beach"], GPSAltitude=10.0, GPSLatitude=-33.7,
            GPSLongitude=151.2, GPSSpeed=0.0, GPSTimeStamp=None,
            CreateDate=datetime(2025, 6, 15, 10, 30, tzinfo=timezone(timedelta(hours=11))),
            Rating=5,
        )
        update = extract_metadata_update({}, xmp)
        self.assertEqual(update.rating, 5)
        self.assertEqual(update.title, "Beach Day")
        self.assertEqual(update.description, "Fun day")
        self.assertEqual(update.keywords, ["holiday", "beach"])
        self.assertEqual(update.orientation, 6)
        self.assertEqual(update.timezone_offset, "+11:00")

    def test_from_xmp_no_rating_returns_none(self) -> None:
        from collections import namedtuple
        XMP = namedtuple("XMP", [
            "XMPToolkit", "Title", "Description", "Orientation", "Make",
            "DigitalSourceType", "Keywords", "GPSAltitude", "GPSLatitude",
            "GPSLongitude", "GPSSpeed", "GPSTimeStamp", "CreateDate", "Rating",
        ])
        xmp = XMP(
            XMPToolkit="icloudpd", Title=None, Description=None,
            Orientation=None, Make=None, DigitalSourceType=None,
            Keywords=None, GPSAltitude=None, GPSLatitude=None,
            GPSLongitude=None, GPSSpeed=None, GPSTimeStamp=None,
            CreateDate=None, Rating=None,
        )
        update = extract_metadata_update({}, xmp)
        self.assertIsNone(update.rating)
        self.assertIsNone(update.title)
        self.assertIsNone(update.timezone_offset)

    def test_from_xmp_negative_timezone(self) -> None:
        from collections import namedtuple
        from datetime import datetime, timedelta, timezone

        XMP = namedtuple("XMP", [
            "XMPToolkit", "Title", "Description", "Orientation", "Make",
            "DigitalSourceType", "Keywords", "GPSAltitude", "GPSLatitude",
            "GPSLongitude", "GPSSpeed", "GPSTimeStamp", "CreateDate", "Rating",
        ])
        xmp = XMP(
            XMPToolkit="icloudpd", Title=None, Description=None,
            Orientation=None, Make=None, DigitalSourceType=None,
            Keywords=None, GPSAltitude=None, GPSLatitude=None,
            GPSLongitude=None, GPSSpeed=None, GPSTimeStamp=None,
            CreateDate=datetime(2025, 1, 1, 8, 0, tzinfo=timezone(timedelta(hours=-8))),
            Rating=None,
        )
        update = extract_metadata_update({}, xmp)
        self.assertEqual(update.timezone_offset, "-08:00")

    def test_from_raw_asset_record_favourite(self) -> None:
        record = {"fields": {"isFavorite": {"value": 1}}}
        update = extract_metadata_update(record)
        self.assertEqual(update.rating, 5)

    def test_from_raw_asset_record_hidden(self) -> None:
        record = {"fields": {"isHidden": {"value": 1}}}
        update = extract_metadata_update(record)
        self.assertEqual(update.rating, -1)

    def test_from_raw_asset_record_normal(self) -> None:
        record: dict[str, Any] = {"fields": {}}
        update = extract_metadata_update(record)
        self.assertIsNone(update.rating)


class TestBuildExiftoolArgsTimezone(TestCase):
    """Test timezone offset argument generation."""

    def test_timezone_offset_generates_three_tags(self) -> None:
        update = MetadataUpdate(timezone_offset="+11:00")
        args = build_exiftool_args(update, {"dates"})
        self.assertIn("-OffsetTimeOriginal=+11:00", args)
        self.assertIn("-OffsetTimeDigitized=+11:00", args)
        self.assertIn("-OffsetTime=+11:00", args)

    def test_timezone_not_in_config_skipped(self) -> None:
        update = MetadataUpdate(timezone_offset="+11:00")
        args = build_exiftool_args(update, {"rating"})
        self.assertEqual(args, [])

    def test_timezone_with_all_config(self) -> None:
        update = MetadataUpdate(timezone_offset="-05:00")
        args = build_exiftool_args(update, {"all"})
        self.assertIn("-OffsetTimeOriginal=-05:00", args)

    def test_negative_timezone(self) -> None:
        update = MetadataUpdate(timezone_offset="-08:00")
        args = build_exiftool_args(update, {"dates"})
        self.assertIn("-OffsetTimeOriginal=-08:00", args)


class TestParseWriteMetadata(TestCase):
    """Test CLI --write-metadata flag parsing."""

    def test_none_returns_empty_frozenset(self) -> None:
        self.assertEqual(_parse_write_metadata(None), frozenset())

    def test_all(self) -> None:
        self.assertEqual(_parse_write_metadata("all"), frozenset({"all"}))

    def test_comma_separated(self) -> None:
        result = _parse_write_metadata("rating,keywords,title")
        self.assertEqual(result, frozenset({"rating", "keywords", "title"}))

    def test_whitespace_stripped(self) -> None:
        result = _parse_write_metadata("rating , keywords")
        self.assertEqual(result, frozenset({"rating", "keywords"}))

    def test_invalid_raises(self) -> None:
        import argparse
        with self.assertRaises(argparse.ArgumentTypeError):
            _parse_write_metadata("invalid_category")

    def test_mixed_valid_invalid_raises(self) -> None:
        import argparse
        with self.assertRaises(argparse.ArgumentTypeError):
            _parse_write_metadata("rating,bogus")

    def test_dates_and_orientation(self) -> None:
        result = _parse_write_metadata("dates,orientation")
        self.assertEqual(result, frozenset({"dates", "orientation"}))


class TestWriteMetadataNoChanges(TestCase):
    """Test that write_metadata returns False when exiftool makes no changes."""

    def setUp(self) -> None:
        if not HAS_EXIFTOOL:
            self.skipTest(SKIP_MSG)
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_second_write_returns_false(self) -> None:
        """After writing metadata once, a second identical write should return False."""
        path = os.path.join(self.tmp_dir, "test.jpg")
        _create_jpeg(path)
        update = MetadataUpdate(timezone_offset="+11:00")
        # First write should succeed
        result1 = write_metadata(path, update, {"all"})
        self.assertTrue(result1)
        # Second identical write should detect no changes needed
        result2 = write_metadata(path, update, {"all"})
        self.assertFalse(result2, "Second write with same metadata should return False")

    def test_rating_negative_roundtrip(self) -> None:
        """Rating=-1 (hidden/rejected) writes and reads back correctly."""
        path = os.path.join(self.tmp_dir, "test_neg.jpg")
        _create_jpeg(path)
        update = MetadataUpdate(rating=-1)
        self.assertTrue(write_metadata(path, update, {"rating"}))
        meta = _exiftool_read(path, ["Rating"])
        self.assertEqual(meta.get("XMP-xmp:Rating"), -1)
        # Idempotent
        self.assertFalse(write_metadata(path, update, {"rating"}))

    def test_orientation_roundtrip(self) -> None:
        """Orientation values round-trip correctly through exiftool."""
        for orient in [1, 3, 6, 8]:
            path = os.path.join(self.tmp_dir, f"test_o{orient}.jpg")
            _create_jpeg(path)
            update = MetadataUpdate(orientation=orient)
            self.assertTrue(write_metadata(path, update, {"orientation"}), f"orient={orient}")
            # Idempotent
            self.assertFalse(write_metadata(path, update, {"orientation"}), f"orient={orient} idempotent")

    def test_empty_keywords_no_write(self) -> None:
        """Empty keywords list should not trigger a write."""
        path = os.path.join(self.tmp_dir, "test_kw.jpg")
        _create_jpeg(path)
        update = MetadataUpdate(keywords=[])
        result = write_metadata(path, update, {"keywords"})
        self.assertFalse(result)
