import datetime
import json
import logging
import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest import mock

import pytest

from icloudpd.base import DownloadResult, core_single_run, download_builder
from icloudpd.cli import parse
from icloudpd.counter import Counter
from icloudpd.prune import PruneSnapshot, file_record, library_photo_ids, lock_file
from icloudpd.status import StatusExchange
from pyicloud_ipd.asset_version import AssetVersion
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.item_type import AssetItemType
from pyicloud_ipd.raw_policy import RawTreatmentPolicy
from pyicloud_ipd.services.photos import PhotoAlbum, PhotoAsset, PhotoLibrary
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize, VersionSize
from tests.helpers import run_main

LOGGER = logging.getLogger("icloudpd-prune-test")


def photo(asset_id: str, master_id: str | None = None) -> PhotoAsset:
    return PhotoAsset({"recordName": master_id or asset_id}, {"recordName": asset_id})


def album(*photos: PhotoAsset) -> mock.MagicMock:
    result = mock.MagicMock(spec=PhotoAlbum)
    result.__iter__.side_effect = lambda: iter(photos)
    result.__len__.return_value = len(photos)
    return result


def library(*photos: PhotoAsset, hidden: tuple[PhotoAsset, ...] = ()) -> mock.MagicMock:
    result = mock.MagicMock(spec=PhotoLibrary)
    result.all = album(*photos)
    result.hidden = album(*hidden)
    result.zone_id = {"zoneName": "SharedSync-test"}
    result.library_type = "shared"
    return result


@pytest.fixture
def snapshot(tmp_path: Path) -> Iterator[PruneSnapshot]:
    result = PruneSnapshot(str(tmp_path), "test-scope")
    try:
        yield result
    finally:
        result.close()


def baseline(tmp_path: Path) -> bytes:
    snapshot = PruneSnapshot(str(tmp_path), "test-scope")
    try:
        for identifier in ("removed", "kept"):
            target = tmp_path / f"{identifier}.JPG"
            target.write_bytes(identifier.encode())
            snapshot.record(identifier, (str(target),))
        snapshot.finish(LOGGER, library(photo("removed"), photo("kept")), False)
    finally:
        snapshot.close()
    return (tmp_path / PruneSnapshot.filename).read_bytes()


def assert_lock_available(directory: Path) -> None:
    with (directory / ".icloudpd-prune.lock").open("r+b") as handle:
        lock_file(handle)


def test_first_run_only_establishes_baseline(tmp_path: Path, snapshot: PruneSnapshot) -> None:
    target = tmp_path / "download.JPG"
    target.write_bytes(b"downloaded")
    unknown = tmp_path / "existing.JPG"
    unknown.write_bytes(b"existing")
    snapshot.record("new", (str(target),))
    snapshot.finish(LOGGER, library(photo("another")), False)
    assert target.exists()
    assert unknown.exists()
    assert set(json.loads(snapshot.path.read_text())["files"]) == {"new"}


def test_prunes_only_tracked_downloads(tmp_path: Path) -> None:
    baseline(tmp_path)
    for filename in (
        "user.txt",
        "other-library.JPG",
        "old-size.JPG",
        "download.part",
        "kept.JPG.xmp",
    ):
        (tmp_path / filename).write_bytes(b"untracked")
    snapshot = PruneSnapshot(str(tmp_path), "test-scope")
    try:
        snapshot.finish(LOGGER, library(photo("kept")), False)
    finally:
        snapshot.close()
    assert not (tmp_path / "removed.JPG").exists()
    assert (tmp_path / "kept.JPG").exists()
    assert (
        next((tmp_path / PruneSnapshot.quarantine).glob("*/removed.JPG")).read_bytes() == b"removed"
    )
    for filename in (
        "user.txt",
        "other-library.JPG",
        "old-size.JPG",
        "download.part",
        "kept.JPG.xmp",
    ):
        assert (tmp_path / filename).read_bytes() == b"untracked"
    assert set(json.loads(snapshot.path.read_text())["files"]) == {"kept"}


