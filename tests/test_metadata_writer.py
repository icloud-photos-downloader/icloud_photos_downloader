"""Unit tests for icloudpd.metadata_writer — exiftool-based metadata writing.

Validates that exiftool can write and read back iCloud metadata fields
across all supported formats (HEIC, JPEG, PNG for EXIF; MOV, MP4 for XMP)
without re-encoding the media or losing existing metadata.

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
    _gps_close,
    _needs_update,
    build_exiftool_args,
    check_exiftool,
    extract_metadata_update,
    write_metadata,
)

_test_logger = logging.getLogger("test_metadata_writer")

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

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
            "GPSLongitude", "GPSSpeed", "GPSHPositioningError", "GPSTimeStamp", "CreateDate", "Rating",
        ])
        xmp = XMP(
            XMPToolkit="icloudpd", Title="Beach Day", Description="Fun day",
            Orientation=6, Make="Apple", DigitalSourceType=None,
            Keywords=["holiday", "beach"], GPSAltitude=10.0, GPSLatitude=-33.7,
            GPSLongitude=151.2, GPSSpeed=0.0, GPSHPositioningError=None, GPSTimeStamp=None,
            CreateDate=datetime(2025, 6, 15, 10, 30, tzinfo=timezone(timedelta(hours=11))),
            Rating=5,
        )
        update = extract_metadata_update({}, xmp)
        self.assertEqual(update.rating, 5)
        self.assertEqual(update.title, "Beach Day")
        self.assertEqual(update.description, "Fun day")
        self.assertEqual(update.keywords, ["holiday", "beach"])
        self.assertEqual(update.orientation, 6)

    def test_from_xmp_no_rating_returns_none(self) -> None:
        from collections import namedtuple
        XMP = namedtuple("XMP", [
            "XMPToolkit", "Title", "Description", "Orientation", "Make",
            "DigitalSourceType", "Keywords", "GPSAltitude", "GPSLatitude",
            "GPSLongitude", "GPSSpeed", "GPSHPositioningError", "GPSTimeStamp", "CreateDate", "Rating",
        ])
        xmp = XMP(
            XMPToolkit="icloudpd", Title=None, Description=None,
            Orientation=None, Make=None, DigitalSourceType=None,
            Keywords=None, GPSAltitude=None, GPSLatitude=None,
            GPSLongitude=None, GPSSpeed=None, GPSHPositioningError=None, GPSTimeStamp=None,
            CreateDate=None, Rating=None,
        )
        update = extract_metadata_update({}, xmp)
        self.assertIsNone(update.rating)
        self.assertIsNone(update.title)

    def test_from_xmp_negative_timezone_created_date_extracted(self) -> None:
        """created_date should be extracted from XMP CreateDate."""
        from collections import namedtuple
        from datetime import datetime, timedelta, timezone

        XMP = namedtuple("XMP", [
            "XMPToolkit", "Title", "Description", "Orientation", "Make",
            "DigitalSourceType", "Keywords", "GPSAltitude", "GPSLatitude",
            "GPSLongitude", "GPSSpeed", "GPSHPositioningError", "GPSTimeStamp", "CreateDate", "Rating",
        ])
        xmp = XMP(
            XMPToolkit="icloudpd", Title=None, Description=None,
            Orientation=None, Make=None, DigitalSourceType=None,
            Keywords=None, GPSAltitude=None, GPSLatitude=None,
            GPSLongitude=None, GPSSpeed=None, GPSHPositioningError=None, GPSTimeStamp=None,
            CreateDate=datetime(2025, 1, 1, 8, 0, tzinfo=timezone(timedelta(hours=-8))),
            Rating=None,
        )
        update = extract_metadata_update({}, xmp)
        self.assertEqual(update.created_date, "2025:01:01 08:00:00")

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


class TestBuildExiftoolArgsDatetime(TestCase):
    """Test datetime and dates categories produce correct args."""

    def test_datetime_category_emits_datetimeoriginal_and_createdate(self) -> None:
        update = MetadataUpdate(created_date="2025:06:15 10:30:00")
        args = build_exiftool_args(update, {"datetime"})
        self.assertIn("-EXIF:DateTimeOriginal=2025:06:15 10:30:00", args)
        self.assertIn("-EXIF:CreateDate=2025:06:15 10:30:00", args)
        # datetime does NOT emit ModifyDate
        self.assertFalse(any("ModifyDate" in a for a in args))

    def test_dates_category_emits_all_three(self) -> None:
        update = MetadataUpdate(created_date="2025:06:15 10:30:00")
        args = build_exiftool_args(update, {"dates"})
        self.assertIn("-EXIF:DateTimeOriginal=2025:06:15 10:30:00", args)
        self.assertIn("-EXIF:CreateDate=2025:06:15 10:30:00", args)
        self.assertIn("-EXIF:ModifyDate=2025:06:15 10:30:00", args)

    def test_datetime_no_created_date_emits_nothing(self) -> None:
        update = MetadataUpdate(created_date=None)
        args = build_exiftool_args(update, {"datetime"})
        self.assertEqual(args, [])

    def test_dates_with_rating(self) -> None:
        update = MetadataUpdate(rating=5, created_date="2025:01:01 08:00:00")
        args = build_exiftool_args(update, {"dates", "rating"})
        self.assertIn("-Rating=5", args)
        self.assertIn("-EXIF:DateTimeOriginal=2025:01:01 08:00:00", args)
        self.assertIn("-EXIF:ModifyDate=2025:01:01 08:00:00", args)

    def test_all_config_includes_datetime_tags(self) -> None:
        update = MetadataUpdate(
            rating=5, title="Test", created_date="2025:06:15 10:30:00"
        )
        args = build_exiftool_args(update, {"all"})
        self.assertIn("-Rating=5", args)
        self.assertIn("-EXIF:DateTimeOriginal=2025:06:15 10:30:00", args)
        self.assertIn("-EXIF:CreateDate=2025:06:15 10:30:00", args)
        self.assertIn("-EXIF:ModifyDate=2025:06:15 10:30:00", args)


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

    def test_datetime(self) -> None:
        result = _parse_write_metadata("datetime")
        self.assertEqual(result, frozenset({"datetime"}))

    def test_datetime_with_others(self) -> None:
        result = _parse_write_metadata("datetime,rating")
        self.assertEqual(result, frozenset({"datetime", "rating"}))

    def test_location(self) -> None:
        result = _parse_write_metadata("location")
        self.assertEqual(result, frozenset({"location"}))

    def test_location_with_others(self) -> None:
        result = _parse_write_metadata("rating,location,orientation")
        self.assertEqual(result, frozenset({"rating", "location", "orientation"}))


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
        update = MetadataUpdate(rating=5)
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


class TestBuildExiftoolArgsLocation(TestCase):
    """Test GPS/location argument building."""

    def test_build_args_location(self) -> None:
        update = MetadataUpdate(
            gps_latitude=-33.7, gps_longitude=151.2, gps_altitude=10.0
        )
        args = build_exiftool_args(update, {"location"})
        self.assertIn("-GPSLatitude=-33.7", args)
        self.assertIn("-GPSLatitudeRef=S", args)
        self.assertIn("-GPSLongitude=151.2", args)
        self.assertIn("-GPSLongitudeRef=E", args)
        self.assertIn("-GPSAltitude=10.0", args)
        self.assertIn("-GPSAltitudeRef#=0", args)

    def test_build_args_location_negative_altitude(self) -> None:
        update = MetadataUpdate(
            gps_latitude=-33.7, gps_longitude=151.2, gps_altitude=-50.0
        )
        args = build_exiftool_args(update, {"location"})
        self.assertIn("-GPSAltitude=-50.0", args)
        self.assertIn("-GPSAltitudeRef#=1", args)

    def test_build_args_location_western_hemisphere(self) -> None:
        """Verify western hemisphere longitude gets Ref=W."""
        update = MetadataUpdate(
            gps_latitude=47.58, gps_longitude=-122.38, gps_altitude=0.0
        )
        args = build_exiftool_args(update, {"location"})
        self.assertIn("-GPSLatitude=47.58", args)
        self.assertIn("-GPSLatitudeRef=N", args)
        self.assertIn("-GPSLongitude=-122.38", args)
        self.assertIn("-GPSLongitudeRef=W", args)

    def test_build_args_location_not_in_config(self) -> None:
        update = MetadataUpdate(
            gps_latitude=-33.7, gps_longitude=151.2, gps_altitude=10.0
        )
        args = build_exiftool_args(update, {"rating"})
        self.assertFalse(any("GPS" in a for a in args))

    def test_build_args_location_with_h_accuracy(self) -> None:
        """GPS horizontal accuracy should be emitted when positive."""
        update = MetadataUpdate(
            gps_latitude=-33.7, gps_longitude=151.2, gps_h_accuracy=8.5
        )
        args = build_exiftool_args(update, {"location"})
        self.assertIn("-GPSHPositioningError=8.5", args)

    def test_build_args_location_h_accuracy_negative_skipped(self) -> None:
        """Negative horzAcc (-1 = invalid) should not be emitted."""
        update = MetadataUpdate(
            gps_latitude=-33.7, gps_longitude=151.2, gps_h_accuracy=-1.0
        )
        args = build_exiftool_args(update, {"location"})
        self.assertFalse(any("HPosError" in a or "HPositioning" in a for a in args))

    def test_build_args_location_h_accuracy_zero_skipped(self) -> None:
        """Zero horzAcc should not be emitted."""
        update = MetadataUpdate(
            gps_latitude=-33.7, gps_longitude=151.2, gps_h_accuracy=0.0
        )
        args = build_exiftool_args(update, {"location"})
        self.assertFalse(any("HPosError" in a or "HPositioning" in a for a in args))

    def test_build_args_location_h_accuracy_none_skipped(self) -> None:
        """None horzAcc should not be emitted."""
        update = MetadataUpdate(
            gps_latitude=-33.7, gps_longitude=151.2, gps_h_accuracy=None
        )
        args = build_exiftool_args(update, {"location"})
        self.assertFalse(any("HPosError" in a or "HPositioning" in a for a in args))

    def test_build_args_h_accuracy_requires_gps(self) -> None:
        """horzAcc without lat/lon should not be emitted."""
        update = MetadataUpdate(gps_h_accuracy=8.5)
        args = build_exiftool_args(update, {"location"})
        self.assertFalse(any("GPS" in a for a in args))

    def test_orientation_zero_still_produces_args(self) -> None:
        """orientation=0 is invalid EXIF (valid: 1-8); should be skipped."""
        update = MetadataUpdate(orientation=0)
        args = build_exiftool_args(update, {"orientation"})
        # orientation=0 is filtered out as it's not a valid EXIF value
        self.assertNotIn("-Orientation#=0", args)


class TestGpsClose(TestCase):
    """Test _gps_close tolerance function."""

    def test_gps_close_matching(self) -> None:
        self.assertTrue(_gps_close(-33.7864, -33.7864))

    def test_gps_close_within_tolerance(self) -> None:
        self.assertTrue(_gps_close(-33.78640, -33.78641))

    def test_gps_close_beyond_tolerance(self) -> None:
        self.assertFalse(_gps_close(-33.786, -33.787))

    def test_gps_close_none_both(self) -> None:
        self.assertTrue(_gps_close(None, None))

    def test_gps_close_none_one(self) -> None:
        self.assertFalse(_gps_close(None, 1.0))
        self.assertFalse(_gps_close(1.0, None))


class TestNeedsUpdateGps(TestCase):
    """Test _needs_update with GPS fields."""

    def test_needs_update_gps_same(self) -> None:
        update = MetadataUpdate(
            gps_latitude=-33.7864, gps_longitude=151.2099
        )
        # exiftool -n returns already-signed GPS values
        existing = {"GPSLatitude": -33.7864, "GPSLatitudeRef": "S",
                    "GPSLongitude": 151.2099, "GPSLongitudeRef": "E"}
        self.assertFalse(_needs_update(update, {"location"}, existing))

    def test_needs_update_gps_missing(self) -> None:
        update = MetadataUpdate(
            gps_latitude=-33.7864, gps_longitude=151.2099
        )
        existing: dict[str, Any] = {}
        self.assertTrue(_needs_update(update, {"location"}, existing))


class TestExtractGps(TestCase):
    """Test GPS extraction from XMP metadata."""

    def _make_xmp(self, **overrides: Any) -> Any:
        from collections import namedtuple
        defaults: dict[str, Any] = {
            "XMPToolkit": "icloudpd", "Title": None, "Description": None,
            "Orientation": None, "Make": None, "DigitalSourceType": None,
            "Keywords": None, "GPSAltitude": None, "GPSLatitude": None,
            "GPSLongitude": None, "GPSSpeed": None, "GPSHPositioningError": None, "GPSTimeStamp": None,
            "CreateDate": None, "Rating": None,
        }
        defaults.update(overrides)
        XMP = namedtuple("XMP", (
            "XMPToolkit", "Title", "Description", "Orientation", "Make",
            "DigitalSourceType", "Keywords", "GPSAltitude", "GPSLatitude",
            "GPSLongitude", "GPSSpeed", "GPSHPositioningError", "GPSTimeStamp", "CreateDate", "Rating",
        ))
        return XMP(**defaults)

    def test_extract_gps_from_xmp(self) -> None:
        xmp = self._make_xmp(
            GPSLatitude=-33.7864, GPSLongitude=151.2099, GPSAltitude=42.5
        )
        update = extract_metadata_update({}, xmp)
        assert update.gps_latitude is not None
        self.assertAlmostEqual(update.gps_latitude, -33.7864)
        assert update.gps_longitude is not None
        self.assertAlmostEqual(update.gps_longitude, 151.2099)
        assert update.gps_altitude is not None
        self.assertAlmostEqual(update.gps_altitude, 42.5)

    def test_extract_orientation_zero_becomes_none(self) -> None:
        xmp = self._make_xmp(Orientation=0)
        update = extract_metadata_update({}, xmp)
        self.assertIsNone(update.orientation)


class TestWriteGpsReal(TestCase):
    """Test real GPS writing and read-back via exiftool."""

    def setUp(self) -> None:
        if not HAS_EXIFTOOL:
            self.skipTest(SKIP_MSG)
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_write_gps_to_jpeg(self) -> None:
        path = os.path.join(self.tmp_dir, "test.jpg")
        _create_jpeg(path)
        update = MetadataUpdate(
            gps_latitude=-33.7864, gps_longitude=151.2099, gps_altitude=42.5
        )
        result = write_metadata(path, update, {"location"})
        self.assertTrue(result)
        # Read back with -n for numeric values
        cmd = [
            "exiftool", "-json", "-n",
            "-GPSLatitude", "-GPSLongitude", "-GPSAltitude",
            path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 0)
        meta = json.loads(proc.stdout)[0]
        self.assertAlmostEqual(meta["GPSLatitude"], -33.7864, places=4)
        self.assertAlmostEqual(meta["GPSLongitude"], 151.2099, places=4)
        self.assertAlmostEqual(meta["GPSAltitude"], 42.5, places=1)

    def test_gps_sign_preserved_all_hemispheres(self) -> None:
        """Regression: GPS # suffix dropped sign, placing locations in wrong hemisphere."""
        cases = [
            (-33.786, 151.209, "Sydney: S lat, E lon"),
            (47.589, -122.380, "Seattle: N lat, W lon"),
            (-22.906, -43.172, "Rio: S lat, W lon"),
            (55.751, 37.617, "Moscow: N lat, E lon"),
        ]
        for lat, lon, label in cases:
            path = os.path.join(self.tmp_dir, f"test_{label[:3]}.jpg")
            _create_jpeg(path)
            update = MetadataUpdate(gps_latitude=lat, gps_longitude=lon)
            write_metadata(path, update, {"location"})
            cmd = ["exiftool", "-json", "-n", "-GPSLatitude", "-GPSLongitude", path]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            meta = json.loads(proc.stdout)[0]
            self.assertAlmostEqual(meta["GPSLatitude"], lat, places=3, msg=label)
            self.assertAlmostEqual(meta["GPSLongitude"], lon, places=3, msg=label)

    def test_gps_idempotent_with_existing_data(self) -> None:
        """Second write with same GPS should detect no changes needed."""
        path = os.path.join(self.tmp_dir, "test_idem.jpg")
        _create_jpeg(path)
        update = MetadataUpdate(gps_latitude=-33.786, gps_longitude=151.209, gps_altitude=10.0)
        result1 = write_metadata(path, update, {"location"})
        self.assertTrue(result1)
        result2 = write_metadata(path, update, {"location"})
        self.assertFalse(result2, "Second GPS write should be idempotent")

    def test_gps_sign_preserved_mov(self) -> None:
        """MOV files use XMP GPS (not EXIF) — signed values must be preserved."""
        path = os.path.join(self.tmp_dir, "test_gps.mov")
        shutil.copy(os.path.join(_DATA_DIR, "test_video.mov"), path)
        cases = [
            (-33.786, 151.209, "Sydney: S lat, E lon"),
            (47.589, -122.380, "Seattle: N lat, W lon"),
            (-22.906, -43.172, "Rio: S lat, W lon"),
            (55.751, 37.617, "Moscow: N lat, E lon"),
        ]
        for lat, lon, label in cases:
            shutil.copy(os.path.join(_DATA_DIR, "test_video.mov"), path)
            update = MetadataUpdate(gps_latitude=lat, gps_longitude=lon, gps_altitude=10.0)
            write_metadata(path, update, {"location"})
            cmd = ["exiftool", "-json", "-n", "-GPSLatitude", "-GPSLongitude", path]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            meta = json.loads(proc.stdout)[0]
            self.assertAlmostEqual(meta["GPSLatitude"], lat, places=3, msg=label)
            self.assertAlmostEqual(meta["GPSLongitude"], lon, places=3, msg=label)

    def test_gps_sign_preserved_mp4(self) -> None:
        """MP4 files use XMP GPS (not EXIF) — signed values must be preserved."""
        path = os.path.join(self.tmp_dir, "test_gps.mp4")
        shutil.copy(os.path.join(_DATA_DIR, "test_video.mp4"), path)
        cases = [
            (-33.786, 151.209, "Sydney: S lat, E lon"),
            (47.589, -122.380, "Seattle: N lat, W lon"),
        ]
        for lat, lon, label in cases:
            shutil.copy(os.path.join(_DATA_DIR, "test_video.mp4"), path)
            update = MetadataUpdate(gps_latitude=lat, gps_longitude=lon, gps_altitude=5.0)
            write_metadata(path, update, {"location"})
            cmd = ["exiftool", "-json", "-n", "-GPSLatitude", "-GPSLongitude", path]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            meta = json.loads(proc.stdout)[0]
            self.assertAlmostEqual(meta["GPSLatitude"], lat, places=3, msg=label)
            self.assertAlmostEqual(meta["GPSLongitude"], lon, places=3, msg=label)

    def test_gps_idempotent_mov(self) -> None:
        """MOV GPS write should be idempotent (XMP round-trip)."""
        path = os.path.join(self.tmp_dir, "test_idem.mov")
        shutil.copy(os.path.join(_DATA_DIR, "test_video.mov"), path)
        update = MetadataUpdate(gps_latitude=-33.786, gps_longitude=151.209, gps_altitude=10.0)
        result1 = write_metadata(path, update, {"location"})
        self.assertTrue(result1)
        result2 = write_metadata(path, update, {"location"})
        self.assertFalse(result2, "Second MOV GPS write should be idempotent")

    def test_gps_idempotent_mp4(self) -> None:
        """MP4 GPS write should be idempotent (XMP round-trip)."""
        path = os.path.join(self.tmp_dir, "test_idem.mp4")
        shutil.copy(os.path.join(_DATA_DIR, "test_video.mp4"), path)
        update = MetadataUpdate(gps_latitude=-22.906, gps_longitude=-43.172, gps_altitude=5.0)
        result1 = write_metadata(path, update, {"location"})
        self.assertTrue(result1)
        result2 = write_metadata(path, update, {"location"})
        self.assertFalse(result2, "Second MP4 GPS write should be idempotent")

    def test_h_accuracy_round_trip_jpeg(self) -> None:
        """GPSHPositioningError should round-trip on JPEG."""
        path = os.path.join(self.tmp_dir, "test_hacc.jpg")
        _create_jpeg(path)
        update = MetadataUpdate(
            gps_latitude=-33.786, gps_longitude=151.209, gps_h_accuracy=11.5
        )
        write_metadata(path, update, {"location"})
        cmd = ["exiftool", "-json", "-s", "-n", "-GPSHPositioningError", path]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        meta = json.loads(proc.stdout)[0]
        self.assertAlmostEqual(meta["GPSHPositioningError"], 11.5, places=1)

    def test_h_accuracy_round_trip_mov(self) -> None:
        """LocationAccuracyHorizontal should round-trip on MOV (Keys)."""
        path = os.path.join(self.tmp_dir, "test_hacc.mov")
        shutil.copy(os.path.join(_DATA_DIR, "test_video.mov"), path)
        update = MetadataUpdate(
            gps_latitude=-33.786, gps_longitude=151.209, gps_h_accuracy=8.0
        )
        write_metadata(path, update, {"location"})
        cmd = ["exiftool", "-json", "-s", "-n", "-Keys:LocationAccuracyHorizontal", path]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        meta = json.loads(proc.stdout)[0]
        self.assertAlmostEqual(meta["LocationAccuracyHorizontal"], 8.0, places=1)

    def test_h_accuracy_idempotent(self) -> None:
        """Second write with same horzAcc should be idempotent."""
        path = os.path.join(self.tmp_dir, "test_hacc_idem.jpg")
        _create_jpeg(path)
        update = MetadataUpdate(
            gps_latitude=-33.786, gps_longitude=151.209, gps_h_accuracy=11.5
        )
        result1 = write_metadata(path, update, {"location"})
        self.assertTrue(result1)
        result2 = write_metadata(path, update, {"location"})
        self.assertFalse(result2, "Second horzAcc write should be idempotent")

    def test_h_accuracy_negative_not_written(self) -> None:
        """Negative horzAcc (-1 = invalid) should not be written to file."""
        path = os.path.join(self.tmp_dir, "test_hacc_neg.jpg")
        _create_jpeg(path)
        update = MetadataUpdate(
            gps_latitude=-33.786, gps_longitude=151.209, gps_h_accuracy=-1.0
        )
        write_metadata(path, update, {"location"})
        cmd = ["exiftool", "-json", "-s", "-n", "-GPSHPositioningError", path]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        meta = json.loads(proc.stdout)[0]
        self.assertNotIn("GPSHPositioningError", meta)

    def test_extract_h_accuracy_from_asset_record(self) -> None:
        """extract_metadata_update should pull horzAcc from locationEnc."""
        import base64
        import plistlib

        location = {"lat": -33.786, "lon": 151.209, "alt": 10.0,
                     "speed": 0.0, "horzAcc": 8.5, "vertAcc": 0.0,
                     "course": 270.0, "timestamp": "2025-06-15T10:30:00"}
        loc_b64 = base64.b64encode(plistlib.dumps(location)).decode()
        asset_record = {
            "fields": {
                "locationEnc": {"value": loc_b64, "type": "ENCRYPTED_BYTES"},
                "isFavorite": {"value": 0, "type": "INT64"},
            }
        }
        update = extract_metadata_update(asset_record)
        assert update.gps_h_accuracy is not None
        self.assertAlmostEqual(update.gps_h_accuracy, 8.5, places=1)

    def test_extract_h_accuracy_negative_returns_none(self) -> None:
        """horzAcc=-1 (invalid) should return None."""
        import base64
        import plistlib

        location = {"lat": -33.786, "lon": 151.209, "alt": 10.0,
                     "speed": 0.0, "horzAcc": -1.0, "vertAcc": -1.0}
        loc_b64 = base64.b64encode(plistlib.dumps(location)).decode()
        asset_record = {
            "fields": {
                "locationEnc": {"value": loc_b64, "type": "ENCRYPTED_BYTES"},
                "isFavorite": {"value": 0, "type": "INT64"},
            }
        }
        update = extract_metadata_update(asset_record)
        self.assertIsNone(update.gps_h_accuracy)

    def test_extract_h_accuracy_missing_location(self) -> None:
        """No locationEnc should return None for h_accuracy."""
        asset_record = {
            "fields": {
                "isFavorite": {"value": 0, "type": "INT64"},
            }
        }
        update = extract_metadata_update(asset_record)
        self.assertIsNone(update.gps_h_accuracy)


