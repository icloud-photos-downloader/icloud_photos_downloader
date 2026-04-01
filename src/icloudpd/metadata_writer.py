"""Write iCloud metadata into photo/video files using exiftool.

This module patches EXIF/XMP metadata in-place without re-encoding images.
exiftool manipulates container metadata boxes directly, so file quality is
preserved and size changes are minimal (+1-3KB typically).

Supported formats: HEIC, JPEG, PNG, MOV, MP4.
Requires exiftool to be installed on the system.
"""

import base64
import json
import logging
import os
import plistlib
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
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    gps_altitude: float | None = None
    gps_h_accuracy: float | None = None
    created_date: str | None = None  # format: "YYYY:MM:DD HH:MM:SS"


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


_VIDEO_EXTENSIONS = frozenset({".mov", ".mp4", ".m4v", ".avi"})

_GIF_EXTENSIONS = frozenset({".gif"})


def _is_video(file_path: str) -> bool:
    """Check if a file is a video based on extension."""
    return os.path.splitext(file_path.lower())[1] in _VIDEO_EXTENSIONS


def _is_gif(file_path: str) -> bool:
    """Check if a file is a GIF based on extension."""
    return os.path.splitext(file_path.lower())[1] in _GIF_EXTENSIONS


def build_exiftool_args(
    update: MetadataUpdate, config: set[str], file_path: str = ""
) -> list[str]:
    """Build exiftool command-line arguments for the given metadata update.

    Args:
        update: The metadata to write.
        config: Set of enabled field categories ('rating', 'keywords',
                'title', 'orientation', 'location', 'all').
                Note: 'dates' is accepted but deprecated (no-op).

    Returns:
        List of exiftool arguments (e.g. ['-Rating=5', '-XPTitle=...'])
    """
    args: list[str] = []
    if _is_gif(file_path):
        return args  # GIF doesn't support EXIF; metadata goes in XMP sidecar only
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

    # orientation=0 is not a valid EXIF value (valid: 1-8); skip it
    # Orientation is not meaningful for videos or PNG files
    if (
        (write_all or "orientation" in config)
        and update.orientation is not None
        and update.orientation != 0
        and not _is_video(file_path)
        and os.path.splitext(file_path.lower())[1] != ".png"
    ):
        args.append(f"-Orientation#={update.orientation}")

    if (write_all or "location" in config) and update.gps_latitude is not None and update.gps_longitude is not None:
        if _is_video(file_path):
            # QuickTime native GPS format (ISO 6709): "+DD.DDDDDD+DDD.DDDDDD+AAA.AAA/"
            alt = update.gps_altitude if update.gps_altitude is not None else 0.0
            args.append(f"-Keys:GPSCoordinates={update.gps_latitude:+.6f}{update.gps_longitude:+.6f}{alt:+.3f}/")
            if update.gps_h_accuracy is not None and update.gps_h_accuracy > 0:
                args.append(f"-Keys:LocationAccuracyHorizontal={update.gps_h_accuracy}")
            # Strip legacy XMP-exif GPS tags (3KB overhead, replaced by native Keys)
            args.extend([
                "-XMP-exif:GPSLatitude=",
                "-XMP-exif:GPSLongitude=",
                "-XMP-exif:GPSAltitude=",
                "-XMP-exif:GPSAltitudeRef=",
                "-XMP-exif:GPSHPositioningError=",
            ])
        else:
            lat_ref = "S" if update.gps_latitude < 0 else "N"
            lon_ref = "W" if update.gps_longitude < 0 else "E"
            # Use signed values (works for XMP) plus Ref tags (needed for EXIF longitude)
            args.append(f"-GPSLatitude={update.gps_latitude}")
            args.append(f"-GPSLatitudeRef={lat_ref}")
            args.append(f"-GPSLongitude={update.gps_longitude}")
            args.append(f"-GPSLongitudeRef={lon_ref}")
            if update.gps_altitude is not None:
                alt_ref = 1 if update.gps_altitude < 0 else 0
                args.append(f"-GPSAltitude={update.gps_altitude}")
                args.append(f"-GPSAltitudeRef#={alt_ref}")
            if update.gps_h_accuracy is not None and update.gps_h_accuracy > 0:
                args.append(f"-GPSHPositioningError={update.gps_h_accuracy}")

    if (write_all or "datetime" in config or "dates" in config) and update.created_date is not None:
        if _is_video(file_path):
            args.append(f"-QuickTime:CreateDate={update.created_date}")
        else:
            args.append(f"-EXIF:DateTimeOriginal={update.created_date}")
            args.append(f"-EXIF:CreateDate={update.created_date}")

    if (write_all or "dates" in config) and update.created_date is not None:
        if _is_video(file_path):
            args.append(f"-QuickTime:ModifyDate={update.created_date}")
        else:
            args.append(f"-EXIF:ModifyDate={update.created_date}")

    return args


