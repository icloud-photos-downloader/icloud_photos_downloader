from enum import Enum


class PasswordProvider(Enum):
    PARAMETER = "parameter"
    CONSOLE = "console"
    KEYRING = "keyring"
    