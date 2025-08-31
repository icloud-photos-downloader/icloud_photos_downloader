import base64
import copy
import json
import logging
import re
import typing
from datetime import datetime
from typing import Any, Callable, Dict, Generator, Sequence, Tuple, cast
from urllib.parse import urlencode

import pytz
from requests import Response, Session
from tzlocal import get_localzone

from foundation import bytes_decode, wrap_param_in_exception
from foundation.core import compose, identity
from foundation.core.optional import fromMaybe
from icloudpd.paths import clean_filename
from pyicloud_ipd.asset_version import (
    ITEM_TYPE_EXTENSIONS,
    AssetVersion,
    add_suffix_to_filename,
    calculate_version_filename,
)
from pyicloud_ipd.exceptions import (
    PyiCloudServiceNotActivatedException,
)
from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.item_type import AssetItemType
from pyicloud_ipd.raw_policy import RawTreatmentPolicy
from pyicloud_ipd.session import PyiCloudSession
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize, VersionSize


def apply_file_match_policy(
    file_match_policy: FileMatchPolicy, asset_id: str
) -> Callable[[str], str]:
    """
    Create a function that applies the specified file match policy to a filename.

    Args:
        file_match_policy: The file match policy to apply
        asset_id: The asset ID used for generating unique suffixes

    Returns:
        A function that transforms filenames according to the policy
    """

    def transform_filename(filename: str) -> str:
        if file_match_policy == FileMatchPolicy.NAME_ID7:
            # Generate 7-character base64 suffix from asset ID
            id_suffix = base64.b64encode(asset_id.encode("utf-8")).decode("ascii")[0:7]
            return add_suffix_to_filename(f"_{id_suffix}", filename)
        else:
            # For NAME_SIZE_DEDUP_WITH_SUFFIX and other policies, return filename as-is
            # (the deduplication logic is handled elsewhere in the download process)
            return filename

    return transform_filename


def apply_filename_cleaner(filename_cleaner: Callable[[str], str]) -> Callable[[str], str]:
    """
    Create a function that applies filename cleaning to a raw filename.

    Args:
        filename_cleaner: The filename cleaner function to apply (e.g., unicode handling)

    Returns:
        A function that cleans filenames by composing basic cleaning with additional cleaning
    """

    def clean_filename_transform(raw_filename: str) -> str:
        # Apply basic filesystem character cleaning first, then additional cleaning
        return compose(filename_cleaner, clean_filename)(raw_filename)

    return clean_filename_transform


def generate_fingerprint_filename(asset_id: str, item_type_extension: str) -> str:
    """
    Generate a filename based on asset fingerprint when filenameEnc is not available.

    Args:
        asset_id: The asset ID to use for generating the fingerprint
        item_type_extension: The file extension based on item type

    Returns:
        A filename based on truncated fingerprint hash with proper extension
    """
    # Use the truncated fingerprint (hash) plus the correct extension
    fingerprint = re.sub("[^0-9a-zA-Z]", "_", asset_id)[0:12]
    return ".".join([fingerprint, item_type_extension])


def filename_with_fallback(asset_id: str, item_type_extension: str) -> Callable[[str | None], str]:
    """
    Create a function that extracts filename from Maybe, using fingerprint fallback as default.

    Args:
        asset_id: The asset ID for generating fingerprint fallback
        item_type_extension: The file extension for fingerprint fallback

    Returns:
        A function that takes an optional filename and returns a filename,
        falling back to fingerprint if the input is None
    """
    fallback = generate_fingerprint_filename(asset_id, item_type_extension)
    return fromMaybe(fallback)


logger = logging.getLogger(__name__)


def download_asset(session: Session, url: str, start: int = 0) -> Response:
    """
    Download an asset from the given URL using the provided session.

    Args:
        session: The authenticated session to use for the download
        url: The URL to download from
        start: The byte offset to start downloading from (for resume capability)

    Returns:
        The HTTP response for the download request
    """
    headers = {"Range": f"bytes={start}-"}
    return session.get(url, headers=headers, stream=True)


