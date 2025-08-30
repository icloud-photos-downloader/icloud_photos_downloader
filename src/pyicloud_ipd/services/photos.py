import base64
import copy
import json
import logging
import re
import sys
import typing
from datetime import datetime
from typing import Any, Callable, Dict, Generator, Sequence, Tuple, cast
from urllib.parse import urlencode

import pytz
from requests import Response
from tzlocal import get_localzone

from foundation import bytes_decode, wrap_param_in_exception
from foundation.core import compose, identity
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

logger = logging.getLogger(__name__)


class PhotoLibrary:
    """Represents a library in the user's photos.

    This provides access to all the albums as well as the photos.
    """
    WHOLE_COLLECTION = {
            "obj_type": "CPLAssetByAssetDateWithoutHiddenOrDeleted",
            "list_type": "CPLAssetAndMasterByAssetDateWithoutHiddenOrDeleted",
            "query_filter": None
        }
    RECENTLY_DELETED = {
            "obj_type": "CPLAssetDeletedByExpungedDate",
            "list_type": "CPLAssetAndMasterDeletedByExpungedDate",
            "query_filter": None
        }
    SMART_FOLDERS = {
        "Time-lapse": {
            "obj_type": "CPLAssetInSmartAlbumByAssetDate:Timelapse",
            "list_type": "CPLAssetAndMasterInSmartAlbumByAssetDate",
            "query_filter": [{
                "fieldName": "smartAlbum",
                "comparator": "EQUALS",
                "fieldValue": {
                    "type": "STRING",
                    "value": "TIMELAPSE"
                }
            }]
        },
        "Videos": {
            "obj_type": "CPLAssetInSmartAlbumByAssetDate:Video",
            "list_type": "CPLAssetAndMasterInSmartAlbumByAssetDate",
            "query_filter": [{
                "fieldName": "smartAlbum",
                "comparator": "EQUALS",
                "fieldValue": {
                    "type": "STRING",
                    "value": "VIDEO"
                }
            }]
        },
        "Slo-mo": {
            "obj_type": "CPLAssetInSmartAlbumByAssetDate:Slomo",
            "list_type": "CPLAssetAndMasterInSmartAlbumByAssetDate",
            "query_filter": [{
                "fieldName": "smartAlbum",
                "comparator": "EQUALS",
                "fieldValue": {
                    "type": "STRING",
                    "value": "SLOMO"
                }
            }]
        },
        "Bursts": {
            "obj_type": "CPLAssetBurstStackAssetByAssetDate",
            "list_type": "CPLBurstStackAssetAndMasterByAssetDate",
            "query_filter": None
        },
        "Favorites": {
            "obj_type": "CPLAssetInSmartAlbumByAssetDate:Favorite",
            "list_type": "CPLAssetAndMasterInSmartAlbumByAssetDate",
            "query_filter": [{
                "fieldName": "smartAlbum",
                "comparator": "EQUALS",
                "fieldValue": {
                    "type": "STRING",
                    "value": "FAVORITE"
                }
            }]
        },
        "Panoramas": {
            "obj_type": "CPLAssetInSmartAlbumByAssetDate:Panorama",
            "list_type": "CPLAssetAndMasterInSmartAlbumByAssetDate",
            "query_filter": [{
                "fieldName": "smartAlbum",
                "comparator": "EQUALS",
                "fieldValue": {
                    "type": "STRING",
                    "value": "PANORAMA"
                }
            }]
        },
        "Screenshots": {
            "obj_type": "CPLAssetInSmartAlbumByAssetDate:Screenshot",
            "list_type": "CPLAssetAndMasterInSmartAlbumByAssetDate",
            "query_filter": [{
                "fieldName": "smartAlbum",
                "comparator": "EQUALS",
                "fieldValue": {
                    "type": "STRING",
                    "value": "SCREENSHOT"
                }
            }]
        },
        "Live": {
            "obj_type": "CPLAssetInSmartAlbumByAssetDate:Live",
            "list_type": "CPLAssetAndMasterInSmartAlbumByAssetDate",
            "query_filter": [{
                "fieldName": "smartAlbum",
                "comparator": "EQUALS",
                "fieldValue": {
                    "type": "STRING",
                    "value": "LIVE"
                }
            }]
        },
        "Recently Deleted": RECENTLY_DELETED,
        "Hidden": {
            "obj_type": "CPLAssetHiddenByAssetDate",
            "list_type": "CPLAssetAndMasterHiddenByAssetDate",
            "query_filter": None
        },
    }

    def __init__(self, service: "PhotosService", zone_id: Dict[str, Any], library_type: str):
        self.service = service
        self.zone_id = zone_id
        self.library_type = library_type
        self.service_endpoint = self.service.get_service_endpoint(library_type)

        url = ('%s/records/query?%s' %
               (self.service_endpoint, urlencode(self.service.params)))
        json_data = json.dumps({
            "query": {"recordType":"CheckIndexingState"},
            "zoneID": self.zone_id,
        })

        request = self.service.session.post(
            url,
            data=json_data,
            headers={'Content-type': 'text/plain'}
        )
        response = request.json()
        indexing_state = response['records'][0]['fields']['state']['value']
        if indexing_state != 'FINISHED':
            raise PyiCloudServiceNotActivatedException(
                ('Apple iCloud Photo Library has not finished indexing yet'), None)

    @property
    def albums(self) -> Dict[str, "PhotoAlbum"]:
        albums = {
                name: PhotoAlbum(self.service, self.service_endpoint, name, zone_id=self.zone_id, **props) # type: ignore[arg-type] # dynamically builing params
                for (name, props) in self.SMART_FOLDERS.items()
            }

        for folder in self._fetch_folders():
            # FIXME: Handle subfolders
            if folder['recordName'] in ('----Root-Folder----',
                '----Project-Root-Folder----') or \
                (folder['fields'].get('isDeleted') and
                    folder['fields']['isDeleted']['value']):
                continue

            folder_id = folder['recordName']
            folder_obj_type = \
                "CPLContainerRelationNotDeletedByAssetDate:%s" % folder_id
            folder_name = base64.b64decode(
                folder['fields']['albumNameEnc']['value']).decode('utf-8')
            query_filter = [{
                "fieldName": "parentId",
                "comparator": "EQUALS",
                "fieldValue": {
                    "type": "STRING",
                    "value": folder_id
                }
            }]

            album = PhotoAlbum(self.service, self.service_endpoint, folder_name,
                                'CPLContainerRelationLiveByAssetDate',
                                folder_obj_type, query_filter,
                                zone_id=self.zone_id)
            albums[folder_name] = album

        return albums

    def _fetch_folders(self) -> Sequence[Dict[str, Any]]:
        if self.library_type == "shared":
            return []
        url = ('%s/records/query?%s' %
               (self.service_endpoint, urlencode(self.service.params)))
        json_data = json.dumps({
            "query": {"recordType":"CPLAlbumByPositionLive"},
            "zoneID": self.zone_id,
        })

        request = self.service.session.post(
            url,
            data=json_data,
            headers={'Content-type': 'text/plain'}
        )
        response = request.json()

        return typing.cast(Sequence[Dict[str, Any]], response['records'])

    @property
    def all(self) -> "PhotoAlbum":
        return PhotoAlbum(self.service, self.service_endpoint, "", zone_id=self.zone_id, **self.WHOLE_COLLECTION) # type: ignore[arg-type] # dynamically builing params

    @property
    def recently_deleted(self) -> "PhotoAlbum":
        return PhotoAlbum(self.service, self.service_endpoint, "", zone_id=self.zone_id, **self.RECENTLY_DELETED) # type: ignore[arg-type] # dynamically builing params

