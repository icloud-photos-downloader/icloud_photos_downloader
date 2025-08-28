from enum import Enum


class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    ERROR = "error"

    def __str__(self) -> str:
        return self.name
