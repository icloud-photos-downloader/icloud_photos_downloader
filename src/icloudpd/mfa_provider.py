from enum import Enum


class MFAProvider(Enum):
    CONSOLE = "console"
    WEBUI = "webui"

    def __str__(self) -> str:
        return self.name
