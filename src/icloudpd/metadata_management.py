"""Unified metadata management for EXIF and XMP sidecar files"""

import base64
import json
import logging
import os
import plistlib
import typing
import zlib
from datetime import datetime, timedelta, timezone
from typing import Any
from xml.etree import ElementTree

import piexif
from piexif._exceptions import InvalidImageDataError

from foundation import version_info
from foundation.core import compose
from foundation.predicates import not_
from foundation.string_utils import endswith, lower, startswith


# ============================================================================
# Metadata Merging
# ============================================================================


def merge_metadata(
    existing: dict[str, Any],
    desired: dict[str, Any],
    overwrite: bool,
    fields_to_update: set[str] | None = None,
) -> dict[str, Any]:
    """
    Merge existing and desired metadata based on overwrite policy.

    Args:
        existing: What's currently in the file
        desired: What we want to write (from iCloud)
        overwrite: If True, desired wins; if False, existing wins for non-None values
        fields_to_update: Optional set of field names to update (e.g., {"rating"})
                         If None, update all fields in desired

    Returns: Merged metadata dict to write

    Examples:
        existing = {"rating": 3, "datetime": "2024:01:01 12:00:00"}
        desired = {"rating": 5}

        merge_metadata(existing, desired, overwrite=False)
        → {"rating": 3, "datetime": "2024:01:01 12:00:00"}  # Keep existing rating

        merge_metadata(existing, desired, overwrite=True)
        → {"rating": 5, "datetime": "2024:01:01 12:00:00"}  # Overwrite rating

        merge_metadata(existing, desired, overwrite=False, fields_to_update={"rating"})
        → {"rating": 3, "datetime": "2024:01:01 12:00:00"}  # Only consider rating for merge
    """
    # Start with a copy of existing to preserve all fields
    result = existing.copy()

    for key, desired_value in desired.items():
        # Skip if we're only updating specific fields and this isn't one
        if fields_to_update is not None and key not in fields_to_update:
            continue

        # Skip None values (never write None)
        if desired_value is None:
            continue

        # If overwrite is True, always use desired value
        if overwrite:
            result[key] = desired_value
        else:
            # Only write if existing doesn't have a value
            existing_value = existing.get(key)
            if existing_value is None:
                result[key] = desired_value
            # else: keep existing value

    return result


# ============================================================================
# EXIF Metadata Functions
# ============================================================================


def read_exif_metadata(logger: logging.Logger, path: str) -> dict[str, typing.Any]:
    """
    Read EXIF metadata from a photo file.

    Returns a dict with:
    - rating: int | None - EXIF rating value (tag 18246)
    - datetime: bytes | None - EXIF datetime original value (tag 36867)
    - _exif_dict: dict - Full EXIF dict to preserve unknown fields

    Returns empty dict on error.
    """
    try:
        exif_dict = piexif.load(path)
        result: dict[str, typing.Any] = {"_exif_dict": exif_dict}

        # Extract rating from 0th IFD (tag 18246)
        if "0th" in exif_dict and 18246 in exif_dict["0th"]:
            result["rating"] = exif_dict["0th"][18246]
        else:
            result["rating"] = None

        # Extract datetime from Exif IFD (tag 36867 - DateTimeOriginal)
        if "Exif" in exif_dict and 36867 in exif_dict["Exif"]:
            result["datetime"] = exif_dict["Exif"][36867]
        else:
            result["datetime"] = None

        return result
    except (ValueError, InvalidImageDataError, FileNotFoundError):
        logger.debug("Error reading EXIF data for %s", path)
        return {}


