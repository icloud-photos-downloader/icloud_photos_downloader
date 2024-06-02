from enum import Enum
from typing import Union

class AssetVersionSize(Enum):
    ORIGINAL = "original"
    ADJUSTED = "adjusted"
    ALTERNATIVE = "alternative"
    MEDIUM = "medium"
    THUMB = "thumb"

class LivePhotoVersionSize(Enum):
    ORIGINAL = "originalVideo"
    MEDIUM = "mediumVideo"
    THUMB = "smallVideo"

VersionSize = Union[AssetVersionSize, LivePhotoVersionSize]
