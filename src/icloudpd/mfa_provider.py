from enum import Enum


class MFAProvider(Enum):
    CONSOLE = "console"
    WEBUI = "webui"
    TELEGRAM = "telegram"

    def __str__(self) -> str:
        return self.name
