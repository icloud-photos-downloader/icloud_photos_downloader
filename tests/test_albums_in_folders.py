"""Albums in folders (#482, #1071)

The album list (CPLAlbumByPositionLive) only holds the top level: albums (albumType 0)
and folders (albumType 3). The content of a folder comes from the same query filtered
on the folder's id as parentId. The structure below is the one seen on a real account:

    icloudpd test/            folder
        folder B/             folder
            Test B            album
        test A                album
    Holiday                   album
"""

import base64
import json
from typing import Any, Dict, List
from unittest import TestCase, mock

from pyicloud_ipd.services.photos import PhotoLibrary

ZONE_ID = {"zoneName": "PrimarySync", "zoneType": "REGULAR_CUSTOM_ZONE"}

INDEXING_FINISHED = {"records": [{"fields": {"state": {"value": "FINISHED"}}}]}


def record(
    record_id: str, name: str | None, album_type: int, deleted: bool = False
) -> Dict[str, Any]:
    fields: Dict[str, Any] = {"albumType": {"value": album_type}}
    if name is not None:
        fields["albumNameEnc"] = {"value": base64.b64encode(name.encode()).decode()}
    if deleted:
        fields["isDeleted"] = {"value": 1}
    return {"recordName": record_id, "fields": fields}


TOP_LEVEL = [
    record("----Project-Root-Folder----", None, 3),
    record("----Root-Folder----", None, 3),
    record("folder-test", "icloudpd test", 3),
    record("album-holiday", "Holiday", 0),
]
CHILDREN = {
    "folder-test": [record("folder-b", "folder B", 3), record("album-a", "test A", 0)],
    "folder-b": [record("album-b", "Test B", 0)],
}


def parent_of(query: Dict[str, Any]) -> str | None:
    filters = query["query"].get("filterBy", [])
    return str(filters[0]["fieldValue"]["value"]) if filters else None


class AlbumsInFoldersTestCase(TestCase):
    def make_library(self, top_level: List[Dict[str, Any]], children: Dict[str, Any]) -> None:
        self.queries: List[Dict[str, Any]] = []

        def post(_url: str, data: str, **_kwargs: Any) -> mock.MagicMock:
            query = json.loads(data)
            if query["query"]["recordType"] == "CheckIndexingState":
                return mock.MagicMock(**{"json.return_value": INDEXING_FINISHED})
            self.queries.append(query)
            parent = parent_of(query)
            page = children[parent] if parent is not None else top_level
            if isinstance(page, dict):
                page = page[query.get("continuationMarker")]
            else:
                page = {"records": page}
            return mock.MagicMock(**{"json.return_value": page})

        session = mock.MagicMock()
        session.post.side_effect = post
        self.library = PhotoLibrary(
            "https://example.com/endpoint", {}, session, zone_id=ZONE_ID, library_type="private"
        )

    def test_albums_in_folders_are_listed_with_their_path(self) -> None:
        self.make_library(TOP_LEVEL, CHILDREN)
        albums = self.library.albums
        self.assertIn("Holiday", albums)
        self.assertIn("icloudpd test/test A", albums)
        self.assertIn("icloudpd test/folder B/Test B", albums)
        self.assertEqual(
            "icloudpd test/folder B/Test B", albums["icloudpd test/folder B/Test B"].name
        )

    def test_folders_are_not_listed_as_albums(self) -> None:
        self.make_library(TOP_LEVEL, CHILDREN)
        albums = self.library.albums
        for folder in ("icloudpd test", "icloudpd test/folder B", "folder B"):
            self.assertNotIn(folder, albums)

    def test_each_folder_is_queried_by_its_id(self) -> None:
        self.make_library(TOP_LEVEL, CHILDREN)
        _ = self.library.albums
        self.assertEqual([None, "folder-test", "folder-b"], [parent_of(q) for q in self.queries])
        for query in self.queries:
            self.assertEqual("CPLAlbumByPositionLive", query["query"]["recordType"])
            self.assertEqual(ZONE_ID, query["zoneID"])

    def test_album_in_a_folder_lists_its_own_photos(self) -> None:
        self.make_library(TOP_LEVEL, CHILDREN)
        album = self.library.albums["icloudpd test/folder B/Test B"]
        self.assertEqual("CPLContainerRelationNotDeletedByAssetDate:album-b", album.obj_type)
        assert album.query_filter is not None
        self.assertEqual("album-b", album.query_filter[0]["fieldValue"]["value"])

    def test_folder_content_over_several_pages(self) -> None:
        self.make_library(
            TOP_LEVEL,
            {
                "folder-test": {
                    None: {"records": [record("album-a", "test A", 0)], "continuationMarker": "p2"},
                    "p2": {"records": [record("album-c", "test C", 0)]},
                },
                "folder-b": [],
            },
        )
        albums = self.library.albums
        self.assertIn("icloudpd test/test A", albums)
        self.assertIn("icloudpd test/test C", albums)

    def test_deleted_folder_is_skipped(self) -> None:
        self.make_library(
            [record("folder-test", "icloudpd test", 3, deleted=True)],
            {"folder-test": [record("album-a", "test A", 0)]},
        )
        self.assertNotIn("icloudpd test/test A", self.library.albums)
        self.assertEqual([None], [parent_of(q) for q in self.queries])

    def test_folder_listed_twice_is_walked_once(self) -> None:
        self.make_library(
            TOP_LEVEL,
            {
                "folder-test": [
                    record("folder-test", "icloudpd test", 3),
                    record("album-a", "test A", 0),
                ],
            },
        )
        albums = self.library.albums
        self.assertIn("icloudpd test/test A", albums)
        self.assertEqual([None, "folder-test"], [parent_of(q) for q in self.queries])