def test_consistently_short_inventory_keeps_missing_files_recoverable(tmp_path: Path) -> None:
    baseline(tmp_path)
    current = library(photo("kept"))
    assert len(current.all) == len(list(current.all))
    snapshot = PruneSnapshot(str(tmp_path), "test-scope")
    try:
        snapshot.finish(LOGGER, current, False)
    finally:
        snapshot.close()
    recovered = next((tmp_path / PruneSnapshot.quarantine).glob("*/removed.JPG"))
    recovered.rename(tmp_path / "removed.JPG")
    assert (tmp_path / "removed.JPG").read_bytes() == b"removed"


def test_changed_file_is_preserved(tmp_path: Path) -> None:
    baseline(tmp_path)
    target = tmp_path / "removed.JPG"
    target.write_bytes(b"changed")
    snapshot = PruneSnapshot(str(tmp_path), "test-scope")
    try:
        snapshot.finish(LOGGER, library(photo("kept")), False)
    finally:
        snapshot.close()
    assert target.read_bytes() == b"changed"


def test_missing_tracked_file_is_forgotten(tmp_path: Path) -> None:
    baseline(tmp_path)
    (tmp_path / "removed.JPG").unlink()
    snapshot = PruneSnapshot(str(tmp_path), "test-scope")
    try:
        snapshot.finish(LOGGER, library(photo("kept")), False)
    finally:
        snapshot.close()
    assert "removed" not in json.loads(snapshot.path.read_text())["files"]


def test_hidden_photo_is_not_an_orphan(tmp_path: Path) -> None:
    baseline(tmp_path)
    snapshot = PruneSnapshot(str(tmp_path), "test-scope")
    try:
        snapshot.finish(LOGGER, library(photo("kept"), hidden=(photo("removed"),)), False)
    finally:
        snapshot.close()
    assert (tmp_path / "removed.JPG").exists()


def test_duplicate_asset_retains_shared_original(tmp_path: Path) -> None:
    baseline(tmp_path)
    snapshot = PruneSnapshot(str(tmp_path), "test-scope")
    try:
        snapshot.finish(LOGGER, library(photo("duplicate", "removed"), photo("kept")), False)
    finally:
        snapshot.close()
    assert (tmp_path / "removed.JPG").exists()
    assert library_photo_ids(library(photo("first", "shared"), photo("second", "shared"))) == {
        "shared"
    }


def test_shared_tracked_path_is_not_deleted(tmp_path: Path) -> None:
    baseline(tmp_path)
    snapshot = PruneSnapshot(str(tmp_path), "test-scope")
    try:
        snapshot.record("kept", (str(tmp_path / "removed.JPG"),))
        snapshot.finish(LOGGER, library(photo("kept")), False)
    finally:
        snapshot.close()
    assert (tmp_path / "removed.JPG").exists()


def test_dry_run_changes_neither_files_nor_snapshot(tmp_path: Path) -> None:
    before = baseline(tmp_path)
    snapshot = PruneSnapshot(str(tmp_path), "test-scope", True)
    try:
        snapshot.finish(LOGGER, library(photo("kept")), True)
    finally:
        snapshot.close()
    assert (tmp_path / "removed.JPG").exists()
    assert snapshot.path.read_bytes() == before
    assert_lock_available(tmp_path)


def test_dry_run_does_not_create_destination(tmp_path: Path) -> None:
    directory = tmp_path / "missing"
    snapshot = PruneSnapshot(str(directory), "test-scope", True)
    snapshot.finish(LOGGER, library(photo("kept")), True)
    snapshot.close()
    assert not directory.exists()


