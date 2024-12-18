import copy
import os
import sys
import json
import logging
import base64
import re

from datetime import datetime
from typing import Any, Callable, Dict, Generator, Optional, Sequence, Tuple, TypeVar, Union, cast
import typing

from requests import Response
from foundation import wrap_param_in_exception, bytes_decode
from foundation.core import compose, identity
from pyicloud_ipd.asset_version import AssetVersion
from pyicloud_ipd.exceptions import PyiCloudServiceNotActivatedException
from pyicloud_ipd.exceptions import PyiCloudAPIResponseException

import pytz

from urllib.parse import urlencode

from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.item_type import AssetItemType
from pyicloud_ipd.raw_policy import RawTreatmentPolicy
from pyicloud_ipd.session import PyiCloudSession
from pyicloud_ipd.utils import add_suffix_to_filename
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize, VersionSize

logger = logging.getLogger(__name__)


class PhotoLibrary(object):
    """Represents a library in the user's photos.

    This provides access to all the albums as well as the photos.
    """
    SMART_FOLDERS = {
        "All Photos": {
            "obj_type": "CPLAssetByAssetDateWithoutHiddenOrDeleted",
            "list_type": "CPLAssetAndMasterByAssetDateWithoutHiddenOrDeleted",
            "direction": "ASCENDING",
            "query_filter": None
        },
        "Time-lapse": {
            "obj_type": "CPLAssetInSmartAlbumByAssetDate:Timelapse",
            "list_type": "CPLAssetAndMasterInSmartAlbumByAssetDate",
            "direction": "ASCENDING",
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
            "direction": "ASCENDING",
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
            "direction": "ASCENDING",
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
            "direction": "ASCENDING",
            "query_filter": None
        },
        "Favorites": {
            "obj_type": "CPLAssetInSmartAlbumByAssetDate:Favorite",
            "list_type": "CPLAssetAndMasterInSmartAlbumByAssetDate",
            "direction": "ASCENDING",
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
            "direction": "ASCENDING",
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
            "direction": "ASCENDING",
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
            "direction": "ASCENDING",
            "query_filter": [{
                "fieldName": "smartAlbum",
                "comparator": "EQUALS",
                "fieldValue": {
                    "type": "STRING",
                    "value": "LIVE"
                }
            }]
        },
        "Recently Deleted": {
            "obj_type": "CPLAssetDeletedByExpungedDate",
            "list_type": "CPLAssetAndMasterDeletedByExpungedDate",
            "direction": "ASCENDING",
            "query_filter": None
        },
        "Hidden": {
            "obj_type": "CPLAssetHiddenByAssetDate",
            "list_type": "CPLAssetAndMasterHiddenByAssetDate",
            "direction": "ASCENDING",
            "query_filter": None
        },
    }

    def __init__(self, service: "PhotosService", zone_id: Dict[str, Any]):
        self.service = service
        self.zone_id = zone_id

        self._albums: Optional[Dict[str, PhotoAlbum]] = None

        url = ('%s/records/query?%s' %
               (self.service._service_endpoint, urlencode(self.service.params)))
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
                ('iCloud Photo Library not finished indexing.  Please try '
                 'again in a few minutes'), None)

    @property
    def albums(self) -> Dict[str, "PhotoAlbum"]:
        if not self._albums:
            self._albums = {
                name: PhotoAlbum(self.service, name, zone_id=self.zone_id, **props) # type: ignore[arg-type] # dynamically builing params 
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

                album = PhotoAlbum(self.service, folder_name,
                                   'CPLContainerRelationLiveByAssetDate',
                                   folder_obj_type, 'ASCENDING', query_filter,
                                   zone_id=self.zone_id)
                self._albums[folder_name] = album

        return self._albums

    def _fetch_folders(self) -> Sequence[Dict[str, Any]]:
        url = ('%s/records/query?%s' %
               (self.service._service_endpoint, urlencode(self.service.params)))
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
        return self.albums['All Photos']


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
            lp_filename_generator: Callable[[str], str], 
            raw_policy: RawTreatmentPolicy,
            file_match_policy: FileMatchPolicy):
        self.session = session
        self.params = dict(params)
        self._service_root = service_root
        self._service_endpoint = \
            ('%s/database/1/com.apple.photos.cloud/production/private'
             % self._service_root)

        self._libraries: Optional[Dict[str, PhotoLibrary]] = None

        self.filename_cleaner = filename_cleaner
        self.lp_filename_generator = lp_filename_generator
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
            service=self, zone_id={u'zoneName': u'PrimarySync'})

    @property
    def libraries(self) -> Dict[str, PhotoLibrary]:
        if not self._libraries:
            try:
                url = ('%s/zones/list' %
                    (self._service_endpoint, ))
                request = self.session.post(
                    url,
                    data='{}',
                    headers={'Content-type': 'text/plain'}
                )
                response = request.json()
                zones = response['zones'] 
            except Exception as e:
                    logger.error("library exception: %s" % str(e))

            libraries = {}
            for zone in zones:
                if not zone.get('deleted'):
                    zone_name = zone['zoneID']['zoneName']
                    libraries[zone_name] = PhotoLibrary(
                        self, zone_id=zone['zoneID'])
                        # obj_type='CPLAssetByAssetDateWithoutHiddenOrDeleted',
                        # list_type="CPLAssetAndMasterByAssetDateWithoutHiddenOrDeleted",
                        # direction="ASCENDING", query_filter=None,
                        # zone_id=zone['zoneID'])

            self._libraries = libraries

        return self._libraries


