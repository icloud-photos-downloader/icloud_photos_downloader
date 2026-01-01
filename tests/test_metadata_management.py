"""Tests for metadata management"""

import logging
import os
import piexif
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree

"""Tests for metadata merging logic"""

class TestMergeMetadata(unittest.TestCase):
    """Test metadata merging with various policies"""

    def test_merge_empty_dicts(self):
        """Merge two empty dicts returns empty dict"""
        from icloudpd.metadata_management import merge_metadata

        result = merge_metadata(existing={}, desired={}, overwrite=False)

        self.assertEqual(result, {})

    def test_merge_no_existing_no_overwrite(self):
        """With no existing data, desired values are written"""
        from icloudpd.metadata_management import merge_metadata

        existing = {}
        desired = {"rating": 5, "datetime": "2024:01:15 10:30:00"}

        result = merge_metadata(existing, desired, overwrite=False)

        self.assertEqual(result["rating"], 5)
        self.assertEqual(result["datetime"], "2024:01:15 10:30:00")

    def test_merge_existing_values_no_overwrite_preserves(self):
        """Without overwrite, existing values are preserved"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3, "datetime": "2023:12:01 09:00:00"}
        desired = {"rating": 5, "datetime": "2024:01:15 10:30:00"}

        result = merge_metadata(existing, desired, overwrite=False)

        # Should keep existing values
        self.assertEqual(result["rating"], 3)
        self.assertEqual(result["datetime"], "2023:12:01 09:00:00")

    def test_merge_existing_values_with_overwrite_replaces(self):
        """With overwrite, desired values replace existing"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3, "datetime": "2023:12:01 09:00:00"}
        desired = {"rating": 5, "datetime": "2024:01:15 10:30:00"}

        result = merge_metadata(existing, desired, overwrite=True)

        # Should use desired values
        self.assertEqual(result["rating"], 5)
        self.assertEqual(result["datetime"], "2024:01:15 10:30:00")

    def test_merge_partial_existing_no_overwrite_adds_missing(self):
        """Without overwrite, missing fields are added from desired"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3}
        desired = {"rating": 5, "datetime": "2024:01:15 10:30:00"}

        result = merge_metadata(existing, desired, overwrite=False)

        # Keeps existing rating, adds new datetime
        self.assertEqual(result["rating"], 3)
        self.assertEqual(result["datetime"], "2024:01:15 10:30:00")

    def test_merge_partial_existing_with_overwrite_replaces_all(self):
        """With overwrite, all desired values replace existing"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3}
        desired = {"rating": 5, "datetime": "2024:01:15 10:30:00"}

        result = merge_metadata(existing, desired, overwrite=True)

        # Replaces rating, adds datetime
        self.assertEqual(result["rating"], 5)
        self.assertEqual(result["datetime"], "2024:01:15 10:30:00")

    def test_merge_preserves_existing_unknown_fields(self):
        """Merge preserves fields in existing that aren't in desired"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3, "custom_field": "preserve me", "another": 42}
        desired = {"rating": 5}

        result = merge_metadata(existing, desired, overwrite=False)

        # Known field preserved, unknown fields also preserved
        self.assertEqual(result["rating"], 3)
        self.assertEqual(result["custom_field"], "preserve me")
        self.assertEqual(result["another"], 42)

    def test_merge_with_overwrite_preserves_existing_unknown_fields(self):
        """Merge with overwrite still preserves unknown fields from existing"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3, "custom_field": "preserve me"}
        desired = {"rating": 5}

        result = merge_metadata(existing, desired, overwrite=True)

        # Known field overwritten, unknown field preserved
        self.assertEqual(result["rating"], 5)
        self.assertEqual(result["custom_field"], "preserve me")

    def test_merge_none_values_in_desired_no_overwrite(self):
        """None values in desired don't overwrite existing without overwrite flag"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3, "datetime": "2023:12:01 09:00:00"}
        desired = {"rating": None, "datetime": "2024:01:15 10:30:00"}

        result = merge_metadata(existing, desired, overwrite=False)

        # Existing rating preserved (desired is None), datetime preserved
        self.assertEqual(result["rating"], 3)
        self.assertEqual(result["datetime"], "2023:12:01 09:00:00")

    def test_merge_none_values_in_desired_with_overwrite_skips(self):
        """None values in desired are skipped even with overwrite"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3, "datetime": "2023:12:01 09:00:00"}
        desired = {"rating": None, "datetime": "2024:01:15 10:30:00"}

        result = merge_metadata(existing, desired, overwrite=True)

        # Rating preserved (None in desired), datetime overwritten
        self.assertEqual(result["rating"], 3)
        self.assertEqual(result["datetime"], "2024:01:15 10:30:00")

    def test_merge_fields_to_update_only_rating(self):
        """With fields_to_update, only specified fields are merged"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3, "datetime": "2023:12:01 09:00:00"}
        desired = {"rating": 5, "datetime": "2024:01:15 10:30:00"}

        result = merge_metadata(existing, desired, overwrite=False, fields_to_update={"rating"})

        # Only rating is considered for merging, datetime from existing preserved
        self.assertEqual(result["rating"], 3)  # Not overwritten (overwrite=False)
        self.assertEqual(result["datetime"], "2023:12:01 09:00:00")

    def test_merge_fields_to_update_only_rating_with_overwrite(self):
        """With fields_to_update and overwrite, only specified field is overwritten"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3, "datetime": "2023:12:01 09:00:00"}
        desired = {"rating": 5, "datetime": "2024:01:15 10:30:00"}

        result = merge_metadata(existing, desired, overwrite=True, fields_to_update={"rating"})

        # Rating overwritten, datetime ignored (not in fields_to_update)
        self.assertEqual(result["rating"], 5)
        self.assertEqual(result["datetime"], "2023:12:01 09:00:00")

    def test_merge_fields_to_update_adds_missing_field(self):
        """With fields_to_update, can add missing field if not in existing"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"datetime": "2023:12:01 09:00:00"}
        desired = {"rating": 5, "title": "Photo"}

        result = merge_metadata(existing, desired, overwrite=False, fields_to_update={"rating"})

        # Rating added (not in existing), title ignored, datetime preserved
        self.assertEqual(result["rating"], 5)
        self.assertNotIn("title", result)
        self.assertEqual(result["datetime"], "2023:12:01 09:00:00")

    def test_merge_fields_to_update_empty_set_does_nothing(self):
        """With empty fields_to_update, nothing from desired is merged"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3, "datetime": "2023:12:01 09:00:00"}
        desired = {"rating": 5, "datetime": "2024:01:15 10:30:00"}

        result = merge_metadata(existing, desired, overwrite=True, fields_to_update=set())

        # Nothing should change
        self.assertEqual(result["rating"], 3)
        self.assertEqual(result["datetime"], "2023:12:01 09:00:00")

    def test_merge_preserves_xml_tree_from_existing(self):
        """Merge preserves special _xml_tree field from existing for XMP"""
        from icloudpd.metadata_management import merge_metadata
        from xml.etree import ElementTree

        xml_tree = ElementTree.Element("test")
        existing = {"rating": 3, "_xml_tree": xml_tree}
        desired = {"rating": 5}

        result = merge_metadata(existing, desired, overwrite=False)

        # Should preserve the XML tree reference
        self.assertIs(result["_xml_tree"], xml_tree)
        self.assertEqual(result["rating"], 3)

    def test_merge_complex_scenario_process_existing_favorites(self):
        """Complex scenario: --process-existing-favorites workflow"""
        from icloudpd.metadata_management import merge_metadata

        # Scenario: JPEG has rating=3, we want to set rating=5 for favorite
        # But without --metadata-overwrite, should preserve existing
        existing_exif = {"rating": 3, "datetime": "2023:12:01 09:00:00"}
        desired_rating = {"rating": 5}

        result = merge_metadata(
            existing_exif, desired_rating, overwrite=False, fields_to_update={"rating"}
        )

        # Should preserve existing rating
        self.assertEqual(result["rating"], 3)
        self.assertEqual(result["datetime"], "2023:12:01 09:00:00")

    def test_merge_complex_scenario_with_metadata_overwrite(self):
        """Complex scenario: --process-existing-favorites with --metadata-overwrite"""
        from icloudpd.metadata_management import merge_metadata

        # Scenario: JPEG has rating=3, we want to set rating=5 for favorite
        # With --metadata-overwrite, should replace
        existing_exif = {"rating": 3, "datetime": "2023:12:01 09:00:00"}
        desired_rating = {"rating": 5}

        result = merge_metadata(
            existing_exif, desired_rating, overwrite=True, fields_to_update={"rating"}
        )

        # Should overwrite rating, preserve datetime
        self.assertEqual(result["rating"], 5)
        self.assertEqual(result["datetime"], "2023:12:01 09:00:00")