@pytest.mark.parametrize(
    "failure", ["empty", "partial", "duplicate", "changing", "overlap", "error"]
)
def test_unreliable_inventory_preserves_files_and_baseline(tmp_path: Path, failure: str) -> None:
    before = baseline(tmp_path)
    current = library(photo("kept"))
    if failure == "empty":
        current = library()
    elif failure == "partial":
        current.all.__len__.return_value = 2
    elif failure == "duplicate":
        current = library(photo("kept"), photo("kept"))
    elif failure == "changing":
        current.all.__len__.side_effect = [1, 2]
    elif failure == "overlap":
        current.hidden = album(photo("kept"))
    else:
        current.all.__iter__.side_effect = OSError("network failed")
    snapshot = PruneSnapshot(str(tmp_path), "test-scope")
    try:
        with pytest.raises((OSError, ValueError)):
            snapshot.finish(LOGGER, current, False)
    finally:
        snapshot.close()
    assert (tmp_path / "removed.JPG").exists()
    assert snapshot.path.read_bytes() == before


@pytest.mark.parametrize("scope", ["other-account", "other-library", "changed-settings"])
def test_scope_mismatch_is_refused(tmp_path: Path, scope: str) -> None:
    before = baseline(tmp_path)
    with pytest.raises(ValueError, match="another account, library or configuration"):
        PruneSnapshot(str(tmp_path), scope)
    assert (tmp_path / PruneSnapshot.filename).read_bytes() == before
    assert_lock_available(tmp_path)


@pytest.mark.parametrize("dry_run", [False, True])
def test_concurrent_run_is_refused(tmp_path: Path, snapshot: PruneSnapshot, dry_run: bool) -> None:
    with pytest.raises((OSError, ValueError)):
        PruneSnapshot(str(tmp_path), "test-scope", dry_run)
    assert snapshot.lock.exists()


@pytest.mark.timeout(20)
def test_lock_is_released_after_process_is_killed(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(
            None,
            (str(Path(__file__).resolve().parents[1] / "src"), environment.get("PYTHONPATH", "")),
        )
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "from icloudpd.prune import PruneSnapshot; "
            "import sys; snapshot = PruneSnapshot(sys.argv[1], 'test-scope'); "
            "print('locked', flush=True); input()",
            str(tmp_path),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        cwd=tmp_path,
        env=environment,
    )
    try:
        assert process.stdout is not None
        assert process.stdout.readline().strip() == "locked"
        with pytest.raises(OSError):
            PruneSnapshot(str(tmp_path), "test-scope")
    finally:
        process.kill()
        process.communicate(timeout=10)
    assert (tmp_path / ".icloudpd-prune.lock").exists()
    snapshot = PruneSnapshot(str(tmp_path), "test-scope")
    snapshot.close()
    assert_lock_available(tmp_path)


def test_quarantine_preserves_relative_paths_and_never_overwrites(tmp_path: Path) -> None:
    for index in range(2):
        snapshot = PruneSnapshot(str(tmp_path), "test-scope")
        target = tmp_path / "2026" / "removed.JPG"
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(str(index).encode())
        try:
            snapshot.record("removed", (str(target),))
            snapshot.finish(LOGGER, library(photo("removed"), photo("kept")), False)
        finally:
            snapshot.close()
        snapshot = PruneSnapshot(str(tmp_path), "test-scope")
        try:
            snapshot.finish(LOGGER, library(photo("kept")), False)
        finally:
            snapshot.close()
    quarantined = list((tmp_path / PruneSnapshot.quarantine).glob("*/2026/removed.JPG"))
    assert {target.read_bytes() for target in quarantined} == {b"0", b"1"}


def test_symlinked_quarantine_is_refused(tmp_path: Path) -> None:
    before = baseline(tmp_path)
    outside = tmp_path / "other-directory"
    outside.mkdir()
    (tmp_path / PruneSnapshot.quarantine).symlink_to(outside, target_is_directory=True)
    snapshot = PruneSnapshot(str(tmp_path), "test-scope")
    try:
        with pytest.raises(ValueError, match="quarantine"):
            snapshot.finish(LOGGER, library(photo("kept")), False)
    finally:
        snapshot.close()
    assert not list(outside.iterdir())
    assert (tmp_path / "removed.JPG").read_bytes() == b"removed"
    assert snapshot.path.read_bytes() == before