class PhotosService(PhotoLibrary):
    """The 'Photos' iCloud service.

    This also acts as a way to access the user's primary library.
    """
    def __init__(
            self, 
            service_root: str, 
            session: PyiCloudSession, 
            params: Dict[str, Any], 
            filename_cleaner:Callable[[str], str], 
            raw_policy: RawTreatmentPolicy,
            file_match_policy: FileMatchPolicy):
        self.session = session
        self.params = dict(params)
        self._service_root = service_root

        self._private_libraries: Dict[str, PhotoLibrary] | None = None
        self._shared_libraries: Dict[str, PhotoLibrary] | None = None

        self.filename_cleaner = filename_cleaner
        self.raw_policy = raw_policy
        self.file_match_policy = file_match_policy

        self.params.update({
            'remapEnums': True,
            'getCurrentSyncToken': True
        })

        # TODO: Does syncToken ever change?
        # self.params.update({
        #     'syncToken': response['syncToken'],
        #     'clientInstanceId': self.params.pop('clientId')
        # })

        # self._photo_assets = {}

        super(PhotosService, self).__init__(
            service=self, zone_id={'zoneName': 'PrimarySync'}, library_type="private")

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
            url = ('%s/zones/list' %
                (service_endpoint, ))
            request = self.session.post(
                url,
                data='{}',
                headers={'Content-type': 'text/plain'}
            )
            response = request.json()
            for zone in response['zones']:
                if not zone.get('deleted'):
                    zone_name = zone['zoneID']['zoneName']
                    libraries[zone_name] = PhotoLibrary(
                        self, zone_id=zone['zoneID'], library_type=library_type)
                        # obj_type='CPLAssetByAssetDateWithoutHiddenOrDeleted',
                        # list_type="CPLAssetAndMasterByAssetDateWithoutHiddenOrDeleted",
                        # direction="ASCENDING", query_filter=None,
                        # zone_id=zone['zoneID'])
        except Exception as e:
                logger.error("library exception: %s" % str(e))
        return libraries

    def get_service_endpoint(self, library_type: str) -> str:
        return ('%s/database/1/com.apple.photos.cloud/production/%s'
                % (self._service_root, library_type))


