"""Exercise download naming, complete scans and deletion together, without iCloud access."""

import datetime
import hashlib
import json
import logging
from collections.abc import Iterator
from contextlib import nullcontext
from pathlib import Path
from unittest import mock

import pytest
from requests.exceptions import ChunkedEncodingError

from icloudpd.autodelete_manifest import AutoDeleteManifest
from icloudpd.base import _process_all_users_once, download_scope
from icloudpd.cli import parse
from icloudpd.prune import PruneSnapshot
from icloudpd.status import StatusExchange
from pyicloud_ipd.asset_version import AssetVersion
from pyicloud_ipd.item_type import AssetItemType
from pyicloud_ipd.services.photos import PhotoAsset, PhotoLibrary
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize
from tests.helpers import run_main
from tests.test_prune import album

LOGGER = logging.getLogger(__name__)


def photo(identifier: str, filename: str = "photo.JPG", heic: bool = False) -> mock.MagicMock:
    item = mock.MagicMock(spec=PhotoAsset)
    item.id = identifier
    item._asset_record = {"recordName": identifier, "fields": {}}
    item.calculate_filename.return_value = filename
    item.item_type_extension = "HEIC" if heic else "JPG"
    item.item_type = AssetItemType.IMAGE
    item.created = datetime.datetime(2018, 7, 12, tzinfo=datetime.UTC)
    original = AssetVersion(
        5, "https://example.invalid/photo", "public.heic" if heic else "public.jpeg", ""
    )
    item.versions_with_raw_policy.return_value = {
        AssetVersionSize.ORIGINAL: original,
        AssetVersionSize.MEDIUM: AssetVersion(
            5, "https://example.invalid/medium", "public.jpeg", ""
        ),
        AssetVersionSize.ADJUSTED: original,
        AssetVersionSize.ALTERNATIVE: original,
        LivePhotoVersionSize.ORIGINAL: AssetVersion(
            5, "https://example.invalid/video", "com.apple.quicktime-movie", ""
        ),
    }
    return item


def library(*items: PhotoAsset, deleted: tuple[PhotoAsset, ...] = ()) -> mock.MagicMock:
    result = mock.MagicMock(spec=PhotoLibrary)
    result.all = album(*items)
    result.hidden = album()
    result.recently_deleted = deleted
    result.albums = {"Favorites": result.all}
    result.zone_id = {"zoneName": "PrimarySync"}
    result.library_type = "private"
    return result


@pytest.fixture
def media_writer() -> Iterator[mock.MagicMock]:
    def write_media(_logger, dry_run, _icloud, _photo, target, _version, _size, _builder):
        if not dry_run:
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            Path(target).write_bytes(b"photo")
        return True

    def write_sidecar(_logger, target, _record, dry_run):
        if not dry_run:
            Path(target + ".xmp").write_bytes(b"metadata")

    with (
        mock.patch("icloudpd.base.download.download_media", side_effect=write_media) as writer,
        mock.patch("icloudpd.base.generate_xmp_file", side_effect=write_sidecar),
        mock.patch(
            "requests.Session.request", side_effect=AssertionError("unexpected network access")
        ),
    ):
        yield writer


def arguments(tmp_path: Path, extra: tuple[str, ...] = ()) -> list[str]:
    return [
        "--username",
        "test@example.com",
        "--password",
        "unused",
        "--directory",
        str(tmp_path / "data"),
        "--cookie-directory",
        str(tmp_path / "cookies"),
        "--auto-delete",
        "--no-progress-bar",
        *extra,
    ]


def run(
    tmp_path: Path,
    current: mock.MagicMock,
    extra: tuple[str, ...] = (),
    exchange: StatusExchange | None = None,
    username: str = "test@example.com",
) -> int:
    params = arguments(tmp_path, extra)
    params[1] = username
    global_config, configs = parse(params)
    icloud = mock.MagicMock()
    libraries = {configs[0].library: current}
    icloud.photos.private_libraries = {} if current.library_type == "shared" else libraries
    icloud.photos.shared_libraries = libraries if current.library_type == "shared" else {}
    with mock.patch("icloudpd.base.authenticator", return_value=icloud):
        return _process_all_users_once(global_config, configs, LOGGER, exchange or StatusExchange())


