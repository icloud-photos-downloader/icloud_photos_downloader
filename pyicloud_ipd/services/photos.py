import sys
import json
import logging
import base64
import re

from datetime import datetime
from pyicloud_ipd.exceptions import PyiCloudServiceNotActivatedErrror
from pyicloud_ipd.exceptions import PyiCloudAPIResponseError

import pytz

from future.moves.urllib.parse import urlencode

logger = logging.getLogger(__name__)


class PhotosService(object):
    """ The 'Photos' iCloud service."""
    SMART_FOLDERS = {
        "All Photos": {
            "obj_type": "CPLAssetByAddedDate",
            "list_type": "CPLAssetAndMasterByAddedDate",
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

    def __init__(self, service_root, session, params):
        self.session = session
        self.params = dict(params)
        self._service_root = service_root
        self._service_endpoint = \
            ('%s/database/1/com.apple.photos.cloud/production/private'
             % self._service_root)

        self._albums = None

        self.params.update({
            'remapEnums': True,
            'getCurrentSyncToken': True
        })

        url = ('%s/records/query?%s' %
               (self._service_endpoint, urlencode(self.params)))
        json_data = ('{"query":{"recordType":"CheckIndexingState"},'
                     '"zoneID":{"zoneName":"PrimarySync"}}')
        request = self.session.post(
            url,
            data=json_data,
            headers={'Content-type': 'text/plain'}
        )
        response = request.json()
        indexing_state = response['records'][0]['fields']['state']['value']
        if indexing_state != 'FINISHED':
            raise PyiCloudServiceNotActivatedErrror(
                ('iCloud Photo Library not finished indexing.  Please try '
                 'again in a few minutes'), None)

        # TODO: Does syncToken ever change?
        # self.params.update({
        #     'syncToken': response['syncToken'],
        #     'clientInstanceId': self.params.pop('clientId')
        # })

        self._photo_assets = {}

    @property
    def albums(self):
        if not self._albums:
            self._albums = {name: PhotoAlbum(self, name, **props)
                            for (name, props) in self.SMART_FOLDERS.items()}

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

                album = PhotoAlbum(self, folder_name,
                                   'CPLContainerRelationLiveByAssetDate',
                                   folder_obj_type, 'ASCENDING', query_filter)
                self._albums[folder_name] = album

        return self._albums

    def _fetch_folders(self):
        url = ('%s/records/query?%s' %
               (self._service_endpoint, urlencode(self.params)))
        json_data = ('{"query":{"recordType":"CPLAlbumByPositionLive"},'
                     '"zoneID":{"zoneName":"PrimarySync"}}')

        request = self.session.post(
            url,
            data=json_data,
            headers={'Content-type': 'text/plain'}
        )
        response = request.json()

        return response['records']

    @property
    def all(self):
        return self.albums['All Photos']


class PhotoAlbum(object):

    def __init__(self, service, name, list_type, obj_type, direction,
                 query_filter=None, page_size=100):
        self.name = name
        self.service = service
        self.list_type = list_type
        self.obj_type = obj_type
        self.direction = direction
        self.query_filter = query_filter
        self.page_size = page_size
        self.exception_handler = None

        self._len = None

    @property
    def title(self):
        return self.name

    def __iter__(self):
        return self.photos

    def __len__(self):
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
    def photos_request(self, offset):
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
    def photos(self):
        if self.direction == "DESCENDING":
            offset = len(self) - 1
        else:
            offset = 0

        exception_retries = 0

        while(True):
            try:
                request = self.photos_request(offset)
            except PyiCloudAPIResponseError as ex:
                if self.exception_handler:
                    exception_retries += 1
                    self.exception_handler(ex, exception_retries)
                    continue
                else:
                    raise

            exception_retries = 0
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

    def _count_query_gen(self, obj_type):
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
                u'zoneID': {
                    u'zoneName': u'PrimarySync'
                }
            }]
        }

        return query

    def _list_query_gen(self, offset, list_type, direction, query_filter=None):
        query = {
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
                u'vidComplVisibilityState', u'customRenderedValue',
                u'containerId', u'itemId', u'position', u'isKeyAsset'
            ],
            u'zoneID': {u'zoneName': u'PrimarySync'}
        }

        if query_filter:
            query['query']['filterBy'].extend(query_filter)

        return query

    def __unicode__(self):
        return self.title

    def __str__(self):
        as_unicode = self.__unicode__()
        if sys.version_info[0] >= 3:
            return as_unicode
        else:
            return as_unicode.encode('utf-8', 'ignore')

    def __repr__(self):
        return "<%s: '%s'>" % (
            type(self).__name__,
            self
        )


