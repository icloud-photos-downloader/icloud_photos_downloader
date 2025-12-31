"""Unified metadata management for EXIF and XMP sidecar files"""

import logging
import os
from typing import Any

from foundation.core import compose
from foundation.string_utils import endswith, lower


def merge_metadata(
    existing: dict[str, Any],
    desired: dict[str, Any],
    overwrite: bool,
    fields_to_update: set[str] | None = None,
) -> dict[str, Any]:
    """
    Merge existing and desired metadata based on overwrite policy.

    Args:
        existing: Current metadata from file
        desired: Desired metadata from iCloud
        overwrite: If True, desired values replace existing. If False, only add missing fields.
        fields_to_update: Optional set of field names to update. If provided, only these fields are merged.

    Returns:
        Merged metadata dict

    Preserves special keys like "_xml_tree" from existing metadata.
    """
    result = existing.copy()

    for key, desired_value in desired.items():
        # Skip if we have a field filter and this field isn't in it
        if fields_to_update is not None and key not in fields_to_update:
            continue

        # Skip None values - never overwrite with None
        if desired_value is None:
            continue

        # Apply overwrite policy
        if overwrite:
            result[key] = desired_value
        else:
            existing_value = existing.get(key)
            if existing_value is None:
                # Only add if field is missing
                result[key] = desired_value

    return result


def sync_exif_metadata(
    logger: logging.Logger,
    download_path: str,
    photo: Any,  # PhotoAsset type
    created_date: Any,  # datetime
    favorite_to_rating: int | None,
    set_exif_datetime: bool,
    process_existing_favorites: bool,
    metadata_overwrite: bool,
    dry_run: bool,
) -> None:
    """
    Synchronize EXIF metadata for photo file.

    Handles both new and existing files. Internally determines:
    - Whether file is JPEG (only JPEGs get EXIF)
    - Whether file already exists
    - Whether photo is favorited
    - What metadata to write based on flags
    - Whether to read/merge existing metadata
    - Whether to write (only if changed)

    Args:
        logger: Logger instance
        download_path: Path to the photo file
        photo: PhotoAsset object with _asset_record
        created_date: datetime object for EXIF timestamp
        favorite_to_rating: Rating value for favorites (or None)
        set_exif_datetime: Whether to set EXIF datetime
        process_existing_favorites: Whether to process existing files
        metadata_overwrite: Whether to overwrite existing metadata
        dry_run: If True, don't write to disk
    """
    # Import here to avoid circular dependencies
    from icloudpd.exif_datetime import read_exif_metadata, write_exif_metadata

    # Only process JPEG files for EXIF
    is_jpeg = compose(endswith((".jpg", ".jpeg")), lower)
    if not is_jpeg(download_path):
        return

    # Check if file already exists
    is_existing_file = os.path.exists(download_path)

    # Determine if photo is favorited
    is_favorite = photo._asset_record["fields"].get("isFavorite", {}).get("value") == 1

    # Skip existing files unless process_existing_favorites is enabled
    if is_existing_file and not process_existing_favorites:
        return

    # Build desired metadata
    desired_metadata: dict[str, Any] = {}

    # Add datetime if requested (only for new files or if set_exif_datetime is enabled)
    if set_exif_datetime and (not is_existing_file or not read_exif_metadata(logger, download_path).get("datetime")):
        desired_metadata["datetime"] = created_date.strftime("%Y:%m:%d %H:%M:%S")

    # Add rating if photo is favorited
    if favorite_to_rating and is_favorite:
        desired_metadata["rating"] = favorite_to_rating

    # Early return if nothing to write
    if not desired_metadata:
        return

    # Skip writes in dry-run mode
    if dry_run:
        return

    # For new files, write directly
    if not is_existing_file:
        logger.debug(
            "Setting EXIF for new file %s: datetime=%s, rating=%s",
            download_path,
            desired_metadata.get("datetime"),
            desired_metadata.get("rating"),
        )
        write_exif_metadata(logger, download_path, desired_metadata)
        return

    # For existing files, read → merge → write
    existing_metadata = read_exif_metadata(logger, download_path)

    merged_metadata = merge_metadata(
        existing_metadata,
        desired_metadata,
        overwrite=metadata_overwrite,
        fields_to_update={"rating"},  # Only update rating for existing files
    )

    # Only write if something changed
    if merged_metadata != existing_metadata:
        logger.debug(
            "Updating EXIF for existing file %s: rating=%s",
            download_path,
            merged_metadata.get("rating"),
        )
        write_exif_metadata(logger, download_path, merged_metadata)


def sync_xmp_metadata(
    logger: logging.Logger,
    download_path: str,
    photo: Any,  # PhotoAsset type
    favorite_to_rating: int | None,
    process_existing_favorites: bool,
    metadata_overwrite: bool,
    dry_run: bool,
) -> None:
    """
    Synchronize XMP sidecar metadata for photo file.

    Handles both new and existing files. Internally determines:
    - XMP file path construction (.xmp extension)
    - Whether XMP is writable (not created by external tool)
    - Whether file already exists
    - What metadata to extract from photo asset record
    - Whether to read/merge existing metadata
    - Whether to write (only if changed)

    Args:
        logger: Logger instance
        download_path: Path to the photo file (without .xmp extension)
        photo: PhotoAsset object with _asset_record
        favorite_to_rating: Rating value for favorites (or None)
        process_existing_favorites: Whether to process existing files
        metadata_overwrite: Whether to overwrite existing metadata
        dry_run: If True, don't write to disk
    """
    # Import here to avoid circular dependencies
    from icloudpd.xmp_sidecar import (
        build_metadata,
        can_write_xmp_file,
        generate_xml,
        read_xmp_metadata,
        write_xmp_metadata,
    )

    # Construct XMP path
    xmp_path = download_path + ".xmp"

    # Check if we're allowed to write this file
    writable = can_write_xmp_file(logger, xmp_path)
    if not writable:
        return

    # Check if file already exists
    is_existing_file = os.path.exists(xmp_path)

    # Skip existing files unless process_existing_favorites is enabled
    if is_existing_file and not process_existing_favorites:
        return

    # For new files, build full metadata and create new XMP
    if not is_existing_file:
        from xml.etree import ElementTree

        xmp_metadata = build_metadata(photo._asset_record, favorite_to_rating)
        xml_doc = generate_xml(xmp_metadata)
        if not dry_run:
            logger.debug("Creating XMP sidecar for %s", download_path)
            with open(xmp_path, "wb") as f:
                f.write(ElementTree.tostring(xml_doc, encoding="utf-8", xml_declaration=True))
        return

    # For existing files, only update rating if photo is favorited
    is_favorite = photo._asset_record["fields"].get("isFavorite", {}).get("value") == 1
    if not (favorite_to_rating and is_favorite):
        return

    # Read existing metadata
    existing_metadata = read_xmp_metadata(logger, xmp_path)

    # Build desired metadata (only rating for existing files)
    desired_metadata: dict[str, Any] = {"rating": favorite_to_rating}

    # Merge with existing
    merged_metadata = merge_metadata(
        existing_metadata,
        desired_metadata,
        overwrite=metadata_overwrite,
        fields_to_update={"rating"},
    )

    # Only write if something changed
    if merged_metadata != existing_metadata:
        logger.debug(
            "Updating XMP sidecar for existing file %s: rating=%s",
            xmp_path,
            merged_metadata.get("rating"),
        )
        write_xmp_metadata(logger, xmp_path, merged_metadata, dry_run)
