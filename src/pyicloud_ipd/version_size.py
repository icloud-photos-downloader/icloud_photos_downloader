from enum import Enum


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


VersionSize = AssetVersionSize | LivePhotoVersionSize
