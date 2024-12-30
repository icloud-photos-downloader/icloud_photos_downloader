"""
Delete any files found in "Recently Deleted"
"""

import datetime
import logging
import os
from typing import Sequence, Set

from tzlocal import get_localzone

from icloudpd.paths import local_download_path
from pyicloud_ipd.services.photos import PhotoLibrary
from pyicloud_ipd.utils import disambiguate_filenames
from pyicloud_ipd.version_size import AssetVersionSize, VersionSize


def delete_file(logger: logging.Logger, path: str) -> bool:
    """Actual deletion of files"""
    os.remove(path)
    logger.info("Deleted %s", path)
    return True


def delete_file_dry_run(logger: logging.Logger, path: str) -> bool:
    """Dry run deletion of files"""
    logger.info("[DRY RUN] Would delete %s", path)
    return True


def autodelete_photos(
    logger: logging.Logger,
    dry_run: bool,
    library_object: PhotoLibrary,
    folder_structure: str,
    directory: str,
    _sizes: Sequence[AssetVersionSize],
) -> None:
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
            logger.error("Could not convert media created date to local timezone %s", media.created)
            created_date = media.created

        if folder_structure.lower() == "none":
            date_path = ""
        else:
            try:
                date_path = folder_structure.format(created_date)
            except ValueError:  # pragma: no cover
                # This error only seems to happen in Python 2
                logger.error("Photo created date was not valid (%s)", created_date)
                # e.g. ValueError: year=5 is before 1900
                # (https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/122)
                # Just use the Unix epoch
                created_date = datetime.datetime.fromtimestamp(0)
                date_path = folder_structure.format(created_date)

        download_dir = os.path.join(directory, date_path)

        paths: Set[str] = set({})
        _size: VersionSize
        for _size, _version in disambiguate_filenames(media.versions, _sizes).items():
            if _size in [AssetVersionSize.ALTERNATIVE, AssetVersionSize.ADJUSTED]:
                paths.add(os.path.normpath(local_download_path(_version.filename, download_dir)))
                paths.add(
                    os.path.normpath(local_download_path(_version.filename, download_dir)) + ".xmp"
                )
        for _size, _version in media.versions.items():
            if _size not in [AssetVersionSize.ALTERNATIVE, AssetVersionSize.ADJUSTED]:
                paths.add(os.path.normpath(local_download_path(_version.filename, download_dir)))
                paths.add(
                    os.path.normpath(local_download_path(_version.filename, download_dir)) + ".xmp"
                )
        for path in paths:
            if os.path.exists(path):
                logger.debug("Deleting %s...", path)
                delete_local = delete_file_dry_run if dry_run else delete_file
                delete_local(logger, path)