def manifest_path(tmp_path: Path) -> Path:
    return tmp_path / "data" / AutoDeleteManifest.filename


@pytest.mark.parametrize(
    "mode,extra,expected",
    [
        ("default", (), {"photo.JPG", "photo.MOV"}),
        (
            "name-id7",
            ("--file-match-policy", "name-id7"),
            {"photo_cmVtb3Z.JPG", "photo_cmVtb3Z.MOV"},
        ),
        ("unicode", (), {"phot.JPG", "phot.MOV"}),
        ("keep-unicode", ("--keep-unicode-in-filenames",), {"photé.JPG", "photé.MOV"}),
        ("flat", ("--folder-structure", "none"), {"photo.JPG", "photo.MOV"}),
        ("heic", (), {"photo.HEIC", "photo_HEVC.MOV"}),
        (
            "medium",
            ("--size", "original", "--size", "medium"),
            {"photo.JPG", "photo-medium.JPG", "photo.MOV"},
        ),
        (
            "variants",
            (
                "--file-match-policy",
                "name-id7",
                "--size",
                "original",
                "--size",
                "adjusted",
                "--size",
                "alternative",
            ),
            {
                "photo_cmVtb3Z.JPG",
                "photo_cmVtb3Z-adjusted.JPG",
                "photo_cmVtb3Z-alternative.JPG",
                "photo_cmVtb3Z.MOV",
            },
        ),
        ("xmp", ("--xmp-sidecar",), {"photo.JPG", "photo.JPG.xmp", "photo.MOV"}),
    ],
)
def test_download_paths_survive_first_absence_then_delete(
    tmp_path: Path,
    media_writer: mock.MagicMock,
    mode: str,
    extra: tuple[str, ...],
    expected: set[str],
) -> None:
    filename = "photé.JPG" if "unicode" in mode else "photo.HEIC" if mode == "heic" else "photo.JPG"
    removed, kept = photo("removed", filename, mode == "heic"), photo("kept", "kept.JPG")
    assert run(tmp_path, library(removed, kept), extra) == 0
    root = tmp_path / "data"
    state = json.loads(manifest_path(tmp_path).read_text())
    tracked = {root / relative for relative in state["files"]["removed"]}
    assert {path.name for path in tracked} == expected
    assert all(path.exists() for path in tracked)
    assert all(path.parent == (root if mode == "flat" else root / "2018/07/12") for path in tracked)
    # Actual deletion must use recorded paths even if Apple changes the filename/date.
    removed.calculate_filename.return_value = "renamed.JPG"
    removed.created = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    current = library(kept, deleted=(removed,))
    assert run(tmp_path, current, extra) == 0
    assert all(path.exists() for path in tracked)
    before = manifest_path(tmp_path).read_bytes()
    assert run(tmp_path, current, (*extra, "--dry-run")) == 0
    assert manifest_path(tmp_path).read_bytes() == before
    assert all(path.exists() for path in tracked)
    assert run(tmp_path, current, extra) == 0
    assert all(not path.exists() for path in tracked)
    assert "removed" not in json.loads(manifest_path(tmp_path).read_text())["files"]
    assert (
        (root / "2018/07/12/kept.JPG").exists()
        if mode != "flat" and "--file-match-policy" not in extra
        else list(root.rglob("kept*"))
    )