def apply_raw_policy(
    versions: Dict[VersionSize, AssetVersion], raw_policy: RawTreatmentPolicy
) -> Dict[VersionSize, AssetVersion]:
    """
    Apply raw treatment policy to asset versions, swapping original and alternative if needed.

    Args:
        versions: Dictionary of asset versions
        raw_policy: The raw treatment policy to apply

    Returns:
        Dictionary of versions with raw policy applied
    """
    # Make a copy to avoid modifying the original
    result_versions = dict(versions)

    # swap original & alternative according to raw_policy
    if AssetVersionSize.ALTERNATIVE in result_versions and (
        (
            "raw" in result_versions[AssetVersionSize.ALTERNATIVE].type
            and raw_policy == RawTreatmentPolicy.AS_ORIGINAL
        )
        or (
            "raw" in result_versions[AssetVersionSize.ORIGINAL].type
            and raw_policy == RawTreatmentPolicy.AS_ALTERNATIVE
        )
    ):
        _a = copy.copy(result_versions[AssetVersionSize.ALTERNATIVE])
        _o = copy.copy(result_versions[AssetVersionSize.ORIGINAL])
        result_versions[AssetVersionSize.ALTERNATIVE] = _o
        result_versions[AssetVersionSize.ORIGINAL] = _a

    return result_versions


