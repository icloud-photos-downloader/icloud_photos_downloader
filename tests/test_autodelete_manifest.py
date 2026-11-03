import json
import logging
import os
import unicodedata
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from icloudpd.autodelete import autodelete_photos
from icloudpd.autodelete_manifest import AutoDeleteManifest
from icloudpd.prune import PruneSnapshot, file_record

SCOPE = "test-scope"


def _autodelete(manifest: AutoDeleteManifest, *asset_ids: str, dry_run: bool = False) -> None:
    library = SimpleNamespace(recently_deleted=[SimpleNamespace(id=key) for key in asset_ids])
    autodelete_photos(logging.getLogger(__name__), dry_run, library, manifest)


def _baseline(root: Path) -> AutoDeleteManifest:
    root.mkdir(parents=True, exist_ok=True)
    for name in ("removed.jpg", "kept.jpg"):
        (root / name).write_bytes(name.encode())
    manifest = AutoDeleteManifest(root, SCOPE)
    manifest.record_active("removed", [str(root / "removed.jpg")])
    manifest.record_active("kept", [str(root / "kept.jpg")])
    manifest.commit_generation()
    manifest.save()
    return manifest


def _eligible(root: Path) -> AutoDeleteManifest:
    _baseline(root)
    second = AutoDeleteManifest.load(root, SCOPE)
    second.record_active("kept", [str(root / "kept.jpg")])
    second.commit_generation()
    second.save()
    third = AutoDeleteManifest.load(root, SCOPE)
    third.record_active("kept", [str(root / "kept.jpg")])
    return third


def test_requires_two_consecutive_absences_and_roundtrips(tmp_path: Path) -> None:
    first = _baseline(tmp_path)
    assert first.paths_for_deleted("removed") == set()
    second = AutoDeleteManifest.load(tmp_path, SCOPE)
    second.record_active("kept", [str(tmp_path / "kept.jpg")])
    assert second.paths_for_deleted("removed") == set()
    second.commit_generation()
    second.save()
    third = AutoDeleteManifest.load(tmp_path, SCOPE)
    third.record_active("kept", [str(tmp_path / "kept.jpg")])
    assert third.paths_for_deleted("removed") == {str(tmp_path / "removed.jpg")}
    assert third.paths_for_deleted("kept") == set()
    assert third.paths_for_deleted("unknown") == set()


def test_history_and_ids_without_local_files_survive_roundtrip(tmp_path: Path) -> None:
    manifest = _baseline(tmp_path)
    old_record = manifest.files["removed"]["removed.jpg"].copy()
    (tmp_path / "new.jpg").write_bytes(b"new")
    manifest.record_active("removed", [str(tmp_path / "new.jpg")])
    manifest.record_active("no-local-file", [])
    manifest.commit_generation()
    manifest.save()
    restored = AutoDeleteManifest.load(tmp_path, SCOPE)
    assert set(restored.files["removed"]) == {"removed.jpg", "new.jpg"}
    assert restored.files["removed"]["removed.jpg"] == old_record
    assert restored.previous_active_ids == {"removed", "kept", "no-local-file"}


@pytest.mark.parametrize("version", [1, 2])
def test_old_manifest_formats_are_rejected_without_migration(tmp_path: Path, version: int) -> None:
    path = tmp_path / AutoDeleteManifest.filename
    path.write_text(json.dumps({"version": version, "assets": {"old": ["photo.jpg"]}}))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="cannot safely read"):
        AutoDeleteManifest.load(tmp_path, SCOPE)
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "relative",
    [
        "/tmp/outside.jpg",
        "../outside.jpg",
        "./removed.jpg",
        "nested//photo.jpg",
        ".",
        "",
        ".icloudpd-autodelete.json",
        ".icloudpd-prune.json",
        ".icloudpd-prune.lock",
        ".icloudpd-pruned/batch/photo.JPG",
        "photo.part",
    ],
)
def test_load_rejects_unsafe_persisted_paths(tmp_path: Path, relative: str) -> None:
    manifest = _baseline(tmp_path)
    data = json.loads(manifest.path.read_text())
    data["files"]["removed"] = {relative: file_record(tmp_path / "removed.jpg")}
    manifest.path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="unsafe auto-delete path"):
        AutoDeleteManifest.load(tmp_path, SCOPE)


