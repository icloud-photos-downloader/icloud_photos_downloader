"""Albums listed over several pages (PR #1131)

iCloud returns the album list in pages: a response with a continuationMarker has more
albums, which come back when the marker is sent with the same query.
"""

import base64
import json
from typing import Any, Dict, List
from unittest import TestCase, mock

from pyicloud_ipd.services.photos import PhotoLibrary

ZONE_ID = {"zoneName": "PrimarySync", "zoneType": "REGULAR_CUSTOM_ZONE"}

INDEXING_FINISHED = {"records": [{"fields": {"state": {"value": "FINISHED"}}}]}


def album_page(names: List[str], marker: str | None = None) -> Dict[str, Any]:
    page: Dict[str, Any] = {
        "records": [
            {
                "recordName": f"id-{name}",
                "fields": {"albumNameEnc": {"value": base64.b64encode(name.encode()).decode()}},
            }
            for name in names
        ]
    }
    if marker is not None:
        page["continuationMarker"] = marker
    return page


def make_library(pages: List[Dict[str, Any]]) -> tuple[PhotoLibrary, mock.MagicMock]:
    session = mock.MagicMock()
    session.post.side_effect = [
        mock.MagicMock(**{"json.return_value": response})
        for response in [INDEXING_FINISHED, *pages]
    ]
    library = PhotoLibrary(
        "https://example.com/endpoint", {}, session, zone_id=ZONE_ID, library_type="private"
    )
    return library, session


def sent_queries(session: mock.MagicMock) -> List[Dict[str, Any]]:
    """Album queries sent after the indexing state check"""
    queries: List[Dict[str, Any]] = [
        json.loads(call.kwargs["data"]) for call in session.post.call_args_list[1:]
    ]
    return queries


class AlbumPaginationTestCase(TestCase):
    def test_single_page(self) -> None:
        library, session = make_library([album_page(["Holiday"])])
        self.assertIn("Holiday", library.albums)
        queries = sent_queries(session)
        self.assertEqual(len(queries), 1)
        self.assertNotIn("continuationMarker", queries[0])

    def test_albums_on_later_pages_are_listed(self) -> None:
        library, session = make_library(
            [
                album_page(["Holiday"], marker="page-2"),
                album_page(["Harry Potter"], marker="page-3"),
                album_page(["Birthday"]),
            ]
        )
        albums = library.albums
        for name in ("Holiday", "Harry Potter", "Birthday"):
            self.assertIn(name, albums)
        queries = sent_queries(session)
        self.assertEqual(
            [query.get("continuationMarker") for query in queries], [None, "page-2", "page-3"]
        )
        for query in queries:
            self.assertEqual(query["query"], {"recordType": "CPLAlbumByPositionLive"})
            self.assertEqual(query["zoneID"], ZONE_ID)

    def test_repeated_marker_stops(self) -> None:
        library, session = make_library(
            [
                album_page(["Holiday"], marker="page-2"),
                album_page(["Birthday"], marker="page-2"),
            ]
        )
        albums = library.albums
        self.assertIn("Holiday", albums)
        self.assertIn("Birthday", albums)
        self.assertEqual(len(sent_queries(session)), 2)
