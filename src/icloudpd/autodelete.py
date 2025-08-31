"""
Delete any files found in "Recently Deleted"
"""

import datetime
import logging
import os
from typing import Callable, Sequence, Set

from tzlocal import get_localzone

from icloudpd.paths import local_download_path
from pyicloud_ipd.asset_version import calculate_version_filename
from pyicloud_ipd.raw_policy import RawTreatmentPolicy
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
    lp_filename_generator: Callable[[str], str],
    raw_policy: RawTreatmentPolicy,
) -> None:
    """
    Scans the "Recently Deleted" folder and deletes any matching files
    from the download directory.
    (I.e. If you delete a photo on your phone, it's also deleted on your computer.)
    """
    logger.info("Deleting any files found in 'Recently Deleted'...")

    recently_deleted = library_object.recently_deleted

    for media in recently_deleted:
        try:
            created_date = media.created.astimezone(get_localzone())
        except (ValueError, OSError):
            logger.error("Could not convert media created date to local timezone %s", media.created)
            created_date = media.created

        from foundation.core import compose
        from foundation.string_utils import eq, lower

        is_none_folder = compose(eq("none"), lower)

        if is_none_folder(folder_structure):
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
        versions, filename_overrides = disambiguate_filenames(
            media.versions_with_raw_policy(raw_policy), _sizes, media, lp_filename_generator
        )
        for _size, _version in versions.items():
            if _size in [AssetVersionSize.ALTERNATIVE, AssetVersionSize.ADJUSTED]:
                version_filename = calculate_version_filename(
                    media.filename,
                    _version,
                    _size,
                    lp_filename_generator,
                    media.item_type,
                    filename_overrides.get(_size),
                )
                paths.add(os.path.normpath(local_download_path(version_filename, download_dir)))
                paths.add(
                    os.path.normpath(local_download_path(version_filename, download_dir)) + ".xmp"
                )
        for _size, _version in media.versions_with_raw_policy(raw_policy).items():
            if _size not in [AssetVersionSize.ALTERNATIVE, AssetVersionSize.ADJUSTED]:
                version_filename = calculate_version_filename(
                    media.filename,
                    _version,
                    _size,
                    lp_filename_generator,
                    media.item_type,
                )
                paths.add(os.path.normpath(local_download_path(version_filename, download_dir)))
                paths.add(
                    os.path.normpath(local_download_path(version_filename, download_dir)) + ".xmp"
                )
        for path in paths:
            if os.path.exists(path):
                logger.debug("Deleting %s...", path)
                delete_local = delete_file_dry_run if dry_run else delete_file
                delete_local(logger, path)