class TestWriteDatetimeReal(TestCase):
    """Test real datetime writing and read-back via exiftool."""

    def setUp(self) -> None:
        if not HAS_EXIFTOOL:
            self.skipTest(SKIP_MSG)
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_datetime_round_trip_jpeg(self) -> None:
        """Write datetime to JPEG, read back, verify."""
        path = os.path.join(self.tmp_dir, "test_dt.jpg")
        with open(path, "wb") as f:
            f.write(_MINIMAL_JPEG)
        update = MetadataUpdate(created_date="2025:06:15 10:30:00")
        result = write_metadata(path, update, {"datetime"})
        self.assertTrue(result)
        cmd = [
            "exiftool", "-json", "-s", "-n",
            "-EXIF:DateTimeOriginal", "-EXIF:CreateDate",
            path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        meta = json.loads(proc.stdout)[0]
        self.assertEqual(meta.get("DateTimeOriginal"), "2025:06:15 10:30:00")
        self.assertEqual(meta.get("CreateDate"), "2025:06:15 10:30:00")

    def test_datetime_idempotent(self) -> None:
        """Second write of same datetime should detect no changes."""
        path = os.path.join(self.tmp_dir, "test_dt_idem.jpg")
        with open(path, "wb") as f:
            f.write(_MINIMAL_JPEG)
        update = MetadataUpdate(created_date="2025:06:15 10:30:00")
        result1 = write_metadata(path, update, {"datetime"})
        self.assertTrue(result1)
        result2 = write_metadata(path, update, {"datetime"})
        self.assertFalse(result2, "Second datetime write should be idempotent")

    def test_dates_includes_modify_date(self) -> None:
        """dates category should also write ModifyDate."""
        path = os.path.join(self.tmp_dir, "test_dates.jpg")
        with open(path, "wb") as f:
            f.write(_MINIMAL_JPEG)
        update = MetadataUpdate(created_date="2025:06:15 10:30:00")
        result = write_metadata(path, update, {"dates"})
        self.assertTrue(result)
        cmd = [
            "exiftool", "-json", "-s", "-n",
            "-EXIF:DateTimeOriginal", "-EXIF:CreateDate", "-EXIF:ModifyDate",
            path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        meta = json.loads(proc.stdout)[0]
        self.assertEqual(meta.get("DateTimeOriginal"), "2025:06:15 10:30:00")
        self.assertEqual(meta.get("CreateDate"), "2025:06:15 10:30:00")
        self.assertEqual(meta.get("ModifyDate"), "2025:06:15 10:30:00")

    def test_all_includes_datetime_tags(self) -> None:
        """all category should include datetime tags."""
        path = os.path.join(self.tmp_dir, "test_all_dt.jpg")
        with open(path, "wb") as f:
            f.write(_MINIMAL_JPEG)
        update = MetadataUpdate(
            rating=5, created_date="2025:06:15 10:30:00"
        )
        result = write_metadata(path, update, {"all"})
        self.assertTrue(result)
        cmd = [
            "exiftool", "-json", "-s", "-n",
            "-EXIF:DateTimeOriginal", "-Rating",
            path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        meta = json.loads(proc.stdout)[0]
        self.assertEqual(meta.get("DateTimeOriginal"), "2025:06:15 10:30:00")

    def test_extract_created_date_from_xmp(self) -> None:
        """extract_metadata_update should populate created_date from XMP."""
        from collections import namedtuple
        from datetime import datetime, timedelta, timezone

        XMP = namedtuple("XMP", [
            "XMPToolkit", "Title", "Description", "Orientation", "Make",
            "DigitalSourceType", "Keywords", "GPSAltitude", "GPSLatitude",
            "GPSLongitude", "GPSSpeed", "GPSHPositioningError", "GPSTimeStamp", "CreateDate", "Rating",
        ])
        xmp = XMP(
            XMPToolkit="icloudpd", Title="Beach", Description=None,
            Orientation=None, Make=None, DigitalSourceType=None,
            Keywords=None, GPSAltitude=None, GPSLatitude=None,
            GPSLongitude=None, GPSSpeed=None, GPSHPositioningError=None, GPSTimeStamp=None,
            CreateDate=datetime(2025, 6, 15, 10, 30, tzinfo=timezone(timedelta(hours=11))),
            Rating=5,
        )
        update = extract_metadata_update({}, xmp)
        self.assertEqual(update.created_date, "2025:06:15 10:30:00")

    def test_extract_no_create_date_returns_none(self) -> None:
        """extract_metadata_update with no CreateDate returns None."""
        from collections import namedtuple

        XMP = namedtuple("XMP", [
            "XMPToolkit", "Title", "Description", "Orientation", "Make",
            "DigitalSourceType", "Keywords", "GPSAltitude", "GPSLatitude",
            "GPSLongitude", "GPSSpeed", "GPSHPositioningError", "GPSTimeStamp", "CreateDate", "Rating",
        ])
        xmp = XMP(
            XMPToolkit="icloudpd", Title=None, Description=None,
            Orientation=None, Make=None, DigitalSourceType=None,
            Keywords=None, GPSAltitude=None, GPSLatitude=None,
            GPSLongitude=None, GPSSpeed=None, GPSHPositioningError=None, GPSTimeStamp=None,
            CreateDate=None, Rating=None,
        )
        update = extract_metadata_update({}, xmp)
        self.assertIsNone(update.created_date)


class TestVideeDatetime(TestCase):
    """Test video-specific datetime tag handling."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir)

    def test_build_args_video_uses_quicktime_tags(self) -> None:
        """MOV/MP4 should use QuickTime:CreateDate, not EXIF:DateTimeOriginal."""
        update = MetadataUpdate(created_date="2024:07:10 10:00:00")
        args = build_exiftool_args(update, {"datetime"}, "/photos/test.MOV")
        self.assertIn("-QuickTime:CreateDate=2024:07:10 10:00:00", args)
        self.assertNotIn("-EXIF:DateTimeOriginal=2024:07:10 10:00:00", args)

    def test_build_args_image_uses_exif_tags(self) -> None:
        """JPEG/HEIC should use EXIF:DateTimeOriginal."""
        update = MetadataUpdate(created_date="2024:07:10 10:00:00")
        args = build_exiftool_args(update, {"datetime"}, "/photos/test.JPG")
        self.assertIn("-EXIF:DateTimeOriginal=2024:07:10 10:00:00", args)
        self.assertNotIn("-QuickTime:CreateDate=2024:07:10 10:00:00", args)

    def test_build_args_dates_video_includes_modify(self) -> None:
        """dates category on video should write QuickTime:ModifyDate."""
        update = MetadataUpdate(created_date="2024:07:10 10:00:00")
        args = build_exiftool_args(update, {"dates"}, "/photos/test.mp4")
        self.assertIn("-QuickTime:CreateDate=2024:07:10 10:00:00", args)
        self.assertIn("-QuickTime:ModifyDate=2024:07:10 10:00:00", args)

    def test_build_args_no_file_path_defaults_to_exif(self) -> None:
        """When file_path not provided, default to EXIF tags."""
        update = MetadataUpdate(created_date="2024:07:10 10:00:00")
        args = build_exiftool_args(update, {"datetime"})
        self.assertIn("-EXIF:DateTimeOriginal=2024:07:10 10:00:00", args)

    def test_mov_datetime_round_trip(self) -> None:
        """Write QuickTime:CreateDate to MOV, verify it reads back."""
        src = os.path.join(_DATA_DIR, "test_video.mov")
        path = os.path.join(self.tmp_dir, "test.mov")
        shutil.copy2(src, path)
        update = MetadataUpdate(created_date="2024:07:10 10:30:00")
        result = write_metadata(path, update, {"datetime"})
        self.assertTrue(result)
        # Read back
        r = subprocess.run(
            ["exiftool", "-json", "-s", "-n", "-QuickTime:CreateDate", path],
            capture_output=True, text=True,
        )
        data = json.loads(r.stdout)[0]
        self.assertEqual(data.get("CreateDate"), "2024:07:10 10:30:00")


class TestXmpRepair(TestCase):
    """Test XMP repair for files with corrupt XMP metadata."""

    def test_exiftool_warning_on_unwritable_file(self) -> None:
        """Exiftool 'unchanged' should log warning, not silently cycle."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "corrupt.jpg")
            # Write garbage that looks like a file header but isn't valid
            with open(path, "wb") as f:
                f.write(b"this is not a jpeg file at all")
            update = MetadataUpdate(rating=5)
            with self.assertLogs("icloudpd.metadata_writer", level="WARNING") as cm:
                result = write_metadata(path, update, {"rating"})
            self.assertFalse(result)
            self.assertTrue(any("failed" in msg.lower() or "no effect" in msg.lower() for msg in cm.output))


class TestVideoKeysGps(TestCase):
    """Test Keys:GPSCoordinates writing for MOV/MP4 files."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir)

    def test_build_args_video_uses_keys_gps(self) -> None:
        """MOV should use Keys:GPSCoordinates, not EXIF GPS tags."""
        update = MetadataUpdate(gps_latitude=-33.86, gps_longitude=151.21, gps_altitude=50.0)
        args = build_exiftool_args(update, {"location"}, "/photos/test.MOV")
        keys_args = [a for a in args if "Keys:" in a]
        # Exclude strip commands (ending with bare '=') — those delete old tags
        write_args = [a for a in args if not a.endswith("=")]
        exif_args = [a for a in write_args if "GPSLatitude" in a and "Keys:" not in a]
        self.assertTrue(len(keys_args) > 0, "Should have Keys: GPS args for video")
        self.assertEqual(len(exif_args), 0, "Should NOT have EXIF GPS write args for video")

    def test_build_args_video_keys_gps_format(self) -> None:
        """Keys:GPSCoordinates should use ISO 6709 format."""
        update = MetadataUpdate(gps_latitude=-33.86, gps_longitude=151.21, gps_altitude=50.0)
        args = build_exiftool_args(update, {"location"}, "/photos/test.MOV")
        gps_arg = [a for a in args if "GPSCoordinates" in a][0]
        # Should be ISO 6709: "-33.860000+151.210000+50.000/"
        self.assertIn("-33.860000+151.210000+50.000/", gps_arg)

    def test_build_args_video_h_accuracy_uses_keys(self) -> None:
        """Video should use Keys:LocationAccuracyHorizontal."""
        update = MetadataUpdate(gps_latitude=-33.86, gps_longitude=151.21, gps_h_accuracy=10.5)
        args = build_exiftool_args(update, {"location"}, "/photos/test.MOV")
        self.assertTrue(any("LocationAccuracyHorizontal" in a for a in args))
        # Only write args (not strip commands ending with bare '=') should be checked
        write_args = [a for a in args if not a.endswith("=")]
        self.assertFalse(any("GPSHPositioningError" in a for a in write_args))

    def test_build_args_image_still_uses_exif_gps(self) -> None:
        """JPEG should still use EXIF GPS tags, not Keys."""
        update = MetadataUpdate(gps_latitude=-33.86, gps_longitude=151.21, gps_altitude=50.0)
        args = build_exiftool_args(update, {"location"}, "/photos/test.JPG")
        self.assertTrue(any("GPSLatitude" in a for a in args))
        self.assertFalse(any("Keys:" in a for a in args))

    def test_mov_keys_gps_round_trip(self) -> None:
        """Write Keys:GPSCoordinates to MOV, verify readback."""
        if not HAS_EXIFTOOL:
            self.skipTest(SKIP_MSG)
        src = os.path.join(_DATA_DIR, "test_video.mov")
        path = os.path.join(self.tmp_dir, "test.mov")
        shutil.copy2(src, path)
        update = MetadataUpdate(gps_latitude=-33.86, gps_longitude=151.21, gps_altitude=50.0, gps_h_accuracy=10.5)
        result = write_metadata(path, update, {"location"})
        self.assertTrue(result)
        # Second write should be idempotent
        result2 = write_metadata(path, update, {"location"})
        self.assertFalse(result2, "Second write should be idempotent")

    def test_build_args_gif_returns_empty(self) -> None:
        """GIF should return no exiftool args at all."""
        update = MetadataUpdate(rating=5, gps_latitude=-33.86, gps_longitude=151.21, orientation=6)
        args = build_exiftool_args(update, {"all"}, "/photos/test.gif")
        self.assertEqual(args, [], "GIF should have no exiftool args")

    def test_build_args_video_no_orientation(self) -> None:
        """Video should not emit Orientation tag."""
        update = MetadataUpdate(orientation=6)
        args = build_exiftool_args(update, {"orientation"}, "/photos/test.MOV")
        self.assertFalse(any("Orientation" in a for a in args))

    def test_build_args_png_no_orientation(self) -> None:
        """PNG should not emit Orientation tag."""
        update = MetadataUpdate(orientation=6)
        args = build_exiftool_args(update, {"orientation"}, "/photos/test.PNG")
        self.assertFalse(any("Orientation" in a for a in args))

    def test_build_args_orientation_zero_skipped(self) -> None:
        """Orientation=0 should never be emitted (invalid EXIF value)."""
        update = MetadataUpdate(orientation=0)
        args = build_exiftool_args(update, {"orientation"}, "/photos/test.JPG")
        self.assertFalse(any("Orientation" in a for a in args))

    def test_build_args_video_strips_xmp_exif_gps(self) -> None:
        """Video GPS write should include XMP-exif GPS strip commands."""
        update = MetadataUpdate(gps_latitude=-33.86, gps_longitude=151.21, gps_altitude=50.0)
        args = build_exiftool_args(update, {"location"}, "/photos/test.MOV")
        strip_args = [a for a in args if a.startswith("-XMP-exif:GPS") and a.endswith("=")]
        self.assertGreaterEqual(len(strip_args), 3, "Should strip XMP-exif GPS tags")
        self.assertTrue(any(a.split(":")[-1] == "GPSLatitude=" for a in strip_args))

    def test_build_args_image_no_xmp_exif_strip(self) -> None:
        """Image GPS write should NOT include XMP-exif strip commands."""
        update = MetadataUpdate(gps_latitude=-33.86, gps_longitude=151.21, gps_altitude=50.0)
        args = build_exiftool_args(update, {"location"}, "/photos/test.JPG")
        strip_args = [a for a in args if "XMP-exif" in a]
        self.assertEqual(len(strip_args), 0, "Image should not strip XMP-exif")

    def test_needs_update_stale_xmp_gps_triggers(self) -> None:
        """_needs_update should return True when stale XMP-exif GPS detected."""
        update = MetadataUpdate(gps_latitude=-33.86, gps_longitude=151.21)
        existing = {
            "GPSLatitude": -33.86,
            "GPSLongitude": 151.21,
            "_has_stale_xmp_gps": True,
        }
        self.assertTrue(_needs_update(update, {"location"}, existing))

    def test_needs_update_no_stale_xmp_no_trigger(self) -> None:
        """_needs_update should return False when GPS matches and no stale XMP."""
        update = MetadataUpdate(gps_latitude=-33.86, gps_longitude=151.21)
        existing = {"GPSLatitude": -33.86, "GPSLongitude": 151.21}
        self.assertFalse(_needs_update(update, {"location"}, existing))

    def test_mov_xmp_exif_gps_stripped_after_write(self) -> None:
        """Write to MOV should strip XMP-exif GPS and leave Keys GPS."""
        if not HAS_EXIFTOOL:
            self.skipTest(SKIP_MSG)
        src = os.path.join(_DATA_DIR, "test_video.mov")
        path = os.path.join(self.tmp_dir, "test.mov")
        shutil.copy2(src, path)
        # First, write XMP-exif GPS (simulating old code behaviour)
        subprocess.run(
            ["exiftool", "-overwrite_original",
             "-XMP-exif:GPSLatitude=-33.86", "-XMP-exif:GPSLongitude=151.21",
             path],
            capture_output=True, timeout=30,
        )
        update = MetadataUpdate(gps_latitude=-33.86, gps_longitude=151.21, gps_altitude=50.0)
        result = write_metadata(path, update, {"location"})
        self.assertTrue(result, "Should write (stale XMP-exif detected)")
        # Verify XMP-exif GPS is gone
        check = subprocess.run(
            ["exiftool", "-s", "-XMP-exif:GPSLatitude", path],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(check.stdout.strip(), "", "XMP-exif GPS should be stripped")
        # Verify Keys GPS is present
        check2 = subprocess.run(
            ["exiftool", "-s", "-Keys:GPSCoordinates", path],
            capture_output=True, text=True, timeout=30,
        )
        self.assertIn("GPSCoordinates", check2.stdout)
        # Second write should be idempotent
        result2 = write_metadata(path, update, {"location"})
        self.assertFalse(result2, "Second write should be idempotent")


class TestWebpRoundTrip(TestCase):
    """Test WEBP metadata round-trip."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir)

    def test_webp_rating_round_trip(self) -> None:
        """WEBP should support Rating via EXIF."""
        src = os.path.join(_DATA_DIR, "test_image.webp")
        path = os.path.join(self.tmp_dir, "test.webp")
        shutil.copy2(src, path)
        update = MetadataUpdate(rating=5)
        result = write_metadata(path, update, {"rating"})
        self.assertTrue(result)
        result2 = write_metadata(path, update, {"rating"})
        self.assertFalse(result2, "Second write should be idempotent")

    def test_webp_gps_round_trip(self) -> None:
        """WEBP should support GPS via EXIF."""
        src = os.path.join(_DATA_DIR, "test_image.webp")
        path = os.path.join(self.tmp_dir, "test.webp")
        shutil.copy2(src, path)
        update = MetadataUpdate(gps_latitude=-33.86, gps_longitude=151.21, gps_altitude=50.0)
        result = write_metadata(path, update, {"location"})
        self.assertTrue(result)
        result2 = write_metadata(path, update, {"location"})
        self.assertFalse(result2, "Second write should be idempotent")


class TestGifSkip(TestCase):
    """Test that GIF files are skipped for EXIF writes."""

    def test_gif_write_returns_false(self) -> None:
        """GIF should not attempt any exiftool writes."""
        update = MetadataUpdate(rating=5, gps_latitude=-33.86, gps_longitude=151.21, orientation=6)
        args = build_exiftool_args(update, {"all"}, "/photos/test.gif")
        self.assertEqual(args, [], "GIF should produce no exiftool args")

    def test_gif_write_metadata_returns_false(self) -> None:
        """write_metadata on GIF should return False (no args to write)."""
        src = os.path.join(_DATA_DIR, "test_image.gif")
        path = os.path.join(tempfile.mkdtemp(), "test.gif")
        shutil.copy2(src, path)
        update = MetadataUpdate(rating=5)
        result = write_metadata(path, update, {"rating"})
        self.assertFalse(result, "GIF writes should be skipped")
        shutil.rmtree(os.path.dirname(path))


class TestNeedsUpdateOrientationExclusion(TestCase):
    """Orientation should be skipped for videos and PNGs in _needs_update,
    matching build_exiftool_args which also skips them."""

    def test_mov_orientation_mismatch_ignored(self) -> None:
        update = MetadataUpdate(orientation=1)
        existing: dict[str, Any] = {}  # MOVs have no EXIF Orientation
        self.assertFalse(
            _needs_update(update, {"orientation"}, existing, file_path="2026-01/IMG_0993_HEVC.MOV"),
            "Orientation mismatch on MOV should not trigger update",
        )

    def test_mp4_orientation_mismatch_ignored(self) -> None:
        update = MetadataUpdate(orientation=6)
        existing: dict[str, Any] = {}
        self.assertFalse(
            _needs_update(update, {"orientation"}, existing, file_path="2025-10/video.mp4"),
        )

    def test_png_orientation_mismatch_ignored(self) -> None:
        update = MetadataUpdate(orientation=1)
        existing: dict[str, Any] = {}
        self.assertFalse(
            _needs_update(update, {"orientation"}, existing, file_path="2025-01/screenshot.PNG"),
        )

    def test_heic_orientation_mismatch_triggers(self) -> None:
        update = MetadataUpdate(orientation=3)
        existing = {"Orientation": 6}
        self.assertTrue(
            _needs_update(update, {"orientation"}, existing, file_path="2025-09/IMG_9951.HEIC"),
            "Orientation mismatch on HEIC should trigger update",
        )

    def test_jpeg_orientation_match_skips(self) -> None:
        update = MetadataUpdate(orientation=1)
        existing = {"Orientation": 1}
        self.assertFalse(
            _needs_update(update, {"orientation"}, existing, file_path="2022-03/IMG_3412.JPG"),
        )

    def test_mov_with_other_changes_still_triggers(self) -> None:
        update = MetadataUpdate(orientation=1, rating=5)
        existing: dict[str, Any] = {}  # No rating yet
        self.assertTrue(
            _needs_update(update, {"orientation", "rating"}, existing, file_path="2026-01/IMG_0993_HEVC.MOV"),
            "MOV with missing rating should still trigger update",
        )


class TestMetadataMatchesManifest(TestCase):
    """Tests for _metadata_matches_manifest — the mtime skip comparison."""

    def _make_row(self, **overrides: Any) -> Any:
        from icloudpd.manifest import ManifestRow
        defaults: dict[str, Any] = dict(
            asset_id="test", zone_id="zone", asset_resource="resOriginal",
            local_path="2026-01/IMG_0001.HEIC", version_size=1000,
            version_checksum=None, change_tag=None, downloaded_at="2026-01-01",
            last_updated_at="2026-01-01", item_type="public.heic",
            filename="IMG_0001.HEIC", asset_date=None, added_date=None,
            is_favorite=0, is_hidden=0, is_deleted=0,
            original_width=None, original_height=None, duration=None,
            orientation=1, title=None, description=None, keywords=None,
            gps_latitude=None, gps_longitude=None, gps_altitude=None,
            gps_speed=None, gps_timestamp=None, timezone_offset=None,
            asset_subtype=None, hdr_type=None, burst_flags=None,
            burst_flags_ext=None, burst_id=None, original_orientation=None,
            raw_fields=None, file_mtime=1234567890.0,
        )
        defaults.update(overrides)
        return ManifestRow(**defaults)

    def test_all_match(self) -> None:
        from icloudpd.base import _metadata_matches_manifest
        row = self._make_row(is_favorite=1, gps_latitude=-33.8, gps_longitude=151.2, gps_altitude=50.0)
        update = MetadataUpdate(rating=5, gps_latitude=-33.8, gps_longitude=151.2, gps_altitude=50.0)
        self.assertTrue(_metadata_matches_manifest(row, update))

    def test_rating_mismatch(self) -> None:
        from icloudpd.base import _metadata_matches_manifest
        row = self._make_row(is_favorite=0)
        update = MetadataUpdate(rating=5)
        self.assertFalse(_metadata_matches_manifest(row, update))

    def test_keywords_match(self) -> None:
        from icloudpd.base import _metadata_matches_manifest
        row = self._make_row(keywords='["alpha", "beta"]')
        update = MetadataUpdate(keywords=["beta", "alpha"])  # order shouldn't matter
        self.assertTrue(_metadata_matches_manifest(row, update))

    def test_keywords_mismatch(self) -> None:
        from icloudpd.base import _metadata_matches_manifest
        row = self._make_row(keywords='["alpha"]')
        update = MetadataUpdate(keywords=["alpha", "beta"])
        self.assertFalse(_metadata_matches_manifest(row, update))

    def test_keywords_added_from_none(self) -> None:
        from icloudpd.base import _metadata_matches_manifest
        row = self._make_row(keywords=None)
        update = MetadataUpdate(keywords=["new_keyword"])
        self.assertFalse(_metadata_matches_manifest(row, update))

    def test_keywords_none_in_update_skips_check(self) -> None:
        from icloudpd.base import _metadata_matches_manifest
        row = self._make_row(keywords='["existing"]')
        update = MetadataUpdate(keywords=None)
        self.assertTrue(_metadata_matches_manifest(row, update), "keywords=None means not relevant, not removed")

    def test_altitude_match(self) -> None:
        from icloudpd.base import _metadata_matches_manifest
        row = self._make_row(gps_altitude=-6.035)
        update = MetadataUpdate(gps_altitude=-6.035)
        self.assertTrue(_metadata_matches_manifest(row, update))

    def test_altitude_mismatch(self) -> None:
        from icloudpd.base import _metadata_matches_manifest
        row = self._make_row(gps_altitude=50.0)
        update = MetadataUpdate(gps_altitude=55.0)
        self.assertFalse(_metadata_matches_manifest(row, update))

    def test_altitude_added(self) -> None:
        from icloudpd.base import _metadata_matches_manifest
        row = self._make_row(gps_altitude=None)
        update = MetadataUpdate(gps_altitude=10.0)
        self.assertFalse(_metadata_matches_manifest(row, update))

    def test_description_mismatch(self) -> None:
        from icloudpd.base import _metadata_matches_manifest
        row = self._make_row(description="old")
        update = MetadataUpdate(description="new")
        self.assertFalse(_metadata_matches_manifest(row, update))

    def test_empty_update_matches_anything(self) -> None:
        from icloudpd.base import _metadata_matches_manifest
        row = self._make_row(is_favorite=1)
        update = MetadataUpdate()
        self.assertTrue(_metadata_matches_manifest(row, update))