def test_symlinked_lock_is_refused(tmp_path: Path) -> None:
    outside = tmp_path / "user.txt"
    outside.write_bytes(b"user file")
    (tmp_path / ".icloudpd-prune.lock").symlink_to(outside)
    with pytest.raises(ValueError, match="lock must not be a symlink"):
        PruneSnapshot(str(tmp_path), "test-scope")
    assert outside.read_bytes() == b"user file"


@pytest.mark.parametrize(
    "relative",
    [
        "../outside.JPG",
        "/outside.JPG",
        "",
        ".",
        "image.part",
        ".icloudpd-prune.json",
        ".icloudpd-pruned/image.JPG",
    ],
)
def test_unsafe_snapshot_paths_are_refused(tmp_path: Path, relative: str) -> None:
    state = {
        "version": 1,
        "scope": "test-scope",
        "files": {"removed": {relative: {"size": 1, "sha256": "a" * 64}}},
    }
    (tmp_path / PruneSnapshot.filename).write_text(json.dumps(state))
    with pytest.raises(ValueError, match="Unsafe path"):
        PruneSnapshot(str(tmp_path), "test-scope")


@pytest.mark.parametrize(
    "contents",
    [
        "not json",
        "[]",
        '{"version": 2}',
        '{"version": 1, "scope": "test-scope", "files": []}',
        '{"version": 1, "scope": "test-scope", "files": {"": {}}}',
        '{"version": 1, "scope": "test-scope", "files": {"removed": {"file.JPG": {}}}}',
    ],
)
def test_corrupt_snapshot_is_refused(tmp_path: Path, contents: str) -> None:
    target = tmp_path / PruneSnapshot.filename
    target.write_text(contents)
    with pytest.raises(ValueError):
        PruneSnapshot(str(tmp_path), "test-scope")
    assert target.read_text() == contents
    assert_lock_available(tmp_path)


def test_symlinked_tracked_file_is_refused(tmp_path: Path) -> None:
    before = baseline(tmp_path)
    outside = tmp_path / "outside.JPG"
    outside.write_bytes(b"not managed")
    target = tmp_path / "removed.JPG"
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises(ValueError, match="Unsafe path"):
        PruneSnapshot(str(tmp_path), "test-scope")
    assert outside.read_bytes() == b"not managed"
    assert (tmp_path / PruneSnapshot.filename).read_bytes() == before


def test_symlinked_snapshot_is_refused(tmp_path: Path) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    (tmp_path / PruneSnapshot.filename).symlink_to(outside)
    with pytest.raises(ValueError, match="must not be a symlink"):
        PruneSnapshot(str(tmp_path), "test-scope")


def test_preexisting_temporary_symlink_is_not_followed(
    tmp_path: Path, snapshot: PruneSnapshot
) -> None:
    target = tmp_path / "user.txt"
    target.write_bytes(b"user file")
    snapshot.path.with_suffix(".json.part").symlink_to(target)
    snapshot.finish(LOGGER, library(photo("kept")), False)
    assert target.read_bytes() == b"user file"


def test_record_rejects_paths_outside_destination(tmp_path: Path, snapshot: PruneSnapshot) -> None:
    with pytest.raises(ValueError):
        snapshot.record("removed", (str(tmp_path.parent / "outside.JPG"),))


def test_file_record_checks_content_not_only_size(tmp_path: Path) -> None:
    target = tmp_path / "image.JPG"
    target.write_bytes(b"first")
    before = file_record(target)
    target.write_bytes(b"other")
    assert file_record(target) != before