class PhotoAlbum:

    def __init__(self, service:PhotosService, service_endpoint: str, name: str, list_type: str, obj_type: str,
                 query_filter:Sequence[Dict[str, Any]] | None=None, page_size:int=100, zone_id:Dict[str, Any] | None=None):
        self.name = name
        self.service = service
        self.service_endpoint = service_endpoint
        self.list_type = list_type
        self.obj_type = obj_type
        self.offset = 0
        self.query_filter = query_filter
        self.page_size = page_size

        if zone_id:
            self._zone_id: Dict[str, Any] = zone_id
        else:
            self._zone_id = {'zoneName': 'PrimarySync'}

    @property
    def title(self) -> str:
        return self.name

    def __iter__(self) -> Generator["PhotoAsset", Any, None]:
        return self.photos

    def __len__(self) -> int:
        url = ('%s/internal/records/query/batch?%s' %
                (self.service_endpoint,
                urlencode(self.service.params)))
        request = self.service.session.post(
            url,
            data=json.dumps(self._count_query_gen(self.obj_type)),
            headers={'Content-type': 'text/plain'}
        )
        response = request.json()

        return int(response["batch"][0]["records"][0]["fields"]
                        ["itemCount"]["value"])

    # Perform the request in a separate method so that we
    # can mock it to test session errors.
    def photos_request(self) -> Response:
        url = ('%s/records/query?' % self.service_endpoint) + \
            urlencode(self.service.params)
        return self.service.session.post(
            url,
            data=json.dumps(self._list_query_gen(
                self.offset, self.list_type,
                self.query_filter)),
            headers={'Content-type': 'text/plain'}
        )


    @property
    def photos(self) -> Generator["PhotoAsset", Any, None]:

        while(True):
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
            for rec in response['records']:
                if rec['recordType'] == "CPLAsset":
                    master_id = \
                        rec['fields']['masterRef']['value']['recordName']
                    asset_records[master_id] = rec
                elif rec['recordType'] == "CPLMaster":
                    master_records.append(rec)

            master_records_len = len(master_records)
            if master_records_len:
                for master_record in master_records:
                    record_name = master_record['recordName']
                    yield PhotoAsset(self.service, master_record,
                                     asset_records[record_name])
                    self.increment_offset(1)
            else:
                break

    def increment_offset(self, value: int) -> None:
        self.offset += value

    def _count_query_gen(self, obj_type: str) -> Dict[str, Any]:
        query = {
            'batch': [{
                'resultsLimit': 1,
                'query': {
                    'filterBy': {
                        'fieldName': 'indexCountID',
                        'fieldValue': {
                            'type': 'STRING_LIST',
                            'value': [
                                obj_type
                            ]
                        },
                        'comparator': 'IN'
                    },
                    'recordType': 'HyperionIndexCountLookup'
                },
                'zoneWide': True,
                'zoneID': self._zone_id
            }]
        }

        return query

    def _list_query_gen(self, offset: int, list_type: str, query_filter:Sequence[Dict[str, None]] | None=None) -> Dict[str, Any]:
        query: Dict[str, Any] = {
            'query': {
                'filterBy': [
                    {'fieldName': 'startRank', 'fieldValue':
                        {'type': 'INT64', 'value': offset},
                        'comparator': 'EQUALS'},
                    {'fieldName': 'direction', 'fieldValue':
                        {'type': 'STRING', 'value': 'ASCENDING'},
                        'comparator': 'EQUALS'}
                ],
                'recordType': list_type
            },
            'resultsLimit': self.page_size * 2,
            'desiredKeys': [
                'resJPEGFullWidth', 'resJPEGFullHeight',
                'resJPEGFullFileType', 'resJPEGFullFingerprint',
                'resJPEGFullRes', 'resJPEGLargeWidth',
                'resJPEGLargeHeight', 'resJPEGLargeFileType',
                'resJPEGLargeFingerprint', 'resJPEGLargeRes',
                'resJPEGMedWidth', 'resJPEGMedHeight',
                'resJPEGMedFileType', 'resJPEGMedFingerprint',
                'resJPEGMedRes', 'resJPEGThumbWidth',
                'resJPEGThumbHeight', 'resJPEGThumbFileType',
                'resJPEGThumbFingerprint', 'resJPEGThumbRes',
                'resVidFullWidth', 'resVidFullHeight',
                'resVidFullFileType', 'resVidFullFingerprint',
                'resVidFullRes', 'resVidMedWidth', 'resVidMedHeight',
                'resVidMedFileType', 'resVidMedFingerprint',
                'resVidMedRes', 'resVidSmallWidth', 'resVidSmallHeight',
                'resVidSmallFileType', 'resVidSmallFingerprint',
                'resVidSmallRes', 'resSidecarWidth', 'resSidecarHeight',
                'resSidecarFileType', 'resSidecarFingerprint',
                'resSidecarRes', 'itemType', 'dataClassType',
                'filenameEnc', 'originalOrientation', 'resOriginalWidth',
                'resOriginalHeight', 'resOriginalFileType',
                'resOriginalFingerprint', 'resOriginalRes',
                'resOriginalAltWidth', 'resOriginalAltHeight',
                'resOriginalAltFileType', 'resOriginalAltFingerprint',
                'resOriginalAltRes', 'resOriginalVidComplWidth',
                'resOriginalVidComplHeight', 'resOriginalVidComplFileType',
                'resOriginalVidComplFingerprint', 'resOriginalVidComplRes',
                'isDeleted', 'isExpunged', 'dateExpunged', 'remappedRef',
                'recordName', 'recordType', 'recordChangeTag',
                'masterRef', 'adjustmentRenderType', 'assetDate',
                'addedDate', 'isFavorite', 'isHidden', 'orientation',
                'duration', 'assetSubtype', 'assetSubtypeV2',
                'assetHDRType', 'burstFlags', 'burstFlagsExt', 'burstId',
                'captionEnc', 'locationEnc', 'locationV2Enc',
                'locationLatitude', 'locationLongitude', 'adjustmentType',
                'timeZoneOffset', 'vidComplDurValue', 'vidComplDurScale',
                'vidComplDispValue', 'vidComplDispScale',
                'keywordsEnc','extendedDescEnc','adjustedMediaMetaDataEnc','adjustmentSimpleDataEnc',
                'vidComplVisibilityState', 'customRenderedValue',
                'containerId', 'itemId', 'position', 'isKeyAsset'
            ],
            'zoneID': self._zone_id
        }

        if query_filter:
            query['query']['filterBy'].extend(query_filter)

        return query

    def __unicode__(self) -> str:
        return self.title

    def __str__(self) -> str:
        as_unicode = self.__unicode__()
        if sys.version_info[0] >= 3:
            return as_unicode
        else:
            return as_unicode.encode('ascii', 'ignore')

    def __repr__(self) -> str:
        return "<%s: '%s'>" % (
            type(self).__name__,
            self
        )


