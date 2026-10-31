import datetime
import json
import logging
from pathlib import Path
from unittest import mock

import pytest

from icloudpd.base import DownloadResult
from icloudpd.prune import PruneSnapshot
from pyicloud_ipd.asset_version import AssetVersion
from pyicloud_ipd.item_type import AssetItemType
from pyicloud_ipd.services.photos import PhotoAsset
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize
from tests.helpers import run_main
from tests.test_prune import LOGGER, downloader_for, library, photo, run_shared_download


def media_photo(identifier: str) -> mock.MagicMock:
    media = mock.MagicMock(spec=PhotoAsset)
    media.id = identifier
    media.created = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    media.filename = f"{identifier}.JPG"
    media.calculate_filename.return_value = media.filename
    media.item_type_extension = "JPG"
    media.item_type = AssetItemType.IMAGE
    media._asset_record = {"recordName": identifier, "fields": {}}
    media.versions_with_raw_policy.return_value = {
        AssetVersionSize.ORIGINAL: AssetVersion(
            len(identifier), "https://example.invalid/photo", "public.jpeg", ""
        ),
    }
    return media


def test_bootstrap_cleans_existing_orphans_and_tracks_visible_and_hidden_downloads(
    tmp_path: Path,
) -> None:
    for identifier in ("kept", "hidden", "already-removed"):
        (tmp_path / f"{identifier}.JPG").write_bytes(identifier.encode())
    (tmp_path / "kept.JPG.xmp").write_bytes(b"existing metadata")
    (tmp_path / "already-removed.JPG.xmp").write_bytes(b"orphan metadata")
    (tmp_path / "already-removed_HEVC.MOV").write_bytes(b"orphan live video")
    download = mock.Mock(side_effect=downloader_for(tmp_path))
    arguments = ["--folder-structure", "none", "--prune-orphans-adopt-existing"]
    current = library(media_photo("kept"), hidden=(media_photo("hidden"),))
    with mock.patch("icloudpd.base.download.download_media") as network_download:
        assert run_shared_download(tmp_path, current, download, [*arguments, "--recent", "1"]) == 0
    network_download.assert_not_called()
    assert download.call_count == 1
    assert (tmp_path / "hidden.JPG").read_bytes() == b"hidden"
    quarantined = list((tmp_path / PruneSnapshot.quarantine).glob("*/*"))
    assert {path.name for path in quarantined} == {
        "already-removed.JPG",
        "already-removed.JPG.xmp",
        "already-removed_HEVC.MOV",
    }
    state = json.loads((tmp_path / PruneSnapshot.filename).read_text())
    assert set(state["files"]) == {"kept", "hidden"}
    assert set(state["files"]["kept"]) == {"kept.JPG", "kept.JPG.xmp"}
    (tmp_path / "new-untracked.JPG").write_bytes(b"not opted in")
    assert run_shared_download(tmp_path, library(media_photo("kept")), download, arguments) == 0
    assert not (tmp_path / "hidden.JPG").exists()
    assert (tmp_path / "new-untracked.JPG").read_bytes() == b"not opted in"


def test_bootstrap_preserves_nonmedia_subdirectories_and_sibling_libraries(tmp_path: Path) -> None:
    destination = tmp_path / "shared"
    destination.mkdir()
    for filename in ("kept.JPG", "orphan.MP4", "notes.txt", "image.part", "notes.xmp", ".DS_Store"):
        (destination / filename).write_bytes(filename.encode())
    cache = destination / "@eaDir"
    cache.mkdir()
    (cache / "thumbnail.JPG").write_bytes(b"NAS metadata")
    personal = tmp_path / "PrimarySync"
    personal.mkdir()
    (personal / "personal.JPG").write_bytes(b"personal")
    snapshot = PruneSnapshot(str(destination), "test-scope")
    try:
        snapshot.finish(
            LOGGER,
            library(photo("kept")),
            False,
            adopt_existing=lambda item: (str(destination / f"{item.id}.JPG"),),
        )
    finally:
        snapshot.close()
    assert not (destination / "orphan.MP4").exists()
    for filename in ("notes.txt", "image.part", "notes.xmp", ".DS_Store"):
        assert (destination / filename).read_bytes() == filename.encode()
    assert (cache / "thumbnail.JPG").read_bytes() == b"NAS metadata"
    assert (personal / "personal.JPG").read_bytes() == b"personal"