@pytest.mark.parametrize(
    "extra",
    [
        [],
        ["--delete-after-download"],
        ["--keep-icloud-recent-days", "0"],
        ["--only-print-filenames"],
    ],
)
def test_cli_rejects_incompatible_pruning_options(extra: list[str]) -> None:
    arguments = ["--username", "user@example.com", "--directory", "/unused", "--prune-orphans"]
    if extra:
        arguments.extend(["--library", "SharedSync-test", *extra])
    assert run_main(arguments).exit_code == 2


def test_cli_parses_pruning_flag() -> None:
    assert parse(["--username", "user@example.com", "--prune-orphans"])[1][0].prune_orphans


@pytest.mark.parametrize("directory", ["/downloads", "/downloads/subfolder", "/"])
def test_cli_rejects_overlapping_destinations(directory: str) -> None:
    result = run_main(
        [
            "--username",
            "first@example.com",
            "--directory",
            "/downloads",
            "--library",
            "SharedSync-test",
            "--prune-orphans",
            "--username",
            "second@example.com",
            "--directory",
            directory,
        ]
    )
    assert result.exit_code == 2


def run_shared_download(
    tmp_path: Path,
    current: mock.MagicMock,
    downloader: Callable[[PyiCloudService, Counter, PhotoAsset], DownloadResult],
    extra: list[str] | None = None,
    exchange: StatusExchange | None = None,
) -> int:
    global_config, configs = parse(
        [
            "--username",
            "user@example.com",
            "--directory",
            str(tmp_path),
            "--library",
            "SharedSync-test",
            "--prune-orphans",
            "--no-progress-bar",
            *(extra or []),
        ]
    )
    icloud = mock.MagicMock()
    icloud.photos.private_libraries = {}
    icloud.photos.shared_libraries = {"SharedSync-test": current}
    with mock.patch("icloudpd.base.authenticator", return_value=icloud):
        return core_single_run(
            LOGGER,
            exchange or StatusExchange(),
            global_config,
            configs[0],
            {},
            lambda _photo: True,
            downloader,
            lambda: None,
            lambda filename: filename,
        )


def downloader_for(
    tmp_path: Path,
) -> Callable[[PyiCloudService, Counter, PhotoAsset], DownloadResult]:
    def download(_icloud: PyiCloudService, _counter: Counter, item: PhotoAsset) -> DownloadResult:
        target = tmp_path / f"{item.id}.JPG"
        if target.exists():
            return DownloadResult(False, True)
        target.write_bytes(item.id.encode())
        return DownloadResult(True, True, (str(target),))

    return download


def test_shared_to_personal_move_is_pruned_on_next_run(tmp_path: Path) -> None:
    download = downloader_for(tmp_path)
    assert run_shared_download(tmp_path, library(photo("removed"), photo("kept")), download) == 0
    assert (tmp_path / "removed.JPG").exists()
    assert run_shared_download(tmp_path, library(photo("kept")), download) == 0
    assert not (tmp_path / "removed.JPG").exists()
    assert (tmp_path / "kept.JPG").exists()


@pytest.mark.parametrize(
    "failure", ["download", "cancel", "empty", "partial", "scope", "private", "record"]
)
def test_failed_run_does_not_prune_or_advance_snapshot(tmp_path: Path, failure: str) -> None:
    download = downloader_for(tmp_path)
    assert run_shared_download(tmp_path, library(photo("removed"), photo("kept")), download) == 0
    target = tmp_path / PruneSnapshot.filename
    before = target.read_bytes()
    current = library(photo("kept"))
    exchange = StatusExchange()
    extra: list[str] = []
    if failure == "download":
        download = mock.Mock(return_value=DownloadResult(False, False))
    elif failure == "cancel":
        exchange.get_progress().cancel = True
    elif failure == "empty":
        current = library()
    elif failure == "partial":
        current.hidden.__len__.return_value = 1
    elif failure == "scope":
        extra = ["--size", "medium"]
    elif failure == "private":
        current.library_type = "private"
    else:
        download = mock.Mock(return_value=DownloadResult(True, True, ("/outside.JPG",)))
    assert run_shared_download(tmp_path, current, download, extra, exchange) == 0
    assert (tmp_path / "removed.JPG").exists()
    assert target.read_bytes() == before
    assert_lock_available(tmp_path)


