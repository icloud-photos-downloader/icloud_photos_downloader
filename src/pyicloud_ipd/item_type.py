from enum import Enum


class AssetItemType(Enum):
    MOVIE = "movie"
    IMAGE = "image"

    def __str__(self) -> str:
        return self.name