@pytest.mark.parametrize(
    "record",
    [
        {},
        {"size": True, "sha256": "a" * 64},
        {"size": -1, "sha256": "a" * 64},
        {"size": 1, "sha256": "invalid"},
        {"size": 1, "sha256": "g" * 64},
    ],
)
def test_load_rejects_invalid_fingerprints(tmp_path: Path, record: object) -> None:
    manifest = _baseline(tmp_path)
    data = json.loads(manifest.path.read_text())
    data["files"]["removed"]["removed.jpg"] = record
    manifest.path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="invalid file fingerprint"):
        AutoDeleteManifest.load(tmp_path, SCOPE)


@pytest.mark.parametrize(
    "field,value",
    [
        ("generation", 0),
        ("generation", True),
        ("previous_active_ids", []),
        ("previous_active_ids", ["a", "a"]),
        ("previous_active_ids", [None]),
    ],
)
def test_load_rejects_invalid_generations(tmp_path: Path, field: str, value: object) -> None:
    manifest = _baseline(tmp_path)
    data = json.loads(manifest.path.read_text())
    data[field] = value
    manifest.path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="invalid complete generation"):
        AutoDeleteManifest.load(tmp_path, SCOPE)


def test_scope_mismatch_preserves_state(tmp_path: Path) -> None:
    manifest = _baseline(tmp_path)
    before = manifest.path.read_bytes()
    with pytest.raises(ValueError, match="another account, library or configuration"):
        AutoDeleteManifest.load(tmp_path, "different-scope")
    assert manifest.path.read_bytes() == before


@pytest.mark.parametrize("kind", ["invalid-json", "symlink", "dangling-symlink"])
def test_load_rejects_invalid_json_and_manifest_symlinks(tmp_path: Path, kind: str) -> None:
    root = tmp_path / "library"
    root.mkdir()
    path = root / AutoDeleteManifest.filename
    if kind == "invalid-json":
        path.write_text("not json")
    else:
        target = tmp_path / "other.json"
        if kind == "symlink":
            target.write_text("{}")
        path.symlink_to(target)
    with pytest.raises(ValueError, match="cannot safely read"):
        AutoDeleteManifest.load(root, SCOPE)


def test_paths_outside_root_and_symlinked_media_are_refused(tmp_path: Path) -> None:
    root = tmp_path / "library"
    root.mkdir()
    outside = tmp_path / "outside.jpg"
    outside.touch()
    manifest = AutoDeleteManifest(root, SCOPE)
    with pytest.raises(ValueError, match="outside auto-delete directory"):
        manifest.record_active("asset", [str(outside)])
    escape = root / "escape.jpg"
    escape.symlink_to(outside)
    with pytest.raises(ValueError, match="unsafe auto-delete path"):
        manifest.record_active("asset", [str(escape)])


def test_ambiguous_paths_protect_entire_asset(tmp_path: Path) -> None:
    shared, unique = tmp_path / "shared.jpg", tmp_path / "unique.jpg"
    shared.write_bytes(b"shared")
    unique.write_bytes(b"unique")
    manifest = AutoDeleteManifest(tmp_path, SCOPE, previous_active_ids={"kept"}, generation=2)
    manifest.record_active("a", [str(shared), str(unique)])
    manifest.record_active("b", [str(shared)])
    manifest.active_ids = {"kept"}
    assert manifest.paths_for_deleted("a") == set()
    assert manifest.paths_for_deleted("b") == set()
    _autodelete(manifest, "a", "b")
    assert shared.exists() and unique.exists()