def test_preexisting_files_are_not_adopted(tmp_path: Path) -> None:
    target = tmp_path / "removed.JPG"
    target.write_bytes(b"untracked")
    download = downloader_for(tmp_path)
    assert run_shared_download(tmp_path, library(photo("removed"), photo("kept")), download) == 0
    assert run_shared_download(tmp_path, library(photo("kept")), download) == 0
    assert target.read_bytes() == b"untracked"


def test_inventory_is_independent_of_download_limit(tmp_path: Path) -> None:
    download = downloader_for(tmp_path)
    current = library(photo("first"), photo("second"))
    assert run_shared_download(tmp_path, current, download, ["--recent", "1"]) == 0
    assert not (tmp_path / "second.JPG").exists()
    assert library_photo_ids(current) == {"first", "second"}
    assert (
        run_shared_download(
            tmp_path,
            library(photo("new"), photo("first"), photo("second")),
            download,
            ["--recent", "1"],
        )
        == 0
    )
    assert (tmp_path / "first.JPG").exists()


def test_changing_download_limits_does_not_change_scope(tmp_path: Path) -> None:
    download = downloader_for(tmp_path)
    assert run_shared_download(tmp_path, library(photo("removed"), photo("kept")), download) == 0
    assert run_shared_download(tmp_path, library(photo("kept")), download, ["--recent", "1"]) == 0
    assert not (tmp_path / "removed.JPG").exists()


@pytest.mark.parametrize(
    "failure", ["busy", "unsupported", "inventory", "tracking", "save", "programming"]
)
def test_pruning_errors_warn_without_failing_downloads(
    tmp_path: Path, failure: str, caplog: pytest.LogCaptureFixture
) -> None:
    before = baseline(tmp_path)
    download = mock.Mock(side_effect=downloader_for(tmp_path))
    target = (
        "icloudpd.prune.lock_file"
        if failure in ("busy", "unsupported")
        else {
            "inventory": "icloudpd.prune.library_photo_ids",
            "tracking": "icloudpd.prune.PruneSnapshot.record",
            "save": "icloudpd.prune.json.dump",
            "programming": "icloudpd.prune.library_photo_ids",
        }[failure]
    )
    error = (
        RuntimeError("unexpected inventory defect")
        if failure == "programming"
        else BlockingIOError("busy")
        if failure == "busy"
        else OSError(failure)
    )
    current = library(photo("removed"), photo("kept"), photo("new"))
    with mock.patch(target, side_effect=error), caplog.at_level(logging.DEBUG):
        assert run_shared_download(tmp_path, current, download) == 0
    assert download.call_count == 3
    assert (tmp_path / "new.JPG").read_bytes() == b"new"
    assert (tmp_path / PruneSnapshot.filename).read_bytes() == before
    assert "Skipping orphan pruning" in caplog.text
    assert any(
        record.levelno == logging.DEBUG and record.exc_info is not None for record in caplog.records
    )
    assert_lock_available(tmp_path)