def _extract_h_accuracy(asset_record: dict[str, Any]) -> float | None:
    """Extract GPS horizontal accuracy from locationEnc plist blob."""
    fields = asset_record.get("fields", {})
    loc_enc = fields.get("locationEnc", {}).get("value", "")
    if not loc_enc:
        return None
    try:
        location = plistlib.loads(base64.b64decode(loc_enc))
        h_acc = location.get("horzAcc")
        if h_acc is not None and h_acc > 0:
            return float(h_acc)
    except (plistlib.InvalidFileException, ValueError, TypeError, AttributeError):
        pass
    return None


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
        # orientation=0 from iCloud means "no override"; falsy check naturally skips it
        orientation = xmp_metadata.Orientation if xmp_metadata.Orientation else None
        gps_latitude = xmp_metadata.GPSLatitude if xmp_metadata.GPSLatitude is not None else None
        gps_longitude = xmp_metadata.GPSLongitude if xmp_metadata.GPSLongitude is not None else None
        gps_altitude = xmp_metadata.GPSAltitude if xmp_metadata.GPSAltitude is not None else None
        # horzAcc is not in XMPMetadata — extract from raw locationEnc
        gps_h_accuracy = _extract_h_accuracy(asset_record)
        # Extract created_date for datetime/dates categories
        created_date_val = None
        if xmp_metadata.CreateDate:
            created_date_val = xmp_metadata.CreateDate.strftime("%Y:%m:%d %H:%M:%S")
        return MetadataUpdate(
            rating=rating,
            title=title,
            description=description,
            keywords=keywords,
            orientation=orientation,
            gps_latitude=gps_latitude,
            gps_longitude=gps_longitude,
            gps_altitude=gps_altitude,
            gps_h_accuracy=gps_h_accuracy,
            created_date=created_date_val,
        )

    # Fallback: extract from raw asset_record (same logic as xmp_sidecar.build_metadata)
    fields = asset_record.get("fields", {})
    rating = None
    if fields.get("isFavorite", {}).get("value") == 1:
        rating = 5
    elif fields.get("isHidden", {}).get("value") == 1 or fields.get("isDeleted", {}).get("value") == 1:
        rating = -1

    return MetadataUpdate(rating=rating, gps_h_accuracy=_extract_h_accuracy(asset_record))


