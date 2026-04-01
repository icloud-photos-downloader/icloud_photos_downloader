"""Write iCloud metadata into photo/video files using exiftool.

This module patches EXIF/XMP metadata in-place without re-encoding images.
exiftool manipulates container metadata boxes directly, so file quality is
preserved and size changes are minimal (+1-3KB typically).

Supported formats: HEIC, JPEG, PNG, MOV, MP4.
Requires exiftool to be installed on the system.
"""

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MetadataUpdate:
    """Metadata fields to write into a file."""

    rating: int | None = None
    title: str | None = None
    description: str | None = None
    keywords: list[str] | None = None
    orientation: int | None = None
    timezone_offset: str | None = None  # e.g. "+11:00", "-05:00"


class ExiftoolNotFoundError(RuntimeError):
    """Raised when exiftool is not installed."""


def check_exiftool() -> str:
    """Check exiftool is available. Returns version string or raises."""
    try:
        result = subprocess.run(
            ["exiftool", "-ver"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        pass
    raise ExiftoolNotFoundError(
        "exiftool is required for --write-metadata but was not found. "
        "Install it with: apt install libimage-exiftool-perl (Linux), "
        "brew install exiftool (macOS), or choco install exiftool (Windows)."
    )


def build_exiftool_args(
    update: MetadataUpdate, config: set[str]
) -> list[str]:
    """Build exiftool command-line arguments for the given metadata update.

    Args:
        update: The metadata to write.
        config: Set of enabled field categories ('rating', 'keywords',
                'title', 'dates', 'all').

    Returns:
        List of exiftool arguments (e.g. ['-Rating=5', '-XPTitle=...'])
    """
    args: list[str] = []
    write_all = "all" in config

    if (write_all or "rating" in config) and update.rating is not None:
        args.append(f"-Rating={update.rating}")

    if (write_all or "title" in config) and update.title is not None:
        args.append(f"-XPTitle={update.title}")
        args.append(f"-XMP:Title={update.title}")

    if (write_all or "title" in config) and update.description is not None:
        args.append(f"-ImageDescription={update.description}")
        args.append(f"-XMP:Description={update.description}")

    if (write_all or "keywords" in config) and update.keywords:
        # Write to both Windows EXIF and XMP/IPTC for broad compatibility
        xp_kw = "; ".join(update.keywords)
        args.append(f"-XPKeywords={xp_kw}")
        for kw in update.keywords:
            args.append(f"-XMP:Subject+={kw}")
            args.append(f"-IPTC:Keywords+={kw}")

    if (write_all or "orientation" in config) and update.orientation is not None:
        args.append(f"-Orientation#={update.orientation}")

    if (write_all or "dates" in config) and update.timezone_offset is not None:
        args.append(f"-OffsetTimeOriginal={update.timezone_offset}")
        args.append(f"-OffsetTimeDigitized={update.timezone_offset}")
        args.append(f"-OffsetTime={update.timezone_offset}")

    return args


def extract_metadata_update(
    asset_record: dict[str, Any], xmp_metadata: Any | None = None
) -> MetadataUpdate:
    """Extract writable metadata from an iCloud asset record.

    Reuses XMPMetadata if already built (avoids double-decoding), or
    extracts directly from the asset record fields.

    Args:
        asset_record: Raw iCloud asset record dict.
        xmp_metadata: Optional pre-built XMPMetadata namedtuple.

    Returns:
        MetadataUpdate with fields to write.
    """
    if xmp_metadata is not None:
        rating = xmp_metadata.Rating if xmp_metadata.Rating and xmp_metadata.Rating != 0 else None
        keywords = xmp_metadata.Keywords if xmp_metadata.Keywords else None
        title = xmp_metadata.Title if xmp_metadata.Title else None
        description = xmp_metadata.Description if xmp_metadata.Description else None
        orientation = xmp_metadata.Orientation if xmp_metadata.Orientation else None
        timezone_offset = None
        if xmp_metadata.CreateDate is not None and xmp_metadata.CreateDate.utcoffset() is not None:
            offset = xmp_metadata.CreateDate.utcoffset()
            total_seconds = int(offset.total_seconds())
            sign = "+" if total_seconds >= 0 else "-"
            hours, remainder = divmod(abs(total_seconds), 3600)
            minutes = remainder // 60
            timezone_offset = f"{sign}{hours:02d}:{minutes:02d}"
        return MetadataUpdate(
            rating=rating,
            title=title,
            description=description,
            keywords=keywords,
            orientation=orientation,
            timezone_offset=timezone_offset,
        )

    # Fallback: extract from raw asset_record (same logic as xmp_sidecar.build_metadata)
    fields = asset_record.get("fields", {})
    rating = None
    if fields.get("isFavorite", {}).get("value") == 1:
        rating = 5
    elif fields.get("isHidden", {}).get("value") == 1 or fields.get("isDeleted", {}).get("value") == 1:
        rating = -1

    return MetadataUpdate(rating=rating)


def _read_existing_metadata(file_path: str) -> dict[str, str]:
    """Read current metadata values using exiftool for comparison."""
    cmd = [
        "exiftool", "-json", "-s",
        "-Rating", "-XPTitle", "-XPKeywords", "-ImageDescription",
        "-Orientation#", "-OffsetTimeOriginal",
        file_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.debug("exiftool read failed for %s: %s", file_path, result.stderr.strip())
            return {}
        data = json.loads(result.stdout)
        return data[0] if data else {}
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError) as e:
        logger.debug("Could not read existing metadata from %s: %s", file_path, e)
        return {}


def _needs_update(
    update: MetadataUpdate, config: set[str], existing: dict[str, Any], is_video: bool = False
) -> bool:
    """Check if the file already has the correct metadata values."""
    write_all = "all" in config

    if (write_all or "rating" in config) and update.rating is not None and existing.get("Rating") != update.rating:
        return True

    if (write_all or "title" in config) and update.title is not None and existing.get("XPTitle") != update.title:
        return True

    if (write_all or "title" in config) and update.description is not None and existing.get("ImageDescription") != update.description:
        return True

    if (write_all or "keywords" in config) and update.keywords:
        xp_kw = "; ".join(update.keywords)
        if existing.get("XPKeywords") != xp_kw:
            return True

    if (write_all or "orientation" in config) and update.orientation is not None and existing.get("Orientation") != update.orientation:
        return True

    # OffsetTime is EXIF-only — skip for video files (QuickTime doesn't support it)
    return (
        not is_video
        and (write_all or "dates" in config)
        and update.timezone_offset is not None
        and existing.get("OffsetTimeOriginal") != update.timezone_offset
    )


def write_metadata(
    file_path: str,
    update: MetadataUpdate,
    config: set[str],
    dry_run: bool = False,
) -> bool:
    """Write metadata to a file using exiftool.

    Reads existing metadata first and only writes if values differ,
    ensuring true idempotency.

    Args:
        file_path: Path to the image/video file.
        update: Metadata fields to write.
        config: Set of enabled field categories.
        dry_run: If True, log what would be written but don't modify the file.

    Returns:
        True if metadata was written (or would be written in dry-run), False if
        no changes were needed or an error occurred.
    """
    # Video files (MOV/MP4) use QuickTime metadata, not EXIF.
    # OffsetTimeOriginal is an EXIF tag that doesn't apply to video containers.
    ext = os.path.splitext(file_path)[1].lower()
    is_video = ext in (".mov", ".mp4", ".m4v")

    args = build_exiftool_args(update, config)
    if is_video:
        # Remove EXIF-only tags that QuickTime doesn't support
        args = [a for a in args if not a.startswith("-OffsetTime")]
    if not args:
        return False

    # Check existing values to avoid unnecessary writes
    existing = _read_existing_metadata(file_path)
    if existing and not _needs_update(update, config, existing, is_video=is_video):
        return False

    if dry_run:
        logger.info(
            "Would write metadata to %s: %s",
            file_path,
            " ".join(args),
        )
        return True

    cmd = ["exiftool", "-overwrite_original"] + args + [file_path]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0 and "1 image files updated" in result.stdout:
            # Check for corrupt XMP even on success — exiftool may have written
            # some tags (GPS) but silently skipped others (Rating) due to XMP issues
            if "Duplicate XMP property" in result.stderr:
                logger.warning(
                    "Corrupt XMP in %s — stripping XMP and retrying",
                    file_path,
                )
                strip_result = subprocess.run(
                    ["exiftool", "-overwrite_original", "-XMP:all=", file_path],
                    capture_output=True, text=True, timeout=600,
                )
                if "1 image files updated" in strip_result.stdout:
                    retry = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=600
                    )
                    if "1 image files updated" in retry.stdout:
                        logger.info("Wrote metadata to %s (after XMP repair)", file_path)
                        return True
                logger.warning(
                    "Metadata write failed for %s even after XMP repair", file_path
                )
                return False
            logger.info("Wrote metadata to %s", file_path)
            return True
        if "0 image files updated" in result.stdout:
            logger.debug("No metadata changes needed for %s", file_path)
            return False
        logger.warning(
            "exiftool returned unexpected output for %s: %s %s",
            file_path,
            result.stdout.strip(),
            result.stderr.strip(),
        )
        return False
    except subprocess.TimeoutExpired:
        logger.warning("exiftool timed out writing to %s", file_path)
        return False
    except FileNotFoundError:
        logger.error("exiftool not found")
        return False
