"""Photo service."""
import json
import base64
from urllib.parse import urlencode

from datetime import datetime, timezone
from pyicloud_ipd.exceptions import PyiCloudServiceNotActivatedException


class PhotosService:
    """The 'Photos' iCloud service."""

    SMART_FOLDERS = {
        "All Photos": {
            "obj_type": "CPLAssetByAddedDate",
            "list_type": "CPLAssetAndMasterByAddedDate",
            "direction": "ASCENDING",
            "query_filter": None,
        },
        "Time-lapse": {
            "obj_type": "CPLAssetInSmartAlbumByAssetDate:Timelapse",
            "list_type": "CPLAssetAndMasterInSmartAlbumByAssetDate",
            "direction": "ASCENDING",
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
            "direction": "ASCENDING",
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
            "direction": "ASCENDING",
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
            "direction": "ASCENDING",
            "query_filter": None,
        },
        "Favorites": {
            "obj_type": "CPLAssetInSmartAlbumByAssetDate:Favorite",
            "list_type": "CPLAssetAndMasterInSmartAlbumByAssetDate",
            "direction": "ASCENDING",
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
            "direction": "ASCENDING",
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
            "direction": "ASCENDING",
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
            "direction": "ASCENDING",
            "query_filter": [
                {
                    "fieldName": "smartAlbum",
                    "comparator": "EQUALS",
                    "fieldValue": {"type": "STRING", "value": "LIVE"},
                }
            ],
        },
        "Recently Deleted": {
            "obj_type": "CPLAssetDeletedByExpungedDate",
            "list_type": "CPLAssetAndMasterDeletedByExpungedDate",
            "direction": "ASCENDING",
            "query_filter": None,
        },
        "Hidden": {
            "obj_type": "CPLAssetHiddenByAssetDate",
            "list_type": "CPLAssetAndMasterHiddenByAssetDate",
            "direction": "ASCENDING",
            "query_filter": None,
        },
    }

    def __init__(self, service_root, session, params):
        self.session = session
        self.params = dict(params)
        self._service_root = service_root
        self.service_endpoint = (
            "%s/database/1/com.apple.photos.cloud/production/private"
            % self._service_root
        )

        self._albums = None

        self.params.update({"remapEnums": True, "getCurrentSyncToken": True})

        url = f"{self.service_endpoint}/records/query?{urlencode(self.params)}"
        json_data = (
            '{"query":{"recordType":"CheckIndexingState"},'
            '"zoneID":{"zoneName":"PrimarySync"}}'
        )
        request = self.session.post(
            url, data=json_data, headers={"Content-type": "text/plain"}
        )
        response = request.json()
        indexing_state = response["records"][0]["fields"]["state"]["value"]
        if indexing_state != "FINISHED":
            raise PyiCloudServiceNotActivatedException(
                "iCloud Photo Library not finished indexing. "
                "Please try again in a few minutes."
            )

        # TODO: Does syncToken ever change?  # pylint: disable=fixme
        # self.params.update({
        #     'syncToken': response['syncToken'],
        #     'clientInstanceId': self.params.pop('clientId')
        # })

        self._photo_assets = {}

    @property
    def albums(self):
        """Returns photo albums."""
        if not self._albums:
            self._albums = {
                name: PhotoAlbum(self, name, **props)
                for (name, props) in self.SMART_FOLDERS.items()
            }

            for folder in self._fetch_folders():

                # Skiping albums having null name, that can happen sometime
                if "albumNameEnc" not in folder["fields"]:
                    continue

                # TODO: Handle subfolders  # pylint: disable=fixme
                if folder["recordName"] == "----Root-Folder----" or (
                    folder["fields"].get("isDeleted")
                    and folder["fields"]["isDeleted"]["value"]
                ):
                    continue

                folder_id = folder["recordName"]
                folder_obj_type = (
                    "CPLContainerRelationNotDeletedByAssetDate:%s" % folder_id
                )
                folder_name = base64.b64decode(
                    folder["fields"]["albumNameEnc"]["value"]
                ).decode("utf-8")
                query_filter = [
                    {
                        "fieldName": "parentId",
                        "comparator": "EQUALS",
                        "fieldValue": {"type": "STRING", "value": folder_id},
                    }
                ]

                album = PhotoAlbum(
                    self,
                    folder_name,
                    "CPLContainerRelationLiveByAssetDate",
                    folder_obj_type,
                    "ASCENDING",
                    query_filter,
                )
                self._albums[folder_name] = album

        return self._albums

    def _fetch_folders(self):
        url = f"{self.service_endpoint}/records/query?{urlencode(self.params)}"
        json_data = (
            '{"query":{"recordType":"CPLAlbumByPositionLive"},'
            '"zoneID":{"zoneName":"PrimarySync"}}'
        )

        request = self.session.post(
            url, data=json_data, headers={"Content-type": "text/plain"}
        )
        response = request.json()

        return response["records"]

    @property
    def all(self):
        """Returns all photos."""
        return self.albums["All Photos"]