@pytest.mark.parametrize("alias_kind", ["case", "unicode", "hardlink"])
@pytest.mark.parametrize("other_active", [True, False])
def test_filesystem_aliases_protect_entire_asset(
    tmp_path: Path, alias_kind: str, other_active: bool
) -> None:
    source = tmp_path / ("café.JPG" if alias_kind == "unicode" else "Photo.JPG")
    source.write_bytes(b"shared photo")
    if alias_kind == "case":
        alias = tmp_path / "photo.jpg"
    elif alias_kind == "unicode":
        alias = tmp_path / unicodedata.normalize("NFD", source.name)
    else:
        alias = tmp_path / "other.JPG"
        alias.hardlink_to(source)
    if not alias.exists() or not source.samefile(alias):
        pytest.skip(f"Filesystem does not alias {alias_kind} variants")
    sidecar = tmp_path / "Photo.JPG.xmp"
    sidecar.write_bytes(b"metadata")
    manifest = AutoDeleteManifest(tmp_path, SCOPE)
    manifest.record_active("removed", [str(source), str(sidecar)])
    manifest.record_active("other", [str(alias)])
    manifest.record_active("unrelated", [])
    manifest.commit_generation()
    manifest.save()

    # Persist one complete absence, then observe another, with either owner state.
    for _ in range(2):
        manifest = AutoDeleteManifest.load(tmp_path, SCOPE)
        manifest.record_active("unrelated", [])
        if other_active:
            manifest.record_active("other", [str(alias)])
        assert manifest.paths_for_deleted("removed") == set()
        _autodelete(manifest, "removed", "other")
        manifest.commit_generation()
        manifest.save()
    assert source.read_bytes() == b"shared photo"
    assert alias.read_bytes() == b"shared photo"
    assert sidecar.read_bytes() == b"metadata"
    assert "removed" in manifest.files and "other" in manifest.files


def test_identical_content_in_distinct_files_does_not_imply_shared_ownership(
    tmp_path: Path,
) -> None:
    manifest = _eligible(tmp_path)
    source, kept = tmp_path / "removed.jpg", tmp_path / "kept.jpg"
    kept.write_bytes(source.read_bytes())
    assert not source.samefile(kept)
    _autodelete(manifest, "removed")
    assert not source.exists()
    assert kept.read_bytes() == b"removed.jpg"


def test_deletion_refreshes_ownership_after_a_file_becomes_an_alias(tmp_path: Path) -> None:
    manifest = _eligible(tmp_path)
    source, kept = tmp_path / "removed.jpg", tmp_path / "kept.jpg"
    assert manifest.paths_for_deleted("removed") == {str(source)}
    kept.unlink()
    kept.hardlink_to(source)
    _autodelete(manifest, "removed")
    assert source.read_bytes() == b"removed.jpg"
    assert kept.read_bytes() == b"removed.jpg"