class PhotoLibrary:
    """Represents a library in the user's photos.

    This provides access to all the albums as well as the photos.
    """

    WHOLE_COLLECTION: Dict[str, Any] = {
        "obj_type": "CPLAssetByAssetDateWithoutHiddenOrDeleted",
        "list_type": "CPLAssetAndMasterByAssetDateWithoutHiddenOrDeleted",
        "query_filter": None,
    }
    RECENTLY_DELETED: Dict[str, Any] = {
        "obj_type": "CPLAssetDeletedByExpungedDate",
        "list_type": "CPLAssetAndMasterDeletedByExpungedDate",
        "query_filter": None,
    }
    SMART_FOLDERS = {
        "Time-lapse": {
            "obj_type": "CPLAssetInSmartAlbumByAssetDate:Timelapse",
            "list_type": "CPLAssetAndMasterInSmartAlbumByAssetDate",
            "query_filter": [
                {
                    "fieldName": "smartAlbum",
                    "comparator": "EQUALS",
                    "fieldValue": {"type": "STRING", "value": "TIMELAPSE"},
                }
            ],
        },
        "Videos": {
            "obj_type": "CPLAssetInSmartAlbumByAssetDate:Video",
            "list_type": "CPLAssetAndMasterInSmartAlbumByAssetDate",
            "query_filter": [
                {
                    "fieldName": "smartAlbum",
                    "comparator": "EQUALS",
                    "fieldValue": {"type": "STRING", "value": "VIDEO"},
                }
            ],
        },
        "Slo-mo": {
            "obj_type": "CPLAssetInSmartAlbumByAssetDate:Slomo",
            "list_type": "CPLAssetAndMasterInSmartAlbumByAssetDate",
            "query_filter": [
                {
                    "fieldName": "smartAlbum",
                    "comparator": "EQUALS",
                    "fieldValue": {"type": "STRING", "value": "SLOMO"},
                }
            ],
        },
        "Bursts": {
            "obj_type": "CPLAssetBurstStackAssetByAssetDate",
            "list_type": "CPLBurstStackAssetAndMasterByAssetDate",
            "query_filter": None,
        },
        "Favorites": {
            "obj_type": "CPLAssetInSmartAlbumByAssetDate:Favorite",
            "list_type": "CPLAssetAndMasterInSmartAlbumByAssetDate",
            "query_filter": [
                {
                    "fieldName": "smartAlbum",
                    "comparator": "EQUALS",
                    "fieldValue": {"type": "STRING", "value": "FAVORITE"},
                }
            ],
        },
        "Panoramas": {
            "obj_type": "CPLAssetInSmartAlbumByAssetDate:Panorama",
            "list_type": "CPLAssetAndMasterInSmartAlbumByAssetDate",
            "query_filter": [
                {
                    "fieldName": "smartAlbum",
                    "comparator": "EQUALS",
                    "fieldValue": {"type": "STRING", "value": "PANORAMA"},
                }
            ],
        },
        "Screenshots": {
            "obj_type": "CPLAssetInSmartAlbumByAssetDate:Screenshot",
            "list_type": "CPLAssetAndMasterInSmartAlbumByAssetDate",
            "query_filter": [
                {
                    "fieldName": "smartAlbum",
                    "comparator": "EQUALS",
                    "fieldValue": {"type": "STRING", "value": "SCREENSHOT"},
                }
            ],
        },
        "Live": {
            "obj_type": "CPLAssetInSmartAlbumByAssetDate:Live",
            "list_type": "CPLAssetAndMasterInSmartAlbumByAssetDate",
            "query_filter": [
                {
                    "fieldName": "smartAlbum",
                    "comparator": "EQUALS",
                    "fieldValue": {"type": "STRING", "value": "LIVE"},
                }
            ],
        },
        "Recently Deleted": RECENTLY_DELETED,
        "Hidden": {
            "obj_type": "CPLAssetHiddenByAssetDate",
            "list_type": "CPLAssetAndMasterHiddenByAssetDate",
            "query_filter": None,
        },
    }

    def __init__(
        self,
        service_endpoint: str,
        params: Dict[str, Any],
        session: Session,
        zone_id: Dict[str, Any],
        library_type: str,
    ):
        self.service_endpoint = service_endpoint
        self.params = params
        self.session = session
        self.zone_id = zone_id
        self.library_type = library_type

        url = f"{self.service_endpoint}/records/query?{urlencode(self.params)}"
        json_data = json.dumps(
            {
                "query": {"recordType": "CheckIndexingState"},
                "zoneID": self.zone_id,
            }
        )

        request = self.session.post(url, data=json_data, headers={"Content-type": "text/plain"})
        response = request.json()
        indexing_state = response["records"][0]["fields"]["state"]["value"]
        if indexing_state != "FINISHED":
            raise PyiCloudServiceNotActivatedException(
                ("Apple iCloud Photo Library has not finished indexing yet"), None
            )

    @property
    def albums(self) -> Dict[str, "PhotoAlbum"]:
        albums = {
            name: PhotoAlbum(
                self.params,
                self.session,
                self.service_endpoint,
                name,
                zone_id=self.zone_id,
                **props,
            )  # type: ignore[arg-type] # dynamically builing params
            for (name, props) in self.SMART_FOLDERS.items()
        }

        for folder in self._fetch_folders():
            # FIXME: Handle subfolders
            if folder["recordName"] in ("----Root-Folder----", "----Project-Root-Folder----") or (
                folder["fields"].get("isDeleted") and folder["fields"]["isDeleted"]["value"]
            ):
                continue

            folder_id = folder["recordName"]
            folder_obj_type = f"CPLContainerRelationNotDeletedByAssetDate:{folder_id}"
            folder_name = base64.b64decode(folder["fields"]["albumNameEnc"]["value"]).decode(
                "utf-8"
            )
            query_filter = [
                {
                    "fieldName": "parentId",
                    "comparator": "EQUALS",
                    "fieldValue": {"type": "STRING", "value": folder_id},
                }
            ]

            album = PhotoAlbum(
                self.params,
                self.session,
                self.service_endpoint,
                folder_name,
                "CPLContainerRelationLiveByAssetDate",
                folder_obj_type,
                query_filter,
                zone_id=self.zone_id,
            )
            albums[folder_name] = album

        return albums

    def _fetch_folders(self) -> Sequence[Dict[str, Any]]:
        if self.library_type == "shared":
            return []
        url = f"{self.service_endpoint}/records/query?{urlencode(self.params)}"
        json_data = json.dumps(
            {
                "query": {"recordType": "CPLAlbumByPositionLive"},
                "zoneID": self.zone_id,
            }
        )

        request = self.session.post(url, data=json_data, headers={"Content-type": "text/plain"})
        response = request.json()

        return typing.cast(Sequence[Dict[str, Any]], response["records"])

    @property
    def all(self) -> "PhotoAlbum":
        return PhotoAlbum(
            self.params,
            self.session,
            self.service_endpoint,
            "",
            self.WHOLE_COLLECTION["list_type"],
            self.WHOLE_COLLECTION["obj_type"],
            query_filter=self.WHOLE_COLLECTION["query_filter"],
            zone_id=self.zone_id,
        )

    @property
    def recently_deleted(self) -> "PhotoAlbum":
        return PhotoAlbum(
            self.params,
            self.session,
            self.service_endpoint,
            "",
            self.RECENTLY_DELETED["list_type"],
            self.RECENTLY_DELETED["obj_type"],
            query_filter=self.RECENTLY_DELETED["query_filter"],
            zone_id=self.zone_id,
        )


