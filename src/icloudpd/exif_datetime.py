"""Get/set EXIF dates from photos"""

import logging
import struct
import typing

import piexif
from piexif._exceptions import InvalidImageDataError

# Writing the three date tags adds about 70-200 bytes to a JPEG; anything larger is not ours
MAX_DATE_TAGS_SIZE = 1024


def has_own_exif_date(
    logger: logging.Logger, path: str, date: str, local_size: int, icloud_size: int
) -> bool:
    """True when path looks like the iCloud file after --set-exif-datetime wrote date into it.

    Writing the date makes the local JPEG a little larger than the one in iCloud, so the
    name-size check would take it for a different photo and download it again (#380)."""
    if not path.lower().endswith((".jpg", ".jpeg")):
        return False
    if not 0 < local_size - icloud_size <= MAX_DATE_TAGS_SIZE:
        return False
    found: str | bytes | None = get_photo_exif(logger, path)
    if isinstance(found, bytes):
        found = found.decode("ascii", errors="replace")
    return found == date


def get_photo_exif(logger: logging.Logger, path: str) -> str | None:
    """Get EXIF date for a photo, return nothing if there is an error"""
    # piexif raises struct.error on a truncated or malformed EXIF block (hMatoba/Piexif#129)
    try:
        exif_dict: piexif.ExifIFD = piexif.load(path)
        return typing.cast(str | None, exif_dict.get("Exif").get(36867))
    except (ValueError, InvalidImageDataError, struct.error):
        logger.debug("Error fetching EXIF data for %s", path)
        return None


def set_photo_exif(logger: logging.Logger, path: str, date: str) -> None:
    """Set EXIF date on a photo, do nothing if there is an error"""
    try:
        exif_dict = piexif.load(path)
        exif_dict.get("1st")[306] = date
        exif_dict.get("Exif")[36867] = date
        exif_dict.get("Exif")[36868] = date
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, path)
    except (ValueError, InvalidImageDataError, struct.error):
        logger.debug("Error setting EXIF data for %s", path)
        return