def _read_existing_metadata(file_path: str) -> dict[str, str]:
    """Read current metadata values using exiftool for comparison.

    Uses -G to get group-prefixed keys, then normalises to unprefixed names.
    For GPS, prefers XMP values (where we write for videos) over Composite
    values (which read from QuickTime Keys and may differ in precision).
    """
    cmd = [
        "exiftool", "-json", "-s", "-n", "-G",
        "-Rating", "-XPTitle", "-XPKeywords", "-ImageDescription",
        "-Orientation#",
        "-GPSLatitude", "-GPSLongitude", "-GPSAltitude",
        "-GPSHPositioningError",
        "-XMP-exif:GPSLatitude", "-XMP-exif:GPSLongitude",
        "-XMP-exif:GPSAltitude", "-XMP-exif:GPSHPositioningError",
        "-Keys:GPSCoordinates",
        "-Keys:LocationAccuracyHorizontal",
        "-EXIF:DateTimeOriginal",
        "-QuickTime:CreateDate",
        file_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.debug("exiftool read failed for %s: %s", file_path, result.stderr.strip())
            return {}
        data = json.loads(result.stdout)
        if not data:
            return {}
        raw = data[0]
        # Normalise: strip group prefix. Priority for GPS comparison:
        # XMP > Composite > EXIF. XMP has our written values for videos.
        # Composite has correctly-signed values. EXIF GPS stores unsigned
        # values with separate Ref tags, so is unreliable for comparison.
        priority = {"EXIF": 0, "Composite": 1, "XMP": 2}
        sorted_items = sorted(
            raw.items(),
            key=lambda kv: priority.get(kv[0].split(":")[0], 1)
        )
        meta: dict[str, Any] = {}
        for key, val in sorted_items:
            if key == "SourceFile":
                continue
            parts = key.split(":", 1)
            tag = parts[-1]
            meta[tag] = val
        # Parse Keys:GPSCoordinates into lat/lon for comparison
        gps_coords = meta.pop("GPSCoordinates", None)
        if gps_coords is not None and isinstance(gps_coords, str):
            # Space-separated format from exiftool -n: "-33.86 151.21 50"
            parts = gps_coords.replace("/", "").split()
            if len(parts) >= 2:
                try:
                    meta.setdefault("GPSLatitude", float(parts[0]))
                    meta.setdefault("GPSLongitude", float(parts[1]))
                except ValueError:
                    pass
        # Map LocationAccuracyHorizontal to GPSHPositioningError for uniform comparison
        loc_acc = meta.pop("LocationAccuracyHorizontal", None)
        if loc_acc is not None:
            meta.setdefault("GPSHPositioningError", loc_acc)
        # Detect stale XMP-exif GPS on videos (should use native Keys instead)
        if _is_video(file_path):
            for key in raw:
                if key.startswith("XMP:GPS"):
                    meta["_has_stale_xmp_gps"] = True
                    break
        return meta
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError) as e:
        logger.debug("Could not read existing metadata from %s: %s", file_path, e)
        return {}


def _gps_close(a: float | None, b: float | None, tol: float = 1e-5) -> bool:
    """Check if two GPS coordinates are close enough (~1 metre)."""
    if a is None or b is None:
        return a is b
    return abs(a - b) < tol


