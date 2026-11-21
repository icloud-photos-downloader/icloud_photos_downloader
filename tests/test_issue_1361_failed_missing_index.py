"""Test for issue #1361: `--ignore-indexing-state` with FAILED answers about a missing index

https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/1361

On some accounts (seen with an iOS 27 beta device on the account), iCloud answers the
CheckIndexingState query for PrimarySync with FAILED and an error like
"CKCloudDBException:No index with requested name: CPLContainerRelationNotHiddenOrDeletedByAddedDate",
switching between that and RUNNING, and never FINISHED. The library still lists completely: the
full listing matched the count on icloud.com. With the option, such FAILED answers are treated
like RUNNING ones. Any other FAILED answer still stops the run, as does any answer without the
option.
"""

import logging
from typing import Any, Dict, List
from unittest import TestCase, mock

from pyicloud_ipd.exceptions import PyiCloudServiceNotActivatedException
from pyicloud_ipd.services import photos
from pyicloud_ipd.services.photos import (
    PhotoLibrary,
    is_failed_on_missing_index,
    is_running_indexing_state,
)
from tests.test_issue_1387_indexing_state_retry import indexing_state_response

ZONE_ID = {"zoneName": "PrimarySync", "zoneType": "REGULAR_CUSTOM_ZONE"}
ATTEMPTS = photos.INDEXING_STATE_ATTEMPTS
MISSING_INDEX = (
    "CKCloudDBException:No index with requested name: "
    "CPLContainerRelationNotHiddenOrDeletedByAddedDate"
)


def failed_with_error(error: Any) -> Dict[str, Any]:
    response = indexing_state_response("FAILED")
    response["records"][0]["fields"]["progress"]["value"] = 100
    response["records"][0]["fields"]["error"] = {"value": error, "type": "STRING"}
    return response


def failed_on_missing_index() -> Dict[str, Any]:
    # as seen from iCloud: the same error repeated, separated by ", "
    return failed_with_error(", ".join([MISSING_INDEX] * 3))


def running() -> Dict[str, Any]:
    return indexing_state_response("RUNNING")


def make_library(responses: List[Dict[str, Any]], ignore_indexing_state: bool) -> PhotoLibrary:
    session = mock.MagicMock()
    session.post.side_effect = [mock.MagicMock(**{"json.return_value": r}) for r in responses]
    return PhotoLibrary(
        "https://example.com/endpoint",
        {},
        session,
        zone_id=ZONE_ID,
        library_type="private",
        ignore_indexing_state=ignore_indexing_state,
    )


