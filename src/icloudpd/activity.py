import os
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List

MAX_ENTRIES = 200
DEFAULT_LIMIT = 50


class ActivityLog:
    """Thread-safe record of the files downloaded in this process (newest first), for the web API."""

    def __init__(self, maxlen: int = MAX_ENTRIES, enabled: bool = True) -> None:
        self.enabled = enabled
        self._lock = threading.Lock()
        self._items: Deque[Dict[str, Any]] = deque(maxlen=maxlen)
        self._total = 0

    def record_download(self, path: str) -> None:
        if not self.enabled:
            return
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

    def snapshot(self, limit: int = DEFAULT_LIMIT) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._items)[:limit]


# recording starts only when the status API is switched on (--webui-api)
activity_log = ActivityLog(enabled=False)
