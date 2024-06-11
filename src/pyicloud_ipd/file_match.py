from enum import Enum

class FileMatchPolicy(Enum):
    NAME_WITH_SIZE_SUFFIX = "name-size-dedup-with-suffix"
    NAME_WITH_ID7_SUFFIX = "name-id7"