"""Tests for metadata reading functions (EXIF and XMP)"""

class TestReadExifMetadata(unittest.TestCase):
    """Test reading EXIF metadata from photos"""

    def setUp(self):
        self.logger = logging.getLogger("test")
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_jpeg_with_exif(self, filename: str, exif_dict: dict) -> str:
        """Helper to create a JPEG with specific EXIF data"""
        path = os.path.join(self.temp_dir, filename)

        # Create a minimal JPEG by dumping EXIF and using a tiny base image
        # This works around piexif.insert limitations
        import io

        # If no EXIF dict provided, create minimal one
        if not exif_dict:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
        else:
            # Ensure required IFDs exist
            if "Exif" not in exif_dict:
                exif_dict["Exif"] = {}
            if "GPS" not in exif_dict:
                exif_dict["GPS"] = {}
            if "1st" not in exif_dict:
                exif_dict["1st"] = {}
            if "thumbnail" not in exif_dict:
                exif_dict["thumbnail"] = None

        # Dump EXIF bytes
        exif_bytes = piexif.dump(exif_dict)

        # Create minimal JPEG with EXIF marker
        # SOI + APP1 (EXIF) + minimal image data + EOI
        app1_marker = b'\xff\xe1'  # APP1 marker
        app1_size = (len(exif_bytes) + 2).to_bytes(2, byteorder='big')

        jpeg_with_exif = (
            b'\xff\xd8'  # SOI
            + app1_marker
            + app1_size
            + exif_bytes
            # Minimal JPEG image data (1x1 pixel)
            + b'\xff\xdb\x00C\x00\x03\x02\x02\x03\x02\x02\x03\x03\x03\x03\x04\x03\x03\x04\x05\x08\x05\x05\x04\x04\x05\n\x07\x07\x06\x08\x0c\n\x0c\x0c\x0b\n\x0b\x0b\r\x0e\x12\x10\r\x0e\x11\x0e\x0b\x0b\x10\x16\x10\x11\x13\x14\x15\x15\x15\x0c\x0f\x17\x18\x16\x14\x18\x12\x14\x15\x14'
            + b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'
            + b'\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08'
            + b'\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            + b'\xff\xda\x00\x08\x01\x01\x00\x00?\x00\x7f\x00'
            + b'\xff\xd9'  # EOI
        )

        with open(path, "wb") as f:
            f.write(jpeg_with_exif)

        return path

    def test_read_exif_with_rating_and_datetime(self):
        """Read EXIF with both rating and datetime"""
        from icloudpd.metadata_management import read_exif_metadata

        exif_dict = {
            "0th": {18246: 5},  # Rating = 5
            "Exif": {36867: b"2024:01:15 10:30:00"},  # DateTimeOriginal
        }
        path = self._create_jpeg_with_exif("test.jpg", exif_dict)

        result = read_exif_metadata(self.logger, path)

        self.assertEqual(result.get("rating"), 5)
        self.assertEqual(result.get("datetime"), b"2024:01:15 10:30:00")

    def test_read_exif_with_only_rating(self):
        """Read EXIF with only rating, no datetime"""
        from icloudpd.metadata_management import read_exif_metadata

        exif_dict = {
            "0th": {18246: 3},  # Rating = 3
        }
        path = self._create_jpeg_with_exif("test.jpg", exif_dict)

        result = read_exif_metadata(self.logger, path)

        self.assertEqual(result.get("rating"), 3)
        self.assertIsNone(result.get("datetime"))

    def test_read_exif_with_only_datetime(self):
        """Read EXIF with only datetime, no rating"""
        from icloudpd.metadata_management import read_exif_metadata

        exif_dict = {
            "Exif": {36867: b"2024:01:15 10:30:00"},
        }
        path = self._create_jpeg_with_exif("test.jpg", exif_dict)

        result = read_exif_metadata(self.logger, path)

        self.assertIsNone(result.get("rating"))
        self.assertEqual(result.get("datetime"), b"2024:01:15 10:30:00")

    def test_read_exif_empty(self):
        """Read EXIF from file with no EXIF data"""
        from icloudpd.metadata_management import read_exif_metadata

        path = self._create_jpeg_with_exif("test.jpg", {})

        result = read_exif_metadata(self.logger, path)

        # Should return empty dict, not crash
        self.assertIsInstance(result, dict)
        self.assertIsNone(result.get("rating"))
        self.assertIsNone(result.get("datetime"))

    def test_read_exif_corrupt_file(self):
        """Read EXIF from corrupt file returns empty dict"""
        from icloudpd.metadata_management import read_exif_metadata

        path = os.path.join(self.temp_dir, "corrupt.jpg")
        with open(path, "wb") as f:
            f.write(b"not a jpeg")

        result = read_exif_metadata(self.logger, path)

        # Should return empty dict on error, not crash
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 0)

    def test_read_exif_nonexistent_file(self):
        """Read EXIF from nonexistent file returns empty dict"""
        from icloudpd.metadata_management import read_exif_metadata

        path = os.path.join(self.temp_dir, "nonexistent.jpg")

        result = read_exif_metadata(self.logger, path)

        # Should return empty dict on error, not crash
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 0)

    def test_read_exif_preserves_unknown_fields(self):
        """Read EXIF preserves fields we don't explicitly care about"""
        from icloudpd.metadata_management import read_exif_metadata

        exif_dict = {
            "0th": {
                18246: 4,  # Rating
                271: b"Canon",  # Make (unknown field we should preserve)
            },
            "Exif": {
                36867: b"2024:01:15 10:30:00",  # DateTimeOriginal
                37377: (5, 1),  # ShutterSpeed (unknown field) - SRational type
            },
        }
        path = self._create_jpeg_with_exif("test.jpg", exif_dict)

        result = read_exif_metadata(self.logger, path)

        # Should have our known fields
        self.assertEqual(result.get("rating"), 4)
        self.assertEqual(result.get("datetime"), b"2024:01:15 10:30:00")

        # Should preserve unknown fields in the raw EXIF dict
        # We'll verify this by re-reading with piexif
        exif_readback = piexif.load(path)
        self.assertEqual(exif_readback["0th"][271], b"Canon")
        self.assertEqual(exif_readback["Exif"][37377], (5, 1))