class PhotoAlbum(object):

    def __init__(self, service:PhotosService, name: str, list_type: str, obj_type: str, direction: str,
                 query_filter:Optional[Sequence[Dict[str, Any]]]=None, page_size:int=100, zone_id:Optional[Dict[str, Any]]=None):
        self.name = name
        self.service = service
        self.list_type = list_type
        self.obj_type = obj_type
        self.direction = direction
        self.query_filter = query_filter
        self.page_size = page_size
        self.exception_handler: Optional[Callable[[Exception, int], None]] = None

        self._len: Optional[int] = None

        if zone_id:
            self._zone_id: Dict[str, Any] = zone_id
        else:
            self._zone_id = {u'zoneName': u'PrimarySync'}

    @property
    def title(self) -> str:
        return self.name

    def __iter__(self) -> Generator["PhotoAsset", Any, None]:
        return self.photos

    def __len__(self) -> int:
        if self._len is None:
            url = ('%s/internal/records/query/batch?%s' %
                   (self.service._service_endpoint,
                    urlencode(self.service.params)))
            request = self.service.session.post(
                url,
                data=json.dumps(self._count_query_gen(self.obj_type)),
                headers={'Content-type': 'text/plain'}
            )
            response = request.json()

            self._len = (response["batch"][0]["records"][0]["fields"]
                         ["itemCount"]["value"])

        return self._len

    # Perform the request in a separate method so that we
    # can mock it to test session errors.
    def photos_request(self, offset: int) -> Response:
        url = ('%s/records/query?' % self.service._service_endpoint) + \
            urlencode(self.service.params)
        return self.service.session.post(
            url,
            data=json.dumps(self._list_query_gen(
                offset, self.list_type, self.direction,
                self.query_filter)),
            headers={'Content-type': 'text/plain'}
        )


    @property
    def photos(self) -> Generator["PhotoAsset", Any, None]:
        if self.direction == "DESCENDING":
            offset = len(self) - 1
        else:
            offset = 0

        exception_retries = 0

        while(True):
            try:
                request = self.photos_request(offset)
            except PyiCloudAPIResponseException as ex:
                if self.exception_handler:
                    exception_retries += 1
                    self.exception_handler(ex, exception_retries)
                    if exception_retries > 5:
                        raise
                    continue
                else:
                    raise

            exception_retries = 0

