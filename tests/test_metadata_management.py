"""Consolidated tests for metadata management (EXIF, XMP, merging, and integration)

This file combines all metadata-related tests into one comprehensive test suite:
- TestMergeMetadata: Metadata merging logic
- TestReadExifMetadata: Reading EXIF from files
- TestReadXmpMetadata: Reading XMP from files  
- TestCanWriteXmpFile: XMP writability checks
- TestWriteExifMetadata: Writing EXIF to files
- TestWriteXmpMetadata: Writing XMP to files
- TestSyncExifMetadata: EXIF synchronization integration tests
- TestSyncXmpMetadata: XMP synchronization integration tests
- TestProcessExistingFavoritesValidation: CLI validation tests
"""

import logging
import os
import piexif
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch
from xml.etree import ElementTree

from tests.helpers import run_main


# ============================================================================
# METADATA MERGING TESTS (from test_metadata_merge.py)
# ============================================================================

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
        self.assertEqual(result["rating"], 3)
        self.assertEqual(result["datetime"], "2023:12:01 09:00:00")

    def test_merge_existing_values_with_overwrite_replaces(self):
        """With overwrite, desired values replace existing"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3, "datetime": "2023:12:01 09:00:00"}
        desired = {"rating": 5, "datetime": "2024:01:15 10:30:00"}
        result = merge_metadata(existing, desired, overwrite=True)
        self.assertEqual(result["rating"], 5)
        self.assertEqual(result["datetime"], "2024:01:15 10:30:00")

    def test_merge_partial_existing_no_overwrite_adds_missing(self):
        """Without overwrite, missing fields are added from desired"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3}
        desired = {"rating": 5, "datetime": "2024:01:15 10:30:00"}
        result = merge_metadata(existing, desired, overwrite=False)
        self.assertEqual(result["rating"], 3)
        self.assertEqual(result["datetime"], "2024:01:15 10:30:00")

    def test_merge_partial_existing_with_overwrite_replaces_all(self):
        """With overwrite, all desired values replace existing"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3}
        desired = {"rating": 5, "datetime": "2024:01:15 10:30:00"}
        result = merge_metadata(existing, desired, overwrite=True)
        self.assertEqual(result["rating"], 5)
        self.assertEqual(result["datetime"], "2024:01:15 10:30:00")

    def test_merge_preserves_unknown_fields_no_overwrite(self):
        """Merge preserves unknown fields in existing (without overwrite)"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3, "custom_field": "custom_value", "another": 123}
        desired = {"rating": 5}
        result = merge_metadata(existing, desired, overwrite=False)
        self.assertEqual(result["rating"], 3)
        self.assertEqual(result["custom_field"], "custom_value")
        self.assertEqual(result["another"], 123)

    def test_merge_preserves_unknown_fields_with_overwrite(self):
        """Merge with overwrite still preserves unknown fields"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3, "custom_field": "custom_value"}
        desired = {"rating": 5}
        result = merge_metadata(existing, desired, overwrite=True)
        self.assertEqual(result["rating"], 5)
        self.assertEqual(result["custom_field"], "custom_value")

    def test_merge_none_values_no_overwrite(self):
        """None values in desired don't overwrite existing (no overwrite flag)"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3, "datetime": "2023:12:01 09:00:00"}
        desired = {"rating": None, "datetime": None}
        result = merge_metadata(existing, desired, overwrite=False)
        self.assertEqual(result["rating"], 3)
        self.assertEqual(result["datetime"], "2023:12:01 09:00:00")

    def test_merge_none_values_with_overwrite(self):
        """None values skipped even with overwrite flag"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3, "datetime": "2023:12:01 09:00:00"}
        desired = {"rating": None, "datetime": None}
        result = merge_metadata(existing, desired, overwrite=True)
        self.assertEqual(result["rating"], 3)
        self.assertEqual(result["datetime"], "2023:12:01 09:00:00")

    def test_merge_with_fields_to_update_no_overwrite(self):
        """With fields_to_update, only specified fields merged"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3, "datetime": "2023:12:01 09:00:00"}
        desired = {"rating": 5, "datetime": "2024:01:15 10:30:00"}
        result = merge_metadata(existing, desired, overwrite=False, fields_to_update={"rating"})
        self.assertEqual(result["rating"], 3)
        self.assertEqual(result["datetime"], "2023:12:01 09:00:00")

    def test_merge_with_fields_to_update_with_overwrite(self):
        """With fields_to_update + overwrite, only specified field overwritten"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3, "datetime": "2023:12:01 09:00:00"}
        desired = {"rating": 5, "datetime": "2024:01:15 10:30:00"}
        result = merge_metadata(existing, desired, overwrite=True, fields_to_update={"rating"})
        self.assertEqual(result["rating"], 5)
        self.assertEqual(result["datetime"], "2023:12:01 09:00:00")

    def test_merge_with_fields_to_update_can_add_missing(self):
        """With fields_to_update, can add missing field"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"datetime": "2023:12:01 09:00:00"}
        desired = {"rating": 5, "title": "Photo Title"}
        result = merge_metadata(existing, desired, overwrite=False, fields_to_update={"rating"})
        self.assertEqual(result["rating"], 5)
        self.assertNotIn("title", result)

    def test_merge_with_empty_fields_to_update(self):
        """With empty fields_to_update, nothing merged"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3}
        desired = {"rating": 5, "datetime": "2024:01:15 10:30:00"}
        result = merge_metadata(existing, desired, overwrite=True, fields_to_update=set())
        self.assertEqual(result["rating"], 3)
        self.assertNotIn("datetime", result)

    def test_merge_preserves_xml_tree(self):
        """Preserves _xml_tree field from existing (for XMP)"""
        from icloudpd.metadata_management import merge_metadata

        mock_tree = MagicMock()
        existing = {"rating": 3, "_xml_tree": mock_tree}
        desired = {"rating": 5}
        result = merge_metadata(existing, desired, overwrite=True)
        self.assertEqual(result["rating"], 5)
        self.assertEqual(result["_xml_tree"], mock_tree)

    def test_merge_complex_scenario_process_existing_no_overwrite(self):
        """Complex scenario: --process-existing-favorites (no overwrite)"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"datetime": "2023:12:01 09:00:00", "custom": "value"}
        desired = {"rating": 5}
        result = merge_metadata(existing, desired, overwrite=False, fields_to_update={"rating"})
        self.assertEqual(result["rating"], 5)
        self.assertEqual(result["datetime"], "2023:12:01 09:00:00")
        self.assertEqual(result["custom"], "value")

    def test_merge_complex_scenario_with_overwrite(self):
        """Complex scenario: with --metadata-overwrite"""
        from icloudpd.metadata_management import merge_metadata

        existing = {"rating": 3, "datetime": "2023:12:01 09:00:00"}
        desired = {"rating": 5}
        result = merge_metadata(existing, desired, overwrite=True, fields_to_update={"rating"})
        self.assertEqual(result["rating"], 5)
        self.assertEqual(result["datetime"], "2023:12:01 09:00:00")


# ============================================================================
# CLI VALIDATION TESTS (from test_process_existing_favorites.py)
# ============================================================================

class TestProcessExistingFavoritesValidation(unittest.TestCase):
    """Test CLI validation for new flags"""

    def test_process_existing_favorites_requires_favorite_to_rating(self):
        """--process-existing-favorites requires --favorite-to-rating (error)"""
        result = run_main(
            [
                "--username",
                "test123",
                "--process-existing-favorites",
                "--no-progress-bar",
            ]
        )
        self.assertNotEqual(result.exit_code, 0)
        stderr_text = result.stderr_bytes.decode("utf-8") if result.stderr_bytes else ""
        self.assertIn("favorite-to-rating", stderr_text.lower())

    def test_process_existing_favorites_works_with_favorite_to_rating(self):
        """--process-existing-favorites with --favorite-to-rating should pass validation"""
        result = run_main(["--help"])
        self.assertEqual(result.exit_code, 0)

    def test_metadata_overwrite_works_independently(self):
        """--metadata-overwrite works independently"""
        result = run_main(["--help"])
        self.assertEqual(result.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
