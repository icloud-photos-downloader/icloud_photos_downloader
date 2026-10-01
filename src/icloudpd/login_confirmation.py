from enum import Enum


class LoginConfirmation(Enum):
    NONE = "none"
    WEBUI = "webui"

    def __str__(self) -> str:
        return self.name
