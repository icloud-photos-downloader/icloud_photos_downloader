from enum import Enum
from threading import Lock

from icloudpd.config import Config
from icloudpd.progress import Progress


class Status(Enum):
    NO_INPUT_NEEDED = "no_input_needed"
    NEED_MFA = "need_mfa"
    SUPPLIED_MFA = "supplied_mfa"
    CHECKING_MFA = "checking_mfa"
    NEED_PASSWORD = "need_password"
    SUPPLIED_PASSWORD = "supplied_password"
    CHECKING_PASSWORD = "checking_password"

    def __str__(self) -> str:
        return self.name


class StatusExchange:
    def __init__(self) -> None:
        self.lock = Lock()
        self._status = Status.NO_INPUT_NEEDED
        self._payload: str | None = None
        self._error: str | None = None
        self._config: Config | None = None
        self._progress = Progress()

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

    def set_payload(self, payload: str) -> bool:
        with self.lock:
            if self._status != Status.NEED_MFA and self._status != Status.NEED_PASSWORD:
                return False

            self._payload = payload
            self._status = (
                Status.SUPPLIED_MFA if self._status == Status.NEED_MFA else Status.SUPPLIED_PASSWORD
            )
            self._error = None
            return True

    def get_payload(self) -> str | None:
        with self.lock:
            if self._status not in [
                Status.SUPPLIED_MFA,
                Status.CHECKING_MFA,
                Status.SUPPLIED_PASSWORD,
                Status.CHECKING_PASSWORD,
            ]:
                return None

            return self._payload

    def set_error(self, error: str) -> bool:
        with self.lock:
            if self._status != Status.CHECKING_MFA and self._status != Status.CHECKING_PASSWORD:
                return False

            self._error = error
            self._status = (
                Status.NO_INPUT_NEEDED
                if self._status == Status.CHECKING_PASSWORD
                else Status.NEED_MFA
            )
            return True

    def get_error(self) -> str | None:
        with self.lock:
            if self._status not in [
                Status.NO_INPUT_NEEDED,
                Status.NEED_PASSWORD,
                Status.NEED_MFA,
            ]:
                return None

            return self._error

    def set_config(self, config: Config) -> None:
        with self.lock:
            self._config = config

    def get_config(self) -> Config | None:
        with self.lock:
            return self._config

    def get_progress(self) -> Progress:
        with self.lock:
            return self._progress
