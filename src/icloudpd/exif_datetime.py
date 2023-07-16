"""Get/set EXIF dates from photos"""

import logging
import piexif
from piexif._exceptions import InvalidImageDataError


def get_photo_exif(logger, path):
    """Get EXIF date for a photo, return nothing if there is an error"""
    try:
        exif_dict = piexif.load(path)
        return exif_dict.get("Exif").get(36867)
    except (ValueError, InvalidImageDataError):
        logger.tqdm_write(f"Error fetching EXIF data for {path}", logging.DEBUG)
        return None


def set_photo_exif(logger, path, date):
    """Set EXIF date on a photo, do nothing if there is an error"""
    try:
        exif_dict = piexif.load(path)
        exif_dict.get("1st")[306] = date
        exif_dict.get("Exif")[36867] = date
        exif_dict.get("Exif")[36868] = date
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, path)
    except (ValueError, InvalidImageDataError):
        logger.tqdm_write(f"Error setting EXIF data for {path}", logging.DEBUG)
        return