def write_exif_metadata(
    logger: logging.Logger, path: str, metadata: dict[str, typing.Any], dry_run: bool
) -> None:
    """
    Write EXIF metadata to a photo file.

    Args:
        logger: Logger instance
        path: Path to the photo file
        metadata: Dict with rating, datetime, and optionally _exif_dict to preserve unknown fields
        dry_run: If True, don't write to disk

    Metadata dict can contain:
    - rating: int | None - EXIF rating value
    - datetime: bytes | str | None - EXIF datetime original value
    - _exif_dict: dict - Existing EXIF dict to preserve unknown fields
    """
    if dry_run:
        return

    try:
        # Start with existing EXIF if available in metadata, otherwise load from file
        if "_exif_dict" in metadata:
            exif_dict = metadata["_exif_dict"]
        else:
            try:
                exif_dict = piexif.load(path)
            except (ValueError, InvalidImageDataError):
                # Create minimal EXIF structure
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

        # Ensure required IFDs exist
        if "0th" not in exif_dict:
            exif_dict["0th"] = {}
        if "Exif" not in exif_dict:
            exif_dict["Exif"] = {}

        # Update rating if provided
        if "rating" in metadata and metadata["rating"] is not None:
            exif_dict["0th"][18246] = metadata["rating"]

        # Update datetime if provided
        if "datetime" in metadata and metadata["datetime"] is not None:
            datetime_value = metadata["datetime"]
            if isinstance(datetime_value, str):
                datetime_value = datetime_value.encode("utf-8")
            exif_dict["Exif"][36867] = datetime_value
            exif_dict["Exif"][36868] = datetime_value  # DateTimeDigitized
            exif_dict["0th"][306] = datetime_value  # DateTime

        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, path)
    except (ValueError, InvalidImageDataError):
        logger.debug("Error writing EXIF data for %s", path)
        return


def get_photo_exif(logger: logging.Logger, path: str) -> str | None:
    """Get EXIF date for a photo, return nothing if there is an error"""
    try:
        exif_dict: piexif.ExifIFD = piexif.load(path)
        return typing.cast(str | None, exif_dict.get("Exif").get(36867))
    except (ValueError, InvalidImageDataError):
        logger.debug("Error fetching EXIF data for %s", path)
        return None


def set_photo_exif(logger: logging.Logger, path: str, date: str) -> None:
    """Set EXIF date on a photo, do nothing if there is an error"""
    try:
        exif_dict = piexif.load(path)
        exif_dict.get("1st")[306] = date
        exif_dict.get("Exif")[36867] = date
        exif_dict.get("Exif")[36868] = date
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, path)
    except (ValueError, InvalidImageDataError):
        logger.debug("Error setting EXIF data for %s", path)
        return


# ============================================================================
# XMP Metadata Functions
# ============================================================================