class PhotoAsset(object):
    def __init__(self, service, master_record, asset_record):
        self._service = service
        self._master_record = master_record
        self._asset_record = asset_record

        self._versions = None

    ITEM_TYPES = {
        u"public.heic": u"image",
        u"public.jpeg": u"image",
        u"public.png": u"image",
        u"com.apple.quicktime-movie": u"movie"
    }

    ITEM_TYPE_EXTENSIONS = {
        u"public.heic": u"HEIC",
        u"public.jpeg": u"JPG",
        u"public.png": u"PNG",
        u"com.apple.quicktime-movie": u"MOV"
    }

    PHOTO_VERSION_LOOKUP = {
        u"original": u"resOriginal",
        u"medium": u"resJPEGMed",
        u"thumb": u"resJPEGThumb",
        u"originalVideo": u"resOriginalVidCompl",
        u"mediumVideo": u"resVidMed",
        u"thumbVideo": u"resVidSmall",
    }

    VIDEO_VERSION_LOOKUP = {
        u"original": u"resOriginal",
        u"medium": u"resVidMed",
        u"thumb": u"resVidSmall"
    }

    @property
    def id(self):
        return self._master_record['recordName']

    @property
    def filename(self):
        fields = self._master_record['fields']
        if 'filenameEnc' in fields and 'value' in fields['filenameEnc']:
            return base64.b64decode(
                fields['filenameEnc']['value']
            ).decode('utf-8')

        # Some photos don't have a filename.
        # In that case, just use the truncated fingerprint (hash),
        # plus the correct extension.
        filename = re.sub('[^0-9a-zA-Z]', '_', self.id)[0:12]
        return '.'.join([filename, self.item_type_extension])

    @property
    def size(self):
        return self._master_record['fields']['resOriginalRes']['value']['size']

    @property
    def created(self):
        return self.asset_date

    @property
    def asset_date(self):
        try:
            dt = datetime.fromtimestamp(
                self._asset_record['fields']['assetDate']['value'] / 1000.0,
                tz=pytz.utc)
        except:
            dt = datetime.fromtimestamp(0)
        return dt

    @property
    def added_date(self):
        dt = datetime.fromtimestamp(
            self._asset_record['fields']['addedDate']['value'] / 1000.0,
            tz=pytz.utc)
        return dt

    @property
    def dimensions(self):
        return (self._master_record['fields']['resOriginalWidth']['value'],
                self._master_record['fields']['resOriginalHeight']['value'])

    @property
    def item_type(self):
        fields = self._master_record['fields']
        if 'itemType' not in fields or 'value' not in fields['itemType']:
            return 'unknown'
        item_type = self._master_record['fields']['itemType']['value']
        if item_type in self.ITEM_TYPES:
            return self.ITEM_TYPES[item_type]
        if self.filename.lower().endswith(('.heic', '.png', '.jpg', '.jpeg')):
            return 'image'
        return 'movie'

    @property
    def item_type_extension(self):
        fields = self._master_record['fields']
        if 'itemType' not in fields or 'value' not in fields['itemType']:
            return 'unknown'
        item_type = self._master_record['fields']['itemType']['value']
        if item_type in self.ITEM_TYPE_EXTENSIONS:
            return self.ITEM_TYPE_EXTENSIONS[item_type]
        return 'unknown'

    @property
    def versions(self):
        if not self._versions:
            self._versions = {}
            if self.item_type == "movie":
                typed_version_lookup = self.VIDEO_VERSION_LOOKUP
            else:
                typed_version_lookup = self.PHOTO_VERSION_LOOKUP

            for key, prefix in typed_version_lookup.items():
                if '%sRes' % prefix in self._master_record['fields']:
                    f = self._master_record['fields']
                    filename = self.filename
                    version = {'filename': filename}

                    width_entry = f.get('%sWidth' % prefix)
                    if width_entry:
                        version['width'] = width_entry['value']
                    else:
                        version['width'] = None

                    height_entry = f.get('%sHeight' % prefix)
                    if height_entry:
                        version['height'] = height_entry['value']
                    else:
                        version['height'] = None

                    size_entry = f.get('%sRes' % prefix)
                    if size_entry:
                        version['size'] = size_entry['value']['size']
                        version['url'] = size_entry['value']['downloadURL']
                    else:
                        version['size'] = None
                        version['url'] = None

                    type_entry = f.get('%sFileType' % prefix)
                    if type_entry:
                        version['type'] = type_entry['value']
                    else:
                        version['type'] = None

                    # Change live photo movie file extension to .MOV
                    if (self.item_type == "image" and
                        version['type'] == "com.apple.quicktime-movie"):
                        if filename.lower().endswith('.heic'):
                            version['filename']=re.sub(
                                '\.[^.]+$', '_HEVC.MOV', version['filename'])
                        else:
                            version['filename'] = re.sub(
                                '\.[^.]+$', '.MOV', version['filename'])

                    self._versions[key] = version

        return self._versions

    def download(self, version='original', **kwargs):
        if version not in self.versions:
            return None

        return self._service.session.get(
            self.versions[version]['url'],
            stream=True,
            **kwargs
        )

    def __repr__(self):
        return "<%s: id=%s>" % (
            type(self).__name__,
            self.id
        )