class TestReadXmpMetadata(unittest.TestCase):
    """Test reading XMP sidecar metadata"""

    def setUp(self):
        self.logger = logging.getLogger("test")
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_xmp_file(self, filename: str, xmp_content: str) -> str:
        """Helper to create XMP file with content"""
        path = os.path.join(self.temp_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(xmp_content)
        return path

    def test_read_xmp_with_rating(self):
        """Read XMP with rating field"""
        from icloudpd.metadata_management import read_xmp_metadata

        xmp_content = """<?xml version="1.0" encoding="utf-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="icloudpd 1.0">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/">
      <xmp:Rating>5</xmp:Rating>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>"""

        path = self._create_xmp_file("test.xmp", xmp_content)
        result = read_xmp_metadata(self.logger, path)

        self.assertEqual(result.get("rating"), 5)
        self.assertEqual(result.get("xmptk"), "icloudpd 1.0")

    def test_read_xmp_with_multiple_fields(self):
        """Read XMP with rating, datetime, and title"""
        from icloudpd.metadata_management import read_xmp_metadata

        xmp_content = """<?xml version="1.0" encoding="utf-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="icloudpd 1.0">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/">
      <xmp:Rating>4</xmp:Rating>
      <xmp:CreateDate>2024-01-15T10:30:00+00:00</xmp:CreateDate>
    </rdf:Description>
    <rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">
      <dc:title>My Photo</dc:title>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>"""

        path = self._create_xmp_file("test.xmp", xmp_content)
        result = read_xmp_metadata(self.logger, path)

        self.assertEqual(result.get("rating"), 4)
        self.assertEqual(result.get("datetime"), "2024-01-15T10:30:00+00:00")
        self.assertEqual(result.get("title"), "My Photo")

    def test_read_xmp_no_rating(self):
        """Read XMP without rating field"""
        from icloudpd.metadata_management import read_xmp_metadata

        xmp_content = """<?xml version="1.0" encoding="utf-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="icloudpd 1.0">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">
      <dc:title>My Photo</dc:title>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>"""

        path = self._create_xmp_file("test.xmp", xmp_content)
        result = read_xmp_metadata(self.logger, path)

        self.assertIsNone(result.get("rating"))
        self.assertEqual(result.get("title"), "My Photo")

    def test_read_xmp_file_not_exists(self):
        """Read XMP when file doesn't exist returns empty dict"""
        from icloudpd.metadata_management import read_xmp_metadata

        path = os.path.join(self.temp_dir, "nonexistent.xmp")
        result = read_xmp_metadata(self.logger, path)

        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 0)

    def test_read_xmp_corrupt_xml(self):
        """Read XMP with corrupt XML returns empty dict"""
        from icloudpd.metadata_management import read_xmp_metadata

        xmp_content = """<?xml version="1.0"?>
<broken><xml>no closing tag"""

        path = self._create_xmp_file("corrupt.xmp", xmp_content)
        result = read_xmp_metadata(self.logger, path)

        # Should return empty dict on parse error, not crash
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 0)

    def test_read_xmp_preserves_unknown_fields(self):
        """Read XMP preserves unknown fields for later writing"""
        from icloudpd.metadata_management import read_xmp_metadata

        xmp_content = """<?xml version="1.0" encoding="utf-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe Lightroom">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/">
      <xmp:Rating>3</xmp:Rating>
      <xmp:CreatorTool>Adobe Lightroom</xmp:CreatorTool>
    </rdf:Description>
    <rdf:Description rdf:about="" xmlns:lr="http://ns.adobe.com/lightroom/1.0/">
      <lr:privateMetadata>sensitive data</lr:privateMetadata>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>"""

        path = self._create_xmp_file("test.xmp", xmp_content)
        result = read_xmp_metadata(self.logger, path)

        # Should read known fields
        self.assertEqual(result.get("rating"), 3)
        self.assertEqual(result.get("xmptk"), "Adobe Lightroom")

        # Unknown fields should be preserved in the result dict
        # We need to store the raw XML tree for later merging
        self.assertIn("_xml_tree", result)  # Store parsed tree for later


