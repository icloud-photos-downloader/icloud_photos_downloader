"""Drive service."""
from datetime import datetime, timedelta
import json
import logging
import io
import mimetypes
import os
import time
from re import search
from requests import Response

from pyicloud_ipd.exceptions import PyiCloudAPIResponseException


LOGGER = logging.getLogger(__name__)


class DriveService:
    """The 'Drive' iCloud service."""

    def __init__(self, service_root, document_root, session, params):
        self._service_root = service_root
        self._document_root = document_root
        self.session = session
        self.params = dict(params)
        self._root = None

    def _get_token_from_cookie(self):
        for cookie in self.session.cookies:
            if cookie.name == "X-APPLE-WEBAUTH-VALIDATE":
                match = search(r"\bt=([^:]+)", cookie.value)
                if match is None:
                    raise Exception("Can't extract token from %r" % cookie.value)
                return {"token": match.group(1)}
        raise Exception("Token cookie not found")

    def get_node_data(self, node_id):
        """Returns the node data."""
        request = self.session.post(
            self._service_root + "/retrieveItemDetailsInFolders",
            params=self.params,
            data=json.dumps(
                [
                    {
                        "drivewsid": "FOLDER::com.apple.CloudDocs::%s" % node_id,
                        "partialData": False,
                    }
                ]
            ),
        )
        self._raise_if_error(request)
        return request.json()[0]

    def get_file(self, file_id, **kwargs):
        """Returns iCloud Drive file."""
        file_params = dict(self.params)
        file_params.update({"document_id": file_id})
        response = self.session.get(
            self._document_root + "/ws/com.apple.CloudDocs/download/by_id",
            params=file_params,
        )
        self._raise_if_error(response)
        response_json = response.json()
        package_token = response_json.get("package_token")
        data_token = response_json.get("data_token")
        if data_token and data_token.get("url"):
            return self.session.get(data_token["url"], params=self.params, **kwargs)
        if package_token and package_token.get("url"):
            return self.session.get(package_token["url"], params=self.params, **kwargs)
        raise KeyError("'data_token' nor 'package_token'")

    def get_app_data(self):
        """Returns the app library (previously ubiquity)."""
        request = self.session.get(
            self._service_root + "/retrieveAppLibraries", params=self.params
        )
        self._raise_if_error(request)
        return request.json()["items"]

    def _get_upload_contentws_url(self, file_object):
        """Get the contentWS endpoint URL to add a new file."""
        content_type = mimetypes.guess_type(file_object.name)[0]
        if content_type is None:
            content_type = ""

        # Get filesize from file object
        orig_pos = file_object.tell()
        file_object.seek(0, os.SEEK_END)
        file_size = file_object.tell()
        file_object.seek(orig_pos, os.SEEK_SET)

        file_params = self.params
        file_params.update(self._get_token_from_cookie())

        request = self.session.post(
            self._document_root + "/ws/com.apple.CloudDocs/upload/web",
            params=file_params,
            headers={"Content-Type": "text/plain"},
            data=json.dumps(
                {
                    "filename": file_object.name,
                    "type": "FILE",
                    "content_type": content_type,
                    "size": file_size,
                }
            ),
        )
        self._raise_if_error(request)
        return (request.json()[0]["document_id"], request.json()[0]["url"])

    def _update_contentws(self, folder_id, sf_info, document_id, file_object):
        data = {
            "data": {
                "signature": sf_info["fileChecksum"],
                "wrapping_key": sf_info["wrappingKey"],
                "reference_signature": sf_info["referenceChecksum"],
                "size": sf_info["size"],
            },
            "command": "add_file",
            "create_short_guid": True,
            "document_id": document_id,
            "path": {
                "starting_document_id": folder_id,
                "path": file_object.name,
            },
            "allow_conflict": True,
            "file_flags": {
                "is_writable": True,
                "is_executable": False,
                "is_hidden": False,
            },
            "mtime": int(time.time() * 1000),
            "btime": int(time.time() * 1000),
        }

        # Add the receipt if we have one. Will be absent for 0-sized files
        if sf_info.get("receipt"):
            data["data"].update({"receipt": sf_info["receipt"]})

        request = self.session.post(
            self._document_root + "/ws/com.apple.CloudDocs/update/documents",
            params=self.params,
            headers={"Content-Type": "text/plain"},
            data=json.dumps(data),
        )
        self._raise_if_error(request)
        return request.json()

    def send_file(self, folder_id, file_object):
        """Send new file to iCloud Drive."""
        document_id, content_url = self._get_upload_contentws_url(file_object)

        request = self.session.post(content_url, files={file_object.name: file_object})
        self._raise_if_error(request)
        content_response = request.json()["singleFile"]
        self._update_contentws(folder_id, content_response, document_id, file_object)

    def create_folders(self, parent, name):
        """Creates a new iCloud Drive folder"""
        request = self.session.post(
            self._service_root + "/createFolders",
            params=self.params,
            headers={"Content-Type": "text/plain"},
            data=json.dumps(
                {
                    "destinationDrivewsId": parent,
                    "folders": [
                        {
                            "clientId": self.params["clientId"],
                            "name": name,
                        }
                    ],
                }
            ),
        )
        self._raise_if_error(request)
        return request.json()

    def rename_items(self, node_id, etag, name):
        """Renames an iCloud Drive node"""
        request = self.session.post(
            self._service_root + "/renameItems",
            params=self.params,
            data=json.dumps(
                {
                    "items": [
                        {
                            "drivewsid": node_id,
                            "etag": etag,
                            "name": name,
                        }
                    ],
                }
            ),
        )
        self._raise_if_error(request)
        return request.json()

    def move_items_to_trash(self, node_id, etag):
        """Moves an iCloud Drive node to the trash bin"""
        request = self.session.post(
            self._service_root + "/moveItemsToTrash",
            params=self.params,
            data=json.dumps(
                {
                    "items": [
                        {
                            "drivewsid": node_id,
                            "etag": etag,
                            "clientId": self.params["clientId"],
                        }
                    ],
                }
            ),
        )
        self._raise_if_error(request)
        return request.json()

    @property
    def root(self):
        """Returns the root node."""
        if not self._root:
            self._root = DriveNode(self, self.get_node_data("root"))
        return self._root

    def __getattr__(self, attr):
        return getattr(self.root, attr)

    def __getitem__(self, key):
        return self.root[key]

    def _raise_if_error(self, response):  # pylint: disable=no-self-use
        if not response.ok:
            api_error = PyiCloudAPIResponseException(
                response.reason, response.status_code
            )
            LOGGER.error(api_error)
            raise api_error