def build_metadata(asset_record: dict[str, Any]) -> dict[str, Any]:
    """
    Build XMP metadata dict from asset record.

    Returns a flexible dict that can preserve additional fields added by external apps.
    """
    metadata: dict[str, Any] = {
        "XMPToolkit": "icloudpd " + version_info.version + "+" + version_info.commit_sha
    }

    # Title (caption)
    if "captionEnc" in asset_record["fields"]:
        metadata["Title"] = base64.b64decode(asset_record["fields"]["captionEnc"]["value"]).decode(
            "utf-8"
        )

    # Description (extended caption)
    if "extendedDescEnc" in asset_record["fields"]:
        metadata["Description"] = base64.b64decode(
            asset_record["fields"]["extendedDescEnc"]["value"]
        ).decode("utf-8")

    # Orientation
    # adjustementSimpleDataEnc can be one of three formats:
    # - a binary plist - starting with 'bplist00' ( YnBsaXN0MD once encoded), seemingly used for some videos metadata (slow motion range etc)
    # - a CRDT (Conflict-free Replicated Data Types) - starting with 'crdt' (Y3JkdA once encoded) - used for drawings and annotations on photos and screenshots
    # - a zlib compressed JSON - used for simple photo metadata adjustments (orientation etc)
    # for exporting metadata, we only consider the JSON data, but it's the only one that doesn't have a predictable start pattern, so we check by excluding the other two
    if "adjustmentSimpleDataEnc" in asset_record["fields"]:
        data_value = asset_record["fields"]["adjustmentSimpleDataEnc"]["value"]
        is_not_crdt = not_(startswith("Y3JkdA"))
        is_not_bplist = not_(startswith("YnBsaXN0MD"))

        if is_not_crdt(data_value) and is_not_bplist(data_value):  # not "crdt" and not "bplist00"
            adjustments = json.loads(
                zlib.decompress(
                    base64.b64decode(asset_record["fields"]["adjustmentSimpleDataEnc"]["value"]),
                    -zlib.MAX_WBITS,
                )
            )
            if "metadata" in adjustments and "orientation" in adjustments["metadata"]:
                metadata["Orientation"] = adjustments["metadata"]["orientation"]

    # Screenshot detection
    if (
        "assetSubtypeV2" in asset_record["fields"]
        and int(asset_record["fields"]["assetSubtypeV2"]["value"]) == 3
    ):
        metadata["Make"] = "Screenshot"
        metadata["DigitalSourceType"] = "screenCapture"

    # Keywords
    if "keywordsEnc" in asset_record["fields"] and len(asset_record["fields"]["keywordsEnc"]) > 0:
        metadata["Keywords"] = plistlib.loads(
            base64.b64decode(asset_record["fields"]["keywordsEnc"]["value"]),
        )

    # GPS Location
    if "locationEnc" in asset_record["fields"]:
        location = plistlib.loads(
            base64.b64decode(asset_record["fields"]["locationEnc"]["value"]),
        )
        if "alt" in location:
            metadata["GPSAltitude"] = location.get("alt")
        if "lat" in location:
            metadata["GPSLatitude"] = location.get("lat")
        if "lon" in location:
            metadata["GPSLongitude"] = location.get("lon")
        if "speed" in location:
            metadata["GPSSpeed"] = location.get("speed")
        if "timestamp" in location and isinstance(location.get("timestamp"), datetime):
            metadata["GPSTimeStamp"] = location.get("timestamp")

    # Create Date
    if "assetDate" in asset_record["fields"]:
        timezone_offset = 0
        if "timeZoneOffset" in asset_record["fields"]:
            timezone_offset = asset_record["fields"]["timeZoneOffset"]["value"]
        metadata["CreateDate"] = datetime.fromtimestamp(
            int(asset_record["fields"]["assetDate"]["value"]) / 1000,
            tz=timezone(timedelta(seconds=timezone_offset)),
        )

    # Rating
    # Hidden or Deleted Photos should be marked as rejected (needs running as --album "Hidden" or --album "Recently Deleted")
    if (
        "isHidden" in asset_record["fields"] and asset_record["fields"]["isHidden"]["value"] == 1
    ) or (
        "isDeleted" in asset_record["fields"] and asset_record["fields"]["isDeleted"]["value"] == 1
    ):
        metadata["Rating"] = -1  # -1 means rejected: https://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#image-rating
    # only mark photo as favorite if not hidden or deleted
    elif (
        "isFavorite" in asset_record["fields"]
        and asset_record["fields"]["isFavorite"]["value"] == 1
    ):
        metadata["Rating"] = 5

    return metadata


