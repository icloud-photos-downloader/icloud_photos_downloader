"""
Delete any files found in "Recently Deleted"
"""
import logging
import os
from tzlocal import get_localzone
from icloudpd.paths import local_download_path
import pyicloud_ipd


def delete_file(logger: logging.Logger, path: str) -> bool:
    """ Actual deletion of files """
    os.remove(path)
    logger.info("Deleted %s", path)
    return True


def delete_file_dry_run(logger: logging.Logger, path: str) -> bool:
    """ Dry run deletion of files """
    logger.info("[DRY RUN] Would delete %s", path)
    return True


def autodelete_photos(
        logger: logging.Logger,
        dry_run: bool,
        library_object,
        folder_structure: str,
        directory: str):
    """
    Scans the "Recently Deleted" folder and deletes any matching files
    from the download directory.
    (I.e. If you delete a photo on your phone, it's also deleted on your computer.)
    """
    logger.info("Deleting any files found in 'Recently Deleted'...")

    recently_deleted = library_object.albums["Recently Deleted"]

    for media in recently_deleted:
        try:
            created_date = media.created.astimezone(get_localzone())
        except (ValueError, OSError):
            logger.error(
                "Could not convert media created date to local timezone %s",
                media.created)
            created_date = media.created

        date_path = folder_structure.format(created_date)
        download_dir = os.path.join(directory, date_path)

        for size in ["small", "original", "medium", "thumb"]:
            path = os.path.normpath(
                local_download_path(
                    media, size, download_dir))
            if os.path.exists(path):
                logger.debug("Deleting %s...", path)
                delete_local = delete_file_dry_run if dry_run else delete_file
                delete_local(logger, path)
