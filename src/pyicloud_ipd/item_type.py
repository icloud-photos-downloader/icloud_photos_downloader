from enum import Enum
from typing import Union


class AssetItemType(Enum):
    MOVIE = "movie"
    IMAGE = "image"

    def __str__(self) -> str:
        return self.name