class TestCanWriteXmpFile(unittest.TestCase):
    """Test XMP write permission checking"""

    def setUp(self):
        self.logger = logging.getLogger("test")
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_xmp_file(self, filename: str, xmptk: str) -> str:
        """Helper to create XMP file with specific xmptk"""
        path = os.path.join(self.temp_dir, filename)
        xmp_content = f"""<?xml version="1.0" encoding="utf-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="{xmptk}">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  </rdf:RDF>
</x:xmpmeta>"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(xmp_content)
        return path

    def test_can_write_nonexistent_file(self):
        """Can write to XMP file that doesn't exist"""
        from icloudpd.metadata_management import can_write_xmp_file

        path = os.path.join(self.temp_dir, "new.xmp")
        result = can_write_xmp_file(self.logger, path)

        self.assertTrue(result)

    def test_can_write_icloudpd_file(self):
        """Can write to XMP file created by icloudpd"""
        from icloudpd.metadata_management import can_write_xmp_file

        path = self._create_xmp_file("test.xmp", "icloudpd 1.0+abc123")
        result = can_write_xmp_file(self.logger, path)

        self.assertTrue(result)

    def test_cannot_write_external_tool_file(self):
        """Cannot write to XMP file created by external tool"""
        from icloudpd.metadata_management import can_write_xmp_file

        path = self._create_xmp_file("test.xmp", "Adobe Lightroom")
        result = can_write_xmp_file(self.logger, path)

        self.assertFalse(result)

    def test_cannot_write_another_external_tool(self):
        """Cannot write to XMP file created by another external tool"""
        from icloudpd.metadata_management import can_write_xmp_file

        path = self._create_xmp_file("test.xmp", "Darktable")
        result = can_write_xmp_file(self.logger, path)

        self.assertFalse(result)

    def test_can_write_empty_xmptk(self):
        """Can write to XMP file with empty xmptk (treat as new)"""
        from icloudpd.metadata_management import can_write_xmp_file

        path = self._create_xmp_file("test.xmp", "")
        result = can_write_xmp_file(self.logger, path)

        # Empty xmptk should allow writing
        self.assertTrue(result)

    def test_cannot_write_corrupt_xml(self):
        """Cannot write to corrupt XMP file (safety)"""
        from icloudpd.metadata_management import can_write_xmp_file

        path = os.path.join(self.temp_dir, "corrupt.xmp")
        with open(path, "w") as f:
            f.write("not xml")

        result = can_write_xmp_file(self.logger, path)

        # Should return False on parse error to avoid overwriting corrupt file
        self.assertFalse(result)


"""Tests for metadata writing functions (EXIF and XMP)"""