def generate_xml(metadata: dict[str, Any]) -> ElementTree.Element:
    """Generate XMP XML structure from metadata dict"""
    # Create the root element
    xml_doc = ElementTree.Element(
        "x:xmpmeta", {"xmlns:x": "adobe:ns:meta/", "x:xmptk": metadata.get("XMPToolkit", "")}
    )

    # Create the RDF element
    rdf = ElementTree.SubElement(
        xml_doc, "rdf:RDF", {"xmlns:rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#"}
    )

    # Create the Description elements
    description_dc = ElementTree.Element(
        "rdf:Description",
        {
            "rdf:about": "",
            "xmlns:dc": "http://purl.org/dc/elements/1.1/",
        },
    )
    description_exif = ElementTree.Element(
        "rdf:Description",
        {
            "rdf:about": "",
            "xmlns:exif": "http://ns.adobe.com/exif/1.0/",
        },
    )
    description_iptc4xmpext = ElementTree.Element(
        "rdf:Description",
        {
            "rdf:about": "",
            "xmlns:Iptc4xmpExt": "http://iptc.org/std/Iptc4xmpExt/2008-02-29/",
        },
    )
    description_photoshop = ElementTree.Element(
        "rdf:Description",
        {
            "rdf:about": "",
            "xmlns:photoshop": "http://ns.adobe.com/photoshop/1.0/",
        },
    )
    description_tiff = ElementTree.Element(
        "rdf:Description",
        {
            "rdf:about": "",
            "xmlns:tiff": "http://ns.adobe.com/tiff/1.0/",
        },
    )
    description_xmp = ElementTree.Element(
        "rdf:Description",
        {
            "rdf:about": "",
            "xmlns:xmp": "http://ns.adobe.com/xap/1.0/",
        },
    )

    # Populate DC elements
    if "Title" in metadata and metadata["Title"]:
        ElementTree.SubElement(description_dc, "dc:title").text = metadata["Title"]
    if "Description" in metadata and metadata["Description"]:
        ElementTree.SubElement(description_dc, "dc:description").text = metadata["Description"]

    # Populate TIFF elements
    if "Orientation" in metadata and metadata["Orientation"]:
        ElementTree.SubElement(description_tiff, "tiff:Orientation").text = str(
            metadata["Orientation"]
        )
    if "Make" in metadata and metadata["Make"]:
        ElementTree.SubElement(description_tiff, "tiff:Make").text = metadata["Make"]

    # Populate IPTC elements
    if "DigitalSourceType" in metadata and metadata["DigitalSourceType"]:
        ElementTree.SubElement(
            description_iptc4xmpext, "Iptc4xmpExt:DigitalSourceType"
        ).text = metadata["DigitalSourceType"]

    # Populate Keywords
    if "Keywords" in metadata and metadata["Keywords"]:
        subject = ElementTree.SubElement(description_dc, "dc:subject")
        seq = ElementTree.SubElement(subject, "rdf:Seq")
        for keyword in metadata["Keywords"]:
            ElementTree.SubElement(seq, "rdf:li").text = keyword

    # Populate GPS elements
    if "GPSAltitude" in metadata and metadata["GPSAltitude"] is not None:
        ElementTree.SubElement(description_exif, "exif:GPSAltitude").text = str(
            metadata["GPSAltitude"]
        )
    if "GPSLatitude" in metadata and metadata["GPSLatitude"] is not None:
        ElementTree.SubElement(description_exif, "exif:GPSLatitude").text = str(
            metadata["GPSLatitude"]
        )
    if "GPSLongitude" in metadata and metadata["GPSLongitude"] is not None:
        ElementTree.SubElement(description_exif, "exif:GPSLongitude").text = str(
            metadata["GPSLongitude"]
        )
    if "GPSSpeed" in metadata and metadata["GPSSpeed"] is not None:
        ElementTree.SubElement(description_exif, "exif:GPSSpeed").text = str(metadata["GPSSpeed"])
    if "GPSTimeStamp" in metadata and metadata["GPSTimeStamp"]:
        ElementTree.SubElement(description_exif, "exif:GPSTimeStamp").text = metadata[
            "GPSTimeStamp"
        ].strftime("%Y-%m-%dT%H:%M:%S%z")

    # Populate Date elements
    if "CreateDate" in metadata and metadata["CreateDate"]:
        ElementTree.SubElement(description_xmp, "xmp:CreateDate").text = metadata[
            "CreateDate"
        ].strftime("%Y-%m-%dT%H:%M:%S%z")
        ElementTree.SubElement(description_photoshop, "photoshop:DateCreated").text = metadata[
            "CreateDate"
        ].strftime(
            "%Y-%m-%dT%H:%M:%S%z"
        )  # Apple Photos uses this field when exporting an XMP sidecar

    # Populate Rating
    if "Rating" in metadata and metadata["Rating"] is not None:
        ElementTree.SubElement(description_xmp, "xmp:Rating").text = str(metadata["Rating"])

    # Add non-empty description elements to RDF
    if len(list(description_dc)) > 0:
        rdf.append(description_dc)
    if len(list(description_exif)) > 0:
        rdf.append(description_exif)
    if len(list(description_iptc4xmpext)) > 0:
        rdf.append(description_iptc4xmpext)
    if len(list(description_photoshop)) > 0:
        rdf.append(description_photoshop)
    if len(list(description_tiff)) > 0:
        rdf.append(description_tiff)
    if len(list(description_xmp)) > 0:
        rdf.append(description_xmp)

    return xml_doc