class PhotoAlbum:
    """A photo album."""

    def __init__(
        self,
        service,
        name,
        list_type,
        obj_type,
        direction,
        query_filter=None,
        page_size=100,
    ):
        self.name = name
        self.service = service
        self.list_type = list_type
        self.obj_type = obj_type
        self.direction = direction
        self.query_filter = query_filter
        self.page_size = page_size

        self._len = None

    @property
    def title(self):
        """Gets the album name."""
        return self.name

    def __iter__(self):
        return self.photos

    def __len__(self):
        if self._len is None:
            url = "{}/internal/records/query/batch?{}".format(
                self.service.service_endpoint,
                urlencode(self.service.params),
            )
            request = self.service.session.post(
                url,
                data=json.dumps(
                    {
                        "batch": [
                            {
                                "resultsLimit": 1,
                                "query": {
                                    "filterBy": {
                                        "fieldName": "indexCountID",
                                        "fieldValue": {
                                            "type": "STRING_LIST",
                                            "value": [self.obj_type],
                                        },
                                        "comparator": "IN",
                                    },
                                    "recordType": "HyperionIndexCountLookup",
                                },
                                "zoneWide": True,
                                "zoneID": {"zoneName": "PrimarySync"},
                            }
                        ]
                    }
                ),
                headers={"Content-type": "text/plain"},
            )
            response = request.json()

            self._len = response["batch"][0]["records"][0]["fields"]["itemCount"][
                "value"
            ]

        return self._len

    @property
    def photos(self):
        """Returns the album photos."""
        if self.direction == "DESCENDING":
            offset = len(self) - 1
        else:
            offset = 0

        while True:
            url = ("%s/records/query?" % self.service.service_endpoint) + urlencode(
                self.service.params
            )
            request = self.service.session.post(
                url,
                data=json.dumps(
                    self._list_query_gen(
                        offset, self.list_type, self.direction, self.query_filter
                    )
                ),
                headers={"Content-type": "text/plain"},
            )
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
                if self.direction == "DESCENDING":
                    offset = offset - master_records_len
                else:
                    offset = offset + master_records_len

                for master_record in master_records:
                    record_name = master_record["recordName"]
                    yield PhotoAsset(
                        self.service, master_record, asset_records[record_name]
                    )
            else:
                break

    def _list_query_gen(self, offset, list_type, direction, query_filter=None):
        query = {
            "query": {
                "filterBy": [
                    {
                        "fieldName": "startRank",
                        "fieldValue": {"type": "INT64", "value": offset},
                        "comparator": "EQUALS",
                    },
                    {
                        "fieldName": "direction",
                        "fieldValue": {"type": "STRING", "value": direction},
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
                "vidComplVisibilityState",
                "customRenderedValue",
                "containerId",
                "itemId",
                "position",
                "isKeyAsset",
            ],
            "zoneID": {"zoneName": "PrimarySync"},
        }

        if query_filter:
            query["query"]["filterBy"].extend(query_filter)

        return query

    def __str__(self):
        return self.title

    def __repr__(self):
        return f"<{type(self).__name__}: '{self}'>"


class PhotoAsset:
    """A photo."""

    def __init__(self, service, master_record, asset_record):
        self._service = service
        self._master_record = master_record
        self._asset_record = asset_record

        self._versions = None

    PHOTO_VERSION_LOOKUP = {
        "original": "resOriginal",
        "medium": "resJPEGMed",
        "thumb": "resJPEGThumb",
    }

    VIDEO_VERSION_LOOKUP = {
        "original": "resOriginal",
        "medium": "resVidMed",
        "thumb": "resVidSmall",
    }

    ITEM_TYPES = {
        u"public.heic": u"image",
        u"public.jpeg": u"image",
        u"public.png": u"image",
        u"com.apple.quicktime-movie": u"movie"
    }

    @property
    def id(self):
        """Gets the photo id."""
        return self._master_record["recordName"]

    @property
    def filename(self):
        """Gets the photo file name."""
        return base64.b64decode(
            self._master_record["fields"]["filenameEnc"]["value"]
        ).decode("utf-8")

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
    def size(self):
        """Gets the photo size."""
        return self._master_record["fields"]["resOriginalRes"]["value"]["size"]

    @property
    def created(self):
        """Gets the photo created date."""
        return self.asset_date

    @property
    def asset_date(self):
        """Gets the photo asset date."""
        try:
            return datetime.utcfromtimestamp(
                self._asset_record["fields"]["assetDate"]["value"] / 1000.0
            ).replace(tzinfo=timezone.utc)
        except KeyError:
            return datetime.utcfromtimestamp(0).replace(tzinfo=timezone.utc)

    @property
    def added_date(self):
        """Gets the photo added date."""
        return datetime.utcfromtimestamp(
            self._asset_record["fields"]["addedDate"]["value"] / 1000.0
        ).replace(tzinfo=timezone.utc)

    @property
    def dimensions(self):
        """Gets the photo dimensions."""
        return (
            self._master_record["fields"]["resOriginalWidth"]["value"],
            self._master_record["fields"]["resOriginalHeight"]["value"],
        )

    @property
    def versions(self):
        """Gets the photo versions."""
        if not self._versions:
            self._versions = {}
            if "resVidSmallRes" in self._master_record["fields"]:
                typed_version_lookup = self.VIDEO_VERSION_LOOKUP
            else:
                typed_version_lookup = self.PHOTO_VERSION_LOOKUP

            for key, prefix in typed_version_lookup.items():
                if "%sRes" % prefix in self._master_record["fields"]:
                    fields = self._master_record["fields"]
                    version = {"filename": self.filename}

                    width_entry = fields.get("%sWidth" % prefix)
                    if width_entry:
                        version["width"] = width_entry["value"]
                    else:
                        version["width"] = None

                    height_entry = fields.get("%sHeight" % prefix)
                    if height_entry:
                        version["height"] = height_entry["value"]
                    else:
                        version["height"] = None

                    size_entry = fields.get("%sRes" % prefix)
                    if size_entry:
                        version["size"] = size_entry["value"]["size"]
                        version["url"] = size_entry["value"]["downloadURL"]
                    else:
                        version["size"] = None
                        version["url"] = None

                    type_entry = fields.get("%sFileType" % prefix)
                    if type_entry:
                        version["type"] = type_entry["value"]
                    else:
                        version["type"] = None

                    self._versions[key] = version

        return self._versions

    def download(self, version="original", **kwargs):
        """Returns the photo file."""
        if version not in self.versions:
            return None

        return self._service.session.get(
            self.versions[version]["url"], stream=True, **kwargs
        )

    def delete(self):
        """Deletes the photo."""
        json_data = (
            '{"query":{"recordType":"CheckIndexingState"},'
            '"zoneID":{"zoneName":"PrimarySync"}}'
        )

        json_data = (
            '{"operations":[{'
            '"operationType":"update",'
            '"record":{'
            '"recordName":"%s",'
            '"recordType":"%s",'
            '"recordChangeTag":"%s",'
            '"fields":{"isDeleted":{"value":1}'
            "}}}],"
            '"zoneID":{'
            '"zoneName":"PrimarySync"'
            '},"atomic":true}'
            % (
                self._asset_record["recordName"],
                self._asset_record["recordType"],
                self._master_record["recordChangeTag"],
            )
        )

        endpoint = self._service.service_endpoint
        params = urlencode(self._service.params)
        url = f"{endpoint}/records/modify?{params}"

        return self._service.session.post(
            url, data=json_data, headers={"Content-type": "text/plain"}
        )

    def __repr__(self):
        return f"<{type(self).__name__}: id={self.id}>"