@pytest.mark.parametrize(
    "extra",
    [
        ("--recent", "1"),
        ("--recent", "0"),
        ("--until-found", "1"),
        ("--album", "Favorites"),
        ("--skip-created-before", "2010-01-01"),
        ("--skip-created-after", "2030-01-01"),
        ("--skip-photos",),
        ("--skip-videos",),
        ("--only-print-filenames",),
    ],
)
def test_filtered_cli_runs_download_without_advancing_manifest(
    tmp_path: Path, media_writer: mock.MagicMock, extra: tuple[str, ...]
) -> None:
    removed, kept = photo("removed"), photo("kept", "kept.JPG")
    assert run(tmp_path, library(removed, kept)) == 0
    assert run(tmp_path, library(kept, deleted=(removed,))) == 0
    before = manifest_path(tmp_path).read_bytes()
    current = library(photo("new", "new.JPG"), kept, deleted=(removed,))
    icloud = mock.MagicMock()
    icloud.photos.private_libraries = {"PrimarySync": current}
    icloud.photos.shared_libraries = {}
    with mock.patch("icloudpd.base.authenticator", return_value=icloud):
        result = run_main(arguments(tmp_path, extra))
    assert result.exit_code == 0, result.output
    # Print-only mode suppresses logs to keep stdout machine-readable.
    if extra != ("--only-print-filenames",):
        assert "Skipping auto-delete: a complete unfiltered" in result.output
    assert manifest_path(tmp_path).read_bytes() == before
    assert (tmp_path / "data/2018/07/12/photo.JPG").exists()
    if extra not in [("--recent", "0"), ("--skip-photos",), ("--only-print-filenames",)]:
        assert (tmp_path / "data/2018/07/12/new.JPG").exists()


@pytest.mark.parametrize(
    "failure",
    [
        "download",
        "cancel",
        "empty",
        "partial",
        "duplicate",
        "inventory",
        "recently-deleted",
        "cancel-inventory",
        "cancel-deleted",
    ],
)
def test_incomplete_runs_never_delete_or_advance(
    tmp_path: Path, media_writer: mock.MagicMock, failure: str
) -> None:
    removed, kept = photo("removed"), photo("kept", "kept.JPG")
    assert run(tmp_path, library(removed, kept)) == 0
    assert run(tmp_path, library(kept, deleted=(removed,))) == 0
    before = manifest_path(tmp_path).read_bytes()
    current = library(kept, deleted=(removed,))
    exchange = StatusExchange()
    if failure == "download":
        current = library(photo("new", "new.JPG"), kept, deleted=(removed,))
        media_writer.side_effect = None
        media_writer.return_value = False
    elif failure == "cancel":
        exchange.get_progress().cancel = True
    elif failure == "empty":
        current.all = album()
    elif failure == "partial":
        current.all.__len__.return_value = 2
    elif failure == "duplicate":
        current.all = album(kept, kept)
    elif failure == "inventory":
        current.hidden.__iter__.side_effect = ValueError("incomplete hidden listing")
    elif failure == "recently-deleted":

        def interrupted() -> Iterator[PhotoAsset]:
            yield removed
            raise ValueError("incomplete Recently Deleted listing")

        current.recently_deleted = interrupted()
    elif failure == "cancel-inventory":

        def cancel_inventory() -> Iterator[PhotoAsset]:
            exchange.get_progress().cancel = True
            return iter(())

        current.hidden.__iter__.side_effect = cancel_inventory
    elif failure == "cancel-deleted":

        def cancel_deleted() -> Iterator[PhotoAsset]:
            yield removed
            exchange.get_progress().cancel = True

        current.recently_deleted = cancel_deleted()
    assert run(tmp_path, current, exchange=exchange) == 0
    assert manifest_path(tmp_path).read_bytes() == before
    assert (tmp_path / "data/2018/07/12/photo.JPG").exists()


def test_retry_discards_incomplete_scan_state(tmp_path: Path, media_writer: mock.MagicMock) -> None:
    removed, kept = photo("removed"), photo("kept", "kept.JPG")
    assert run(tmp_path, library(removed, kept)) == 0
    current = library(kept, deleted=(removed,))

    def interrupted() -> Iterator[PhotoAsset]:
        yield removed
        raise ChunkedEncodingError("retry")

    current.all.__iter__.side_effect = [interrupted(), iter((kept,)), iter((kept,))]
    assert run(tmp_path, current) == 0
    state = json.loads(manifest_path(tmp_path).read_text())
    assert state["previous_active_ids"] == ["kept"]
    assert state["generation"] == 2
    assert (tmp_path / "data/2018/07/12/photo.JPG").exists()