def can_write_xmp_file(logger: logging.Logger, sidecar_path: str) -> bool:
    """
    Check if XMP sidecar file can be written.

    Returns False if file exists and was created by external tool.
    Returns True if file doesn't exist or was created by icloudpd.
    """
    if not os.path.exists(sidecar_path) or os.path.getsize(sidecar_path) == 0:
        return True

    try:
        root = ElementTree.parse(sidecar_path).getroot()
        xmptk_value = root.attrib.get("{adobe:ns:meta/}xmptk")
        starts_with_icloudpd = startswith("icloudpd")

        if not xmptk_value or not starts_with_icloudpd(xmptk_value):
            logger.info(f"Not overwriting XMP file {sidecar_path} created by {xmptk_value}")
            return False
        else:
            return True
    except ElementTree.ParseError as e:
        logger.info(f"Not overwriting XMP file {sidecar_path} due to parser error: {e}")
        return False


def read_xmp_metadata(logger: logging.Logger, path: str) -> dict[str, Any]:
    """
    Read XMP metadata from a sidecar file.

    Returns a dict with lowercase keys:
    - rating: int | None - XMP rating value
    - datetime: str | None - XMP CreateDate value
    - title: str | None - DC title value
    - xmptk: str | None - XMP toolkit identifier
    - _xml_tree: ElementTree.Element - Full XML tree to preserve unknown fields

    Returns empty dict on error.
    """
    if not os.path.exists(path):
        return {}

    try:
        tree = ElementTree.parse(path)
        root = tree.getroot()
        result: dict[str, Any] = {"_xml_tree": root}

        # Extract xmptk attribute
        result["xmptk"] = root.attrib.get("{adobe:ns:meta/}xmptk")

        # Find RDF element
        rdf = root.find(".//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF")
        if rdf is None:
            return result

        # Extract rating from xmp:Rating
        rating_elem = rdf.find(".//{http://ns.adobe.com/xap/1.0/}Rating")
        if rating_elem is not None and rating_elem.text:
            result["rating"] = int(rating_elem.text)
        else:
            result["rating"] = None

        # Extract datetime from xmp:CreateDate
        datetime_elem = rdf.find(".//{http://ns.adobe.com/xap/1.0/}CreateDate")
        if datetime_elem is not None:
            result["datetime"] = datetime_elem.text
        else:
            result["datetime"] = None

        # Extract title from dc:title
        title_elem = rdf.find(".//{http://purl.org/dc/elements/1.1/}title")
        if title_elem is not None:
            result["title"] = title_elem.text
        else:
            result["title"] = None

        return result
    except ElementTree.ParseError:
        logger.debug("Error parsing XMP file %s", path)
        return {}