class PhotosService(PhotoLibrary):
    """The 'Photos' iCloud service.

    This also acts as a way to access the user's primary library.
    """

    def __init__(self, service_root: str, session: PyiCloudSession, params: Dict[str, Any]):
        self.session = session
        self.params = dict(params)
        self._service_root = service_root

        self._private_libraries: Dict[str, PhotoLibrary] | None = None
        self._shared_libraries: Dict[str, PhotoLibrary] | None = None

        self.params.update({"remapEnums": True, "getCurrentSyncToken": True})

        # Initialize as primary library
        service_endpoint = self.get_service_endpoint("private")
        zone_id = {"zoneName": "PrimarySync"}
        super().__init__(service_endpoint, self.params, self.session, zone_id, "private")

        # TODO: Does syncToken ever change?
        # self.params.update({
        #     'syncToken': response['syncToken'],
        #     'clientInstanceId': self.params.pop('clientId')
        # })

        # self._photo_assets = {}

    @property
    def private_libraries(self) -> Dict[str, PhotoLibrary]:
        if not self._private_libraries:
            self._private_libraries = self._fetch_libraries("private")

        return self._private_libraries

    @property
    def shared_libraries(self) -> Dict[str, PhotoLibrary]:
        if not self._shared_libraries:
            self._shared_libraries = self._fetch_libraries("shared")

        return self._shared_libraries

    def _fetch_libraries(self, library_type: str) -> Dict[str, PhotoLibrary]:
        try:
            libraries = {}
            service_endpoint = self.get_service_endpoint(library_type)
            url = f"{service_endpoint}/zones/list"
            request = self.session.post(url, data="{}", headers={"Content-type": "text/plain"})
            response = request.json()
            for zone in response["zones"]:
                if not zone.get("deleted"):
                    zone_name = zone["zoneID"]["zoneName"]
                    service_endpoint = self.get_service_endpoint(library_type)
                    libraries[zone_name] = PhotoLibrary(
                        service_endpoint,
                        self.params,
                        self.session,
                        zone_id=zone["zoneID"],
                        library_type=library_type,
                    )
                    # obj_type='CPLAssetByAssetDateWithoutHiddenOrDeleted',
                    # list_type="CPLAssetAndMasterByAssetDateWithoutHiddenOrDeleted",
                    # direction="ASCENDING", query_filter=None,
                    # zone_id=zone['zoneID'])
        except Exception as e:
            logger.error(f"library exception: {str(e)}")
        return libraries

    def get_service_endpoint(self, library_type: str) -> str:
        return f"{self._service_root}/database/1/com.apple.photos.cloud/production/{library_type}"