def _needs_update(
    update: MetadataUpdate, config: set[str], existing: dict[str, Any],
    file_path: str = "",
) -> bool:
    """Check if the file already has the correct metadata values."""
    write_all = "all" in config

    if (write_all or "rating" in config) and update.rating is not None and existing.get("Rating") != update.rating:
        logger.debug("needs_update: %s: rating (existing=%s, update=%s)", file_path, existing.get("Rating"), update.rating)
        return True

    if (write_all or "title" in config) and update.title is not None and existing.get("XPTitle") != update.title:
        logger.debug("needs_update: %s: title (existing=%s, update=%s)", file_path, existing.get("XPTitle"), update.title)
        return True

    if (write_all or "title" in config) and update.description is not None and existing.get("ImageDescription") != update.description:
        logger.debug("needs_update: %s: description (existing=%s, update=%s)", file_path, existing.get("ImageDescription"), update.description)
        return True

    if (write_all or "keywords" in config) and update.keywords:
        xp_kw = "; ".join(update.keywords)
        if existing.get("XPKeywords") != xp_kw:
            logger.debug("needs_update: %s: keywords", file_path)
            return True

    # Orientation is not meaningful for videos or PNG — matches build_exiftool_args
    if (
        (write_all or "orientation" in config)
        and update.orientation is not None
        and not _is_video(file_path)
        and os.path.splitext(file_path.lower())[1] != ".png"
        and existing.get("Orientation") != update.orientation
    ):
        logger.debug("needs_update: %s: orientation (existing=%s, update=%s)", file_path, existing.get("Orientation"), update.orientation)
        return True

    if (write_all or "location" in config) and update.gps_latitude is not None and update.gps_longitude is not None:
        # exiftool -n returns already-signed GPS values
        if not _gps_close(existing.get("GPSLatitude"), update.gps_latitude):
            logger.debug("needs_update: %s: gps_latitude (existing=%s, update=%s)", file_path, existing.get("GPSLatitude"), update.gps_latitude)
            return True
        if not _gps_close(existing.get("GPSLongitude"), update.gps_longitude):
            logger.debug("needs_update: %s: gps_longitude", file_path)
            return True
        if update.gps_h_accuracy is not None and update.gps_h_accuracy > 0 and not _gps_close(existing.get("GPSHPositioningError"), update.gps_h_accuracy, tol=0.1):
            logger.debug("needs_update: %s: gps_h_accuracy", file_path)
            return True
        # Strip legacy XMP-exif GPS from videos (replaced by native Keys)
        if existing.get("_has_stale_xmp_gps"):
            logger.debug("needs_update: %s: stale XMP GPS", file_path)
            return True

    if (write_all or "datetime" in config or "dates" in config) and update.created_date is not None and not _has_valid_date(existing):
        logger.debug("needs_update: %s: datetime", file_path)
        return True

    return False


_ZERO_DATE = "0000:00:00 00:00:00"


def _has_valid_date(existing: dict[str, Any]) -> bool:
    """Check if the file has a valid (non-zero) date tag."""
    dt = existing.get("DateTimeOriginal") or existing.get("CreateDate")
    return dt is not None and dt != _ZERO_DATE


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
    args = build_exiftool_args(update, config, file_path)
    if not args:
        return False

    # Check existing values to avoid unnecessary writes
    existing = _read_existing_metadata(file_path)
    if existing and not _needs_update(update, config, existing, file_path=file_path):
        return False

    # Don't overwrite existing dates — the camera's value is ground truth;
    # iCloud's assetDate may differ due to timezone/rounding.
    # Check both EXIF (images) and QuickTime (videos) date tags.
    if existing and _has_valid_date(existing):
        args = [a for a in args if not a.startswith("-EXIF:DateTimeOriginal=")
                and not a.startswith("-EXIF:CreateDate=")
                and not a.startswith("-EXIF:ModifyDate=")
                and not a.startswith("-QuickTime:CreateDate=")
                and not a.startswith("-QuickTime:ModifyDate=")]
        if not args:
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
            cmd, capture_output=True, text=True, timeout=1200
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
                    capture_output=True, text=True, timeout=1200,
                )
                if "1 image files updated" in strip_result.stdout:
                    retry = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=1200
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
            # Check for corrupt XMP — auto-repair by stripping and retrying
            if "Duplicate XMP property" in result.stderr:
                logger.warning(
                    "Corrupt XMP in %s — stripping XMP and retrying",
                    file_path,
                )
                if not dry_run:
                    strip_result = subprocess.run(
                        ["exiftool", "-overwrite_original", "-XMP:all=", file_path],
                        capture_output=True, text=True, timeout=1200,
                    )
                    if "1 image files updated" in strip_result.stdout:
                        retry = subprocess.run(
                            cmd, capture_output=True, text=True, timeout=1200
                        )
                        if "1 image files updated" in retry.stdout:
                            logger.info("Wrote metadata to %s (after XMP repair)", file_path)
                            return True
                logger.warning(
                    "Metadata write failed for %s even after XMP repair", file_path
                )
                return False
            if result.returncode == 1:
                logger.warning(
                    "Metadata write failed for %s: %s",
                    file_path, result.stderr.strip()[:200],
                )
            else:
                logger.warning(
                    "Metadata write had no effect on %s (file may have corrupt metadata)",
                    file_path,
                )
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