@mock.patch("pyicloud_ipd.services.photos.time.sleep")
class Issue1361FailedMissingIndexTest(TestCase):
    def test_continues_and_warns_when_always_failed_on_missing_index(
        self, sleep: mock.MagicMock
    ) -> None:
        with self.assertLogs("pyicloud_ipd.services.photos", level="WARNING") as logs:
            library = make_library([failed_on_missing_index()] * ATTEMPTS, True)
        self.assertTrue(library.indexing_state_ignored)
        self.assertEqual(sleep.call_count, ATTEMPTS - 1)
        self.assertEqual(len(logs.records), 1)
        self.assertIn("PrimarySync is still reported as indexing", logs.output[0])
        self.assertIn(
            f"RUNNING, or FAILED with 'No index with requested name', on all {ATTEMPTS} checks",
            logs.output[0],
        )
        self.assertIn("the listing may be incomplete", logs.output[0])

    def test_continues_when_running_and_failed_on_missing_index_alternate(
        self, sleep: mock.MagicMock
    ) -> None:
        # the order seen from iCloud: FAILED, RUNNING x4, then FAILED until the last check
        responses = [failed_on_missing_index()] + [running()] * 4
        responses += [failed_on_missing_index()] * (ATTEMPTS - len(responses))
        with self.assertLogs("pyicloud_ipd.services.photos", level="WARNING"):
            library = make_library(responses, True)
        self.assertTrue(library.indexing_state_ignored)

    def test_raises_without_option(self, sleep: mock.MagicMock) -> None:
        with self.assertRaises(PyiCloudServiceNotActivatedException) as context:
            make_library([failed_on_missing_index()] * ATTEMPTS, False)
        self.assertIn("has not finished indexing yet", str(context.exception))

    def test_raises_on_failed_with_another_error(self, sleep: mock.MagicMock) -> None:
        for error in ["CKCloudDBException:Something else", "", None, 42]:
            with self.subTest(error=error):
                responses = [failed_on_missing_index()] * ATTEMPTS
                responses[ATTEMPTS // 2] = failed_with_error(error)
                with self.assertRaises(PyiCloudServiceNotActivatedException):
                    make_library(responses, True)

    def test_raises_on_failed_without_error(self, sleep: mock.MagicMock) -> None:
        responses = [failed_on_missing_index()] * ATTEMPTS
        responses[3] = indexing_state_response("FAILED")
        with self.assertRaises(PyiCloudServiceNotActivatedException):
            make_library(responses, True)

    def test_raises_on_missing_index_in_another_record_type(self, sleep: mock.MagicMock) -> None:
        responses = [failed_on_missing_index()] * ATTEMPTS
        other = failed_on_missing_index()
        other["records"][0]["recordType"] = "SomethingElse"
        responses[3] = other
        with self.assertRaises(PyiCloudServiceNotActivatedException):
            make_library(responses, True)

    def test_finished_after_failed_continues_without_warning(self, sleep: mock.MagicMock) -> None:
        with self.assertNoLogs("pyicloud_ipd.services.photos", level="WARNING"):
            library = make_library(
                [failed_on_missing_index(), indexing_state_response("FINISHED")], True
            )
        self.assertFalse(library.indexing_state_ignored)

    def test_debug_log_shows_the_error(self, sleep: mock.MagicMock) -> None:
        with self.assertLogs("pyicloud_ipd.services.photos", level=logging.DEBUG) as logs:
            make_library([failed_on_missing_index(), indexing_state_response("FINISHED")], True)
        self.assertIn(
            f"Library indexing state is FAILED ({MISSING_INDEX}, {MISSING_INDEX}, {MISSING_INDEX})"
            f" (attempt 1/{ATTEMPTS}), retrying in",
            logs.output[0],
        )

    def test_debug_log_without_error_is_unchanged(self, sleep: mock.MagicMock) -> None:
        with self.assertLogs("pyicloud_ipd.services.photos", level=logging.DEBUG) as logs:
            make_library([running(), indexing_state_response("FINISHED")], True)
        self.assertIn(
            f"Library indexing state is RUNNING (attempt 1/{ATTEMPTS}), retrying in",
            logs.output[0],
        )


class IndexingStateRecordTest(TestCase):
    def test_is_failed_on_missing_index(self) -> None:
        self.assertTrue(is_failed_on_missing_index(failed_on_missing_index()["records"][0]))
        self.assertTrue(is_failed_on_missing_index(failed_with_error(MISSING_INDEX)["records"][0]))
        self.assertFalse(is_failed_on_missing_index(failed_with_error("other")["records"][0]))
        self.assertFalse(is_failed_on_missing_index(failed_with_error(None)["records"][0]))
        self.assertFalse(
            is_failed_on_missing_index(indexing_state_response("FAILED")["records"][0])
        )
        self.assertFalse(is_failed_on_missing_index(running()["records"][0]))

    def test_is_running_indexing_state(self) -> None:
        self.assertTrue(is_running_indexing_state(running()["records"][0]))
        self.assertFalse(is_running_indexing_state(failed_on_missing_index()["records"][0]))
        without_type = running()["records"][0]
        del without_type["recordType"]
        self.assertFalse(is_running_indexing_state(without_type))