def test_busy_lock_does_not_stop_downloads(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    before = baseline(tmp_path)
    snapshot = PruneSnapshot(str(tmp_path), "test-scope")
    try:
        with caplog.at_level(logging.WARNING):
            assert (
                run_shared_download(tmp_path, library(photo("new")), downloader_for(tmp_path)) == 0
            )
    finally:
        snapshot.close()
    assert (tmp_path / "new.JPG").exists()
    assert snapshot.path.read_bytes() == before
    assert "Skipping orphan pruning" in caplog.text


@pytest.mark.parametrize("checks", [[True], [False, True]])
def test_cancellation_during_pruning_preserves_baseline(tmp_path: Path, checks: list[bool]) -> None:
    before = baseline(tmp_path)
    snapshot = PruneSnapshot(str(tmp_path), "test-scope")
    try:
        with pytest.raises(ValueError, match="cancelled"):
            snapshot.finish(LOGGER, library(photo("kept")), False, mock.Mock(side_effect=checks))
    finally:
        snapshot.close()
    assert (tmp_path / "removed.JPG").exists()
    assert snapshot.path.read_bytes() == before


@pytest.mark.parametrize(
    "mode", ["normal", "dedup", "existing", "dry-run", "sidecar", "existing-sidecar", "failed"]
)
def test_download_result_records_only_newly_written_actual_paths(tmp_path: Path, mode: str) -> None:
    media = mock.MagicMock(spec=PhotoAsset)
    media.created = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    media.filename = "IMG-2024.JPG"
    media.item_type = AssetItemType.IMAGE
    media._asset_record = {"fields": {}}
    media.versions_with_raw_policy.return_value = {
        AssetVersionSize.ORIGINAL: AssetVersion(
            5, "https://example.invalid/photo", "public.jpeg", ""
        ),
        LivePhotoVersionSize.ORIGINAL: AssetVersion(
            5, "https://example.invalid/video", "com.apple.quicktime-movie", ""
        ),
    }
    if mode in ("dedup", "existing"):
        for filename in ("IMG-2024.JPG", "IMG-2024.MOV"):
            (tmp_path / filename).write_bytes(b"photo" if mode == "existing" else b"different size")
    if mode == "existing-sidecar":
        (tmp_path / "IMG-2024.JPG.xmp").write_bytes(b"user metadata")

    def write_media(
        _logger: logging.Logger,
        dry_run: bool,
        _icloud: PyiCloudService,
        _photo: PhotoAsset,
        target: str,
        _version: AssetVersion,
        _size: VersionSize,
        _filename_builder: Callable[[PhotoAsset], str],
    ) -> bool:
        if mode == "failed":
            return False
        if not dry_run:
            Path(target).write_bytes(b"photo")
        return True

    def write_sidecar(
        _logger: logging.Logger,
        target: str,
        _record: dict[str, object],
        dry_run: bool,
    ) -> None:
        if not dry_run:
            Path(target + ".xmp").write_bytes(b"metadata")

    with (
        mock.patch("icloudpd.base.download.download_media", side_effect=write_media),
        mock.patch("icloudpd.base.generate_xmp_file", side_effect=write_sidecar),
    ):
        result = download_builder(
            LOGGER,
            "none",
            str(tmp_path),
            [AssetVersionSize.ORIGINAL],
            False,
            False,
            False,
            False,
            LivePhotoVersionSize.ORIGINAL,
            mode == "dry-run",
            FileMatchPolicy.NAME_SIZE_DEDUP_WITH_SUFFIX,
            mode in ("sidecar", "existing-sidecar"),
            lambda filename: str(Path(filename).with_suffix(".MOV")),
            lambda item: item.filename,
            RawTreatmentPolicy.AS_IS,
            mock.MagicMock(),
            Counter(),
            media,
        )
    if mode in ("existing", "dry-run", "failed"):
        assert result.created_paths == ()
    else:
        suffix = "-5" if mode == "dedup" else ""
        expected = {
            str(tmp_path / f"IMG-2024{suffix}.JPG"),
            str(tmp_path / f"IMG-2024{suffix}.MOV"),
        }
        if mode == "sidecar":
            expected.add(str(tmp_path / "IMG-2024.JPG.xmp"))
        assert set(result.created_paths) == expected


def test_hidden_property_uses_selected_zone() -> None:
    selected = object.__new__(PhotoLibrary)
    selected.params = {}
    selected.session = mock.MagicMock()
    selected.service_endpoint = "https://example.invalid/shared"
    selected.zone_id = {"zoneName": "SharedSync-test"}
    hidden = selected.hidden
    assert hidden._zone_id == selected.zone_id
    assert hidden.list_type == "CPLAssetAndMasterHiddenByAssetDate"
