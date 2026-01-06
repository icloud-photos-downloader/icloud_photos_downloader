from enum import Enum
from threading import Lock
from typing import Sequence

from icloudpd.config import GlobalConfig, UserConfig
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
        self._global_config: GlobalConfig | None = None
        self._user_configs: Sequence[UserConfig] = []
        self._current_user: str | None = None
        self._progress = Progress()
        self._force_full_sync = False
        self._manual_sync = False  # True if sync was triggered manually via Telegram
        self._telegram_bot = None  # Reference to Telegram bot for auth requests

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

    def get_progress(self) -> Progress:
        with self.lock:
            return self._progress

    def set_global_config(self, global_config: GlobalConfig) -> None:
        with self.lock:
            self._global_config = global_config

    def get_global_config(self) -> GlobalConfig | None:
        with self.lock:
            return self._global_config

    def set_user_configs(self, user_configs: Sequence[UserConfig]) -> None:
        with self.lock:
            self._user_configs = user_configs

    def get_user_configs(self) -> Sequence[UserConfig]:
        with self.lock:
            return self._user_configs

    def set_current_user(self, username: str) -> None:
        with self.lock:
            self._current_user = username

    def get_current_user(self) -> str | None:
        with self.lock:
            return self._current_user

    def clear_current_user(self) -> None:
        with self.lock:
            self._current_user = None

    def set_force_full_sync(self, force: bool) -> None:
        with self.lock:
            self._force_full_sync = force

    def get_force_full_sync(self) -> bool:
        with self.lock:
            return self._force_full_sync

    def set_manual_sync(self, manual: bool) -> None:
        with self.lock:
            self._manual_sync = manual

    def get_manual_sync(self) -> bool:
        with self.lock:
            return self._manual_sync

    def set_telegram_bot(self, telegram_bot) -> None:
        """Set Telegram bot reference for authentication requests"""
        with self.lock:
            self._telegram_bot = telegram_bot

    def get_telegram_bot(self):
        """Get Telegram bot reference"""
        with self.lock:
            return self._telegram_bot