@pytest.mark.parametrize("failure", ["unreadable", "unknown-inode"])
def test_unverifiable_ownership_never_uses_a_partial_index(tmp_path: Path, failure: str) -> None:
    manifest = _eligible(tmp_path)
    source, kept = tmp_path / "removed.jpg", tmp_path / "kept.jpg"
    original_stat = Path.stat

    def stat_with_failure(path: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        result = original_stat(path, follow_symlinks=follow_symlinks)
        if path == kept:
            if failure == "unreadable":
                raise PermissionError("cannot inspect other owner's file")
            values = list(result)
            values[1] = 0  # Filesystem did not supply a usable file identifier.
            return os.stat_result(values)
        return result

    with (
        mock.patch.object(Path, "stat", stat_with_failure),
        pytest.raises((OSError, ValueError)),
    ):
        _autodelete(manifest, "removed")
    assert source.read_bytes() == b"removed.jpg"
    assert kept.read_bytes() == b"kept.jpg"

    # The failed lookup must not leave a partial index that misses this owner.
    kept.unlink()
    kept.hardlink_to(source)
    assert manifest.paths_for_deleted("removed") == set()
    _autodelete(manifest, "removed")
    assert source.exists() and kept.exists()


def test_empty_scan_cannot_delete_before_generation_validation(tmp_path: Path) -> None:
    manifest = _eligible(tmp_path)
    manifest.active_ids.clear()
    with pytest.raises(ValueError, match="empty active-library generation"):
        _autodelete(manifest, "removed")
    with pytest.raises(ValueError, match="empty active-library generation"):
        manifest.commit_generation()
    assert (tmp_path / "removed.jpg").exists()
    assert manifest.generation == 2


def test_manifest_is_private_atomic_and_beside_prune(tmp_path: Path) -> None:
    manifest = _baseline(tmp_path)
    assert manifest.path == tmp_path / ".icloudpd-autodelete.json"
    assert manifest.path.stat().st_mode & 0o777 == 0o600
    assert not list(tmp_path.glob(".icloudpd-autodelete.*.part"))
    before = manifest.path.read_bytes()
    with (
        mock.patch("icloudpd.autodelete_manifest.os.replace", side_effect=OSError("disk failure")),
        pytest.raises(OSError, match="disk failure"),
    ):
        manifest.save()
    assert manifest.path.read_bytes() == before
    assert not list(tmp_path.glob(".icloudpd-autodelete.*.part"))


def test_file_records_and_scope_are_compatible_with_prune(tmp_path: Path) -> None:
    manifest = _baseline(tmp_path)
    data = json.loads(manifest.path.read_text())
    # Both readers use the same scope and per-ID, relative-path fingerprint format.
    snapshot_data = {"version": 1, "scope": data["scope"], "files": data["files"]}
    prune_path = tmp_path / PruneSnapshot.filename
    prune_path.write_text(json.dumps(snapshot_data))
    before = prune_path.read_bytes()
    snapshot = PruneSnapshot(str(tmp_path), SCOPE)
    try:
        assert snapshot.files == manifest.files
        assert snapshot.scope == manifest.scope
    finally:
        snapshot.close()
    assert prune_path.read_bytes() == before


def test_deletes_only_unchanged_eligible_asset(tmp_path: Path) -> None:
    manifest = _eligible(tmp_path)
    _autodelete(manifest, "removed", "kept")
    assert not (tmp_path / "removed.jpg").exists()
    assert (tmp_path / "kept.jpg").exists()
    assert "removed" not in manifest.files


@pytest.mark.parametrize("change", ["same-size", "different-size", "missing", "symlink"])
def test_changed_asset_preserves_all_members_and_fingerprints(tmp_path: Path, change: str) -> None:
    manifest = _eligible(tmp_path)
    target = tmp_path / "removed.jpg"
    sidecar = tmp_path / "removed.jpg.xmp"
    sidecar.write_bytes(b"sidecar")
    manifest.record_active("removed", [str(sidecar)])
    manifest.active_ids = {"kept"}
    before = manifest.files["removed"].copy()
    if change == "same-size":
        target.write_bytes(b"x" * target.stat().st_size)
    elif change == "different-size":
        target.write_bytes(b"edited")
    elif change == "missing":
        target.unlink()
    else:
        target.unlink()
        target.symlink_to(tmp_path / "kept.jpg")
    if change == "symlink":
        with pytest.raises(ValueError, match="unsafe auto-delete path"):
            _autodelete(manifest, "removed")
    else:
        _autodelete(manifest, "removed")
    assert sidecar.read_bytes() == b"sidecar"
    assert manifest.files["removed"] == before
    assert (tmp_path / "kept.jpg").exists()


def test_active_local_edit_never_refreshes_fingerprint(tmp_path: Path) -> None:
    manifest = _baseline(tmp_path)
    expected = manifest.files["removed"]["removed.jpg"].copy()
    (tmp_path / "removed.jpg").write_bytes(b"local modification")
    with mock.patch("icloudpd.autodelete_manifest.file_record") as fingerprint:
        manifest.record_active("removed", [str(tmp_path / "removed.jpg")])
        fingerprint.assert_not_called()
    assert manifest.files["removed"]["removed.jpg"] == expected


def test_media_sidecar_and_live_photo_delete_as_one_asset(tmp_path: Path) -> None:
    manifest = AutoDeleteManifest(tmp_path, SCOPE, previous_active_ids={"kept"}, generation=2)
    targets = [tmp_path / name for name in ("photo.HEIC", "photo_HEVC.MOV", "photo.HEIC.xmp")]
    for target in targets:
        target.write_bytes(target.name.encode())
    manifest.record_active("removed", map(str, targets))
    manifest.active_ids = {"kept"}
    _autodelete(manifest, "removed", dry_run=True)
    assert all(target.exists() for target in targets)
    assert "removed" in manifest.files
    _autodelete(manifest, "removed")
    assert all(not target.exists() for target in targets)
    assert "removed" not in manifest.files
