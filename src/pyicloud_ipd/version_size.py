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


# Maps VersionSize enums to Apple's iCloud resource field prefixes.
# These prefixes are stable identifiers from the CPLMaster record.
_VERSION_TO_RESOURCE: dict[VersionSize, str] = {
    AssetVersionSize.ORIGINAL: "resOriginal",
    AssetVersionSize.ALTERNATIVE: "resOriginalAlt",
    AssetVersionSize.ADJUSTED: "resJPEGFull",
    AssetVersionSize.MEDIUM: "resJPEGMed",
    AssetVersionSize.THUMB: "resJPEGThumb",
    LivePhotoVersionSize.ORIGINAL: "resOriginalVidCompl",
    LivePhotoVersionSize.MEDIUM: "resVidMed",
    LivePhotoVersionSize.THUMB: "resVidSmall",
}


def version_to_resource(version_size: VersionSize) -> str:
    """Map a VersionSize enum to its Apple resource field prefix."""
    return _VERSION_TO_RESOURCE[version_size]
