"""Identity-based deletion state using the pruning snapshot's scope and file records."""

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Iterable

from icloudpd.prune import FileRecord, file_record


class AutoDeleteManifest:
    """Track exact files and complete generations independently of orphan pruning."""

    VERSION = 2
    filename = ".icloudpd-autodelete.json"

    def __init__(
        self,
        root: Path,
        scope: str,
        files: dict[str, dict[str, FileRecord]] | None = None,
        previous_active_ids: set[str] | None = None,
        generation: int = 0,
    ) -> None:
        self._input_root = Path(os.path.abspath(root))
        self.root = root.resolve()
        self.path = self.root / self.filename
        self.scope = scope
        self.files = files or {}
        self.previous_active_ids = previous_active_ids
        self.generation = generation
        self.active_ids: set[str] = set()
        self._path_owners: dict[str, str | None] | None = None
        self._file_owners: dict[tuple[int, int], str | None] | None = None

    @classmethod
    def load(cls, root: Path, scope: str) -> "AutoDeleteManifest":
        manifest = cls(root, scope)
        try:
            # Check before exists(): a dangling symlink must not become a new baseline.
            if manifest.path.is_symlink():
                raise ValueError("manifest must not be a symbolic link")
            if not manifest.path.exists():
                return manifest
            raw = json.loads(manifest.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or raw.get("version") != cls.VERSION:
                raise ValueError("unsupported manifest version")
            if raw.get("scope") != scope:
                raise ValueError("manifest belongs to another account, library or configuration")
            manifest.files = manifest._load_files(raw.get("files"))
            previous = raw.get("previous_active_ids")
            generation = raw.get("generation")
            if (
                not isinstance(previous, list)
                or not previous
                or not all(isinstance(asset_id, str) and asset_id for asset_id in previous)
                or len(set(previous)) != len(previous)
                or type(generation) is not int
                or generation < 1
            ):
                raise ValueError("invalid complete generation")
            manifest.previous_active_ids = set(previous)
            manifest.generation = generation
            return manifest
        except (OSError, ValueError, TypeError) as error:
            raise ValueError(
                f"cannot safely read auto-delete manifest {manifest.path}: {error}"
            ) from error

    def _load_files(self, raw_files: object) -> dict[str, dict[str, FileRecord]]:
        if not isinstance(raw_files, dict):
            raise ValueError("invalid files")
        files: dict[str, dict[str, FileRecord]] = {}
        for asset_id, paths in raw_files.items():
            if not isinstance(asset_id, str) or not asset_id or not isinstance(paths, dict):
                raise ValueError("invalid asset paths")
            records: dict[str, FileRecord] = {}
            for relative, record in paths.items():
                self._local_path(relative)
                if (
                    not isinstance(record, dict)
                    or type(record.get("size")) is not int
                    or record["size"] < 0
                    or not isinstance(record.get("sha256"), str)
                    or len(record["sha256"]) != 64
                    or any(char not in "0123456789abcdef" for char in record["sha256"])
                ):
                    raise ValueError("invalid file fingerprint")
                records[relative] = {"size": record["size"], "sha256": record["sha256"]}
            files[asset_id] = records
        return files

    def _local_path(self, relative: str) -> Path:
        if not isinstance(relative, str) or not relative:
            raise ValueError("unsafe auto-delete path")
        candidate = Path(relative)
        path = self.root / candidate
        if (
            candidate.is_absolute()
            or str(candidate) != relative
            or candidate == Path(".")
            or ".." in candidate.parts
            or path.resolve() != path
            or candidate.parts[0] == ".icloudpd-pruned"
            or any(part.startswith(".icloudpd-") for part in candidate.parts)
            or path.name.endswith(".part")
        ):
            raise ValueError(f"unsafe auto-delete path: {relative}")
        return path

    @property
    def has_previous_generation(self) -> bool:
        return self.previous_active_ids is not None

    def record_active(self, asset_id: str, paths: Iterable[str]) -> None:
        if not asset_id:
            raise ValueError("asset ID must not be empty")
        self.active_ids.add(asset_id)
        for path in paths:
            relative = self._relative(path)
            local_path = self._local_path(relative)
            records = self.files.setdefault(asset_id, {})
            if relative not in records:
                # Never refresh a known fingerprint from a local edit during a later scan.
                records[relative] = file_record(local_path)
                self.invalidate_ownership()

    def invalidate_ownership(self) -> None:
        """Rebuild live file identities for a new cleanup pass or new tracked paths."""
        self._path_owners = None
        self._file_owners = None

    def _file_identity(self, relative: str) -> tuple[int, int] | None:
        try:
            info = self._local_path(relative).stat(follow_symlinks=False)
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(info.st_mode) or info.st_ino <= 0:
            raise ValueError(f"cannot establish file identity: {relative}")
        # The device is essential: inode numbers are only unique within a filesystem.
        return info.st_dev, info.st_ino

    def paths_for_deleted(self, asset_id: str) -> set[str]:
        """Return paths uniquely owned by an ID absent from both complete scans."""
        if (
            self.previous_active_ids is None
            or asset_id in self.previous_active_ids
            or asset_id in self.active_ids
        ):
            return set()
        paths = self.files.get(asset_id, {})
        if not paths:
            return set()
        if self._path_owners is None:
            path_owners: dict[str, str | None] = {}
            file_owners: dict[tuple[int, int], str | None] = {}
            for owner_id, owner_paths in self.files.items():
                for relative in owner_paths:
                    if relative not in path_owners:
                        path_owners[relative] = owner_id
                    elif path_owners[relative] != owner_id:
                        path_owners[relative] = None
                    identity = self._file_identity(relative)
                    if identity is not None:
                        if identity not in file_owners:
                            file_owners[identity] = owner_id
                        elif file_owners[identity] != owner_id:
                            file_owners[identity] = None
            # Do not cache a partial index if any path could not be inspected.
            self._path_owners = path_owners
            self._file_owners = file_owners
        if any(self._path_owners[relative] != asset_id for relative in paths):
            return set()
        assert self._file_owners is not None
        for relative in paths:
            identity = self._file_identity(relative)
            # Missing members are rejected by the whole-asset content preflight.
            # They may also be members already deleted in the current pass.
            if identity is not None and self._file_owners.get(identity) != asset_id:
                return set()
        return {str(self._local_path(relative)) for relative in paths}

    def matches_file(self, asset_id: str, path: str) -> bool:
        relative = self._relative(path)
        candidate = self._local_path(relative)
        expected = self.files.get(asset_id, {}).get(relative)
        return expected is not None and candidate.is_file() and file_record(candidate) == expected

    def forget(self, asset_id: str) -> None:
        self.files.pop(asset_id, None)
        # Keep this pass's conservative ownership index. Rebuilding after each
        # deletion would rescan the entire mirror and could reuse a removed inode.

    def validate_generation(self) -> None:
        """Validate before any deletion, not just before saving the next generation."""
        if not self.active_ids:
            raise ValueError("refusing an empty active-library generation")

    def commit_generation(self) -> None:
        self.validate_generation()
        self.previous_active_ids = set(self.active_ids)
        self.generation += 1

    def _relative(self, path: str) -> str:
        absolute = Path(os.path.abspath(path))
        for root in (self._input_root, self.root):
            try:
                relative = str(absolute.relative_to(root))
            except ValueError:
                continue
            self._local_path(relative)
            return relative
        raise ValueError(f"path outside auto-delete directory: {path}")

    def save(self) -> None:
        if not self.previous_active_ids or self.generation < 1:
            raise ValueError("cannot save without a complete active-library generation")
        if self.path.is_symlink():
            raise ValueError("manifest must not be a symbolic link")
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self.VERSION,
            "scope": self.scope,
            "files": self.files,
            "generation": self.generation,
            "previous_active_ids": sorted(self.previous_active_ids),
        }
        fd, temporary = tempfile.mkstemp(
            prefix=".icloudpd-autodelete.", suffix=".part", dir=self.root
        )
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(payload, file, sort_keys=True)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
            directory_fd = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
