from unittest import TestCase
from unittest.mock import MagicMock, call
from pyicloud_ipd.services.photos import PhotoLibrary

class TestPhotoLibraryListAlbums(TestCase):
    def setUp(self):
        self.mock_service = MagicMock()
        self.mock_service.get_service_endpoint.return_value = "http://example.com"
        self.mock_state_response = MagicMock()
        self.mock_state_response.json.return_value = {
            "records": [{
                "fields": {"state": {"value": "FINISHED"}}
            }]
        }
        self.mock_service.session.post.return_value = self.mock_state_response

    def test_fetch_folders_no_continuation(self):
        folders_response = MagicMock()
        folders_response.json.return_value = {
            "records": [
                {"recordName": "folder1", "fields": {"albumNameEnc": {"value": "Zm9sZGVyMQ=="}}}
            ]
        }
        self.mock_service.session.post.side_effect = [
            self.mock_state_response,  # For __init__ state check
            folders_response           # For _fetch_folders
        ]
        library = PhotoLibrary(self.mock_service, {"zoneName": "PrimarySync"}, "private")
        folders = library._fetch_folders()
        self.assertEqual(len(folders), 1)
        self.assertEqual(folders[0]["recordName"], "folder1")

    def test_fetch_folders_with_continuation(self):
        first_response = MagicMock()
        first_response.json.return_value = {
            "records": [
                {"recordName": "folder1", "fields": {"albumNameEnc": {"value": "Zm9sZGVyMQ=="}}}
            ],
            "continuationMarker": "abc123"
        }
        second_response = MagicMock()
        second_response.json.return_value = {
            "records": [
                {"recordName": "folder2", "fields": {"albumNameEnc": {"value": "Zm9sZGVyMg=="}}}
            ]
        }
        self.mock_service.session.post.side_effect = [
            self.mock_state_response,
            first_response,
            second_response
        ]
        library = PhotoLibrary(self.mock_service, {"zoneName": "PrimarySync"}, "private")
        folders = library._fetch_folders()
        self.assertEqual(len(folders), 2)
        self.assertEqual(folders[0]["recordName"], "folder1")
        self.assertEqual(folders[1]["recordName"], "folder2")

        self.assertEqual(self.mock_service.session.post.call_count, 3)
