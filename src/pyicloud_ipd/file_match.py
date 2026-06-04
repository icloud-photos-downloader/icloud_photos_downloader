from enum import Enum


class FileMatchPolicy(Enum):
    NAME_SIZE_DEDUP_WITH_SUFFIX = "name-size-dedup-with-suffix"
    NAME_ID7 = "name-id7"
    NAME_ID7_VERSIONED = "name-id7-versioned"

    def __str__(self) -> str:
        return self.name
