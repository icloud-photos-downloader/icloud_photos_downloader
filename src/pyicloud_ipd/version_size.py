from enum import Enum
from typing import Union


class AssetVersionSize(Enum):
    ORIGINAL = "original"
    ADJUSTED = "adjusted"
    ALTERNATIVE = "alternative"
    MEDIUM = "medium"
    THUMB = "thumb"

    def __str__(self) -> str:
        return self.name


class LivePhotoVersionSize(Enum):
    ORIGINAL = "original"
    MEDIUM = "medium"
    THUMB = "small"

    def __str__(self) -> str:
        return self.name


VersionSize = Union[AssetVersionSize, LivePhotoVersionSize]
