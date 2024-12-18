from typing import Union


class AssetVersion:
    def __init__(self, filename: str, size: int, url: str, type: str) -> None:
        self.filename = filename
        self.size = size
        self.url = url
        self.type = type

    def __eq__(self, other: object) -> bool: 
        if not isinstance(other, AssetVersion):
            # don't attempt to compare against unrelated types
            return NotImplemented
        return self.filename == other.filename and self.size == other.size and self.url == other.url and self.type == other.type