class PhotoAsset:
    def __init__(self, service:PhotosService, master_record: Dict[str, Any], asset_record: Dict[str, Any]) -> None:
        self._service = service
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
        'com.canon.crw-raw-image': AssetItemType.IMAGE,
        'com.sony.arw-raw-image': AssetItemType.IMAGE,
        'com.fuji.raw-image': AssetItemType.IMAGE,
        'com.panasonic.rw2-raw-image': AssetItemType.IMAGE,
        'com.nikon.nrw-raw-image': AssetItemType.IMAGE,
        'com.pentax.raw-image': AssetItemType.IMAGE,
        'com.nikon.raw-image': AssetItemType.IMAGE,
        'com.olympus.raw-image': AssetItemType.IMAGE,
        'com.canon.cr3-raw-image': AssetItemType.IMAGE,
        'com.olympus.or-raw-image': AssetItemType.IMAGE,
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
        AssetVersionSize.THUMB: "resVidSmall"
    }


    @property
    def id(self) -> str:
        return typing.cast(str, self._master_record['recordName'])

    @property
    def filename(self) -> str:
        fields = self._master_record['fields']
        if 'filenameEnc' in fields:
            filename_enc: Dict[str, Any] = fields['filenameEnc']
            def _get_value(input: Dict[str, Any]) -> str:
                return cast(str,input['value'])
            def _get_type(input: Dict[str, Any]) -> str:
                return cast(str, input['type'])
            
            def _match_type(string_parser: Callable[[str], str], base64_parser: Callable[[str], str]) -> Callable[[str], Callable[[str], str]]:
                def _internal(type:str) -> Callable[[str], str]:
                    if type == "STRING":
                        return string_parser
                    elif type == "ENCRYPTED_BYTES":
                        return base64_parser
                    else:
                        raise ValueError(f"Unsupported filename encoding {type}")
                return _internal

            parse_base64_value = compose(
                bytes_decode('utf-8'), 
                base64.b64decode,
            )
            
            parser_selector = compose(
                _match_type(identity, parse_base64_value),
                _get_type
            )

            type_parser = wrap_param_in_exception("Parsing filenameEnc type", parser_selector)

            _value_parser = type_parser(filename_enc)

            parse_and_clean = compose(
                self._service.filename_cleaner,
                _value_parser
            )

            extract_value_and_parse = compose(
                parse_and_clean,
                _get_value,
            )
            parser = wrap_param_in_exception("Parsing filenameEnc", extract_value_and_parse)

            _filename = parser(filename_enc)

            # _filename = self._service.filename_cleaner(base64.b64decode(
            #     fields['filenameEnc']['value']
            # ).decode('utf-8'))
            
            if self._service.file_match_policy == FileMatchPolicy.NAME_ID7:
                _a = base64.b64encode(self.id.encode('utf-8')).decode('ascii')[0:7]
                _filename = add_suffix_to_filename(f"_{_a}", _filename)
            return _filename

        # Some photos don't have a filename.
        # In that case, just use the truncated fingerprint (hash),
        # plus the correct extension.
        filename = re.sub('[^0-9a-zA-Z]', '_', self.id)[0:12]
        return '.'.join([filename, self.item_type_extension])

    @property
    def size(self) -> int:
        return typing.cast(int, self._master_record['fields']['resOriginalRes']['value']['size'])

    @property
    def created(self) -> datetime:
        try:
            created_date = self.asset_date.astimezone(get_localzone())
        except (ValueError, OSError):
            logger.error("Could not convert photo created date to local timezone (%s)", self.asset_date)
            created_date = self.asset_date

        return created_date

    @property
    def asset_date(self) -> datetime:
        try:
            dt = datetime.fromtimestamp(
                self._asset_record['fields']['assetDate']['value'] / 1000.0,
                tz=pytz.utc)
        except:
            dt = datetime.fromtimestamp(0)
        return dt

    @property
    def added_date(self) -> datetime:
        dt = datetime.fromtimestamp(
            self._asset_record['fields']['addedDate']['value'] / 1000.0,
            tz=pytz.utc)
        return dt

    @property
    def dimensions(self) -> Tuple[int, int]:
        return (self._master_record['fields']['resOriginalWidth']['value'],
                self._master_record['fields']['resOriginalHeight']['value'])

    @property
    def item_type(self) -> AssetItemType | None:
        fields = self._master_record['fields']
        if 'itemType' not in fields:
            # raise ValueError(f"Cannot find itemType in {fields!r}")
            return None
        item_type_field = fields['itemType']
        if 'value' not in item_type_field:
            # raise ValueError(f"Cannot find value in itemType {item_type_field!r}")
            return None
        item_type = item_type_field['value']
        if item_type in self.ITEM_TYPES:
            return self.ITEM_TYPES[item_type]
        if self.filename.lower().endswith(('.heic', '.png', '.jpg', '.jpeg')):
            return AssetItemType.IMAGE
        return AssetItemType.MOVIE

    @property
    def item_type_extension(self) -> str:
        fields = self._master_record['fields']
        if 'itemType' not in fields or 'value' not in fields['itemType']:
            return 'unknown'
        item_type = self._master_record['fields']['itemType']['value']
        if item_type in ITEM_TYPE_EXTENSIONS:
            return ITEM_TYPE_EXTENSIONS[item_type]
        return 'unknown'

    def calculate_version_filename(self, version: AssetVersion, version_size: VersionSize, lp_filename_generator: Callable[[str], str], filename_override: str | None = None) -> str:
        """Calculate filename for a specific asset version."""
        return calculate_version_filename(
            self.filename,
            version,
            version_size, 
            lp_filename_generator,
            self.item_type,
            filename_override
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
                if '%sRes' % prefix in self._asset_record['fields']:
                    f = self._asset_record['fields']
                if not f and '%sRes' % prefix in self._master_record['fields']:
                    f = self._master_record['fields']
                if f:
                    size_entry = f.get('%sRes' % prefix)
                    if size_entry:
                        size = size_entry['value']['size']
                        url = size_entry['value']['downloadURL']
                        checksum = size_entry['value']['fileChecksum']
                    else:
                        raise ValueError(f"Expected {prefix}Res, but missing it")

                    type_entry = f.get('%sFileType' % prefix)
                    if type_entry:
                        asset_type = type_entry['value']
                    else:
                        raise ValueError(f"Expected {prefix}FileType, but missing it")

                    _versions[key] = AssetVersion(size, url, asset_type, checksum)

            # swap original & alternative according to swap_raw_policy
            if AssetVersionSize.ALTERNATIVE in _versions and (("raw" in _versions[AssetVersionSize.ALTERNATIVE].type and self._service.raw_policy == RawTreatmentPolicy.AS_ORIGINAL) or ("raw" in _versions[AssetVersionSize.ORIGINAL].type and self._service.raw_policy == RawTreatmentPolicy.AS_ALTERNATIVE)):
                _a = copy.copy(_versions[AssetVersionSize.ALTERNATIVE])
                _o = copy.copy(_versions[AssetVersionSize.ORIGINAL])
                _versions[AssetVersionSize.ALTERNATIVE] = _o
                _versions[AssetVersionSize.ORIGINAL] = _a

            self._versions = _versions

        return self._versions

    def download(self, url: str, start:int = 0) -> Response:
        headers = {
            "Range": f"bytes={start}-"
        }
        return self._service.session.get(
            url,
            headers=headers,
            stream=True
        )

    def __repr__(self) -> str:
        return "<%s: id=%s>" % (
            type(self).__name__,
            self.id
        )