@pytest.mark.parametrize("mode", ["deduplicated", "legacy-original"])
def test_bootstrap_reuses_actual_live_photo_and_collision_naming(tmp_path: Path, mode: str) -> None:
    media = media_photo("kept")
    media.filename = "IMG_0001.HEIC"
    media.calculate_filename.return_value = media.filename
    media.item_type_extension = "HEIC"
    media.versions_with_raw_policy.return_value = {
        AssetVersionSize.ORIGINAL: AssetVersion(
            5, "https://example.invalid/photo", "public.heic", ""
        ),
        LivePhotoVersionSize.ORIGINAL: AssetVersion(
            7, "https://example.invalid/video", "com.apple.quicktime-movie", ""
        ),
    }
    if mode == "deduplicated":
        photo_filename = "IMG_0001-5.HEIC"
        movie_filename = "IMG_0001_HEVC-7.MOV"
        (tmp_path / "IMG_0001.HEIC").write_bytes(b"old original")
        (tmp_path / "IMG_0001_HEVC.MOV").write_bytes(b"old live video")
    else:
        photo_filename = "IMG_0001-original.HEIC"
        movie_filename = "IMG_0001_HEVC.MOV"
    (tmp_path / photo_filename).write_bytes(b"photo")
    (tmp_path / movie_filename).write_bytes(b"movie!!")
    (tmp_path / f"{photo_filename}.xmp").write_bytes(b"metadata")
    with mock.patch("icloudpd.base.download.download_media") as network_download:
        assert (
            run_shared_download(
                tmp_path,
                library(media),
                mock.Mock(return_value=DownloadResult(False, True)),
                ["--folder-structure", "none", "--prune-orphans-adopt-existing"],
            )
            == 0
        )
    network_download.assert_not_called()
    state = json.loads((tmp_path / PruneSnapshot.filename).read_text())
    expected = {photo_filename, movie_filename, f"{photo_filename}.xmp"}
    if mode == "deduplicated":
        expected.update({"IMG_0001.HEIC", "IMG_0001_HEVC.MOV"})
    assert set(state["files"]["kept"]) == expected
    assert (tmp_path / photo_filename).read_bytes() == b"photo"
    assert (tmp_path / movie_filename).read_bytes() == b"movie!!"
    if mode == "deduplicated":
        assert (tmp_path / "IMG_0001.HEIC").read_bytes() == b"old original"
        assert (tmp_path / "IMG_0001_HEVC.MOV").read_bytes() == b"old live video"
    assert not (tmp_path / PruneSnapshot.quarantine).exists()


@pytest.mark.parametrize("origin", ["exif", "external", "deduplicated"])
def test_bootstrap_retains_current_filenames_despite_size_changes(
    tmp_path: Path, origin: str
) -> None:
    media = media_photo("kept")
    filename = "kept-4.JPG" if origin == "deduplicated" else "kept.JPG"
    (tmp_path / filename).write_bytes(b"edited content with a different size")
    (tmp_path / f"{filename}.xmp").write_bytes(b"edited metadata")
    (tmp_path / "already-removed.JPG").write_bytes(b"old orphan")
    arguments = ["--folder-structure", "none", "--prune-orphans-adopt-existing"]
    if origin == "exif":
        arguments.append("--set-exif-datetime")
    assert (
        run_shared_download(
            tmp_path, library(media), mock.Mock(return_value=DownloadResult(False, True)), arguments
        )
        == 0
    )
    assert (tmp_path / filename).read_bytes() == b"edited content with a different size"
    assert (tmp_path / f"{filename}.xmp").read_bytes() == b"edited metadata"
    assert not (tmp_path / "already-removed.JPG").exists()
    state = json.loads((tmp_path / PruneSnapshot.filename).read_text())
    assert set(state["files"]["kept"]) == {filename, f"{filename}.xmp"}
    assert {path.name for path in (tmp_path / PruneSnapshot.quarantine).glob("*/*")} == {
        "already-removed.JPG"
    }


def test_ambiguous_base_filename_is_retained_while_any_current_photo_references_it(
    tmp_path: Path,
) -> None:
    first = media_photo("first")
    second = media_photo("second")
    for media in (first, second):
        media.filename = "shared.JPG"
        media.calculate_filename.return_value = media.filename
    (tmp_path / "shared.JPG").write_bytes(b"ambiguous edited base file")
    (tmp_path / "shared-6.JPG").write_bytes(b"edited second photo")
    arguments = ["--folder-structure", "none", "--prune-orphans-adopt-existing"]
    download = mock.Mock(return_value=DownloadResult(False, True))
    assert run_shared_download(tmp_path, library(first, second), download, arguments) == 0
    assert run_shared_download(tmp_path, library(first), download, arguments) == 0
    assert (tmp_path / "shared.JPG").read_bytes() == b"ambiguous edited base file"
    assert not (tmp_path / "shared-6.JPG").exists()


def test_bootstrap_dry_run_does_not_create_missing_destination(tmp_path: Path) -> None:
    destination = tmp_path / "missing"
    snapshot = PruneSnapshot(str(destination), "test-scope", True)
    try:
        snapshot.finish(
            LOGGER,
            library(photo("kept")),
            True,
            adopt_existing=lambda item: (str(destination / f"{item.id}.JPG"),),
        )
    finally:
        snapshot.close()
    assert not destination.exists()


