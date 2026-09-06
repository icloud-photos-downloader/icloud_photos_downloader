"""Delete or quarantine only paths proven to belong to a deleted asset."""

import errno
import filecmp
import hashlib
import logging
import os
import shutil
from typing import Callable, Sequence

from icloudpd.autodelete_manifest import AutoDeleteManifest
from pyicloud_ipd.raw_policy import RawTreatmentPolicy
from pyicloud_ipd.services.photos import PhotoLibrary
from pyicloud_ipd.version_size import AssetVersionSize


def delete_file(logger: logging.Logger, path: str) -> bool:
    os.remove(path)
    logger.info("Deleted %s", path)
    return True


def delete_file_dry_run(logger: logging.Logger, path: str) -> bool:
    logger.info("[DRY RUN] Would delete %s", path)
    return True


def _inside_directory(path: str, directory: str) -> bool:
    try:
        root = os.path.realpath(os.path.abspath(directory))
        candidate = os.path.realpath(os.path.abspath(path))
        return candidate != root and os.path.commonpath((candidate, root)) == root
    except ValueError:
        return False


def validate_quarantine_root(directory: str, quarantine_directory: str) -> tuple[str, str]:
    source_root = os.path.realpath(os.path.abspath(directory))
    quarantine_root = os.path.realpath(os.path.abspath(quarantine_directory))
    try:
        if source_root == quarantine_root:
            raise ValueError("Auto-delete directory must differ from the download directory")
        if os.path.commonpath((source_root, quarantine_root)) == source_root:
            raise ValueError("Auto-delete directory must not be inside the download directory")
        if os.path.commonpath((source_root, quarantine_root)) == quarantine_root:
            raise ValueError("Auto-delete directory must not contain the download directory")
    except ValueError as error:
        if str(error).startswith("Auto-delete directory"):
            raise
        raise ValueError("Auto-delete directories must be on compatible paths") from error
    return source_root, quarantine_root


def _collision_safe_destination(destination: str, media_id: str) -> str:
    stem, extension = os.path.splitext(destination)
    suffix = hashlib.sha256(media_id.encode()).hexdigest()[:12]
    candidate = f"{stem}-icloudpd-{suffix}{extension}"
    number = 1
    while os.path.exists(candidate):
        candidate = f"{stem}-icloudpd-{suffix}-{number}{extension}"
        number += 1
    return candidate


def move_file(
    logger: logging.Logger,
    path: str,
    directory: str,
    quarantine_directory: str,
    media_id: str,
    dry_run: bool,
) -> bool:
    """Move a file to a sibling quarantine tree without overwriting data."""
    source_root, quarantine_root = validate_quarantine_root(directory, quarantine_directory)
    source_path = os.path.realpath(os.path.abspath(path))
    if source_path == source_root or os.path.commonpath((source_root, source_path)) != source_root:
        raise ValueError(f"Refusing to move path outside download directory: {path}")

    destination = os.path.realpath(
        os.path.join(quarantine_root, os.path.relpath(source_path, source_root))
    )
    if (
        destination == quarantine_root
        or os.path.commonpath((quarantine_root, destination)) != quarantine_root
    ):
        raise ValueError(f"Refusing quarantine destination outside directory: {destination}")
    if os.path.exists(destination):
        if filecmp.cmp(source_path, destination, shallow=False):
            if dry_run:
                logger.info(
                    "[DRY RUN] Would remove duplicate %s (already at %s)", path, destination
                )
            else:
                os.remove(source_path)
                logger.info("Removed duplicate %s (already quarantined at %s)", path, destination)
            return True
        destination = _collision_safe_destination(destination, media_id)
        logger.warning(
            "Quarantine collision; preserving both files by moving %s to %s",
            path,
            destination,
        )

    if dry_run:
        logger.info("[DRY RUN] Would move %s to %s", path, destination)
        return True

    os.makedirs(os.path.dirname(destination), exist_ok=True)
    try:
        os.replace(source_path, destination)
    except OSError as error:
        if error.errno != errno.EXDEV:
            raise
        shutil.move(source_path, destination)
    logger.info("Moved %s to %s", path, destination)
    return True


def autodelete_photos(
    logger: logging.Logger,
    dry_run: bool,
    library_object: PhotoLibrary,
    directory: str,
    manifest: AutoDeleteManifest,
    _sizes: Sequence[AssetVersionSize],
    _lp_filename_generator: Callable[[str], str],
    _raw_policy: RawTreatmentPolicy,
    auto_delete_directory: str | None = None,
) -> None:
    """Process only uniquely owned paths after two complete absence observations."""
    if auto_delete_directory:
        validate_quarantine_root(directory, auto_delete_directory)
    if not manifest.has_previous_generation:
        logger.info("Skipping auto-delete: no previous complete active-library generation")
        return

    logger.info("Processing manifest-owned files found in 'Recently Deleted'...")
    for media in library_object.recently_deleted:
        asset_id = str(media.id)
        paths = manifest.paths_for_deleted(asset_id)
        if not paths:
            logger.info("Skipping Recently Deleted asset %s: not safely eligible", asset_id)
            continue
        logger.info(
            "Auto-delete asset %s from manifest generation %s: %s eligible path(s)",
            asset_id,
            manifest.generation,
            len(paths),
        )
        complete = True
        for path in sorted(paths):
            if not _inside_directory(path, directory):
                logger.error("Skipping unsafe manifest path for %s: %s", asset_id, path)
                complete = False
                continue
            if not os.path.isfile(path):
                logger.info("Skipping missing manifest path for %s: %s", asset_id, path)
                complete = False
                continue
            try:
                if auto_delete_directory:
                    move_file(
                        logger,
                        path,
                        directory,
                        auto_delete_directory,
                        asset_id,
                        dry_run,
                    )
                else:
                    (delete_file_dry_run if dry_run else delete_file)(logger, path)
            except (OSError, ValueError):
                logger.exception("Could not process manifest path for %s: %s", asset_id, path)
                complete = False
        if complete and not dry_run:
            manifest.forget(asset_id)
