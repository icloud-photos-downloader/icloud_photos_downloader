"""Test for issue #1387: "Apple iCloud Photo Library has not finished indexing yet"

https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/1387

Apple's CheckIndexingState query can return RUNNING for a library that is ready,
answering FINISHED only on some calls. A single RUNNING answer must not fail the run.
"""

from typing import Any, Dict, List
from unittest import TestCase, mock

from pyicloud_ipd.exceptions import PyiCloudServiceNotActivatedException
from pyicloud_ipd.services import photos
from pyicloud_ipd.services.photos import PhotoLibrary

ZONE_ID = {"zoneName": "PrimarySync", "zoneType": "REGULAR_CUSTOM_ZONE"}


def indexing_state_response(state: str) -> Dict[str, Any]:
    return {
        "records": [
            {
                "recordType": "CheckIndexingState",
                "fields": {
                    "state": {"value": state, "type": "STRING"},
                    "progress": {"value": 0, "type": "INT64"},
                },
            }
        ]
    }


def session_returning(states: List[str]) -> mock.MagicMock:
    session = mock.MagicMock()
    session.post.side_effect = [
        mock.MagicMock(**{"json.return_value": indexing_state_response(s)}) for s in states
    ]
    return session


def make_library(session: mock.MagicMock) -> PhotoLibrary:
    return PhotoLibrary(
        "https://example.com/endpoint", {}, session, zone_id=ZONE_ID, library_type="private"
    )


class Issue1387IndexingStateRetryTest(TestCase):
    @mock.patch("pyicloud_ipd.services.photos.time.sleep")
    def test_finished_on_first_check(self, sleep: mock.MagicMock) -> None:
        session = session_returning(["FINISHED"])
        make_library(session)
        self.assertEqual(session.post.call_count, 1)
        sleep.assert_not_called()

    @mock.patch("pyicloud_ipd.services.photos.time.sleep")
    def test_retries_until_finished(self, sleep: mock.MagicMock) -> None:
        session = session_returning(["RUNNING", "RUNNING", "FINISHED"])
        with self.assertLogs("pyicloud_ipd.services.photos", level="DEBUG") as logs:
            make_library(session)
        self.assertEqual(session.post.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        sleep.assert_called_with(photos.INDEXING_STATE_RETRY_DELAY_SECONDS)
        self.assertIn("indexing state is RUNNING (attempt 1/", logs.output[0])

    @mock.patch("pyicloud_ipd.services.photos.time.sleep")
    def test_raises_when_never_finished(self, sleep: mock.MagicMock) -> None:
        attempts = photos.INDEXING_STATE_ATTEMPTS
        session = session_returning(["RUNNING"] * attempts)
        with self.assertRaises(PyiCloudServiceNotActivatedException) as context:
            make_library(session)
        self.assertIn("has not finished indexing yet", str(context.exception))
        self.assertEqual(session.post.call_count, attempts)
        self.assertEqual(sleep.call_count, attempts - 1)
