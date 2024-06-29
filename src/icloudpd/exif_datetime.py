"""Get/set EXIF dates from photos"""

import logging
import typing

import piexif
from piexif._exceptions import InvalidImageDataError


def get_photo_exif(logger: logging.Logger, path: str) -> typing.Optional[str]:
    """Get EXIF date for a photo, return nothing if there is an error"""
    try:
        exif_dict: piexif.ExifIFD = piexif.load(path)
        return typing.cast(typing.Optional[str], exif_dict.get("Exif").get(36867))
    except (ValueError, InvalidImageDataError):
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
    except (ValueError, InvalidImageDataError):
        logger.debug("Error setting EXIF data for %s", path)
        return
