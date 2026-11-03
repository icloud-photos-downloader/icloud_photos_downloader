"""Delete only unchanged files proven to belong exclusively to a deleted iCloud ID."""

import logging
import os
from typing import Callable

from icloudpd.autodelete_manifest import AutoDeleteManifest
from pyicloud_ipd.services.photos import PhotoLibrary


def delete_file(logger: logging.Logger, path: str) -> bool:
    os.remove(path)
    logger.info("Deleted %s", path)
    return True


def delete_file_dry_run(logger: logging.Logger, path: str) -> bool:
    logger.info("[DRY RUN] Would delete %s", path)
    return True


def autodelete_photos(
    logger: logging.Logger,
    dry_run: bool,
    library_object: PhotoLibrary,
    manifest: AutoDeleteManifest,
    *,
    cancelled: Callable[[], bool] | None = None,
) -> None:
    """Process unchanged, uniquely owned files after two complete absence observations."""
    manifest.validate_generation()
    if not manifest.has_previous_generation:
        logger.info("Skipping auto-delete: no previous complete active-library generation")
        return

    logger.info("Processing manifest-owned files found in 'Recently Deleted'...")
    # Finish reading Recently Deleted before acting: an interrupted listing must
    # not delete a prefix of the returned assets.
    recently_deleted = list(library_object.recently_deleted)
    if cancelled is not None and cancelled():
        raise ValueError("auto-delete was cancelled")
    manifest.invalidate_ownership()
    for media in recently_deleted:
        asset_id = str(media.id)
        paths = manifest.paths_for_deleted(asset_id)
        if not paths:
            logger.info("Skipping Recently Deleted asset %s: not safely eligible", asset_id)
            continue
        try:
            # Preflight the whole asset: preserve media and sidecars together if any
            # member changed locally, disappeared or became unsafe.
            if not all(manifest.matches_file(asset_id, path) for path in sorted(paths)):
                logger.warning("Keeping changed or missing files for asset %s", asset_id)
                continue
        except (OSError, ValueError):
            logger.exception("Could not verify manifest files for %s", asset_id)
            continue
        logger.info(
            "Auto-delete asset %s from manifest generation %s: %s eligible path(s)",
            asset_id,
            manifest.generation,
            len(paths),
        )
        complete = True
        for path in sorted(paths):
            if cancelled is not None and cancelled():
                raise ValueError("auto-delete was cancelled")
            try:
                # Recheck path safety immediately before the action (without rehashing).
                if path not in manifest.paths_for_deleted(asset_id):
                    raise ValueError("manifest path is no longer safely eligible")
                (delete_file_dry_run if dry_run else delete_file)(logger, path)
            except (OSError, ValueError):
                logger.exception("Could not process manifest path for %s: %s", asset_id, path)
                complete = False
        if complete and not dry_run:
            manifest.forget(asset_id)