class PhotoAlbum:
    def __init__(
        self,
        params: Dict[str, Any],
        session: Session,
        service_endpoint: str,
        name: str,
        list_type: str,
        obj_type: str,
        query_filter: Sequence[Dict[str, Any]] | None = None,
        page_size: int = 100,
        zone_id: Dict[str, Any] | None = None,
    ):
        self.name = name
        self.params = params
        self.session = session
        self.service_endpoint = service_endpoint
        self.list_type = list_type
        self.obj_type = obj_type
        self.offset = 0
        self.query_filter = query_filter
        self.page_size = page_size

        if zone_id:
            self._zone_id: Dict[str, Any] = zone_id
        else:
            self._zone_id = {"zoneName": "PrimarySync"}

    @property
    def title(self) -> str:
        return self.name

    def __iter__(self) -> Generator["PhotoAsset", Any, None]:
        return self.photos

    def __len__(self) -> int:
        url = f"{self.service_endpoint}/internal/records/query/batch?{urlencode(self.params)}"
        request = self.session.post(
            url,
            data=json.dumps(self._count_query_gen(self.obj_type)),
            headers={"Content-type": "text/plain"},
        )
        response = request.json()

        return int(response["batch"][0]["records"][0]["fields"]["itemCount"]["value"])

    # Perform the request in a separate method so that we
    # can mock it to test session errors.
    def photos_request(self) -> Response:
        url = (f"{self.service_endpoint}/records/query?") + urlencode(self.params)
        return self.session.post(
            url,
            data=json.dumps(self._list_query_gen(self.offset, self.list_type, self.query_filter)),
            headers={"Content-type": "text/plain"},
        )

    @property
    def photos(self) -> Generator["PhotoAsset", Any, None]:
        while True:
            request = self.photos_request()

            #            url = ('%s/records/query?' % self.service_endpoint) + \
            #                urlencode(self.service.params)
            #            request = self.service.session.post(
            #                url,
            #                data=json.dumps(self._list_query_gen(
            #                    offset, self.list_type, self.direction,
            #                    self.query_filter)),
            #                headers={'Content-type': 'text/plain'}
            #            )

            response = request.json()

            asset_records = {}
            master_records = []
            for rec in response["records"]:
                if rec["recordType"] == "CPLAsset":
                    master_id = rec["fields"]["masterRef"]["value"]["recordName"]
                    asset_records[master_id] = rec
                elif rec["recordType"] == "CPLMaster":
                    master_records.append(rec)

            master_records_len = len(master_records)
            if master_records_len:
                for master_record in master_records:
                    record_name = master_record["recordName"]
                    yield PhotoAsset(master_record, asset_records[record_name])
                    self.increment_offset(1)
            else:
                break

    def increment_offset(self, value: int) -> None:
        self.offset += value

    def _count_query_gen(self, obj_type: str) -> Dict[str, Any]:
        query = {
            "batch": [
                {
                    "resultsLimit": 1,
                    "query": {
                        "filterBy": {
                            "fieldName": "indexCountID",
                            "fieldValue": {"type": "STRING_LIST", "value": [obj_type]},
                            "comparator": "IN",
                        },
                        "recordType": "HyperionIndexCountLookup",
                    },
                    "zoneWide": True,
                    "zoneID": self._zone_id,
                }
            ]
        }

        return query

    def _list_query_gen(
        self, offset: int, list_type: str, query_filter: Sequence[Dict[str, None]] | None = None
    ) -> Dict[str, Any]:
        query: Dict[str, Any] = {
            "query": {
                "filterBy": [
                    {
                        "fieldName": "startRank",
                        "fieldValue": {"type": "INT64", "value": offset},
                        "comparator": "EQUALS",
                    },
                    {
                        "fieldName": "direction",
                        "fieldValue": {"type": "STRING", "value": "ASCENDING"},
                        "comparator": "EQUALS",
                    },
                ],
                "recordType": list_type,
            },
            "resultsLimit": self.page_size * 2,
            "desiredKeys": [
                "resJPEGFullWidth",
                "resJPEGFullHeight",
                "resJPEGFullFileType",
                "resJPEGFullFingerprint",
                "resJPEGFullRes",
                "resJPEGLargeWidth",
                "resJPEGLargeHeight",
                "resJPEGLargeFileType",
                "resJPEGLargeFingerprint",
                "resJPEGLargeRes",
                "resJPEGMedWidth",
                "resJPEGMedHeight",
                "resJPEGMedFileType",
                "resJPEGMedFingerprint",
                "resJPEGMedRes",
                "resJPEGThumbWidth",
                "resJPEGThumbHeight",
                "resJPEGThumbFileType",
                "resJPEGThumbFingerprint",
                "resJPEGThumbRes",
                "resVidFullWidth",
                "resVidFullHeight",
                "resVidFullFileType",
                "resVidFullFingerprint",
                "resVidFullRes",
                "resVidMedWidth",
                "resVidMedHeight",
                "resVidMedFileType",
                "resVidMedFingerprint",
                "resVidMedRes",
                "resVidSmallWidth",
                "resVidSmallHeight",
                "resVidSmallFileType",
                "resVidSmallFingerprint",
                "resVidSmallRes",
                "resSidecarWidth",
                "resSidecarHeight",
                "resSidecarFileType",
                "resSidecarFingerprint",
                "resSidecarRes",
                "itemType",
                "dataClassType",
                "filenameEnc",
                "originalOrientation",
                "resOriginalWidth",
                "resOriginalHeight",
                "resOriginalFileType",
                "resOriginalFingerprint",
                "resOriginalRes",
                "resOriginalAltWidth",
                "resOriginalAltHeight",
                "resOriginalAltFileType",
                "resOriginalAltFingerprint",
                "resOriginalAltRes",
                "resOriginalVidComplWidth",
                "resOriginalVidComplHeight",
                "resOriginalVidComplFileType",
                "resOriginalVidComplFingerprint",
                "resOriginalVidComplRes",
                "isDeleted",
                "isExpunged",
                "dateExpunged",
                "remappedRef",
                "recordName",
                "recordType",
                "recordChangeTag",
                "masterRef",
                "adjustmentRenderType",
                "assetDate",
                "addedDate",
                "isFavorite",
                "isHidden",
                "orientation",
                "duration",
                "assetSubtype",
                "assetSubtypeV2",
                "assetHDRType",
                "burstFlags",
                "burstFlagsExt",
                "burstId",
                "captionEnc",
                "locationEnc",
                "locationV2Enc",
                "locationLatitude",
                "locationLongitude",
                "adjustmentType",
                "timeZoneOffset",
                "vidComplDurValue",
                "vidComplDurScale",
                "vidComplDispValue",
                "vidComplDispScale",
                "keywordsEnc",
                "extendedDescEnc",
                "adjustedMediaMetaDataEnc",
                "adjustmentSimpleDataEnc",
                "vidComplVisibilityState",
                "customRenderedValue",
                "containerId",
                "itemId",
                "position",
                "isKeyAsset",
            ],
            "zoneID": self._zone_id,
        }

        if query_filter:
            query["query"]["filterBy"].extend(query_filter)

        return query

    def __unicode__(self) -> str:
        return self.title

    def __str__(self) -> str:
        as_unicode = self.__unicode__()
        return as_unicode

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: '{self}'>"


