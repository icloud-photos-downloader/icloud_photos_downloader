from enum import Enum


class LivePhotoMovFilenamePolicy(Enum):
    SUFFIX = "suffix"
    ORIGINAL = "original"

    def __str__(self) -> str:
        return self.name
