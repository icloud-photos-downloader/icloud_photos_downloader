"""Test for issue #1361: `--ignore-indexing-state` with FAILED answers about a missing index

https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/1361

On some accounts (seen with an iOS 27 beta device on the account), iCloud answers the
CheckIndexingState query for PrimarySync with FAILED and an error like
"CKCloudDBException:No index with requested name: CPLContainerRelationNotHiddenOrDeletedByAddedDate",
switching between that and RUNNING, and never FINISHED. The asset listing doesn't use that index
(it uses CPLAssetAndMasterByAssetDateWithoutHiddenOrDeleted and its count), and the full listing
matched the count on icloud.com. With the option, FAILED answers whose error consists only of
missing CPLContainerRelation* indexes are accepted. Any other FAILED answer still stops the run,
as does any answer without the option.
"""

import inspect
import json
import logging
import os
from typing import Any, Dict, List
from unittest import TestCase, mock

import pytest

from pyicloud_ipd.exceptions import PyiCloudServiceNotActivatedException
from pyicloud_ipd.services import photos
from pyicloud_ipd.services.photos import (
    PhotoLibrary,
    PhotosService,
    indexing_state_error,
    is_failed_on_missing_index,
    is_running_indexing_state,
)
from tests.helpers import path_from_project_root, run_icloudpd_test
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
    # as seen from iCloud: the same error repeated, joined with ", "
    return failed_with_error(", ".join([MISSING_INDEX] * 3))


def running() -> Dict[str, Any]:
    return indexing_state_response("RUNNING")