class PhotoAsset:
    def __init__(self, master_record: Dict[str, Any], asset_record: Dict[str, Any]) -> None:
        self._master_record = master_record
        self._asset_record = asset_record

        self._versions: Dict[VersionSize, AssetVersion] | None = None

    ITEM_TYPES = {
        "public.heic": AssetItemType.IMAGE,
        "public.heif": AssetItemType.IMAGE,
        "public.jpeg": AssetItemType.IMAGE,
        "public.png": AssetItemType.IMAGE,
        "com.apple.quicktime-movie": AssetItemType.MOVIE,
        "com.adobe.raw-image": AssetItemType.IMAGE,
        "com.canon.cr2-raw-image": AssetItemType.IMAGE,
        "com.canon.crw-raw-image": AssetItemType.IMAGE,
        "com.sony.arw-raw-image": AssetItemType.IMAGE,
        "com.fuji.raw-image": AssetItemType.IMAGE,
        "com.panasonic.rw2-raw-image": AssetItemType.IMAGE,
        "com.nikon.nrw-raw-image": AssetItemType.IMAGE,
        "com.pentax.raw-image": AssetItemType.IMAGE,
        "com.nikon.raw-image": AssetItemType.IMAGE,
        "com.olympus.raw-image": AssetItemType.IMAGE,
        "com.canon.cr3-raw-image": AssetItemType.IMAGE,
        "com.olympus.or-raw-image": AssetItemType.IMAGE,
    }

    PHOTO_VERSION_LOOKUP: Dict[VersionSize, str] = {
        AssetVersionSize.ORIGINAL: "resOriginal",
        AssetVersionSize.ALTERNATIVE: "resOriginalAlt",
        AssetVersionSize.MEDIUM: "resJPEGMed",
        AssetVersionSize.THUMB: "resJPEGThumb",
        AssetVersionSize.ADJUSTED: "resJPEGFull",
        LivePhotoVersionSize.ORIGINAL: "resOriginalVidCompl",
        LivePhotoVersionSize.MEDIUM: "resVidMed",
        LivePhotoVersionSize.THUMB: "resVidSmall",
    }

    VIDEO_VERSION_LOOKUP: Dict[VersionSize, str] = {
        AssetVersionSize.ORIGINAL: "resOriginal",
        AssetVersionSize.MEDIUM: "resVidMed",
        AssetVersionSize.THUMB: "resVidSmall",
    }

    @property
    def id(self) -> str:
        return typing.cast(str, self._master_record["recordName"])

    def calculate_filename(self) -> str | None:
        """
        Calculate the raw filename for this asset from filenameEnc if present.
        Returns None if filenameEnc is not available.

        Filename cleaning should be applied by composing this with apply_filename_cleaner().
        File match policy transformations should be applied by composing this with apply_file_match_policy().
        Fallback to fingerprint filename should be handled by filename_with_fallback().
        """
        fields = self._master_record["fields"]
        if "filenameEnc" in fields:
            filename_enc: Dict[str, Any] = fields["filenameEnc"]

            def _get_value(input: Dict[str, Any]) -> str:
                return cast(str, input["value"])

            def _get_type(input: Dict[str, Any]) -> str:
                return cast(str, input["type"])

            def _match_type(
                string_parser: Callable[[str], str], base64_parser: Callable[[str], str]
            ) -> Callable[[str], Callable[[str], str]]:
                def _internal(type: str) -> Callable[[str], str]:
                    if type == "STRING":
                        return string_parser
                    elif type == "ENCRYPTED_BYTES":
                        return base64_parser
                    else:
                        raise ValueError(f"Unsupported filename encoding {type}")

                return _internal

            parse_base64_value = compose(
                bytes_decode("utf-8"),
                base64.b64decode,
            )

            parser_selector = compose(_match_type(identity, parse_base64_value), _get_type)

            type_parser = wrap_param_in_exception("Parsing filenameEnc type", parser_selector)

            _value_parser = type_parser(filename_enc)

            # Just extract and parse the raw value, no cleaning applied
            extract_value_and_parse = compose(
                _value_parser,
                _get_value,
            )
            parser = wrap_param_in_exception("Parsing filenameEnc", extract_value_and_parse)

            return parser(filename_enc)
        else:
            # No filenameEnc available, return None - caller should use fallback
            return None

    @property
    def filename(self) -> str:
        """Backward compatibility property - use calculate_filename() with explicit parameters"""
        # Use default file match policy for backward compatibility and compose with calculate_filename
        from pyicloud_ipd.file_match import FileMatchPolicy

        # Use fromMaybe to extract filename with fallback, then apply cleaning and file match policy
        extract_with_fallback = filename_with_fallback(self.id, self.item_type_extension)
        raw_filename = extract_with_fallback(self.calculate_filename())
        filename_cleaner_transformer = apply_filename_cleaner(identity)
        cleaned_filename = filename_cleaner_transformer(raw_filename)
        policy_transformer = apply_file_match_policy(
            FileMatchPolicy.NAME_SIZE_DEDUP_WITH_SUFFIX, self.id
        )
        return policy_transformer(cleaned_filename)

    @property
    def size(self) -> int:
        return typing.cast(int, self._master_record["fields"]["resOriginalRes"]["value"]["size"])

    @property
    def created(self) -> datetime:
        try:
            created_date = self.asset_date.astimezone(get_localzone())
        except (ValueError, OSError):
            logger.error(
                "Could not convert photo created date to local timezone (%s)", self.asset_date
            )
            created_date = self.asset_date

        return created_date

    @property
    def asset_date(self) -> datetime:
        try:
            dt = datetime.fromtimestamp(
                self._asset_record["fields"]["assetDate"]["value"] / 1000.0, tz=pytz.utc
            )
        except (KeyError, TypeError, ValueError):
            dt = datetime.fromtimestamp(0)
        return dt

    @property
    def added_date(self) -> datetime:
        dt = datetime.fromtimestamp(
            self._asset_record["fields"]["addedDate"]["value"] / 1000.0, tz=pytz.utc
        )
        return dt

    @property
    def dimensions(self) -> Tuple[int, int]:
        return (
            self._master_record["fields"]["resOriginalWidth"]["value"],
            self._master_record["fields"]["resOriginalHeight"]["value"],
        )

    @property
    def item_type(self) -> AssetItemType | None:
        fields = self._master_record["fields"]
        if "itemType" not in fields:
            # raise ValueError(f"Cannot find itemType in {fields!r}")
            return None
        item_type_field = fields["itemType"]
        if "value" not in item_type_field:
            # raise ValueError(f"Cannot find value in itemType {item_type_field!r}")
            return None
        item_type = item_type_field["value"]
        if item_type in self.ITEM_TYPES:
            return self.ITEM_TYPES[item_type]
        from foundation.core import compose
        from foundation.string_utils import endswith, lower

        is_image_ext = compose(endswith((".heic", ".png", ".jpg", ".jpeg")), lower)

        if is_image_ext(self.filename):
            return AssetItemType.IMAGE
        return AssetItemType.MOVIE

    @property
    def item_type_extension(self) -> str:
        fields = self._master_record["fields"]
        if "itemType" not in fields or "value" not in fields["itemType"]:
            return "unknown"
        item_type = self._master_record["fields"]["itemType"]["value"]
        if item_type in ITEM_TYPE_EXTENSIONS:
            return ITEM_TYPE_EXTENSIONS[item_type]
        return "unknown"

    def calculate_version_filename(
        self,
        version: AssetVersion,
        version_size: VersionSize,
        lp_filename_generator: Callable[[str], str],
        filename_override: str | None = None,
    ) -> str:
        """Calculate filename for a specific asset version."""
        return calculate_version_filename(
            self.filename,
            version,
            version_size,
            lp_filename_generator,
            self.item_type,
            filename_override,
        )

    @property
    def versions(self) -> Dict[VersionSize, AssetVersion]:
        if not self._versions:
            _versions: Dict[VersionSize, AssetVersion] = {}
            if self.item_type == AssetItemType.MOVIE:
                typed_version_lookup: Dict[VersionSize, str] = self.VIDEO_VERSION_LOOKUP
            else:
                typed_version_lookup = self.PHOTO_VERSION_LOOKUP

            # self._master_record["dummy"] ## to trigger dump

            for key, prefix in typed_version_lookup.items():
                f: Dict[str, Any] | None = None
                if f"{prefix}Res" in self._asset_record["fields"]:
                    f = self._asset_record["fields"]
                if not f and f"{prefix}Res" in self._master_record["fields"]:
                    f = self._master_record["fields"]
                if f:
                    size_entry = f.get(f"{prefix}Res")
                    if size_entry:
                        size = size_entry["value"]["size"]
                        url = size_entry["value"]["downloadURL"]
                        checksum = size_entry["value"]["fileChecksum"]
                    else:
                        raise ValueError(f"Expected {prefix}Res, but missing it")

                    type_entry = f.get(f"{prefix}FileType")
                    if type_entry:
                        asset_type = type_entry["value"]
                    else:
                        raise ValueError(f"Expected {prefix}FileType, but missing it")

                    _versions[key] = AssetVersion(size, url, asset_type, checksum)

            self._versions = _versions

        return self._versions

    def versions_with_raw_policy(
        self, raw_policy: RawTreatmentPolicy
    ) -> Dict[VersionSize, AssetVersion]:
        """
        Get asset versions with the specified raw policy applied.

        Args:
            raw_policy: The raw treatment policy to apply

        Returns:
            Dictionary of versions with raw policy applied
        """
        return apply_raw_policy(self.versions, raw_policy)

    def download(self, session: Session, url: str, start: int = 0) -> Response:
        """Download this asset using the provided session."""
        return download_asset(session, url, start)

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: id={self.id}>"
