import base64
import json
from datetime import datetime
from typing import Any, cast

import pytz
from requests import Session

from pyicloud_ipd.item_type import AssetItemType
from pyicloud_ipd.services.photos import SharedStreamsLibrary
from pyicloud_ipd.version_size import AssetVersionSize


class FakeResponse:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeSharedStreamsSession:
    def __init__(self) -> None:
        self.posts: list[tuple[str, str]] = []

    def post(self, url: str, data: str, headers: dict[str, str]) -> FakeResponse:
        self.posts.append((url, data))
        if "webgetalbumslist" in url:
            return FakeResponse(
                {
                    "albums": [
                        {
                            "albumlocation": "https://p125-sharedstreams.icloud.com:443/token/sharedstreams",
                            "albumctag": "album-ctag",
                            "ownerdsid": "owner",
                            "attributes": {"name": "Trip", "creationDate": 1700000000000},
                            "sharingtype": "subscribed",
                            "albumguid": "album-guid",
                        }
                    ]
                }
            )
        if "webgetassetcount" in url:
            return FakeResponse({"albumassetcount": 1})
        if "webgetassets" in url:
            return FakeResponse({"records": [_shared_master_record(), _shared_asset_record()]})
        raise AssertionError(f"Unexpected URL {url}")


def field(value: Any, type_: str = "STRING") -> dict[str, Any]:
    return {"value": value, "type": type_}


def _shared_master_record() -> dict[str, Any]:
    return {
        "recordName": "master-record",
        "recordType": "CPLMaster",
        "fields": {
            "filenameEnc": field(base64.b64encode(b"IMG_0001.MP4").decode(), "BYTES"),
            "originalCreationDate": field(1700000000000, "TIMESTAMP"),
            "resOriginalWidth": field(1920, "NUMBER_INT64"),
            "resOriginalHeight": field(1080, "NUMBER_INT64"),
            "resOriginalFileSize": field(12345, "NUMBER_INT64"),
            "resOriginalFileType": field("public.mpeg-4"),
            "resOriginalRes": field(
                {
                    "size": 0,
                    "downloadURL": "https://cvws.icloud-content.com/video",
                    "fileChecksum": base64.b64encode(b"checksum").decode(),
                },
                "ASSETID",
            ),
        },
    }


def _shared_asset_record() -> dict[str, Any]:
    return {
        "recordName": "asset-record",
        "recordType": "CPLAsset",
        "fields": {
            "addedDate": field(1700000000000, "TIMESTAMP"),
            "masterRef": field(
                {
                    "recordName": "master-record",
                    "referenceType": "OWNING",
                    "action": "DELETE_SELF",
                },
                "REFERENCE",
            ),
        },
    }


def test_shared_streams_library_lists_and_reads_assets() -> None:
    session = FakeSharedStreamsSession()
    library = SharedStreamsLibrary(
        "https://p101-sharedstreams.icloud.com:443",
        {
            "clientBuildNumber": "2612Build32",
            "clientMasteringNumber": "2612Build32",
            "clientId": "client-id",
            "dsid": "12345678901",
            "remapEnums": True,
        },
        cast(Session, session),
        "SharedAlbums",
    )

    # Test indexing by name
    album = library.albums["Trip"]
    # Test indexing by GUID
    album_by_guid = library.albums["album-guid"]
    assert album is album_by_guid

    # Test indexing by number/digit
    idx = "1"
    assert idx.isdigit()
    album_by_idx = list(library.albums.values())[int(idx) - 1]
    assert album_by_idx is album

    photos = list(album)
    photo = photos[0]
    version = photo.versions[AssetVersionSize.ORIGINAL]

    assert len(photos) == 1
    assert len(album) == 1
    assert photo.filename == "IMG_0001.MP4"
    assert photo.item_type == AssetItemType.MOVIE
    assert photo.item_type_extension == "MP4"
    assert photo.created == datetime.fromtimestamp(1700000000, tz=pytz.utc)
    assert version.size == 12345
    assert version.type == "public.mpeg-4"
    assert all("remapEnums" not in url for url, _ in session.posts)

    assets_payload = [json.loads(data) for url, data in session.posts if "webgetassets" in url][0]
    assert assets_payload == {
        "albumguid": "album-guid",
        "offset": "0",
        "limit": "1",
        "albumctag": "album-ctag",
    }


def test_xmp_sidecar_generation_with_iso_coordinates(tmp_path) -> None:
    import logging
    import os
    from icloudpd.xmp_sidecar import generate_xmp_file
    from xml.etree import ElementTree

    logger = logging.getLogger("test")
    download_path = str(tmp_path / "test_photo.jpg")

    asset_record = {
        "fields": {
            "locationISO6709Enc": {
                "value": "KzMzLjIxODgtMDk2LjcwNTYrMDAwLjAwMC8="  # +33.2188-096.7056+000.000/
            }
        }
    }

    generate_xmp_file(logger, download_path, asset_record, dry_run=False)

    xmp_file = download_path + ".xmp"
    assert os.path.exists(xmp_file)

    root = ElementTree.parse(xmp_file).getroot()
    xml_str = ElementTree.tostring(root).decode()
    assert "33.2188" in xml_str
    assert "-96.7056" in xml_str