def test_hidden_original_and_shared_paths_are_preserved(
    tmp_path: Path, media_writer: mock.MagicMock
) -> None:
    removed, kept = photo("removed"), photo("kept", "kept.JPG")
    shared = photo("other", "photo.JPG")
    assert run(tmp_path, library(removed, kept, shared)) == 0
    current = library(kept, deleted=(removed, shared))
    current.hidden = album(removed)
    assert run(tmp_path, current) == 0
    assert run(tmp_path, current) == 0
    assert (tmp_path / "data/2018/07/12/photo.JPG").exists()
    current.hidden = album()
    assert run(tmp_path, current) == 0
    assert run(tmp_path, current) == 0
    assert (tmp_path / "data/2018/07/12/photo.JPG").exists()


def test_quarantine_option_is_reserved_for_followup() -> None:
    result = run_main(
        [
            "--username",
            "test@example.com",
            "-d",
            "/unused",
            "--auto-delete-directory",
            "/quarantine",
        ]
    )
    assert result.exit_code == 2
    assert "unrecognized arguments: --auto-delete-directory" in result.output


@pytest.mark.parametrize("change", ["account", "domain", "library", "timezone", "naming"])
def test_scope_changes_keep_downloading_without_touching_state(
    tmp_path: Path,
    media_writer: mock.MagicMock,
    change: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    removed, kept = photo("removed"), photo("kept", "kept.JPG")
    assert run(tmp_path, library(removed, kept)) == 0
    assert run(tmp_path, library(kept, deleted=(removed,))) == 0
    before = manifest_path(tmp_path).read_bytes()
    current = library(photo("new", "new.JPG"), kept, deleted=(removed,))
    extra: tuple[str, ...] = ()
    if change == "domain":
        extra = ("--domain", "cn")
    elif change == "library":
        current.zone_id = {"zoneName": "another-library"}
    elif change == "naming":
        extra = ("--file-match-policy", "name-id7")
    with (
        mock.patch(
            "icloudpd.base.get_localzone",
            return_value=datetime.timezone(datetime.timedelta(hours=1)),
        )
        if change == "timezone"
        else nullcontext()
    ):
        assert (
            run(
                tmp_path,
                current,
                extra,
                username="other@example.com" if change == "account" else "test@example.com",
            )
            == 0
        )
    assert "another account, library or configuration" in caplog.text
    assert manifest_path(tmp_path).read_bytes() == before
    assert (tmp_path / "data/2018/07/12/photo.JPG").exists()
    assert list((tmp_path / "data").rglob("new*"))


@pytest.mark.parametrize("version", [1, 2])
def test_cookie_manifests_are_untouched_and_never_imported(
    tmp_path: Path,
    media_writer: mock.MagicMock,
    version: int,
) -> None:
    root, cookies = tmp_path / "data", tmp_path / "cookies"
    root.mkdir()
    cookies.mkdir()
    orphan = root / "old.JPG"
    orphan.write_bytes(b"old untracked copy")
    digest = hashlib.sha256(f"test@example.com\0{root.resolve()}".encode()).hexdigest()[:20]
    old_path = cookies / (
        "auto-delete-manifest.json" if version == 1 else f"auto-delete-manifest-{digest}.json"
    )
    old_path.write_text(
        json.dumps(
            {
                "version": version,
                "root": str(root),
                "assets": {"removed": ["old.JPG"]},
                "generation": 9,
                "previous_active_ids": ["kept"],
            }
        )
    )
    before = old_path.read_bytes()
    current = library(photo("kept", "kept.JPG"), deleted=(photo("removed"),))
    assert run(tmp_path, current) == 0
    state = json.loads(manifest_path(tmp_path).read_text())
    assert state["generation"] == 1
    assert "removed" not in state["files"]
    assert run(tmp_path, current) == 0
    assert old_path.read_bytes() == before
    assert orphan.read_bytes() == b"old untracked copy"


@pytest.mark.parametrize("edit_when", ["active", "absent"])
def test_local_edits_of_same_size_are_preserved_across_runs(
    tmp_path: Path,
    media_writer: mock.MagicMock,
    edit_when: str,
) -> None:
    removed, kept = photo("removed"), photo("kept", "kept.JPG")
    assert run(tmp_path, library(removed, kept)) == 0
    target = tmp_path / "data/2018/07/12/photo.JPG"
    target.write_bytes(b"local")  # same length as the original, so size alone is insufficient
    fingerprint = json.loads(manifest_path(tmp_path).read_text())["files"]["removed"][
        "2018/07/12/photo.JPG"
    ]
    if edit_when == "active":
        assert run(tmp_path, library(removed, kept)) == 0
    current = library(kept, deleted=(removed,))
    assert run(tmp_path, current) == 0
    assert run(tmp_path, current) == 0
    state = json.loads(manifest_path(tmp_path).read_text())
    assert state["files"]["removed"]["2018/07/12/photo.JPG"] == fingerprint
    assert target.read_bytes() == b"local"
    assert (target.parent / "photo.MOV").exists()


def test_dry_run_does_not_create_manifest_or_download_root(
    tmp_path: Path,
    media_writer: mock.MagicMock,
) -> None:
    assert run(tmp_path, library(photo("new")), ("--dry-run",)) == 0
    assert not manifest_path(tmp_path).exists()
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize("error", ["corrupt", "fingerprint"])
def test_unreadable_state_or_file_disables_cleanup_without_stopping_downloads(
    tmp_path: Path,
    media_writer: mock.MagicMock,
    error: str,
) -> None:
    removed, kept = photo("removed"), photo("kept", "kept.JPG")
    assert run(tmp_path, library(removed, kept)) == 0
    assert run(tmp_path, library(kept, deleted=(removed,))) == 0
    if error == "corrupt":
        manifest_path(tmp_path).write_text("not json")
    before = manifest_path(tmp_path).read_bytes()
    current = library(photo("new", "new.JPG"), kept, deleted=(removed,))
    with mock.patch(
        "icloudpd.autodelete_manifest.file_record", side_effect=OSError("cannot read file")
    ):
        assert run(tmp_path, current) == 0
    assert manifest_path(tmp_path).read_bytes() == before
    assert (tmp_path / "data/2018/07/12/new.JPG").exists()
    assert (tmp_path / "data/2018/07/12/photo.JPG").exists()


def test_pruning_and_autodelete_keep_independent_states_and_existing_prune_behavior(
    tmp_path: Path,
    media_writer: mock.MagicMock,
) -> None:
    removed, kept = photo("removed"), photo("kept", "kept.JPG")
    current = library(removed, kept)
    current.library_type = "shared"
    current.zone_id = {"zoneName": "SharedSync-test"}
    extra = ("--library", "SharedSync-test", "--prune-orphans")
    assert run(tmp_path, current, extra) == 0
    root = tmp_path / "data"
    prune_path = root / PruneSnapshot.filename
    prune_state = json.loads(prune_path.read_text())
    auto_state = json.loads(manifest_path(tmp_path).read_text())
    assert prune_state["scope"] == auto_state["scope"]
    assert prune_state["files"] == auto_state["files"]
    global_config, configs = parse(arguments(tmp_path, extra))
    assert prune_state["scope"] == download_scope(global_config, configs[0], current)
    before = prune_path.read_bytes()
    assert run(tmp_path, current, ("--library", "SharedSync-test")) == 0
    assert prune_path.read_bytes() == before
    current.all = album(kept)
    current.recently_deleted = (removed,)
    assert run(tmp_path, current, extra) == 0
    assert run(tmp_path, current, extra) == 0
    # Prune still quarantines on the first absence; auto-delete does not touch its archive.
    copies = list((root / ".icloudpd-pruned").rglob("photo.JPG"))
    assert len(copies) == 1 and copies[0].read_bytes() == b"photo"
    assert "removed" not in json.loads(prune_path.read_text())["files"]
    assert (root / "2018/07/12/kept.JPG").exists()
