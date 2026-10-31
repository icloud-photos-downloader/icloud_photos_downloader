"""Conservative cleanup of tracked shared-library downloads."""

import hashlib
import json
import logging
from collections.abc import Callable
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TypedDict

from pyicloud_ipd.services.photos import PhotoLibrary


class FileRecord(TypedDict):
    size: int
    sha256: str


def file_record(path: Path) -> FileRecord:
    with path.open("rb") as source:
        checksum = hashlib.file_digest(source, "sha256").hexdigest()
    return {"size": path.stat().st_size, "sha256": checksum}


def library_photo_ids(library: PhotoLibrary) -> set[str]:
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
    """One destination, one configuration, and only files written while tracking."""

    filename = ".icloudpd-prune.json"

    def __init__(self, directory: str, scope: str, dry_run: bool = False) -> None:
        self.directory = Path(directory).resolve()
        self.path = self.directory / self.filename
        self.lock = self.directory / ".icloudpd-prune.lock"
        self.scope = scope
        self.files: dict[str, dict[str, FileRecord]] = {}
        self.locked = False
        if dry_run:
            if self.lock.exists() or self.lock.is_symlink():
                raise ValueError("Another orphan-pruning run holds the destination lock")
        else:
            self.directory.mkdir(parents=True, exist_ok=True)
            self.lock.touch(exist_ok=False)
            self.locked = True
        try:
            if self.path.is_symlink():
                raise ValueError("Pruning snapshot must not be a symlink")
            if self.path.exists():
                self._load()
            self.previous_ids = set(self.files)
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        if self.locked:
            self.lock.unlink()
            self.locked = False

    def _local_path(self, relative: str) -> Path:
        path = self.directory / relative
        if (
            not relative
            or Path(relative).is_absolute()
            or not path.is_relative_to(self.directory)
            or ".." in Path(relative).parts
            or path == self.directory
            or path.resolve() != path
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

    def finish(
        self,
        logger: logging.Logger,
        library: PhotoLibrary,
        dry_run: bool,
        cancelled: Callable[[], bool] | None = None,
    ) -> None:
        inventory = library_photo_ids(library)
        if cancelled is not None and cancelled():
            raise ValueError("Orphan pruning was cancelled")
        retained_paths = {
            relative
            for asset_id, paths in self.files.items()
            if asset_id in inventory
            for relative in paths
        }
        for asset_id in list(self.files):
            if asset_id in inventory or asset_id not in self.previous_ids:
                continue
            for relative, expected in self.files[asset_id].items():
                if cancelled is not None and cancelled():
                    raise ValueError("Orphan pruning was cancelled")
                path = self._local_path(relative)
                if relative in retained_paths or not path.exists():
                    continue
                if not path.is_file() or file_record(path) != expected:
                    logger.warning("Keeping changed tracked file %s", path)
                elif dry_run:
                    logger.info("[DRY RUN] Would prune %s", path)
                else:
                    path.unlink()
                    logger.info("Pruned %s", path)
            del self.files[asset_id]
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
