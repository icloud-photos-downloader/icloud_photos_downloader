import os
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List


class ActivityLog:
    """Thread-safe record of the files downloaded in this process (newest first), for the web API."""

    def __init__(self, maxlen: int = 200) -> None:
        self._lock = threading.Lock()
        self._items: Deque[Dict[str, Any]] = deque(maxlen=maxlen)
        self._total = 0

    def record_download(self, path: str) -> None:
        try:
            size: int | None = os.path.getsize(path)
        except OSError:
            size = None
        with self._lock:
            self._total += 1
            self._items.appendleft(
                {
                    "name": os.path.basename(path),
                    "path": os.path.abspath(path),
                    "size": size,
                    "time": time.time(),
                }
            )

    @property
    def total(self) -> int:
        with self._lock:
            return self._total

    def snapshot(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._items)[:limit]


activity_log = ActivityLog()
