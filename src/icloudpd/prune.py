"""Reversible cleanup of tracked shared-library downloads."""

import hashlib
import json
import logging
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile, mkdtemp
from typing import BinaryIO, TypedDict

from pyicloud_ipd.services.photos import PhotoAsset, PhotoLibrary

MEDIA_EXTENSIONS = {
    ".3g2",
    ".3gp",
    ".arw",
    ".avi",
    ".avif",
    ".bmp",
    ".cr2",
    ".cr3",
    ".crw",
    ".dng",
    ".gif",
    ".heic",
    ".heif",
    ".jpeg",
    ".jpg",
    ".jxl",
    ".m4v",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".nef",
    ".nrf",
    ".nrw",
    ".orf",
    ".pef",
    ".png",
    ".raf",
    ".rw2",
    ".tif",
    ".tiff",
    ".webp",
}


class FileRecord(TypedDict):
    size: int
    sha256: str


def file_record(path: Path) -> FileRecord:
    with path.open("rb") as source:
        checksum = hashlib.file_digest(source, "sha256").hexdigest()
    return {"size": path.stat().st_size, "sha256": checksum}


def lock_file(handle: BinaryIO) -> None:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def library_photo_ids(
    library: PhotoLibrary, inspect: Callable[[PhotoAsset], None] | None = None
) -> set[str]:
    """Validate asset counts, retaining originals referenced by any visible or hidden asset."""
    inventory: set[str] = set()
    seen_assets: set[str] = set()
    albums = (library.all, library.hidden)
    expected_counts = [len(album) for album in albums]
    for album, expected in zip(albums, expected_counts, strict=True):
        asset_ids = []
        for photo in album:
            asset_ids.append(str(photo._asset_record["recordName"]))
            inventory.add(photo.id)
            if inspect is not None:
                inspect(photo)
        if len(asset_ids) != len(set(asset_ids)) or len(asset_ids) != expected:
            raise ValueError("Incomplete or changing library listing; skipping orphan pruning")
        if seen_assets.intersection(asset_ids):
            raise ValueError("Asset appeared in multiple listings; skipping orphan pruning")
        seen_assets.update(asset_ids)
    if [len(album) for album in albums] != expected_counts:
        raise ValueError("Changing library count; skipping orphan pruning")
    if not inventory:
        raise ValueError("Empty library listing; skipping orphan pruning")
    return inventory