class DriveNode:
    """Drive node."""

    def __init__(self, conn, data):
        self.data = data
        self.connection = conn
        self._children = None

    @property
    def name(self):
        """Gets the node name."""
        if "extension" in self.data:
            return "{}.{}".format(self.data["name"], self.data["extension"])
        return self.data["name"]

    @property
    def type(self):
        """Gets the node type."""
        node_type = self.data.get("type")
        return node_type and node_type.lower()

    def get_children(self):
        """Gets the node children."""
        if not self._children:
            if "items" not in self.data:
                self.data.update(self.connection.get_node_data(self.data["docwsid"]))
            if "items" not in self.data:
                raise KeyError("No items in folder, status: %s" % self.data["status"])
            self._children = [
                DriveNode(self.connection, item_data)
                for item_data in self.data["items"]
            ]
        return self._children

    @property
    def size(self):
        """Gets the node size."""
        size = self.data.get("size")  # Folder does not have size
        if not size:
            return None
        return int(size)

    @property
    def date_changed(self):
        """Gets the node changed date (in UTC)."""
        return _date_to_utc(self.data.get("dateChanged"))  # Folder does not have date

    @property
    def date_modified(self):
        """Gets the node modified date (in UTC)."""
        return _date_to_utc(self.data.get("dateModified"))  # Folder does not have date

    @property
    def date_last_open(self):
        """Gets the node last open date (in UTC)."""
        return _date_to_utc(self.data.get("lastOpenTime"))  # Folder does not have date

    def open(self, **kwargs):
        """Gets the node file."""
        # iCloud returns 400 Bad Request for 0-byte files
        if self.data["size"] == 0:
            response = Response()
            response.raw = io.BytesIO()
            return response
        return self.connection.get_file(self.data["docwsid"], **kwargs)

    def upload(self, file_object, **kwargs):
        """Upload a new file."""
        return self.connection.send_file(self.data["docwsid"], file_object, **kwargs)

    def dir(self):
        """Gets the node list of directories."""
        if self.type == "file":
            return None
        return [child.name for child in self.get_children()]

    def mkdir(self, folder):
        """Create a new directory directory."""
        return self.connection.create_folders(self.data["drivewsid"], folder)

    def rename(self, name):
        """Rename an iCloud Drive item."""
        return self.connection.rename_items(
            self.data["drivewsid"], self.data["etag"], name
        )

    def delete(self):
        """Delete an iCloud Drive item."""
        return self.connection.move_items_to_trash(
            self.data["drivewsid"], self.data["etag"]
        )

    def get(self, name):
        """Gets the node child."""
        if self.type == "file":
            return None
        return [child for child in self.get_children() if child.name == name][0]

    def __getitem__(self, key):
        try:
            return self.get(key)
        except IndexError as i:
            raise KeyError(f"No child named '{key}' exists") from i

    def __str__(self):
        return rf"\{type: {self.type}, name: {self.name}\}"

    def __repr__(self):
        return f"<{type(self).__name__}: {str(self)}>"


def _date_to_utc(date):
    if not date:
        return None
    # jump through hoops to return time in UTC rather than California time
    match = search(r"^(.+?)([\+\-]\d+):(\d\d)$", date)
    if not match:
        # Already in UTC
        return datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")
    base = datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%S")
    diff = timedelta(hours=int(match.group(2)), minutes=int(match.group(3)))
    return base - diff
