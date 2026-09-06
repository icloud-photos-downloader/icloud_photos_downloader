import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from icloudpd.autodelete import autodelete_photos, move_file
from icloudpd.autodelete_manifest import AutoDeleteManifest


def _library(*asset_ids: str) -> SimpleNamespace:
    return SimpleNamespace(
        recently_deleted=[SimpleNamespace(id=asset_id) for asset_id in asset_ids]
    )


def _autodelete(
    manifest: AutoDeleteManifest,
    root: Path,
    *asset_ids: str,
    dry_run: bool = False,
    quarantine: Path | None = None,
) -> None:
    autodelete_photos(
        logging.getLogger(__name__),
        dry_run,
        _library(*asset_ids),
        str(root),
        manifest,
        [],
        lambda value: value,
        None,  # type: ignore[arg-type]
        str(quarantine) if quarantine else None,
    )


def test_requires_two_consecutive_absences_and_roundtrips(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    root = tmp_path / "library"
    root.mkdir()
    deleted = root / "deleted.jpg"
    active = root / "active.jpg"
    deleted.touch()
    active.touch()

    first = AutoDeleteManifest(path, root)
    first.record_active("deleted-id", [str(deleted)])
    first.record_active("active-id", [str(active)])
    assert first.paths_for_deleted("deleted-id") == set()
    first.commit_generation()
    first.save()

    second = AutoDeleteManifest.load(path, root)
    second.record_active("active-id", [str(active)])
    assert second.paths_for_deleted("deleted-id") == set()
    second.commit_generation()
    second.save()

    third = AutoDeleteManifest.load(path, root)
    third.record_active("active-id", [str(active)])
    assert third.paths_for_deleted("deleted-id") == {str(deleted)}
    assert third.paths_for_deleted("active-id") == set()
    assert third.paths_for_deleted("unknown-id") == set()


def test_record_active_preserves_history_and_persists_ids_without_paths(
    tmp_path: Path,
) -> None:
    path = tmp_path / "manifest.json"
    root = tmp_path / "library"
    root.mkdir()
    new = root / "new.jpg"

    manifest = AutoDeleteManifest(path, root, {"asset": {"old.jpg"}})
    manifest.record_active("asset", [str(new)])
    manifest.record_active("no-local-file", [])
    manifest.commit_generation()
    manifest.save()

    restored = AutoDeleteManifest.load(path, root)
    assert restored.assets["asset"] == {"old.jpg", "new.jpg"}
    assert restored.previous_active_ids == {"asset", "no-local-file"}


def test_legacy_manifest_migrates_without_enabling_deletion(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    root = tmp_path / "library"
    root.mkdir()
    path.write_text(
        json.dumps({"version": 1, "assets": {"legacy-id": ["legacy.jpg"]}}),
        encoding="utf-8",
    )

    manifest = AutoDeleteManifest.load(path, root)
    assert not manifest.has_previous_generation
    assert manifest.paths_for_deleted("legacy-id") == set()

    manifest.record_active("current-id", [])
    manifest.commit_generation()
    manifest.save()
    restored = AutoDeleteManifest.load(path, root)
    assert restored.generation == 1
    assert restored.previous_active_ids == {"current-id"}
    assert restored.assets["legacy-id"] == {"legacy.jpg"}


@pytest.mark.parametrize("unsafe_path", ["/tmp/outside.jpg", "../outside.jpg", "."])
def test_load_rejects_unsafe_persisted_paths(tmp_path: Path, unsafe_path: str) -> None:
    path = tmp_path / "manifest.json"
    root = tmp_path / "library"
    root.mkdir()
    path.write_text(
        json.dumps(
            {
                "version": 2,
                "root": str(root),
                "generation": 1,
                "previous_active_ids": ["asset"],
                "assets": {"asset": [unsafe_path]},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="cannot safely read"):
        AutoDeleteManifest.load(path, root)


def test_load_fails_closed_for_invalid_json_root_and_symlink(tmp_path: Path) -> None:
    root = tmp_path / "library"
    root.mkdir()
    path = tmp_path / "manifest.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot safely read"):
        AutoDeleteManifest.load(path, root)

    path.write_text(
        json.dumps(
            {
                "version": 2,
                "root": str(tmp_path / "other"),
                "generation": 1,
                "previous_active_ids": [],
                "assets": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="cannot safely read"):
        AutoDeleteManifest.load(path, root)

    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    path.unlink()
    path.symlink_to(target)
    with pytest.raises(ValueError, match="cannot safely read"):
        AutoDeleteManifest.load(path, root)


def test_record_active_rejects_paths_outside_root_and_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "library"
    root.mkdir()
    outside = tmp_path / "outside.jpg"
    outside.touch()
    manifest = AutoDeleteManifest(tmp_path / "manifest.json", root)

    with pytest.raises(ValueError, match="outside auto-delete directory"):
        manifest.record_active("asset", [str(outside)])

    escape = root / "escape.jpg"
    escape.symlink_to(outside)
    with pytest.raises(ValueError, match="outside auto-delete directory"):
        manifest.record_active("asset", [str(escape)])


def test_ambiguous_path_is_never_returned(tmp_path: Path) -> None:
    root = tmp_path / "library"
    root.mkdir()
    manifest = AutoDeleteManifest(
        tmp_path / "manifest.json",
        root,
        {
            "deleted-a": {"shared.jpg", "unique-to-a.jpg"},
            "deleted-b": {"shared.jpg"},
        },
        previous_active_ids=set(),
        generation=1,
    )

    assert manifest.paths_for_deleted("deleted-a") == set()
    assert manifest.paths_for_deleted("deleted-b") == set()


def test_refuses_suspicious_empty_generation(tmp_path: Path) -> None:
    manifest = AutoDeleteManifest(
        tmp_path / "manifest.json",
        tmp_path,
        {"known": {"known.jpg"}},
        previous_active_ids={"known"},
        generation=1,
    )
    with pytest.raises(ValueError, match="empty active-library generation"):
        manifest.commit_generation()


def test_manifest_is_atomic_private_and_namespaced(tmp_path: Path) -> None:
    root = tmp_path / "library"
    root.mkdir()
    path = AutoDeleteManifest.path_for(tmp_path, "person@example.com", root)
    other_path = AutoDeleteManifest.path_for(tmp_path, "other@example.com", root)
    assert path != other_path
    assert "person" not in path.name

    manifest = AutoDeleteManifest(path, root)
    manifest.record_active("asset", [])
    manifest.commit_generation()
    manifest.save()

    assert path.stat().st_mode & 0o777 == 0o600
    assert not list(tmp_path.glob(f".{path.name}.*"))
    assert AutoDeleteManifest.load(path, root).previous_active_ids == {"asset"}


def test_quarantines_only_eligible_asset_and_forgets_it(tmp_path: Path) -> None:
    root = tmp_path / "library"
    quarantine = tmp_path / "quarantine"
    root.mkdir()
    active = root / "active.jpg"
    deleted = root / "deleted.jpg"
    active.touch()
    deleted.write_bytes(b"deleted")
    manifest = AutoDeleteManifest(
        tmp_path / "manifest.json",
        root,
        {"active-id": {"active.jpg"}, "deleted-id": {"deleted.jpg"}},
        previous_active_ids={"active-id"},
        generation=2,
    )
    manifest.record_active("active-id", [str(active)])

    _autodelete(manifest, root, "active-id", "deleted-id", quarantine=quarantine)

    assert active.exists()
    assert not deleted.exists()
    assert (quarantine / "deleted.jpg").read_bytes() == b"deleted"
    assert "deleted-id" not in manifest.assets


def test_direct_delete_remains_supported_without_quarantine(tmp_path: Path) -> None:
    root = tmp_path / "library"
    root.mkdir()
    deleted = root / "deleted.jpg"
    deleted.write_bytes(b"deleted")
    manifest = AutoDeleteManifest(
        tmp_path / "manifest.json",
        root,
        {"deleted-id": {"deleted.jpg"}},
        previous_active_ids=set(),
        generation=2,
    )

    _autodelete(manifest, root, "deleted-id")

    assert not deleted.exists()
    assert "deleted-id" not in manifest.assets


def test_quarantines_media_xmp_and_live_photo_as_one_asset(tmp_path: Path) -> None:
    root = tmp_path / "library"
    quarantine = tmp_path / "quarantine"
    root.mkdir()
    relative_paths = {
        "2026/01/02/photo.heic",
        "2026/01/02/photo.heic.xmp",
        "2026/01/02/photo_HEVC.mov",
    }
    for relative in relative_paths:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative, encoding="utf-8")
    manifest = AutoDeleteManifest(
        tmp_path / "manifest.json",
        root,
        {"deleted-id": set(relative_paths)},
        previous_active_ids=set(),
        generation=2,
    )

    _autodelete(manifest, root, "deleted-id", quarantine=quarantine)

    for relative in relative_paths:
        assert not (root / relative).exists()
        assert (quarantine / relative).read_text(encoding="utf-8") == relative
    assert "deleted-id" not in manifest.assets


def test_dry_run_and_missing_path_do_not_forget_mapping(tmp_path: Path) -> None:
    root = tmp_path / "library"
    quarantine = tmp_path / "quarantine"
    root.mkdir()
    media = root / "deleted.jpg"
    media.touch()
    manifest = AutoDeleteManifest(
        tmp_path / "manifest.json",
        root,
        {"deleted-id": {"deleted.jpg"}},
        previous_active_ids=set(),
        generation=2,
    )

    _autodelete(
        manifest,
        root,
        "deleted-id",
        dry_run=True,
        quarantine=quarantine,
    )
    assert media.exists()
    assert "deleted-id" in manifest.assets

    media.unlink()
    _autodelete(manifest, root, "deleted-id", quarantine=quarantine)
    assert "deleted-id" in manifest.assets


def test_quarantine_collision_preserves_both_files(tmp_path: Path) -> None:
    root = tmp_path / "library"
    quarantine = tmp_path / "quarantine"
    root.mkdir()
    quarantine.mkdir()
    source = root / "photo.jpg"
    destination = quarantine / "photo.jpg"
    source.write_bytes(b"new")
    destination.write_bytes(b"old")

    assert move_file(
        logging.getLogger(__name__),
        str(source),
        str(root),
        str(quarantine),
        "deleted-asset-id",
        False,
    )
    assert destination.read_bytes() == b"old"
    collision_files = list(quarantine.glob("photo-icloudpd-*.jpg"))
    assert len(collision_files) == 1
    assert collision_files[0].read_bytes() == b"new"


def test_identical_quarantine_file_is_kept_without_duplicate(tmp_path: Path) -> None:
    root = tmp_path / "library"
    quarantine = tmp_path / "quarantine"
    root.mkdir()
    quarantine.mkdir()
    source = root / "photo.jpg"
    destination = quarantine / "photo.jpg"
    source.write_bytes(b"same")
    destination.write_bytes(b"same")

    assert move_file(
        logging.getLogger(__name__),
        str(source),
        str(root),
        str(quarantine),
        "deleted-asset-id",
        False,
    )
    assert not source.exists()
    assert destination.read_bytes() == b"same"
    assert list(quarantine.iterdir()) == [destination]


def test_quarantine_rejects_same_or_nested_root(tmp_path: Path) -> None:
    root = tmp_path / "library"
    root.mkdir()
    source = root / "photo.jpg"
    source.touch()

    for invalid in (root, root / "nested", root.parent):
        with pytest.raises(ValueError, match="Auto-delete directory"):
            move_file(
                logging.getLogger(__name__),
                str(source),
                str(root),
                str(invalid),
                "asset-id",
                False,
            )


def test_quarantine_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "library"
    quarantine = tmp_path / "quarantine"
    outside = tmp_path / "outside"
    (root / "nested").mkdir(parents=True)
    quarantine.mkdir()
    outside.mkdir()
    source = root / "nested/photo.jpg"
    source.touch()
    (quarantine / "nested").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="destination outside"):
        move_file(
            logging.getLogger(__name__),
            str(source),
            str(root),
            str(quarantine),
            "asset-id",
            False,
        )