class PruneSnapshot:
    """One destination and configuration, with explicit ownership before pruning."""

    filename = ".icloudpd-prune.json"
    quarantine = ".icloudpd-pruned"

    def __init__(self, directory: str, scope: str, dry_run: bool = False) -> None:
        self.directory = Path(directory).resolve()
        self.path = self.directory / self.filename
        self.lock = self.directory / ".icloudpd-prune.lock"
        self.scope = scope
        self.files: dict[str, dict[str, FileRecord]] = {}
        self.lock_handle: BinaryIO | None = None
        try:
            if self.lock.is_symlink():
                raise ValueError("Pruning lock must not be a symlink")
            if not dry_run:
                self.directory.mkdir(parents=True, exist_ok=True)
            if not dry_run or self.lock.exists():
                self.lock_handle = self.lock.open("r+b" if dry_run else "a+b")
                lock_file(self.lock_handle)
            if self.path.is_symlink():
                raise ValueError("Pruning snapshot must not be a symlink")
            self.initial = not self.path.exists()
            if not self.initial:
                self._load()
            self.previous_ids = set(self.files)
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        if self.lock_handle is not None:
            self.lock_handle.close()
            self.lock_handle = None

    def _local_path(self, relative: str) -> Path:
        path = self.directory / relative
        if (
            not relative
            or Path(relative).is_absolute()
            or not path.is_relative_to(self.directory)
            or ".." in Path(relative).parts
            or path == self.directory
            or path.resolve() != path
            or Path(relative).parts[0] == self.quarantine
            or path.name.startswith(".icloudpd-prune.")
            or path.name.endswith(".part")
        ):
            raise ValueError("Unsafe path in pruning snapshot")
        return path

    def _load(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if (
            not isinstance(data, dict)
            or data.get("version") != 1
            or data.get("scope") != self.scope
        ):
            raise ValueError(
                "Pruning snapshot belongs to another account, library or configuration"
            )
        files = data.get("files")
        if not isinstance(files, dict):
            raise ValueError("Invalid pruning snapshot")
        for asset_id, paths in files.items():
            if not asset_id or not isinstance(paths, dict):
                raise ValueError("Invalid asset in pruning snapshot")
            for relative, record in paths.items():
                self._local_path(relative)
                if (
                    not isinstance(record, dict)
                    or not isinstance(record.get("size"), int)
                    or record["size"] < 0
                    or not isinstance(record.get("sha256"), str)
                    or len(record["sha256"]) != 64
                    or any(char not in "0123456789abcdef" for char in record["sha256"])
                ):
                    raise ValueError("Invalid file in pruning snapshot")
        self.files = files

    def record(self, asset_id: str, created_paths: tuple[str, ...]) -> None:
        for created_path in created_paths:
            absolute = Path(created_path).parent.resolve() / Path(created_path).name
            relative = str(absolute.relative_to(self.directory))
            path = self._local_path(relative)
            self.files.setdefault(asset_id, {})[relative] = file_record(path)

    def _adopt(self, planned: dict[str, set[str]]) -> dict[str, FileRecord]:
        retained: set[str] = set()
        for asset_id, paths in planned.items():
            for planned_path in paths:
                absolute = Path(planned_path).parent.resolve() / Path(planned_path).name
                relative = str(absolute.relative_to(self.directory))
                path = self._local_path(relative)
                retained.add(relative)
                if path.is_file() and relative not in self.files.get(asset_id, {}):
                    self.record(asset_id, (str(path),))
        candidates = {}
        for path in sorted(self.directory.iterdir()) if self.directory.exists() else []:
            extension = path.suffix.lower()
            media = extension in MEDIA_EXTENSIONS or (
                extension == ".xmp" and Path(path.stem).suffix.lower() in MEDIA_EXTENSIONS
            )
            if media and not path.is_dir() and path.name not in retained:
                candidates[path.name] = file_record(self._local_path(path.name))
        return candidates

    def finish(
        self,
        logger: logging.Logger,
        library: PhotoLibrary,
        dry_run: bool,
        cancelled: Callable[[], bool] | None = None,
        adopt_existing: Callable[[PhotoAsset], tuple[str, ...]] | None = None,
    ) -> None:
        planned: dict[str, set[str]] = {}

        def inspect(photo: PhotoAsset) -> None:
            if adopt_existing is not None:
                paths = set(adopt_existing(photo))
                paths.update(f"{path}.xmp" for path in list(paths) if not path.endswith(".xmp"))
                planned.setdefault(photo.id, set()).update(paths)

        adopting = adopt_existing is not None and self.initial
        if adopt_existing is not None and not self.initial:
            logger.info("Pruning baseline already exists; not adopting existing files")
        inventory = library_photo_ids(library, inspect if adopting else None)
        if cancelled is not None and cancelled():
            raise ValueError("Orphan pruning was cancelled")
        candidates = self._adopt(planned) if adopting else {}
        if adopting:
            logger.info(
                "%sExisting-mirror bootstrap: %d current files, %d unmatched media candidates",
                "[DRY RUN] " if dry_run else "",
                sum(len(paths) for paths in self.files.values()),
                len(candidates),
            )
        retained_paths = {
            relative
            for asset_id, paths in self.files.items()
            if asset_id in inventory
            for relative in paths
        }
        batch: Path | None = None
        for asset_id in list(self.files):
            if asset_id in inventory or asset_id not in self.previous_ids:
                continue
            candidates.update(self.files[asset_id])
            del self.files[asset_id]
        for relative, expected in candidates.items():
            if cancelled is not None and cancelled():
                raise ValueError("Orphan pruning was cancelled")
            path = self._local_path(relative)
            if relative in retained_paths or not path.exists():
                continue
            if not path.is_file() or file_record(path) != expected:
                logger.warning("Keeping changed file %s", path)
            elif dry_run:
                logger.info("[DRY RUN] Would quarantine %s", path)
            else:
                if batch is None:
                    quarantine = self.directory / self.quarantine
                    if quarantine.resolve() != quarantine:
                        raise ValueError("Pruning quarantine must not contain symlinks")
                    quarantine.mkdir(exist_ok=True)
                    batch = Path(
                        mkdtemp(
                            prefix=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-"),
                            dir=quarantine,
                        )
                    )
                destination = batch / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                path.rename(destination)
                logger.info("Quarantined %s to %s", path, destination)
        if not dry_run:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.directory,
                prefix=".icloudpd-prune.",
                suffix=".part",
                delete=False,
            ) as temporary:
                json.dump({"version": 1, "scope": self.scope, "files": self.files}, temporary)
            Path(temporary.name).replace(self.path)
