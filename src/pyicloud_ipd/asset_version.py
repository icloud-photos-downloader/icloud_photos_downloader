import os
from typing import Callable, Dict

from pyicloud_ipd.item_type import AssetItemType
from pyicloud_ipd.version_size import AssetVersionSize, VersionSize

# Constants moved from PhotoAsset class
ITEM_TYPE_EXTENSIONS = {
    "public.heic": "HEIC",
    "public.heif": "HEIF",
    "public.jpeg": "JPG",
    "public.png": "PNG",
    "com.apple.quicktime-movie": "MOV",
    "com.adobe.raw-image": "DNG",
    "com.canon.cr2-raw-image": "CR2",
    "com.canon.crw-raw-image": "CRW",
    "com.sony.arw-raw-image": "ARW",
    "com.fuji.raw-image": "RAF",
    "com.panasonic.rw2-raw-image": "RW2",
    "com.nikon.nrw-raw-image": "NRF",
    "com.pentax.raw-image": "PEF",
    "com.nikon.raw-image": "NEF",
    "com.olympus.raw-image": "ORF",
    "com.canon.cr3-raw-image": "CR3",
    "com.olympus.or-raw-image": "ORF",
}

VERSION_FILENAME_SUFFIX_LOOKUP: Dict[VersionSize, str] = {
    AssetVersionSize.MEDIUM: "medium",
    AssetVersionSize.THUMB: "thumb",
}


def add_suffix_to_filename(suffix: str, filename: str) -> str:
    """Add suffix to filename before extension."""
    _n, _e = os.path.splitext(filename)
    return _n + suffix + _e


def calculate_version_filename(
    base_filename: str,
    version: "AssetVersion",
    version_size: VersionSize,
    lp_filename_generator: Callable[[str], str],
    item_type: AssetItemType | None = None,
    filename_override: str | None = None,
) -> str:
    """
    Calculate filename for a specific asset version with optional override.

    Args:
        base_filename: The base filename from PhotoAsset
        version: The AssetVersion object
        version_size: The size key for this version
        lp_filename_generator: Function to generate live photo filenames
        item_type: Asset item type for live photo detection
        filename_override: Optional override filename for disambiguation

    Returns:
        The calculated or override filename for this asset version
    """
    if filename_override is not None:
        return filename_override

    return calculate_asset_version_filename(
        base_filename,
        version.type,
        version_size,
        lp_filename_generator,
        ITEM_TYPE_EXTENSIONS,
        VERSION_FILENAME_SUFFIX_LOOKUP,
        (item_type or AssetItemType.IMAGE) == AssetItemType.IMAGE,
    )


class AssetVersion:
    def __init__(self, size: int, url: str, type: str, checksum: str) -> None:
        self.size = size
        self.url = url
        self.type = type
        self.checksum = checksum

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AssetVersion):
            # don't attempt to compare against unrelated types
            return NotImplemented
        return self.size == other.size and self.url == other.url and self.type == other.type


def calculate_asset_version_filename(
    base_filename: str,
    asset_type: str,
    version_size: VersionSize,
    lp_filename_generator: Callable[[str], str],
    item_type_extensions: Dict[str, str],
    version_filename_suffix_lookup: Dict[VersionSize, str],
    is_image_item_type: bool = True,
) -> str:
    """
    Calculate filename for an AssetVersion based on the base filename and version properties.

    Args:
        base_filename: The base filename from PhotoAsset
        asset_type: The type field from the version
        version_size: The size key for this version
        lp_filename_generator: Function to generate live photo filenames
        item_type_extensions: Mapping of types to extensions
        version_filename_suffix_lookup: Mapping of sizes to filename suffixes
        is_image_item_type: Whether the parent asset is an image (for live photo detection)

    Returns:
        The calculated filename for this asset version
    """
    filename = base_filename

    # Change live photo movie file extension to .MOV
    if is_image_item_type and asset_type == "com.apple.quicktime-movie":
        filename = lp_filename_generator(base_filename)  # without size
    else:
        # for non live photo movie, try to change file type to match asset type
        _f, _e = os.path.splitext(filename)
        filename = _f + "." + item_type_extensions.get(asset_type, _e[1:])

    # add size suffix
    if version_size in version_filename_suffix_lookup:
        _size_suffix = version_filename_suffix_lookup[version_size]
        filename = add_suffix_to_filename(f"-{_size_suffix}", filename)

    return filename
