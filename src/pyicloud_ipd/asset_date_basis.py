from enum import Enum


class AssetDateBasis(Enum):
    CREATED = "created" # assetDate
    ADDED = "added" # addedDate

    def __str__(self) -> str:
        return self.name