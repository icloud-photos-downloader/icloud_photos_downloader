"""
Delete any files found in "Recently Deleted"
"""

import datetime
import logging
import os
from dataclasses import dataclass
from typing import Callable, Sequence, Set

from tzlocal import get_localzone

from icloudpd.paths import local_download_path
from pyicloud_ipd.asset_version import add_suffix_to_filename, calculate_version_filename
from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.live_photo_mov_filename_policy import LivePhotoMovFilenamePolicy
from pyicloud_ipd.raw_policy import RawTreatmentPolicy
from pyicloud_ipd.services.photos import PhotoAsset, PhotoLibrary
from pyicloud_ipd.utils import disambiguate_filenames, size_to_suffix
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize, VersionSize


def delete_file(logger: logging.Logger, path: str) -> bool:
    """Actual deletion of files"""
    os.remove(path)
    logger.info("Deleted %s", path)
    return True


def delete_file_dry_run(logger: logging.Logger, path: str) -> bool:
    """Dry run deletion of files"""
    logger.info("[DRY RUN] Would delete %s", path)
    return True


@dataclass(frozen=True)
class LocalDownloadPathConfig:
    folder_structure: str
    directory: str
    sizes: Sequence[AssetVersionSize]
    force_size: bool
    xmp_sidecar: bool
    skip_live_photos: bool
    live_photo_size: LivePhotoVersionSize
    live_photo_mov_filename_policy: LivePhotoMovFilenamePolicy
    file_match_policy: FileMatchPolicy
    lp_filename_generator: Callable[[str], str]
    raw_policy: RawTreatmentPolicy


def _download_dir_for_media(
    logger: logging.Logger,
    folder_structure: str,
    directory: str,
    media: PhotoAsset,
) -> str:
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
            logger.error("Photo created date was not valid (%s)", media.created)
            created_date = datetime.datetime.fromtimestamp(0)
            date_path = folder_structure.format(created_date)

    return os.path.normpath(os.path.join(directory, date_path))


def _add_path_variants(paths: Set[str], path: str, version_size: int) -> None:
    normalized_path = os.path.normpath(path)
    paths.add(normalized_path)
    paths.add((f"-{version_size}.").join(normalized_path.rsplit(".", 1)))


def local_download_paths_for_media(
    logger: logging.Logger,
    media: PhotoAsset,
    config: LocalDownloadPathConfig,
    include_all_versions: bool = False,
) -> Set[str]:
    download_dir = _download_dir_for_media(logger, config.folder_structure, config.directory, media)
    paths: Set[str] = set()
    raw_versions = media.versions_with_raw_policy(config.raw_policy)
    versions, filename_overrides = disambiguate_filenames(
        raw_versions,
        config.sizes,
        media,
        config.lp_filename_generator,
    )

    for _size in config.sizes:
        if _size not in versions and _size != AssetVersionSize.ORIGINAL:
            if config.force_size:
                continue
            if AssetVersionSize.ORIGINAL in config.sizes:
                continue
            _size = AssetVersionSize.ORIGINAL

        version = versions[_size]
        filename = calculate_version_filename(
            media.filename,
            version,
            _size,
            config.lp_filename_generator,
            media.item_type,
            filename_overrides.get(_size),
        )
        download_path = local_download_path(filename, download_dir)
        _add_path_variants(paths, download_path, version.size)
        if _size == AssetVersionSize.ORIGINAL:
            _add_path_variants(
                paths, add_suffix_to_filename("-original", download_path), version.size
            )

        if config.xmp_sidecar:
            paths.add(os.path.normpath(download_path) + ".xmp")

    if include_all_versions:
        _size: VersionSize
        for _size, version in raw_versions.items():
            if _size in [AssetVersionSize.ALTERNATIVE, AssetVersionSize.ADJUSTED]:
                continue
            filename = calculate_version_filename(
                media.filename,
                version,
                _size,
                config.lp_filename_generator,
                media.item_type,
            )
            download_path = local_download_path(filename, download_dir)
            _add_path_variants(paths, download_path, version.size)
            if config.xmp_sidecar:
                paths.add(os.path.normpath(download_path) + ".xmp")

    if not config.skip_live_photos and config.live_photo_size in raw_versions:
        version = raw_versions[config.live_photo_size]
        lp_filename = calculate_version_filename(
            media.filename,
            version,
            config.live_photo_size,
            config.lp_filename_generator,
            media.item_type,
        )
        if config.live_photo_size != LivePhotoVersionSize.ORIGINAL:
            lp_filename = add_suffix_to_filename(
                size_to_suffix(config.live_photo_size), lp_filename
            )
        _add_path_variants(paths, os.path.join(download_dir, lp_filename), version.size)

    if config.file_match_policy != FileMatchPolicy.NAME_SIZE_DEDUP_WITH_SUFFIX:
        paths = {path for path in paths if not _is_size_dedup_path(path)}

    return paths


def _is_size_dedup_path(path: str) -> bool:
    stem, extension = os.path.splitext(path)
    return extension != "" and stem.rsplit("-", 1)[-1].isdigit()


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