def observed_sequence() -> List[Dict[str, Any]]:
    # the order seen from iCloud: FAILED, RUNNING x4, then FAILED until the last check
    responses = [failed_on_missing_index()] + [running()] * 4
    return responses + [failed_on_missing_index()] * (ATTEMPTS - len(responses))


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
        self.assertTrue(library.indexing_check_failed_on_missing_index)
        self.assertEqual(sleep.call_count, ATTEMPTS - 1)
        self.assertEqual(len(logs.records), 1)
        self.assertIn(
            "PrimarySync: iCloud's indexing check keeps failing on a missing "
            "CPLContainerRelation index, which the listing doesn't use",
            logs.output[0],
        )
        self.assertIn(f"FAILED or RUNNING on all {ATTEMPTS} checks", logs.output[0])
        self.assertNotIn("may be incomplete", logs.output[0])

    def test_continues_when_running_and_failed_on_missing_index_alternate(
        self, sleep: mock.MagicMock
    ) -> None:
        with self.assertLogs("pyicloud_ipd.services.photos", level="WARNING"):
            library = make_library(observed_sequence(), True)
        self.assertTrue(library.indexing_state_ignored)
        self.assertTrue(library.indexing_check_failed_on_missing_index)

    def test_all_running_keeps_the_1387_behavior(self, sleep: mock.MagicMock) -> None:
        with self.assertLogs("pyicloud_ipd.services.photos", level="WARNING") as logs:
            library = make_library([running()] * ATTEMPTS, True)
        self.assertTrue(library.indexing_state_ignored)
        self.assertFalse(library.indexing_check_failed_on_missing_index)
        self.assertIn("the listing may be incomplete", logs.output[0])

    def test_raises_without_option(self, sleep: mock.MagicMock) -> None:
        with self.assertRaises(PyiCloudServiceNotActivatedException) as context:
            make_library(observed_sequence(), False)
        self.assertIn("has not finished indexing yet", str(context.exception))

    def test_raises_on_mixed_error(self, sleep: mock.MagicMock) -> None:
        mixed = [
            f"{MISSING_INDEX}, CKInternalError: Internal server error",
            f"CKInternalError: Internal server error, {MISSING_INDEX}",
            f"{MISSING_INDEX}, {MISSING_INDEX}, CKCloudDBException:Something else",
        ]
        for error in mixed:
            with self.subTest(error=error):
                responses = observed_sequence()
                responses[ATTEMPTS // 2] = failed_with_error(error)
                with self.assertRaises(PyiCloudServiceNotActivatedException):
                    make_library(responses, True)

    def test_raises_on_missing_index_the_listing_may_need(self, sleep: mock.MagicMock) -> None:
        for index in [
            "CPLAssetAndMasterByAssetDateWithoutHiddenOrDeleted",
            "CPLAssetByAssetDateWithoutHiddenOrDeleted",
            "SomethingCPLContainerRelation",
            "",
        ]:
            with self.subTest(index=index):
                responses = observed_sequence()
                responses[3] = failed_with_error(
                    f"CKCloudDBException:No index with requested name: {index}"
                )
                with self.assertRaises(PyiCloudServiceNotActivatedException):
                    make_library(responses, True)

    def test_raises_on_extra_text_around_the_error(self, sleep: mock.MagicMock) -> None:
        for error in [
            f"{MISSING_INDEX} (retry later)",
            f"Error: {MISSING_INDEX}",
            f"{MISSING_INDEX},",
            f"{MISSING_INDEX},{MISSING_INDEX}",
        ]:
            with self.subTest(error=error):
                responses = observed_sequence()
                responses[3] = failed_with_error(error)
                with self.assertRaises(PyiCloudServiceNotActivatedException):
                    make_library(responses, True)

    def test_raises_on_failed_with_another_or_no_error(self, sleep: mock.MagicMock) -> None:
        for error in ["CKCloudDBException:Something else", "", None, 42]:
            with self.subTest(error=error):
                responses = observed_sequence()
                responses[ATTEMPTS // 2] = failed_with_error(error)
                with self.assertRaises(PyiCloudServiceNotActivatedException):
                    make_library(responses, True)
        responses = observed_sequence()
        responses[3] = indexing_state_response("FAILED")
        with self.assertRaises(PyiCloudServiceNotActivatedException):
            make_library(responses, True)

    def test_error_that_is_not_a_dict_does_not_crash(self, sleep: mock.MagicMock) -> None:
        for error_field in ["CKCloudDBException:No index", None, 42, [MISSING_INDEX]]:
            with self.subTest(error_field=error_field):
                odd = indexing_state_response("FAILED")
                odd["records"][0]["fields"]["error"] = error_field
                responses = observed_sequence()
                responses[3] = odd
                with self.assertRaises(PyiCloudServiceNotActivatedException):
                    make_library(responses, True)

    def test_raises_on_missing_index_in_another_record_type(self, sleep: mock.MagicMock) -> None:
        responses = observed_sequence()
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
        self.assertFalse(library.indexing_check_failed_on_missing_index)

    def test_debug_log_shows_the_error_on_every_check(self, sleep: mock.MagicMock) -> None:
        with self.assertLogs("pyicloud_ipd.services.photos", level=logging.DEBUG) as logs:
            make_library([failed_on_missing_index()] * ATTEMPTS, True)
        checks = [line for line in logs.output if "Library indexing state is" in line]
        self.assertEqual(len(checks), ATTEMPTS)
        error = ", ".join([MISSING_INDEX] * 3)
        self.assertIn(
            f"Library indexing state is FAILED ({error}) (attempt 1/{ATTEMPTS}), retrying in",
            checks[0],
        )
        # the last answer is logged too, without "retrying"
        self.assertTrue(
            checks[-1].endswith(
                f"Library indexing state is FAILED ({error}) (attempt {ATTEMPTS}/{ATTEMPTS})"
            ),
            checks[-1],
        )

    def test_debug_log_without_error_is_unchanged(self, sleep: mock.MagicMock) -> None:
        with self.assertLogs("pyicloud_ipd.services.photos", level=logging.DEBUG) as logs:
            make_library([running(), indexing_state_response("FINISHED")], True)
        self.assertIn(
            f"Library indexing state is RUNNING (attempt 1/{ATTEMPTS}), retrying in 4s",
            logs.output[0],
        )


@mock.patch("pyicloud_ipd.services.photos.time.sleep")
class Issue1361PhotosServiceTest(TestCase):
    """The full startup path: PhotosService checks PrimarySync, and on failure lists zones"""

    def service(self, responses: List[Dict[str, Any]], ignore: bool) -> PhotosService:
        answers = iter(responses)

        def post(url: str, data: str = "", **_: Any) -> Any:
            if url.endswith("/zones/list"):
                zones = {"zones": [{"zoneID": {"zoneName": "PrimarySync"}}]}
                return mock.MagicMock(**{"json.return_value": zones})
            self.assertEqual(json.loads(data)["zoneID"]["zoneName"], "PrimarySync")
            return mock.MagicMock(**{"json.return_value": next(answers)})

        session = mock.MagicMock()
        session.post.side_effect = post
        return PhotosService("https://example.com", session, {}, ignore_indexing_state=ignore)

    def test_starts_with_option(self, sleep: mock.MagicMock) -> None:
        with self.assertLogs("pyicloud_ipd.services.photos", level="WARNING"):
            service = self.service(observed_sequence(), ignore=True)
        self.assertEqual(service.zone_id["zoneName"], "PrimarySync")
        self.assertTrue(service.indexing_state_ignored)
        self.assertTrue(service.indexing_check_failed_on_missing_index)

    def test_stops_without_option(self, sleep: mock.MagicMock) -> None:
        with self.assertRaises(PyiCloudServiceNotActivatedException) as context:
            self.service(observed_sequence(), ignore=False)
        self.assertIn("has not finished indexing yet", str(context.exception))

    def test_stops_with_option_on_mixed_error(self, sleep: mock.MagicMock) -> None:
        responses = observed_sequence()
        responses[-1] = failed_with_error(f"{MISSING_INDEX}, CKInternalError: oops")
        with self.assertRaises(PyiCloudServiceNotActivatedException):
            self.service(responses, ignore=True)


class Issue1361EndOfRunTest(TestCase):
    """The last line of a run must not suggest a run without the option, which never works here"""

    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

    def run_with_failed_check(self, base_dir: str, extra: List[str]) -> Any:
        original_init = PhotoLibrary.__init__

        # the recorded responses say FINISHED; mark the library as if the checks had answered
        # FAILED on a missing CPLContainerRelation index and the option let the run continue
        def init_with_failed_check(self: PhotoLibrary, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)
            self.indexing_state_ignored = self.ignore_indexing_state
            self.indexing_check_failed_on_missing_index = self.ignore_indexing_state

        with mock.patch.object(PhotoLibrary, "__init__", init_with_failed_check):
            _, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos.yml",
                [],
                [],
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "0",
                    "--no-progress-bar",
                    *extra,
                ],
            )
        return result

    def test_end_of_run_says_the_option_is_needed_every_run(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        with self.assertLogs("icloudpd", level="INFO") as logs:
            result = self.run_with_failed_check(base_dir, ["--ignore-indexing-state"])
        self.assertEqual(result.exit_code, 0)
        # INFO, not WARNING: this is the expected state on every run for such accounts
        end_of_run = [
            r for r in logs.records if r.getMessage().startswith("All photos and videos that")
        ]
        self.assertEqual([r.levelname for r in end_of_run], ["INFO"])
        self.assertIn(
            "All photos and videos that iCloud listed have been downloaded. iCloud's indexing "
            "check keeps failing on a missing index that the listing doesn't use, so "
            "--ignore-indexing-state is needed on every run for this library",
            result.output,
        )
        self.assertNotIn("A later run without the option", result.output)
        self.assertNotIn("the listing may be incomplete", result.output)

    def test_end_of_run_unchanged_without_option(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        result = self.run_with_failed_check(base_dir, [])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("All photos and videos have been downloaded", result.output)
        self.assertNotIn("--ignore-indexing-state is needed", result.output)


class IndexingStateRecordTest(TestCase):
    def test_is_failed_on_missing_index(self) -> None:
        record = failed_on_missing_index()["records"][0]
        self.assertTrue(is_failed_on_missing_index(record))
        self.assertTrue(is_failed_on_missing_index(failed_with_error(MISSING_INDEX)["records"][0]))
        other_index = MISSING_INDEX.replace("NotHiddenOrDeletedByAddedDate", "ByPosition")
        self.assertTrue(is_failed_on_missing_index(failed_with_error(other_index)["records"][0]))
        for error in [
            "other",
            None,
            f"{MISSING_INDEX}, CKInternalError: x",
            MISSING_INDEX.replace("CPLContainerRelation", "CPLAsset"),
        ]:
            with self.subTest(error=error):
                self.assertFalse(is_failed_on_missing_index(failed_with_error(error)["records"][0]))
        self.assertFalse(
            is_failed_on_missing_index(indexing_state_response("FAILED")["records"][0])
        )
        self.assertFalse(is_failed_on_missing_index(running()["records"][0]))

    def test_indexing_state_error(self) -> None:
        self.assertEqual(
            indexing_state_error(failed_with_error(MISSING_INDEX)["records"][0]), MISSING_INDEX
        )
        self.assertIsNone(indexing_state_error(running()["records"][0]))
        self.assertIsNone(indexing_state_error({"fields": {"error": "not a dict"}}))
        self.assertIsNone(indexing_state_error({"fields": "not a dict"}))
        self.assertIsNone(indexing_state_error({}))

    def test_is_running_indexing_state(self) -> None:
        self.assertTrue(is_running_indexing_state(running()["records"][0]))
        self.assertFalse(is_running_indexing_state(failed_on_missing_index()["records"][0]))
        without_type = running()["records"][0]
        del without_type["recordType"]
        self.assertFalse(is_running_indexing_state(without_type))
