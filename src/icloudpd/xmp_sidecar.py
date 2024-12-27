"""Generate XMP sidecar file from photo asset record"""

from __future__ import annotations

import base64
import json
import logging
import os
import plistlib
import zlib
from datetime import datetime
from typing import Any, NamedTuple
from xml.etree import ElementTree

import dateutil.tz

from foundation import version_info

exif_tool = None


class XMPMetadata(NamedTuple):
    XMPToolkit: str
    Title: str | None
    Description: str | None
    Orientation: int | None
    Make: str | None
    DigitalSourceType: str | None
    Keywords: list[str] | None
    GPSAltitude: float | None
    GPSLatitude: float | None
    GPSLongitude: float | None
    GPSSpeed: float | None
    GPSTimeStamp: datetime | None
    CreateDate: datetime | None
    Rating: int | None


def generate_xmp_file(
    logger: logging.Logger, download_path: str, asset_record: dict[str, Any]
) -> None:
    sidecar_path: str = download_path + ".xmp"
    can_write_file: bool = True
    if os.path.exists(sidecar_path) and os.path.getsize(sidecar_path) != 0:
        can_write_file = False
        try:
            root = ElementTree.parse(sidecar_path).getroot()
            xmptk_value = root.attrib.get("{adobe:ns:meta/}xmptk")
            if not xmptk_value or not xmptk_value.startswith("icloudpd"):
                logger.info(f"Not overwriting XMP file {sidecar_path} created by {xmptk_value}")
            else:
                can_write_file = True
        except ElementTree.ParseError as e:
            logger.info(f"Not overwriting XMP file {sidecar_path} due to parser error: {e}")

    # decode asset record fields
    # for k in asset_record['fields']:
    #    if asset_record["fields"][k]['type'] == "ENCRYPTED_BYTES":
    # try:
    #     asset_record["fields"][k]['decoded'] = plistlib.loads(base64.b64decode(asset_record['fields'][k]['value']), fmt=plistlib.FMT_BINARY)
    # except plistlib.InvalidFileException:
    #     try:
    #         asset_record["fields"][k]['decoded'] =  json.loads(zlib.decompress(base64.b64decode(asset_record['fields'][k]['value']),-zlib.MAX_WBITS))
    #     except Exception as e:
    #         asset_record["fields"][k]['decoded'] = base64.b64decode(asset_record['fields'][k]['value']).decode("utf-8")
    # json.dump(asset_record["fields"],         open(download_path + ".ar.json", "w"),         indent=4,        default=str,        sort_keys=True)

    if can_write_file:
        xmp_metadata: XMPMetadata = build_metadata(asset_record)
        xml_doc: ElementTree.Element = generate_xml(xmp_metadata)
        # Write the XML to the file
        with open(sidecar_path, "wb") as f:
            f.write(ElementTree.tostring(xml_doc, encoding="utf-8", xml_declaration=True))