#            url = ('%s/records/query?' % self.service._service_endpoint) + \
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
                if self.direction == "DESCENDING":
                    offset = offset - master_records_len
                else:
                    offset = offset + master_records_len

                for master_record in master_records:
                    record_name = master_record['recordName']
                    yield PhotoAsset(self.service, master_record,
                                     asset_records[record_name])
            else:
                break

    def _count_query_gen(self, obj_type: str) -> Dict[str, Any]:
        query = {
            u'batch': [{
                u'resultsLimit': 1,
                u'query': {
                    u'filterBy': {
                        u'fieldName': u'indexCountID',
                        u'fieldValue': {
                            u'type': u'STRING_LIST',
                            u'value': [
                                obj_type
                            ]
                        },
                        u'comparator': u'IN'
                    },
                    u'recordType': u'HyperionIndexCountLookup'
                },
                u'zoneWide': True,
                u'zoneID': self._zone_id
            }]
        }

        return query

    def _list_query_gen(self, offset: int, list_type: str, direction: str, query_filter:Optional[Sequence[Dict[str,None]]]=None) -> Dict[str, Any]:
        query: Dict[str, Any] = {
            u'query': {
                u'filterBy': [
                    {u'fieldName': u'startRank', u'fieldValue':
                        {u'type': u'INT64', u'value': offset},
                        u'comparator': u'EQUALS'},
                    {u'fieldName': u'direction', u'fieldValue':
                        {u'type': u'STRING', u'value': direction},
                        u'comparator': u'EQUALS'}
                ],
                u'recordType': list_type
            },
            u'resultsLimit': self.page_size * 2,
            u'desiredKeys': [
                u'resJPEGFullWidth', u'resJPEGFullHeight',
                u'resJPEGFullFileType', u'resJPEGFullFingerprint',
                u'resJPEGFullRes', u'resJPEGLargeWidth',
                u'resJPEGLargeHeight', u'resJPEGLargeFileType',
                u'resJPEGLargeFingerprint', u'resJPEGLargeRes',
                u'resJPEGMedWidth', u'resJPEGMedHeight',
                u'resJPEGMedFileType', u'resJPEGMedFingerprint',
                u'resJPEGMedRes', u'resJPEGThumbWidth',
                u'resJPEGThumbHeight', u'resJPEGThumbFileType',
                u'resJPEGThumbFingerprint', u'resJPEGThumbRes',
                u'resVidFullWidth', u'resVidFullHeight',
                u'resVidFullFileType', u'resVidFullFingerprint',
                u'resVidFullRes', u'resVidMedWidth', u'resVidMedHeight',
                u'resVidMedFileType', u'resVidMedFingerprint',
                u'resVidMedRes', u'resVidSmallWidth', u'resVidSmallHeight',
                u'resVidSmallFileType', u'resVidSmallFingerprint',
                u'resVidSmallRes', u'resSidecarWidth', u'resSidecarHeight',
                u'resSidecarFileType', u'resSidecarFingerprint',
                u'resSidecarRes', u'itemType', u'dataClassType',
                u'filenameEnc', u'originalOrientation', u'resOriginalWidth',
                u'resOriginalHeight', u'resOriginalFileType',
                u'resOriginalFingerprint', u'resOriginalRes',
                u'resOriginalAltWidth', u'resOriginalAltHeight',
                u'resOriginalAltFileType', u'resOriginalAltFingerprint',
                u'resOriginalAltRes', u'resOriginalVidComplWidth',
                u'resOriginalVidComplHeight', u'resOriginalVidComplFileType',
                u'resOriginalVidComplFingerprint', u'resOriginalVidComplRes',
                u'isDeleted', u'isExpunged', u'dateExpunged', u'remappedRef',
                u'recordName', u'recordType', u'recordChangeTag',
                u'masterRef', u'adjustmentRenderType', u'assetDate',
                u'addedDate', u'isFavorite', u'isHidden', u'orientation',
                u'duration', u'assetSubtype', u'assetSubtypeV2',
                u'assetHDRType', u'burstFlags', u'burstFlagsExt', u'burstId',
                u'captionEnc', u'locationEnc', u'locationV2Enc',
                u'locationLatitude', u'locationLongitude', u'adjustmentType',
                u'timeZoneOffset', u'vidComplDurValue', u'vidComplDurScale',
                u'vidComplDispValue', u'vidComplDispScale',
                u'keywordsEnc',u'extendedDescEnc',u'adjustedMediaMetaDataEnc',u'adjustmentSimpleDataEnc',
                u'vidComplVisibilityState', u'customRenderedValue',
                u'containerId', u'itemId', u'position', u'isKeyAsset'
            ],
            u'zoneID': self._zone_id
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


class PhotoAsset(object):
    def __init__(self, service:PhotosService, master_record: Dict[str, Any], asset_record: Dict[str, Any]) -> None:
        self._service = service
        self._master_record = master_record
        self._asset_record = asset_record

        self._versions: Optional[Dict[VersionSize, AssetVersion]] = None

    ITEM_TYPES = {
        u"public.heic": AssetItemType.IMAGE,
        u"public.jpeg": AssetItemType.IMAGE,
        u"public.png": AssetItemType.IMAGE,
        u"com.apple.quicktime-movie": AssetItemType.MOVIE,
        u"com.adobe.raw-image": AssetItemType.IMAGE,
        u"com.canon.cr2-raw-image": AssetItemType.IMAGE,
        u'com.canon.crw-raw-image': AssetItemType.IMAGE,
        u'com.sony.arw-raw-image': AssetItemType.IMAGE,
        u'com.fuji.raw-image': AssetItemType.IMAGE,
        u'com.panasonic.rw2-raw-image': AssetItemType.IMAGE,
        u'com.nikon.nrw-raw-image': AssetItemType.IMAGE,
        u'com.pentax.raw-image': AssetItemType.IMAGE,
        u'com.nikon.raw-image': AssetItemType.IMAGE,
        u'com.olympus.raw-image': AssetItemType.IMAGE,
        u'com.canon.cr3-raw-image': AssetItemType.IMAGE,
        u'com.olympus.or-raw-image': AssetItemType.IMAGE,
    }

    ITEM_TYPE_EXTENSIONS = {
        u"public.heic": u"HEIC",
        u"public.jpeg": u"JPG",
        u"public.png": u"PNG",
        u"com.apple.quicktime-movie": u"MOV",
        u"com.adobe.raw-image": u"DNG",
        u"com.canon.cr2-raw-image": u"CR2",
        u'com.canon.crw-raw-image': u"CRW",
        u'com.sony.arw-raw-image': u"ARW",
        u'com.fuji.raw-image': u"RAF",
        u'com.panasonic.rw2-raw-image': u"RW2",
        u'com.nikon.nrw-raw-image': u"NRF",
        u'com.pentax.raw-image': u"PEF",
        u'com.nikon.raw-image': u"NEF",
        u'com.olympus.raw-image': u"ORF",
        u'com.canon.cr3-raw-image': u"CR3",
        u'com.olympus.or-raw-image': u"ORF",
    }

    PHOTO_VERSION_LOOKUP: Dict[VersionSize, str] = {
        AssetVersionSize.ORIGINAL: u"resOriginal",
        AssetVersionSize.ALTERNATIVE: u"resOriginalAlt",
        AssetVersionSize.MEDIUM: u"resJPEGMed",
        AssetVersionSize.THUMB: u"resJPEGThumb",
        AssetVersionSize.ADJUSTED: u"resJPEGFull",
        LivePhotoVersionSize.ORIGINAL: u"resOriginalVidCompl",
        LivePhotoVersionSize.MEDIUM: u"resVidMed",
        LivePhotoVersionSize.THUMB: u"resVidSmall",
    }

    VIDEO_VERSION_LOOKUP: Dict[VersionSize, str] = {
        AssetVersionSize.ORIGINAL: u"resOriginal",
        AssetVersionSize.MEDIUM: u"resVidMed",
        AssetVersionSize.THUMB: u"resVidSmall"
    }

    VERSION_FILENAME_SUFFIX_LOOKUP: Dict[VersionSize, str] = {
        AssetVersionSize.MEDIUM: u"medium",
        AssetVersionSize.THUMB: u"thumb",
        # LivePhotoVersionSize.MEDIUM: u"medium",
        # LivePhotoVersionSize.THUMB: u"thumb",
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
        return self.asset_date

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
    def item_type(self) -> Optional[AssetItemType]:
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
        if item_type in self.ITEM_TYPE_EXTENSIONS:
            return self.ITEM_TYPE_EXTENSIONS[item_type]
        return 'unknown'

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
                f: Optional[Dict[str, Any]] = None
                if '%sRes' % prefix in self._asset_record['fields']:
                    f = self._asset_record['fields']
                if not f and '%sRes' % prefix in self._master_record['fields']:
                    f = self._master_record['fields']
                if f:
                    version: Dict[str, Any] = {'filename': self.filename}

                    # width_entry = f.get('%sWidth' % prefix)
                    # if width_entry:
                    #     version['width'] = width_entry['value']
                    # else:
                    #     version['width'] = None

                    # height_entry = f.get('%sHeight' % prefix)
                    # if height_entry:
                    #     version['height'] = height_entry['value']
                    # else:
                    #     version['height'] = None

                    size_entry = f.get('%sRes' % prefix)
                    if size_entry:
                        version['size'] = size_entry['value']['size']
                        version['url'] = size_entry['value']['downloadURL']
                    else:
                        raise ValueError(f"Expected {prefix}Res, but missing it")
                        # version['size'] = None
                        # version['url'] = None

                    type_entry = f.get('%sFileType' % prefix)
                    if type_entry:
                        version['type'] = type_entry['value']
                    else:
                        raise ValueError(f"Expected {prefix}FileType, but missing it")
                        # version['type'] = None

                    # Change live photo movie file extension to .MOV
                    if ((self.item_type or AssetItemType.IMAGE) == AssetItemType.IMAGE and
                        version['type'] == "com.apple.quicktime-movie"):
                        version['filename'] = self._service.lp_filename_generator(self.filename) # without size
                    else:
                        # for non live photo movie, try to change file type to match asset type
                        _f, _e = os.path.splitext(version["filename"])
                        version["filename"] = _f + "." + self.ITEM_TYPE_EXTENSIONS.get(version["type"], _e[1:])

                    # add size suffix
                    if key in self.VERSION_FILENAME_SUFFIX_LOOKUP:
                        _size_suffix = self.VERSION_FILENAME_SUFFIX_LOOKUP[key]
                        version["filename"] = add_suffix_to_filename(f"-{_size_suffix}", version["filename"])

                    _versions[key] = AssetVersion(version["filename"], version['size'], version['url'], version['type'])

            # swap original & alternative according to swap_raw_policy
            if AssetVersionSize.ALTERNATIVE in _versions and (("raw" in _versions[AssetVersionSize.ALTERNATIVE].type and self._service.raw_policy == RawTreatmentPolicy.AS_ORIGINAL) or ("raw" in _versions[AssetVersionSize.ORIGINAL].type and self._service.raw_policy == RawTreatmentPolicy.AS_ALTERNATIVE)):
                _a = copy.copy(_versions[AssetVersionSize.ALTERNATIVE])
                _o = copy.copy(_versions[AssetVersionSize.ORIGINAL])
                _versions[AssetVersionSize.ALTERNATIVE] = _o
                _versions[AssetVersionSize.ORIGINAL] = _a

            self._versions = _versions

        return self._versions

    def download(self, url: str) -> Response:
        return self._service.session.get(
            url,
            stream=True
        )

    def __repr__(self) -> str:
        return "<%s: id=%s>" % (
            type(self).__name__,
            self.id
        )
