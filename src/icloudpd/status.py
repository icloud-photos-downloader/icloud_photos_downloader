from enum import Enum
from threading import Lock
from typing import Optional


class Status(Enum):
    INITIALIZING = "initializing"
    AUTHENTICATING = "authenticating"
    WAITING_FOR_2FA = "waiting_for_2fa"
    READY_WITH_2FA = "ready_with_2fa"
    AUTHENTICATING_2FA = "authenticating _2fa"
    AUTHENTICATED = "authenticated"
    DOWNLOADING = "downloading"


class StatusExchange:
    def __init__(self) -> None:
        self.lock = Lock()
        self._status = Status.INITIALIZING
        self._code: Optional[str] = None

    # def set_status(self, status: Status) -> None:
    #     with self.lock:
    #         self._status = status
    #         if status != Status.READY_WITH_2FA:
    #             self._code = None

    def get_status(self) -> Status:
        with self.lock:
            return self._status

    def set_code(self, code: str) -> bool:
        with self.lock:
            if self._status != Status.WAITING_FOR_2FA:
                return False
            
            self._code = code
            self._status = Status.READY_WITH_2FA
            return True

    def get_code(self) -> Optional[str]:
        with self.lock:
            if self._status != Status.READY_WITH_2FA:
                return None
            
            return self._code