def build_metadata(asset_record: dict[str, Any]) -> XMPMetadata:
    """Build XMP metadata from asset record"""

    title = None
    if "captionEnc" in asset_record["fields"]:
        title = base64.b64decode(asset_record["fields"]["captionEnc"]["value"]).decode("utf-8")

    description = None
    if "extendedDescEnc" in asset_record["fields"]:
        description = base64.b64decode(asset_record["fields"]["extendedDescEnc"]["value"]).decode(
            "utf-8"
        )

    orientation = None
    if "adjustmentSimpleDataEnc" in asset_record["fields"]:
        adjustments = json.loads(
            zlib.decompress(
                base64.b64decode(asset_record["fields"]["adjustmentSimpleDataEnc"]["value"]),
                -zlib.MAX_WBITS,
            )
        )
        if "metadata" in adjustments and "orientation" in adjustments["metadata"]:
            orientation = adjustments["metadata"]["orientation"]

    make, digital_source_type = None, None
    if (
        "assetSubtypeV2" in asset_record["fields"]
        and int(asset_record["fields"]["assetSubtypeV2"]["value"]) == 3
    ):
        make = "Screenshot"
        digital_source_type = "screenCapture"

    keywords = None
    if "keywordsEnc" in asset_record["fields"] and len(asset_record["fields"]["keywordsEnc"]) > 0:
        keywords = plistlib.loads(
            base64.b64decode(asset_record["fields"]["keywordsEnc"]["value"]),
            fmt=plistlib.FMT_BINARY,
        )

    if "locationEnc" in asset_record["fields"]:
        location = plistlib.loads(
            base64.b64decode(asset_record["fields"]["locationEnc"]["value"]),
            fmt=plistlib.FMT_BINARY,
        )
        gps_altitude = location.get("alt")
        gps_latitude = location.get("lat")
        gps_longitude = location.get("lon")
        gps_speed = location.get("speed")
        gps_timestamp = (
            location.get("timestamp") if isinstance(location.get("timestamp"), datetime) else None
        )
    else:
        gps_altitude, gps_latitude, gps_longitude, gps_speed, gps_timestamp = (
            None,
            None,
            None,
            None,
            None,
        )

    create_date = None
    if "assetDate" in asset_record["fields"]:
        timezone_offset = 0
        if "timeZoneOffset" in asset_record["fields"]:
            timezone_offset = asset_record["fields"]["timeZoneOffset"]["value"]
        create_date = datetime.fromtimestamp(
            int(asset_record["fields"]["assetDate"]["value"]) / 1000,
            tz=dateutil.tz.tzoffset(None, timezone_offset),
        )

    rating = None
    # Hidden or Deleted Photos should be marked as rejected (needs running as --album "Hidden" or --album "Recently Deleted")
    if (
        "isHidden" in asset_record["fields"] and asset_record["fields"]["isHidden"]["value"] == 1
    ) or (
        "isDeleted" in asset_record["fields"] and asset_record["fields"]["isDeleted"]["value"] == 1
    ):
        rating = -1  # -1 means rejected: https://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#image-rating
    # only mark photo as favorite if not hidden or deleted
    elif asset_record["fields"]["isFavorite"]["value"] == 1:
        rating = 5

    return XMPMetadata(
        XMPToolkit="icloudpd " + version_info.version + "+" + version_info.commit_sha,
        Title=title,
        Description=description,
        Orientation=orientation,
        Make=make,
        DigitalSourceType=digital_source_type,
        Keywords=keywords,
        GPSAltitude=gps_altitude,
        GPSLatitude=gps_latitude,
        GPSLongitude=gps_longitude,
        GPSSpeed=gps_speed,
        GPSTimeStamp=gps_timestamp,
        CreateDate=create_date,
        Rating=rating,
    )


def generate_xml(metadata: XMPMetadata) -> ElementTree.Element:
    # Create the root element
    xml_doc = ElementTree.Element(
        "x:xml_doc", {"xmlns:x": "adobe:ns:meta/", "x:xmptk": metadata.XMPToolkit}
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
    if metadata.Title:
        ElementTree.SubElement(description_dc, "dc:title").text = metadata.Title
    if metadata.Description:
        ElementTree.SubElement(description_dc, "dc:description").text = metadata.Description

    if metadata.Orientation:
        ElementTree.SubElement(description_tiff, "tiff:Orientation").text = str(
            metadata.Orientation
        )
    if metadata.Make:
        ElementTree.SubElement(description_tiff, "tiff:Make").text = metadata.Make
    if metadata.DigitalSourceType:
        ElementTree.SubElement(
            description_iptc4xmpext, "Iptc4xmpExt:DigitalSourceType"
        ).text = metadata.DigitalSourceType

    if metadata.Keywords:
        subject = ElementTree.SubElement(description_dc, "dc:subject")
        seq = ElementTree.SubElement(subject, "rdf:Seq")
        for keyword in metadata.Keywords:
            ElementTree.SubElement(seq, "rdf:li").text = keyword

    if metadata.GPSAltitude:
        ElementTree.SubElement(description_exif, "exif:GPSAltitude").text = str(
            metadata.GPSAltitude
        )
    if metadata.GPSLatitude:
        ElementTree.SubElement(description_exif, "exif:GPSLatitude").text = str(
            metadata.GPSLatitude
        )
    if metadata.GPSLongitude:
        ElementTree.SubElement(description_exif, "exif:GPSLongitude").text = str(
            metadata.GPSLongitude
        )
    if metadata.GPSSpeed:
        ElementTree.SubElement(description_exif, "exif:GPSSpeed").text = str(metadata.GPSSpeed)
    if metadata.GPSTimeStamp:
        ElementTree.SubElement(
            description_exif, "exif:GPSTimeStamp"
        ).text = metadata.GPSTimeStamp.strftime("%Y-%m-%dT%H:%M:%S%z")

    if metadata.CreateDate:
        ElementTree.SubElement(
            description_xmp, "xmp:CreateDate"
        ).text = metadata.CreateDate.strftime("%Y-%m-%dT%H:%M:%S%z")
        ElementTree.SubElement(
            description_photoshop, "photoshop:DateCreated"
        ).text = metadata.CreateDate.strftime(
            "%Y-%m-%dT%H:%M:%S%z"
        )  # Apple Photos uses this field when exporting an XMP sidecar

    if metadata.Rating:
        ElementTree.SubElement(description_xmp, "xmp:Rating").text = str(metadata.Rating)
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