class TestWriteExifMetadata(unittest.TestCase):
    """Test writing EXIF metadata to photos"""

    def setUp(self):
        self.logger = logging.getLogger("test")
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_jpeg_with_exif(self, filename: str, exif_dict: dict) -> str:
        """Helper to create a JPEG with specific EXIF data"""
        path = os.path.join(self.temp_dir, filename)

        # Create a minimal JPEG by dumping EXIF and using a tiny base image
        # This works around piexif.insert limitations
        import io

        # If no EXIF dict provided, create minimal one
        if not exif_dict:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
        else:
            # Ensure required IFDs exist
            if "Exif" not in exif_dict:
                exif_dict["Exif"] = {}
            if "GPS" not in exif_dict:
                exif_dict["GPS"] = {}
            if "1st" not in exif_dict:
                exif_dict["1st"] = {}
            if "thumbnail" not in exif_dict:
                exif_dict["thumbnail"] = None

        # Dump EXIF bytes
        exif_bytes = piexif.dump(exif_dict)

        # Create minimal JPEG with EXIF marker
        # SOI + APP1 (EXIF) + minimal image data + EOI
        app1_marker = b'\xff\xe1'  # APP1 marker
        app1_size = (len(exif_bytes) + 2).to_bytes(2, byteorder='big')

        jpeg_with_exif = (
            b'\xff\xd8'  # SOI
            + app1_marker
            + app1_size
            + exif_bytes
            # Minimal JPEG image data (1x1 pixel)
            + b'\xff\xdb\x00C\x00\x03\x02\x02\x03\x02\x02\x03\x03\x03\x03\x04\x03\x03\x04\x05\x08\x05\x05\x04\x04\x05\n\x07\x07\x06\x08\x0c\n\x0c\x0c\x0b\n\x0b\x0b\r\x0e\x12\x10\r\x0e\x11\x0e\x0b\x0b\x10\x16\x10\x11\x13\x14\x15\x15\x15\x0c\x0f\x17\x18\x16\x14\x18\x12\x14\x15\x14'
            + b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'
            + b'\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08'
            + b'\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            + b'\xff\xda\x00\x08\x01\x01\x00\x00?\x00\x7f\x00'
            + b'\xff\xd9'  # EOI
        )

        with open(path, "wb") as f:
            f.write(jpeg_with_exif)

        return path

    def test_write_exif_rating_only(self):
        """Write only rating to EXIF"""
        from icloudpd.metadata_management import write_exif_metadata

        path = self._create_jpeg_with_exif("test.jpg", {})
        metadata = {"rating": 5}

        write_exif_metadata(self.logger, path, metadata, dry_run=False)

        # Verify rating was written
        exif_dict = piexif.load(path)
        self.assertEqual(exif_dict["0th"][18246], 5)

    def test_write_exif_datetime_only(self):
        """Write only datetime to EXIF"""
        from icloudpd.metadata_management import write_exif_metadata

        path = self._create_jpeg_with_exif("test.jpg", {})
        metadata = {"datetime": "2024:01:15 10:30:00"}

        write_exif_metadata(self.logger, path, metadata, dry_run=False)

        # Verify datetime was written to all three tags
        exif_dict = piexif.load(path)
        self.assertEqual(exif_dict["0th"][306], b"2024:01:15 10:30:00")
        self.assertEqual(exif_dict["Exif"][36867], b"2024:01:15 10:30:00")
        self.assertEqual(exif_dict["Exif"][36868], b"2024:01:15 10:30:00")

    def test_write_exif_rating_and_datetime(self):
        """Write both rating and datetime to EXIF"""
        from icloudpd.metadata_management import write_exif_metadata

        path = self._create_jpeg_with_exif("test.jpg", {})
        metadata = {"rating": 4, "datetime": "2024:01:15 10:30:00"}

        write_exif_metadata(self.logger, path, metadata, dry_run=False)

        # Verify both were written
        exif_dict = piexif.load(path)
        self.assertEqual(exif_dict["0th"][18246], 4)
        self.assertEqual(exif_dict["Exif"][36867], b"2024:01:15 10:30:00")

    def test_write_exif_preserves_existing_unknown_fields(self):
        """Writing EXIF preserves existing unknown fields"""
        from icloudpd.metadata_management import write_exif_metadata

        # Create JPEG with existing unknown EXIF fields
        existing_exif = {
            "0th": {271: b"Canon", 272: b"EOS R5"},  # Make, Model
            "Exif": {37377: (5, 1)},  # ShutterSpeed - SRational type
        }
        path = self._create_jpeg_with_exif("test.jpg", existing_exif)

        # Write only rating
        metadata = {"rating": 5}
        write_exif_metadata(self.logger, path, metadata, dry_run=False)

        # Verify rating written and unknown fields preserved
        exif_dict = piexif.load(path)
        self.assertEqual(exif_dict["0th"][18246], 5)  # Rating added
        self.assertEqual(exif_dict["0th"][271], b"Canon")  # Make preserved
        self.assertEqual(exif_dict["0th"][272], b"EOS R5")  # Model preserved
        self.assertEqual(exif_dict["Exif"][37377], (5, 1))  # ShutterSpeed preserved

    def test_write_exif_updates_existing_rating(self):
        """Writing EXIF updates existing rating value"""
        from icloudpd.metadata_management import write_exif_metadata

        # Create JPEG with existing rating
        existing_exif = {"0th": {18246: 3}}
        path = self._create_jpeg_with_exif("test.jpg", existing_exif)

        # Update rating
        metadata = {"rating": 5}
        write_exif_metadata(self.logger, path, metadata, dry_run=False)

        # Verify rating was updated
        exif_dict = piexif.load(path)
        self.assertEqual(exif_dict["0th"][18246], 5)

    def test_write_exif_empty_metadata_does_nothing(self):
        """Writing empty metadata dict doesn't crash"""
        from icloudpd.metadata_management import write_exif_metadata

        path = self._create_jpeg_with_exif("test.jpg", {})
        metadata = {}

        # Should not crash
        write_exif_metadata(self.logger, path, metadata, dry_run=False)

    def test_write_exif_corrupt_file_handles_gracefully(self):
        """Writing to corrupt file is handled gracefully"""
        from icloudpd.metadata_management import write_exif_metadata

        path = os.path.join(self.temp_dir, "corrupt.jpg")
        with open(path, "wb") as f:
            f.write(b"not a jpeg")

        metadata = {"rating": 5}

        # Should not crash, just log error
        write_exif_metadata(self.logger, path, metadata, dry_run=False)

        # File should still exist (not deleted on error)
        self.assertTrue(os.path.exists(path))

    def test_write_exif_none_values_skipped(self):
        """None values in metadata are skipped"""
        from icloudpd.metadata_management import write_exif_metadata

        path = self._create_jpeg_with_exif("test.jpg", {})
        metadata = {"rating": None, "datetime": "2024:01:15 10:30:00"}

        write_exif_metadata(self.logger, path, metadata, dry_run=False)

        # Only datetime should be written
        exif_dict = piexif.load(path)
        self.assertNotIn(18246, exif_dict.get("0th", {}))  # No rating
        self.assertEqual(exif_dict["Exif"][36867], b"2024:01:15 10:30:00")


