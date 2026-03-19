"""Directory listing cache to avoid per-file stat calls on network mounts.

On network-mounted filesystems (e.g. WSL → Windows), each os.path.isfile()
and os.stat() call incurs significant latency (~5-50ms). For a no-op sync
of 27k+ files, this adds up to 80k+ round trips and ~18 minutes.

This module pre-scans directories with os.scandir() (single round trip per
directory) and serves subsequent existence + size checks from memory.
"""

import logging
import os
import stat
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CachedEntry:
    """Cached file metadata from a directory scan."""
    size: int
    is_file: bool


class DirCache:
    """Caches directory listings to avoid per-file stat calls."""

    def __init__(self) -> None:
        self._cache: dict[str, dict[str, CachedEntry]] = {}

    def _scan_dir(self, directory: str) -> dict[str, CachedEntry]:
        """Scan a directory and cache all entries."""
        entries: dict[str, CachedEntry] = {}
        try:
            with os.scandir(directory) as it:
                for entry in it:
                    try:
                        st = entry.stat()
                        entries[entry.name] = CachedEntry(
                            size=st.st_size,
                            is_file=stat.S_ISREG(st.st_mode),
                        )
                    except OSError:
                        pass
        except OSError as e:
            if os.path.isdir(directory):
                logger.warning("Failed to scan directory %s: %s", directory, e)
        self._cache[directory] = entries
        return entries

    def _get_dir(self, directory: str) -> dict[str, CachedEntry]:
        """Get cached directory listing, scanning on first access."""
        if directory not in self._cache:
            return self._scan_dir(directory)
        return self._cache[directory]

    def isfile(self, path: str) -> bool:
        """Cached equivalent of os.path.isfile()."""
        directory = os.path.dirname(path)
        filename = os.path.basename(path)
        entries = self._get_dir(directory)
        entry = entries.get(filename)
        return entry is not None and entry.is_file

    def stat_size(self, path: str) -> int:
        """Cached equivalent of os.stat(path).st_size."""
        directory = os.path.dirname(path)
        filename = os.path.basename(path)
        entries = self._get_dir(directory)
        entry = entries.get(filename)
        if entry is None:
            raise FileNotFoundError(path)
        return entry.size

    def exists(self, path: str) -> bool:
        """Cached equivalent of os.path.exists()."""
        directory = os.path.dirname(path)
        filename = os.path.basename(path)
        entries = self._get_dir(directory)
        return filename in entries

    def getsize(self, path: str) -> int:
        """Cached equivalent of os.path.getsize()."""
        return self.stat_size(path)

    def notify_new_file(self, path: str, size: int) -> None:
        """Update cache after a new file is created (e.g. after download)."""
        directory = os.path.dirname(path)
        filename = os.path.basename(path)
        entries = self._get_dir(directory)
        entries[filename] = CachedEntry(size=size, is_file=True)