def test_bootstrap_dry_run_previews_without_changing_files_or_creating_state(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    for identifier in ("kept", "removed"):
        (tmp_path / f"{identifier}.JPG").write_bytes(identifier.encode())
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    snapshot = PruneSnapshot(str(tmp_path), "test-scope", True)
    try:
        with caplog.at_level(logging.INFO):
            snapshot.finish(
                LOGGER,
                library(photo("kept")),
                True,
                adopt_existing=lambda item: (str(tmp_path / f"{item.id}.JPG"),),
            )
    finally:
        snapshot.close()
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before
    assert "[DRY RUN] Would quarantine" in caplog.text
    assert "removed.JPG" in caplog.text


@pytest.mark.parametrize("failure", ["empty", "partial", "metadata", "symlink", "cancelled"])
def test_invalid_bootstrap_preserves_every_file_and_does_not_save_baseline(
    tmp_path: Path, failure: str
) -> None:
    kept = tmp_path / "kept.JPG"
    kept.write_bytes(b"kept")
    orphan = tmp_path / "removed.JPG"
    orphan.write_bytes(b"removed")
    current = library(photo("kept"))
    if failure == "empty":
        current = library()
    elif failure == "partial":
        current.hidden.__len__.return_value = 1
    elif failure == "symlink":
        (tmp_path / "linked.JPG").symlink_to(kept)
    inspect = mock.Mock(return_value=(str(kept),))
    if failure == "metadata":
        inspect.side_effect = ValueError("unavailable metadata")
    snapshot = PruneSnapshot(str(tmp_path), "test-scope")
    try:
        with pytest.raises(ValueError):
            snapshot.finish(LOGGER, current, False, lambda: failure == "cancelled", inspect)
    finally:
        snapshot.close()
    assert kept.read_bytes() == b"kept"
    assert orphan.read_bytes() == b"removed"
    assert not snapshot.path.exists()
    assert not (tmp_path / PruneSnapshot.quarantine).exists()


@pytest.mark.parametrize(
    "extra",
    [
        [],
        ["--folder-structure", "none", "--size", "medium"],
        ["--folder-structure", "none", "--skip-live-photos"],
        ["--folder-structure", "none", "--file-match-policy", "name-id7"],
        ["--folder-structure", "none", "--align-raw", "original"],
        ["--folder-structure", "none", "--live-photo-size", "medium"],
        ["--folder-structure", "none", "--live-photo-mov-filename-policy", "original"],
    ],
)
def test_bootstrap_cli_rejects_unsupported_layouts(extra: list[str]) -> None:
    result = run_main(
        [
            "--username",
            "user@example.com",
            "--directory",
            "/unused",
            "--library",
            "SharedSync-test",
            "--prune-orphans",
            "--prune-orphans-adopt-existing",
            *extra,
        ]
    )
    assert result.exit_code == 2


def test_bootstrap_cli_requires_pruning() -> None:
    result = run_main(
        [
            "--username",
            "user@example.com",
            "--directory",
            "/unused",
            "--library",
            "SharedSync-test",
            "--folder-structure",
            "none",
            "--prune-orphans-adopt-existing",
        ]
    )
    assert result.exit_code == 2


def test_bootstrap_cli_accepts_existing_homelab_layout() -> None:
    with mock.patch("icloudpd.cli.run_with_configs", return_value=0) as run:
        result = run_main(
            [
                "--username",
                "user@example.com",
                "--directory",
                "/data/SharedSync-test",
                "--library",
                "SharedSync-test",
                "--folder-structure",
                "none",
                "--size",
                "original",
                "--file-match-policy",
                "name-size-dedup-with-suffix",
                "--align-raw",
                "as-is",
                "--live-photo-size",
                "original",
                "--live-photo-mov-filename-policy",
                "suffix",
                "--auto-delete",
                "--watch-with-interval",
                "3600",
                "--prune-orphans",
                "--prune-orphans-adopt-existing",
                "--dry-run",
            ]
        )
    assert result.exit_code == 0
    run.assert_called_once()


def test_bootstrap_failure_is_nonfatal_for_downloads(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "orphan.JPG").write_bytes(b"old orphan")
    download = mock.Mock(return_value=DownloadResult(False, True))
    with caplog.at_level(logging.WARNING):
        assert (
            run_shared_download(
                tmp_path,
                library(photo("unavailable-metadata")),
                download,
                ["--folder-structure", "none", "--prune-orphans-adopt-existing"],
            )
            == 0
        )
    assert download.called
    assert (tmp_path / "orphan.JPG").read_bytes() == b"old orphan"
    assert not (tmp_path / PruneSnapshot.filename).exists()
    assert "Skipping orphan pruning" in caplog.text
