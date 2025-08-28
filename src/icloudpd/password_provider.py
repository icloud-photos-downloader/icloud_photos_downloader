from enum import Enum


class PasswordProvider(Enum):
    CONSOLE = "console"
    WEBUI = "webui"
    PARAMETER = "parameter"
    KEYRING = "keyring"

    def __str__(self) -> str:
        return self.name