class TestWriteXmpMetadata(unittest.TestCase):
    """Test writing XMP sidecar metadata"""

    def setUp(self):
        self.logger = logging.getLogger("test")
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_xmp_file(self, filename: str, xmp_content: str) -> str:
        """Helper to create XMP file"""
        path = os.path.join(self.temp_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(xmp_content)
        return path

    def _parse_xmp(self, path: str) -> ElementTree.Element:
        """Parse XMP file and return root element"""
        return ElementTree.parse(path).getroot()

    def test_write_xmp_creates_new_file_with_rating(self):
        """Writing XMP creates new file when it doesn't exist"""
        from icloudpd.metadata_management import write_xmp_metadata

        xmp_path = os.path.join(self.temp_dir, "test.xmp")
        metadata = {"rating": 5}

        write_xmp_metadata(self.logger, xmp_path, metadata, dry_run=False)

        # Verify file was created
        self.assertTrue(os.path.exists(xmp_path))

        # Verify rating is in the file
        root = self._parse_xmp(xmp_path)
        rating_elem = root.find(".//{http://ns.adobe.com/xap/1.0/}Rating")
        self.assertIsNotNone(rating_elem)
        self.assertEqual(rating_elem.text, "5")

    def test_write_xmp_creates_new_file_with_multiple_fields(self):
        """Writing XMP creates new file with multiple metadata fields"""
        from icloudpd.metadata_management import write_xmp_metadata

        xmp_path = os.path.join(self.temp_dir, "test.xmp")
        metadata = {
            "rating": 4,
            "title": "My Photo",
            "datetime": "2024-01-15T10:30:00+00:00",
        }

        write_xmp_metadata(self.logger, xmp_path, metadata, dry_run=False)

        # Verify all fields are in the file
        root = self._parse_xmp(xmp_path)
        rating_elem = root.find(".//{http://ns.adobe.com/xap/1.0/}Rating")
        self.assertEqual(rating_elem.text, "4")

        title_elem = root.find(".//{http://purl.org/dc/elements/1.1/}title")
        self.assertEqual(title_elem.text, "My Photo")

        datetime_elem = root.find(".//{http://ns.adobe.com/xap/1.0/}CreateDate")
        self.assertEqual(datetime_elem.text, "2024-01-15T10:30:00+00:00")

    def test_write_xmp_updates_existing_icloudpd_file_rating(self):
        """Writing XMP updates rating in existing icloudpd-created file"""
        from icloudpd.metadata_management import write_xmp_metadata

        # Create existing XMP with rating=3
        xmp_content = """<?xml version="1.0" encoding="utf-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="icloudpd 1.0">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/">
      <xmp:Rating>3</xmp:Rating>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>"""

        xmp_path = self._create_xmp_file("test.xmp", xmp_content)
        metadata = {"rating": 5}

        write_xmp_metadata(self.logger, xmp_path, metadata, dry_run=False)

        # Verify rating was updated
        root = self._parse_xmp(xmp_path)
        rating_elem = root.find(".//{http://ns.adobe.com/xap/1.0/}Rating")
        self.assertEqual(rating_elem.text, "5")

    def test_write_xmp_preserves_existing_unknown_fields(self):
        """Writing XMP preserves unknown fields in existing file"""
        from icloudpd.metadata_management import write_xmp_metadata

        # Create XMP with unknown fields
        xmp_content = """<?xml version="1.0" encoding="utf-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="icloudpd 1.0">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/">
      <xmp:Rating>3</xmp:Rating>
      <xmp:CreatorTool>Some Tool</xmp:CreatorTool>
    </rdf:Description>
    <rdf:Description rdf:about="" xmlns:custom="http://custom.namespace/">
      <custom:field>preserve me</custom:field>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>"""

        xmp_path = self._create_xmp_file("test.xmp", xmp_content)
        metadata = {"rating": 5}

        write_xmp_metadata(self.logger, xmp_path, metadata, dry_run=False)

        # Verify rating updated and unknown fields preserved
        root = self._parse_xmp(xmp_path)
        rating_elem = root.find(".//{http://ns.adobe.com/xap/1.0/}Rating")
        self.assertEqual(rating_elem.text, "5")

        creator_elem = root.find(".//{http://ns.adobe.com/xap/1.0/}CreatorTool")
        self.assertEqual(creator_elem.text, "Some Tool")

        custom_elem = root.find(".//{http://custom.namespace/}field")
        self.assertEqual(custom_elem.text, "preserve me")

    def test_write_xmp_adds_new_field_to_existing_file(self):
        """Writing XMP adds new field to existing file"""
        from icloudpd.metadata_management import write_xmp_metadata

        # Create XMP without rating
        xmp_content = """<?xml version="1.0" encoding="utf-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="icloudpd 1.0">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">
      <dc:title>My Photo</dc:title>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>"""

        xmp_path = self._create_xmp_file("test.xmp", xmp_content)
        metadata = {"rating": 5}

        write_xmp_metadata(self.logger, xmp_path, metadata, dry_run=False)

        # Verify rating added and title preserved
        root = self._parse_xmp(xmp_path)
        rating_elem = root.find(".//{http://ns.adobe.com/xap/1.0/}Rating")
        self.assertEqual(rating_elem.text, "5")

        title_elem = root.find(".//{http://purl.org/dc/elements/1.1/}title")
        self.assertEqual(title_elem.text, "My Photo")

    def test_write_xmp_dry_run_does_not_write(self):
        """Dry run mode doesn't actually write XMP file"""
        from icloudpd.metadata_management import write_xmp_metadata

        xmp_path = os.path.join(self.temp_dir, "test.xmp")
        metadata = {"rating": 5}

        write_xmp_metadata(self.logger, xmp_path, metadata, dry_run=True)

        # File should not exist
        self.assertFalse(os.path.exists(xmp_path))

    def test_write_xmp_dry_run_does_not_update_existing(self):
        """Dry run mode doesn't update existing XMP file"""
        from icloudpd.metadata_management import write_xmp_metadata

        # Create XMP with rating=3
        xmp_content = """<?xml version="1.0" encoding="utf-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="icloudpd 1.0">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/">
      <xmp:Rating>3</xmp:Rating>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>"""

        xmp_path = self._create_xmp_file("test.xmp", xmp_content)
        metadata = {"rating": 5}

        write_xmp_metadata(self.logger, xmp_path, metadata, dry_run=True)

        # Rating should still be 3
        root = self._parse_xmp(xmp_path)
        rating_elem = root.find(".//{http://ns.adobe.com/xap/1.0/}Rating")
        self.assertEqual(rating_elem.text, "3")

    def test_write_xmp_none_values_skipped(self):
        """None values in metadata are not written"""
        from icloudpd.metadata_management import write_xmp_metadata

        xmp_path = os.path.join(self.temp_dir, "test.xmp")
        metadata = {"rating": None, "title": "My Photo"}

        write_xmp_metadata(self.logger, xmp_path, metadata, dry_run=False)

        # Only title should be written
        root = self._parse_xmp(xmp_path)
        rating_elem = root.find(".//{http://ns.adobe.com/xap/1.0/}Rating")
        self.assertIsNone(rating_elem)

        title_elem = root.find(".//{http://purl.org/dc/elements/1.1/}title")
        self.assertEqual(title_elem.text, "My Photo")

    def test_write_xmp_empty_metadata_creates_minimal_file(self):
        """Writing empty metadata creates minimal valid XMP"""
        from icloudpd.metadata_management import write_xmp_metadata

        xmp_path = os.path.join(self.temp_dir, "test.xmp")
        metadata = {}

        write_xmp_metadata(self.logger, xmp_path, metadata, dry_run=False)

        # Should create valid XMP with no metadata fields
        self.assertTrue(os.path.exists(xmp_path))
        root = self._parse_xmp(xmp_path)
        self.assertIsNotNone(root)

    def test_write_xmp_sets_icloudpd_xmptk(self):
        """New XMP file has icloudpd xmptk attribute"""
        from icloudpd.metadata_management import write_xmp_metadata

        xmp_path = os.path.join(self.temp_dir, "test.xmp")
        metadata = {"rating": 5}

        write_xmp_metadata(self.logger, xmp_path, metadata, dry_run=False)

        # Verify xmptk attribute
        root = self._parse_xmp(xmp_path)
        xmptk = root.attrib.get("{adobe:ns:meta/}xmptk")
        self.assertIsNotNone(xmptk)
        self.assertTrue(xmptk.startswith("icloudpd"))


class TestBuildMetadata(unittest.TestCase):
    """Test build_metadata function from XMP sidecar"""

    def test_build_metadata(self) -> None:
        from datetime import datetime
        from typing import Any, Dict
        from foundation import version_info
        from icloudpd.metadata_management import build_metadata

        assetRecordStub: Dict[str, Dict[str, Any]] = {
            "fields": {
                "captionEnc": {"value": "VGl0bGUgSGVyZQ==", "type": "ENCRYPTED_BYTES"},
                "extendedDescEnc": {"value": "Q2FwdGlvbiBIZXJl", "type": "ENCRYPTED_BYTES"},
                "adjustmentSimpleDataEnc": {
                    "type": "ENCRYPTED_BYTES",
                    "value": "PU67DoIwFP2XMzemBRKxo5Mummiig3G4QJEaCqS9sBD+XRDjdnLeI5xhKogJeoSjwMYfjH1VDB3LKBE/7m4LrqATGUcCrbemYWLbNtDpJFC23hHfjA9fSgkMKz42ZbsUZ72ti1PvMuOhESX7nYIAdd0/g61SG7lRqZyFkFfG0cUMdhWlQFcTLzOz01F+vmKepeLdB3bzlwD9eE4f",
                },
                "assetSubtypeV2": {"value": 2, "type": "INT64"},
                "keywordsEnc": {
                    "value": "YnBsaXN0MDChAVxzb21lIGtleXdvcmQICgAAAAAAAAEBAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAAX",
                    "type": "ENCRYPTED_BYTES",
                },
                "locationEnc": {
                    "value": "YnBsaXN0MDDYAQIDBAUGBwgJCQoLCQwNCVZjb3Vyc2VVc3BlZWRTYWx0U2xvbld2ZXJ0QWNjU2xhdFl0aW1lc3RhbXBXaG9yekFjYyMAAAAAAAAAACNAdG9H6P0fpCNAWL2oZnRhiiNAMtKmTC+DezMAAAAAAAAAAAgZICYqLjY6RExVXmdwAAAAAAAAAQEAAAAAAAAADgAAAAAAAAAAAAAAAAAAAHk=",
                    "type": "ENCRYPTED_BYTES",
                },
                "assetDate": {"value": 1532951050176, "type": "TIMESTAMP"},
                "isHidden": {"value": 0, "type": "INT64"},
                "isDeleted": {"value": 0, "type": "INT64"},
                "isFavorite": {"value": 0, "type": "INT64"},
            },
        }

        # Test full metadata record
        metadata = build_metadata(assetRecordStub)
        self.assertEqual(
            metadata["XMPToolkit"], "icloudpd " + version_info.version + "+" + version_info.commit_sha
        )
        self.assertEqual(metadata["Title"], "Title Here")
        self.assertEqual(metadata["Description"], "Caption Here")
        self.assertEqual(metadata["Orientation"], 8)
        self.assertNotIn("Make", metadata)
        self.assertNotIn("DigitalSourceType", metadata)
        self.assertEqual(metadata["Keywords"], ["some keyword"])
        self.assertEqual(metadata["GPSAltitude"], 326.9550561797753)
        self.assertEqual(metadata["GPSLatitude"], 18.82285)
        self.assertEqual(metadata["GPSLongitude"], 98.96340333333333)
        self.assertEqual(metadata["GPSSpeed"], 0.0)
        self.assertEqual(
            metadata["GPSTimeStamp"],
            datetime.strptime("2001:01:01 00:00:00.000000+00:00", "%Y:%m:%d %H:%M:%S.%f%z").replace(
                tzinfo=None
            ),
        )
        self.assertEqual(
            metadata["CreateDate"],
            datetime.strptime("2018:07:30 11:44:10.176000+00:00", "%Y:%m:%d %H:%M:%S.%f%z"),
        )
        self.assertNotIn("Rating", metadata)

        # Some files have different types of adjustmentSimpleDataEnc which are not supported

        # - a binary plist - starting with 'bplist00', example is taken from a video file
        assetRecordStub["fields"]["adjustmentSimpleDataEnc"]["value"] = (
            "YnBsaXN0MDDRAQJac2xvd01vdGlvbtIDBAUWV3JlZ2lvbnNUcmF0ZaEG0QcIWXRpbWVSYW5nZdIJCgsUVXN0YXJ0WGR1cmF0aW9u1AwNDg8QERITVWZsYWdzVXZhbHVlWXRpbWVzY2FsZVVlcG9jaBABER8cEQJYEADUDA0ODxAVEhMRBAQiPoAAAAgLFhsjKCotNzxCS1RaYGpwcnV4eoOGAAAAAAAAAQEAAAAAAAAAFwAAAAAAAAAAAAAAAAAAAIs="
        )
        metadata = build_metadata(assetRecordStub)
        self.assertNotIn("Orientation", metadata)

        # - a CRDT (Conflict-free Replicated Data Types) - starting with 'crdt', example is taken from a photo with a drawing on top
        assetRecordStub["fields"]["adjustmentSimpleDataEnc"]["value"] = (
            "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"
        )
        metadata = build_metadata(assetRecordStub)
        self.assertNotIn("Orientation", metadata)

        # Test Screenshot Tagging
        assetRecordStub["fields"]["assetSubtypeV2"]["value"] = 3
        metadata = build_metadata(assetRecordStub)
        self.assertEqual(metadata["Make"], "Screenshot")
        self.assertEqual(metadata["DigitalSourceType"], "screenCapture")

        # Test Favorites
        assetRecordStub["fields"]["isFavorite"]["value"] = 1
        metadata = build_metadata(assetRecordStub)
        self.assertEqual(metadata["Rating"], 5)

        # Test favorites not present
        del assetRecordStub["fields"]["isFavorite"]
        metadata = build_metadata(assetRecordStub)
        self.assertNotIn("Rating", metadata)

        # Test Deleted
        assetRecordStub["fields"]["isDeleted"]["value"] = 1
        metadata = build_metadata(assetRecordStub)
        self.assertEqual(metadata["Rating"], -1)

        # Test Hidden
        assetRecordStub["fields"]["isDeleted"]["value"] = 0
        assetRecordStub["fields"]["isHidden"]["value"] = 1
        metadata = build_metadata(assetRecordStub)
        self.assertEqual(metadata["Rating"], -1)

        # Test locationEnc in xml format, not binary format
        # Note, this value is taken from a real photo, see https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/1059
        assetRecordStub["fields"]["locationEnc"]["value"] = (
            "PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiIHN0YW5kYWxvbmU9InllcyI/Pgo8IURPQ1RZUEUgcGxpc3QgUFVCTElDICItLy9BcHBsZS8vRFREIFBMSVNUIDEuMC8vRU4iICJodHRwOi8vd3d3LmFwcGxlLmNvbS9EVERzL1Byb3BlcnR5TGlzdC0xLjAuZHRkIj4KPHBsaXN0IHZlcnNpb249IjEuMCI+Cgk8ZGljdD4KCQk8a2V5PnZlcnRBY2M8L2tleT4KCQk8cmVhbD4wLjA8L3JlYWw+CgoJCTxrZXk+YWx0PC9rZXk+CgkJPHJlYWw+MC4wPC9yZWFsPgoKCQk8a2V5Pmxvbjwva2V5PgoJCTxyZWFsPi0xMjIuODgxNTY2NjY2NjY2NjY8L3JlYWw+CgoJCTxrZXk+bGF0PC9rZXk+CgkJPHJlYWw+NTAuMDk0MTgzMzMzMzMzMzM8L3JlYWw+CgoJCTxrZXk+dGltZXN0YW1wPC9rZXk+CgkJPGRhdGU+MjAyMC0wMi0yOVQxODozNTo0OVo8L2RhdGU+CgoJPC9kaWN0Pgo8L3BsaXN0Pg=="
        )
        metadata = build_metadata(assetRecordStub)
        self.assertEqual(
            (
                metadata["GPSAltitude"],
                metadata["GPSLongitude"],
                metadata["GPSLatitude"],
                metadata["GPSTimeStamp"],
            ),
            (
                0.0,
                -122.88156666666666,
                50.09418333333333,
                datetime.fromisoformat("2020-02-29T18:35:49"),
            ),
        )


if __name__ == "__main__":
    unittest.main()
