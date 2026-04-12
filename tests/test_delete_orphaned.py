"""Tests for delete_orphaned functionality."""

import logging
import os

from icloudpd.base import delete_orphaned
from icloudpd.manifest import ManifestDB


def _setup_manifest_with_files(
    tmpdir: str,
    entries: list[dict[str, str]],
) -> ManifestDB:
    """Create a manifest DB with entries and corresponding files on disk."""
    manifest = ManifestDB(tmpdir)
    manifest.open()
    for entry in entries:
        asset_id = entry["asset_id"]
        zone_id = entry.get("zone_id", "PrimarySync")
        local_path = entry["local_path"]
        asset_resource = entry.get("asset_resource", "resOriginal")
        # Create the file on disk
        full_path = os.path.join(tmpdir, local_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write("test content")
        # Create XMP sidecar
        with open(full_path + ".xmp", "w") as f:
            f.write("<xmp>test</xmp>")
        # Add to manifest
        manifest.upsert(
            asset_id=asset_id,
            zone_id=zone_id,
            local_path=local_path,
            version_size=1,
            asset_resource=asset_resource,
        )
    manifest.flush()
    return manifest


class TestFindOrphaned:
    """Tests for ManifestDB.find_orphaned()."""

    def test_no_orphans(self, tmp_path: object) -> None:
        tmpdir = str(tmp_path)
        manifest = _setup_manifest_with_files(tmpdir, [
            {"asset_id": "A1", "local_path": "2024-01/photo1.HEIC"},
            {"asset_id": "A2", "local_path": "2024-01/photo2.HEIC"},
        ])
        seen = {"A1", "A2"}
        orphans = manifest.find_orphaned(seen)
        assert len(orphans) == 0
        manifest.close()

    def test_all_orphaned(self, tmp_path: object) -> None:
        tmpdir = str(tmp_path)
        manifest = _setup_manifest_with_files(tmpdir, [
            {"asset_id": "A1", "local_path": "2024-01/photo1.HEIC"},
            {"asset_id": "A2", "local_path": "2024-01/photo2.HEIC"},
        ])
        seen: set[str] = set()
        orphans = manifest.find_orphaned(seen)
        assert len(orphans) == 2
        assert {o.asset_id for o in orphans} == {"A1", "A2"}
        manifest.close()

    def test_partial_orphan(self, tmp_path: object) -> None:
        tmpdir = str(tmp_path)
        manifest = _setup_manifest_with_files(tmpdir, [
            {"asset_id": "A1", "local_path": "2024-01/photo1.HEIC"},
            {"asset_id": "A2", "local_path": "2024-01/photo2.HEIC"},
            {"asset_id": "A3", "local_path": "2024-01/photo3.HEIC"},
        ])
        seen = {"A1", "A3"}
        orphans = manifest.find_orphaned(seen)
        assert len(orphans) == 1
        assert orphans[0].asset_id == "A2"
        manifest.close()

    def test_multi_resource_orphan(self, tmp_path: object) -> None:
        """An asset with multiple resources (HEIC + MOV) should return all rows."""
        tmpdir = str(tmp_path)
        manifest = _setup_manifest_with_files(tmpdir, [
            {"asset_id": "A1", "local_path": "2024-01/IMG_001.HEIC", "asset_resource": "resOriginal"},
            {"asset_id": "A1", "local_path": "2024-01/IMG_001_HEVC.MOV", "asset_resource": "resOriginalVidCompl"},
            {"asset_id": "A2", "local_path": "2024-01/IMG_002.HEIC", "asset_resource": "resOriginal"},
        ])
        seen = {"A2"}
        orphans = manifest.find_orphaned(seen)
        assert len(orphans) == 2
        assert all(o.asset_id == "A1" for o in orphans)
        manifest.close()

    def test_empty_manifest(self, tmp_path: object) -> None:
        tmpdir = str(tmp_path)
        manifest = ManifestDB(tmpdir)
        manifest.open()
        orphans = manifest.find_orphaned({"A1", "A2"})
        assert len(orphans) == 0
        manifest.close()


class TestDeleteOrphaned:
    """Tests for the delete_orphaned() function."""

    def test_warning_mode_no_flag(self, tmp_path: object) -> None:
        """Without --delete-orphaned, logs warning but doesn't delete."""
        tmpdir = str(tmp_path)
        manifest = _setup_manifest_with_files(tmpdir, [
            {"asset_id": "A1", "local_path": "2024-01/photo1.HEIC"},
        ])
        logger = logging.getLogger("test")
        # Call without delete flag
        delete_orphaned(logger, manifest, tmpdir, set(), delete=False, dry_run=False)
        # File should still exist
        assert os.path.exists(os.path.join(tmpdir, "2024-01/photo1.HEIC"))
        assert os.path.exists(os.path.join(tmpdir, "2024-01/photo1.HEIC.xmp"))
        # Manifest should still have the entry
        assert manifest.count() == 1
        manifest.close()

    def test_delete_mode(self, tmp_path: object) -> None:
        """With --delete-orphaned, files and manifest entries are removed."""
        tmpdir = str(tmp_path)
        manifest = _setup_manifest_with_files(tmpdir, [
            {"asset_id": "A1", "local_path": "2024-01/photo1.HEIC"},
            {"asset_id": "A2", "local_path": "2024-01/photo2.HEIC"},
        ])
        logger = logging.getLogger("test")
        delete_orphaned(logger, manifest, tmpdir, {"A2"}, delete=True, dry_run=False)
        # A1 should be deleted
        assert not os.path.exists(os.path.join(tmpdir, "2024-01/photo1.HEIC"))
        assert not os.path.exists(os.path.join(tmpdir, "2024-01/photo1.HEIC.xmp"))
        # A2 should remain
        assert os.path.exists(os.path.join(tmpdir, "2024-01/photo2.HEIC"))
        assert os.path.exists(os.path.join(tmpdir, "2024-01/photo2.HEIC.xmp"))
        # Manifest should only have A2
        assert manifest.count() == 1
        manifest.close()

    def test_dry_run_skips_deletion(self, tmp_path: object) -> None:
        """Dry run logs but doesn't delete files or manifest entries."""
        tmpdir = str(tmp_path)
        manifest = _setup_manifest_with_files(tmpdir, [
            {"asset_id": "A1", "local_path": "2024-01/photo1.HEIC"},
        ])
        logger = logging.getLogger("test")
        delete_orphaned(logger, manifest, tmpdir, set(), delete=True, dry_run=True)
        # File should still exist
        assert os.path.exists(os.path.join(tmpdir, "2024-01/photo1.HEIC"))
        assert os.path.exists(os.path.join(tmpdir, "2024-01/photo1.HEIC.xmp"))
        # Manifest should still have the entry
        assert manifest.count() == 1
        manifest.close()

    def test_multi_resource_cleanup(self, tmp_path: object) -> None:
        """Deleting orphaned asset removes all resources (HEIC + MOV + XMPs)."""
        tmpdir = str(tmp_path)
        manifest = _setup_manifest_with_files(tmpdir, [
            {"asset_id": "A1", "local_path": "2024-01/IMG.HEIC", "asset_resource": "resOriginal"},
            {"asset_id": "A1", "local_path": "2024-01/IMG_HEVC.MOV", "asset_resource": "resOriginalVidCompl"},
        ])
        logger = logging.getLogger("test")
        delete_orphaned(logger, manifest, tmpdir, set(), delete=True, dry_run=False)
        assert not os.path.exists(os.path.join(tmpdir, "2024-01/IMG.HEIC"))
        assert not os.path.exists(os.path.join(tmpdir, "2024-01/IMG.HEIC.xmp"))
        assert not os.path.exists(os.path.join(tmpdir, "2024-01/IMG_HEVC.MOV"))
        assert not os.path.exists(os.path.join(tmpdir, "2024-01/IMG_HEVC.MOV.xmp"))
        assert manifest.count() == 0
        manifest.close()

    def test_no_orphans_no_action(self, tmp_path: object) -> None:
        """When all assets are seen, no warning or deletion."""
        tmpdir = str(tmp_path)
        manifest = _setup_manifest_with_files(tmpdir, [
            {"asset_id": "A1", "local_path": "2024-01/photo1.HEIC"},
        ])
        logger = logging.getLogger("test")
        delete_orphaned(logger, manifest, tmpdir, {"A1"}, delete=True, dry_run=False)
        assert os.path.exists(os.path.join(tmpdir, "2024-01/photo1.HEIC"))
        assert manifest.count() == 1
        manifest.close()

    def test_file_already_missing(self, tmp_path: object) -> None:
        """Orphan in manifest but file already deleted from disk."""
        tmpdir = str(tmp_path)
        manifest = _setup_manifest_with_files(tmpdir, [
            {"asset_id": "A1", "local_path": "2024-01/photo1.HEIC"},
        ])
        # Remove the file manually
        os.remove(os.path.join(tmpdir, "2024-01/photo1.HEIC"))
        os.remove(os.path.join(tmpdir, "2024-01/photo1.HEIC.xmp"))
        logger = logging.getLogger("test")
        # Should not crash, just remove manifest entry
        delete_orphaned(logger, manifest, tmpdir, set(), delete=True, dry_run=False)
        assert manifest.count() == 0
        manifest.close()

    def test_dedup_suffix_files(self, tmp_path: object) -> None:
        """Orphan with dedup suffix in path is handled correctly."""
        tmpdir = str(tmp_path)
        manifest = _setup_manifest_with_files(tmpdir, [
            {"asset_id": "A1", "local_path": "2024-01/IMG_001_aB3x.HEIC"},
        ])
        logger = logging.getLogger("test")
        delete_orphaned(logger, manifest, tmpdir, set(), delete=True, dry_run=False)
        assert not os.path.exists(os.path.join(tmpdir, "2024-01/IMG_001_aB3x.HEIC"))
        assert manifest.count() == 0
        manifest.close()
