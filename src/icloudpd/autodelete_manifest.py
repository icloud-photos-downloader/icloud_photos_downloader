"""Persistent identity-to-path state used by safe auto-delete."""

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Iterable


class AutoDeleteManifest:
    """Track exact paths and the previous complete active-library generation."""

    VERSION = 2
    LEGACY_VERSION = 1

    def __init__(
        self,
        path: Path,
        root: Path,
        assets: dict[str, set[str]] | None = None,
        previous_active_ids: set[str] | None = None,
        generation: int = 0,
    ) -> None:
        self.path = path
        self.root = root.resolve()
        self.assets = assets or {}
        self.previous_active_ids = previous_active_ids
        self.generation = generation
        self.active_ids: set[str] = set()
        self._path_owners: dict[str, str | None] | None = None

    @classmethod
    def path_for(cls, cookie_directory: Path, username: str, root: Path) -> Path:
        """Return a non-identifying manifest path scoped to one user and root."""
        identity = f"{username}\0{root.resolve()}".encode()
        digest = hashlib.sha256(identity).hexdigest()[:20]
        return cookie_directory / f"auto-delete-manifest-{digest}.json"

    @classmethod
    def load(cls, path: Path, root: Path) -> "AutoDeleteManifest":
        if not path.exists():
            return cls(path, root)
        try:
            if path.is_symlink():
                raise ValueError("manifest must not be a symbolic link")
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or not isinstance(raw.get("assets"), dict):
                raise ValueError("invalid manifest")

            resolved_root = root.resolve()
            version = raw.get("version")
            assets = cls._load_assets(raw["assets"])
            if version == cls.LEGACY_VERSION:
                return cls(path, resolved_root, assets)
            if version != cls.VERSION:
                raise ValueError("unsupported manifest version")
            if raw.get("root") != str(resolved_root):
                raise ValueError("manifest download directory does not match")

            previous = raw.get("previous_active_ids")
            generation = raw.get("generation")
            if (
                not isinstance(previous, list)
                or not all(isinstance(asset_id, str) and asset_id for asset_id in previous)
                or len(set(previous)) != len(previous)
                or not isinstance(generation, int)
                or isinstance(generation, bool)
                or generation < 1
            ):
                raise ValueError("invalid complete generation")
            return cls(path, resolved_root, assets, set(previous), generation)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            raise ValueError(f"cannot safely read auto-delete manifest {path}") from error

    @classmethod
    def _load_assets(cls, raw_assets: object) -> dict[str, set[str]]:
        if not isinstance(raw_assets, dict):
            raise ValueError("invalid assets")
        assets: dict[str, set[str]] = {}
        for asset_id, paths in raw_assets.items():
            if (
                not isinstance(asset_id, str)
                or not asset_id
                or not isinstance(paths, list)
                or not all(isinstance(item, str) and item for item in paths)
            ):
                raise ValueError("invalid asset paths")
            validated = {cls._validate_relative(item) for item in paths}
            if len(validated) != len(paths):
                raise ValueError("duplicate asset paths")
            assets[asset_id] = validated
        return assets

    @staticmethod
    def _validate_relative(relative: str) -> str:
        candidate = Path(relative)
        if candidate.is_absolute() or candidate == Path(".") or ".." in candidate.parts:
            raise ValueError(f"unsafe relative path: {relative}")
        normalized = Path(os.path.normpath(relative))
        if normalized == Path(".") or normalized != candidate:
            raise ValueError(f"unsafe relative path: {relative}")
        return str(normalized)

    @property
    def has_previous_generation(self) -> bool:
        return self.previous_active_ids is not None

    def record_active(self, asset_id: str, paths: Iterable[str]) -> None:
        if not asset_id:
            raise ValueError("asset ID must not be empty")
        self.active_ids.add(asset_id)
        resolved = {self._relative(path) for path in paths}
        if resolved:
            self.assets.setdefault(asset_id, set()).update(resolved)
            self._path_owners = None

    def paths_for_deleted(self, asset_id: str) -> set[str]:
        """Return only paths uniquely owned by an ID absent in two full scans."""
        if (
            self.previous_active_ids is None
            or asset_id in self.previous_active_ids
            or asset_id in self.active_ids
        ):
            return set()
        paths = self.assets.get(asset_id, set())
        if not paths:
            return set()

        if self._path_owners is None:
            self._path_owners = {}
            for owner_id, owner_paths in self.assets.items():
                for relative in owner_paths:
                    if relative not in self._path_owners:
                        self._path_owners[relative] = owner_id
                    elif self._path_owners[relative] != owner_id:
                        self._path_owners[relative] = None
        if any(self._path_owners[relative] != asset_id for relative in paths):
            return set()
        return {str(self.root / relative) for relative in paths}

    def forget(self, asset_id: str) -> None:
        self.assets.pop(asset_id, None)
        self._path_owners = None

    def commit_generation(self) -> None:
        """Promote the current scan only after the full active scan completed."""
        if not self.active_ids and (self.assets or self.previous_active_ids):
            raise ValueError("refusing to commit an empty active-library generation")
        self.previous_active_ids = set(self.active_ids)
        self.generation += 1

    def _relative(self, path: str) -> str:
        resolved = Path(path).resolve()
        try:
            relative = resolved.relative_to(self.root)
        except ValueError as error:
            raise ValueError(f"path outside auto-delete directory: {path}") from error
        return self._validate_relative(str(relative))

    def save(self) -> None:
        if self.previous_active_ids is None or self.generation < 1:
            raise ValueError("cannot save without a complete active-library generation")
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = {
            "version": self.VERSION,
            "root": str(self.root),
            "generation": self.generation,
            "previous_active_ids": sorted(self.previous_active_ids),
            "assets": {asset_id: sorted(paths) for asset_id, paths in sorted(self.assets.items())},
        }
        fd, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(payload, file, sort_keys=True)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
            directory_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
