from enum import Enum
from threading import Lock
from typing import Optional


class Status(Enum):
    NOT_NEED_MFA = "not_need_mfa"
    NEED_MFA = "need_mfa"
    SUPPLIED_MFA = "supplied_mfa"
    CHECKING_MFA = "checking_mfa"


class StatusExchange:
    def __init__(self) -> None:
        self.lock = Lock()
        self._status = Status.NOT_NEED_MFA
        self._code: Optional[str] = None

    def get_status(self) -> Status:
        with self.lock:
            return self._status

    def replace_status(self, expected_status: Status, new_status: Status) -> bool:
        with self.lock:
            if self._status == expected_status:
                self._status = new_status
                return True
            else:
                return False

    def set_code(self, code: str) -> bool:
        with self.lock:
            if self._status != Status.NEED_MFA:
                return False

            self._code = code
            self._status = Status.SUPPLIED_MFA
            return True

    def get_code(self) -> Optional[str]:
        with self.lock:
            if self._status not in [Status.SUPPLIED_MFA,Status.CHECKING_MFA]:
                return None

            return self._code