def write_xmp_metadata(
    logger: logging.Logger, path: str, metadata: dict[str, Any], dry_run: bool
) -> None:
    """
    Write XMP metadata to a sidecar file.

    Args:
        logger: Logger instance
        path: Path to the XMP sidecar file
        metadata: Dict with rating, datetime, title, and optionally _xml_tree to preserve unknown fields
        dry_run: If True, don't write to disk

    Metadata dict can contain lowercase keys:
    - rating: int | None - XMP rating value
    - datetime: str | None - XMP CreateDate value
    - title: str | None - DC title value
    - xmptk: str | None - XMP toolkit identifier (defaults to icloudpd version)
    - _xml_tree: ElementTree.Element - Existing XML tree to preserve unknown fields
    """
    if dry_run:
        return

    try:
        # Start with existing XML tree if available, otherwise create new
        if "_xml_tree" in metadata and metadata["_xml_tree"] is not None:
            root = metadata["_xml_tree"]
        else:
            # Create minimal XMP structure
            from foundation import version_info

            xmptk = metadata.get("xmptk", "icloudpd " + version_info.version + "+" + version_info.commit_sha)
            root = ElementTree.Element("x:xmpmeta", {"xmlns:x": "adobe:ns:meta/", "x:xmptk": xmptk})
            rdf = ElementTree.SubElement(
                root, "rdf:RDF", {"xmlns:rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#"}
            )

        # Find or create RDF element
        rdf = root.find(".//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF")
        if rdf is None:
            rdf = ElementTree.SubElement(
                root, "rdf:RDF", {"xmlns:rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#"}
            )

        # Find or create xmp Description
        xmp_desc = rdf.find(
            ".//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description[@xmlns:xmp='http://ns.adobe.com/xap/1.0/']"
        )
        if xmp_desc is None:
            xmp_desc = ElementTree.SubElement(
                rdf,
                "rdf:Description",
                {"rdf:about": "", "xmlns:xmp": "http://ns.adobe.com/xap/1.0/"},
            )

        # Find or create dc Description
        dc_desc = rdf.find(
            ".//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description[@xmlns:dc='http://purl.org/dc/elements/1.1/']"
        )
        if dc_desc is None and "title" in metadata:
            dc_desc = ElementTree.SubElement(
                rdf,
                "rdf:Description",
                {"rdf:about": "", "xmlns:dc": "http://purl.org/dc/elements/1.1/"},
            )

        # Update rating
        if "rating" in metadata and metadata["rating"] is not None:
            rating_elem = xmp_desc.find(".//{http://ns.adobe.com/xap/1.0/}Rating")
            if rating_elem is None:
                rating_elem = ElementTree.SubElement(xmp_desc, "xmp:Rating")
            rating_elem.text = str(metadata["rating"])

        # Update datetime
        if "datetime" in metadata and metadata["datetime"] is not None:
            datetime_elem = xmp_desc.find(".//{http://ns.adobe.com/xap/1.0/}CreateDate")
            if datetime_elem is None:
                datetime_elem = ElementTree.SubElement(xmp_desc, "xmp:CreateDate")
            datetime_elem.text = metadata["datetime"]

        # Update title
        if "title" in metadata and metadata["title"] is not None and dc_desc is not None:
            title_elem = dc_desc.find(".//{http://purl.org/dc/elements/1.1/}title")
            if title_elem is None:
                title_elem = ElementTree.SubElement(dc_desc, "dc:title")
            title_elem.text = metadata["title"]

        # Write to file
        with open(path, "wb") as f:
            f.write(ElementTree.tostring(root, encoding="utf-8", xml_declaration=True))
    except Exception:
        logger.debug("Error writing XMP file %s", path)
        return


def generate_xmp_file(
    logger: logging.Logger, download_path: str, asset_record: dict[str, Any], dry_run: bool
) -> None:
    """Generate XMP sidecar file from photo asset record"""
    sidecar_path: str = download_path + ".xmp"

    if can_write_xmp_file(logger, sidecar_path):
        xmp_metadata: dict[str, Any] = build_metadata(asset_record)
        xml_doc: ElementTree.Element = generate_xml(xmp_metadata)
        if not dry_run:
            # Write the XML to the file
            with open(sidecar_path, "wb") as f:
                f.write(ElementTree.tostring(xml_doc, encoding="utf-8", xml_declaration=True))


# ============================================================================
# Public Sync APIs
# ============================================================================


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
    # Only process JPEG files for EXIF
    is_jpeg = compose(endswith((".jpg", ".jpeg")), lower)
    if not is_jpeg(download_path):
        return

    # Skip writes in dry-run mode
    if dry_run:
        return

    # For new files (process_existing_favorites=False), set EXIF datetime if requested
    if not process_existing_favorites and set_exif_datetime:
        date_str = created_date.strftime("%Y-%m-%d %H:%M:%S%z")
        logger.debug("Setting EXIF timestamp for %s: %s", download_path, date_str)
        set_photo_exif(logger, download_path, created_date.strftime("%Y:%m:%d %H:%M:%S"))


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
    # Use the XMP generation function which internally checks if file exists
    # and whether to overwrite (won't overwrite external XMP files)
    generate_xmp_file(logger, download_path, photo._asset_record, dry_run)
