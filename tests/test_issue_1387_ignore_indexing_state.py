"""Test for issue #1387: `--ignore-indexing-state`

https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/1387

iCloud can keep answering RUNNING to the CheckIndexingState query for a library that lists
normally, so the retries from #1388 never see FINISHED. With the option, the run continues
when every answer was a well-formed RUNNING record, and warns that the listing may be
incomplete. Any other answer stops the run as without the option.
"""

import inspect
import logging
import os
from typing import Any, Dict, List
from unittest import TestCase, mock

import pytest

from icloudpd.authentication import authenticator
from icloudpd.base import core_single_run, lp_filename_concatinator
from icloudpd.cli import parse
from icloudpd.mfa_provider import MFAProvider
from icloudpd.status import StatusExchange
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.exceptions import PyiCloudServiceNotActivatedException
from pyicloud_ipd.services import photos
from pyicloud_ipd.services.photos import PhotoLibrary, PhotosService
from tests.helpers import path_from_project_root, run_icloudpd_test, run_main
from tests.test_issue_1387_indexing_state_retry import indexing_state_response

ZONE_ID = {"zoneName": "PrimarySync", "zoneType": "REGULAR_CUSTOM_ZONE"}
ATTEMPTS = photos.INDEXING_STATE_ATTEMPTS


def session_returning_responses(responses: List[Dict[str, Any]]) -> mock.MagicMock:
    session = mock.MagicMock()
    session.post.side_effect = [mock.MagicMock(**{"json.return_value": r}) for r in responses]
    return session


def make_library(responses: List[Dict[str, Any]], ignore_indexing_state: bool) -> mock.MagicMock:
    session = session_returning_responses(responses)
    PhotoLibrary(
        "https://example.com/endpoint",
        {},
        session,
        zone_id=ZONE_ID,
        library_type="private",
        ignore_indexing_state=ignore_indexing_state,
    )
    return session


def running() -> Dict[str, Any]:
    return indexing_state_response("RUNNING")


def running_with_record_type(record_type: str) -> Dict[str, Any]:
    response = running()
    response["records"][0]["recordType"] = record_type
    return response


@mock.patch("pyicloud_ipd.services.photos.time.sleep")
class Issue1387IgnoreIndexingStateTest(TestCase):
    def test_continues_and_warns_when_always_running(self, sleep: mock.MagicMock) -> None:
        with self.assertLogs("pyicloud_ipd.services.photos", level="WARNING") as logs:
            session = make_library([running()] * ATTEMPTS, ignore_indexing_state=True)
        self.assertEqual(session.post.call_count, ATTEMPTS)
        self.assertEqual(sleep.call_count, ATTEMPTS - 1)
        self.assertEqual(len(logs.records), 1)
        self.assertEqual(logs.records[0].levelname, "WARNING")
        self.assertIn("PrimarySync is still reported as indexing", logs.output[0])
        self.assertIn(f"RUNNING on all {ATTEMPTS} checks", logs.output[0])
        self.assertIn("the listing may be incomplete", logs.output[0])

    def test_marks_the_library_when_the_state_was_ignored(self, sleep: mock.MagicMock) -> None:
        session = session_returning_responses([running()] * ATTEMPTS)
        library = PhotoLibrary(
            "https://example.com/endpoint",
            {},
            session,
            zone_id=ZONE_ID,
            library_type="private",
            ignore_indexing_state=True,
        )
        self.assertTrue(library.indexing_state_ignored)

    def test_does_not_mark_the_library_when_finished(self, sleep: mock.MagicMock) -> None:
        session = session_returning_responses([running(), indexing_state_response("FINISHED")])
        library = PhotoLibrary(
            "https://example.com/endpoint",
            {},
            session,
            zone_id=ZONE_ID,
            library_type="private",
            ignore_indexing_state=True,
        )
        self.assertFalse(library.indexing_state_ignored)

    def test_raises_when_always_running_without_option(self, sleep: mock.MagicMock) -> None:
        with self.assertRaises(PyiCloudServiceNotActivatedException) as context:
            make_library([running()] * ATTEMPTS, ignore_indexing_state=False)
        self.assertIn("has not finished indexing yet", str(context.exception))

    def test_raises_on_another_state_among_running(self, sleep: mock.MagicMock) -> None:
        for position in [0, ATTEMPTS // 2, ATTEMPTS - 1]:
            for state in ["FAILED", "UNKNOWN", ""]:
                with self.subTest(position=position, state=state):
                    responses = [running()] * ATTEMPTS
                    responses[position] = indexing_state_response(state)
                    with self.assertRaises(PyiCloudServiceNotActivatedException):
                        make_library(responses, ignore_indexing_state=True)

    def test_raises_on_another_record_type_among_running(self, sleep: mock.MagicMock) -> None:
        responses = [running()] * ATTEMPTS
        responses[3] = running_with_record_type("SomethingElse")
        with self.assertRaises(PyiCloudServiceNotActivatedException):
            make_library(responses, ignore_indexing_state=True)

    def test_raises_on_missing_record_type_among_running(self, sleep: mock.MagicMock) -> None:
        responses = [running()] * ATTEMPTS
        without_record_type = running()
        del without_record_type["records"][0]["recordType"]
        responses[3] = without_record_type
        with self.assertRaises(PyiCloudServiceNotActivatedException):
            make_library(responses, ignore_indexing_state=True)

    def test_malformed_answer_stops_the_run(self, sleep: mock.MagicMock) -> None:
        malformed: List[Dict[str, Any]] = [
            {"records": []},
            {"records": [{"recordType": "CheckIndexingState", "fields": {}}]},
            {"serverErrorCode": "ATOMIC_ERROR", "reason": "Atomic failure"},
        ]
        for answer in malformed:
            with self.subTest(answer=answer):
                responses = [running(), answer] + [running()] * (ATTEMPTS - 2)
                with self.assertRaises((KeyError, IndexError)):
                    make_library(responses, ignore_indexing_state=True)

    def test_finished_continues_without_warning(self, sleep: mock.MagicMock) -> None:
        for ignore_indexing_state in [True, False]:
            with self.subTest(ignore_indexing_state=ignore_indexing_state):
                with self.assertNoLogs("pyicloud_ipd.services.photos", level="WARNING"):
                    session = make_library(
                        [running(), running(), indexing_state_response("FINISHED")],
                        ignore_indexing_state=ignore_indexing_state,
                    )
                self.assertEqual(session.post.call_count, 3)


class IgnoreIndexingStatePassedDownTest(TestCase):
    def test_photos_service_passes_option_to_libraries(self) -> None:
        session = mock.MagicMock()
        session.post.return_value.json.side_effect = [
            indexing_state_response("FINISHED"),
            {"zones": [{"zoneID": {"zoneName": "SharedSync-1234"}}]},
            indexing_state_response("FINISHED"),
        ]
        service = PhotosService("https://example.com", session, {}, ignore_indexing_state=True)
        self.assertTrue(service.ignore_indexing_state)
        self.assertTrue(service.shared_libraries["SharedSync-1234"].ignore_indexing_state)

    def test_photos_service_default_is_off(self) -> None:
        session = mock.MagicMock()
        session.post.return_value.json.return_value = indexing_state_response("FINISHED")
        self.assertFalse(PhotosService("https://example.com", session, {}).ignore_indexing_state)

    def test_icloud_service_passes_option_to_photos(self) -> None:
        for ignore_indexing_state in [True, False]:
            with self.subTest(ignore_indexing_state=ignore_indexing_state):
                service = mock.MagicMock()
                service._photos = None
                service.ignore_indexing_state = ignore_indexing_state
                with mock.patch("pyicloud_ipd.base.PhotosService") as photos_service:
                    PyiCloudService.photos.fget(service)  # type: ignore[attr-defined]
                self.assertEqual(
                    photos_service.call_args.kwargs,
                    {"ignore_indexing_state": ignore_indexing_state},
                )


class IgnoreIndexingStateCliTest(TestCase):
    USER = ["--username", "jdoe@gmail.com", "--password", "password1", "-d", "/tmp"]

    def test_option_alone_parses(self) -> None:
        _, configs = parse([*self.USER, "--ignore-indexing-state"])
        self.assertTrue(configs[0].ignore_indexing_state)

    def test_option_is_off_by_default(self) -> None:
        _, configs = parse(self.USER)
        self.assertFalse(configs[0].ignore_indexing_state)

    def test_option_before_username_applies_to_every_user(self) -> None:
        _, configs = parse(
            ["--ignore-indexing-state", "-d", "/tmp", "--username", "u1", "--username", "u2"]
        )
        self.assertEqual([c.ignore_indexing_state for c in configs], [True, True])

    def test_rejected_with_deleting_options(self) -> None:
        deleting_options = [
            ["--auto-delete"],
            ["--delete-after-download"],
            ["--keep-icloud-recent-days", "30"],
            ["--keep-icloud-recent-days", "0"],
            ["--prune-orphans", "--library", "SharedSync-1234"],
        ]
        for deleting in deleting_options:
            for options in [
                [*self.USER, "--ignore-indexing-state", *deleting],
                # given as a default before the first --username
                ["--ignore-indexing-state", *deleting, *self.USER],
            ]:
                with self.subTest(options=options):
                    with mock.patch("icloudpd.cli.run_with_configs") as run_with_configs:
                        result = run_main(options)
                    self.assertEqual(result.exit_code, 2, "exit code")
                    self.assertIn(
                        "--ignore-indexing-state cannot be combined with --auto-delete, "
                        "--delete-after-download, --keep-icloud-recent-days or --prune-orphans",
                        result.output,
                    )
                    run_with_configs.assert_not_called()

    def test_rejected_when_only_one_configuration_deletes(self) -> None:
        with mock.patch("icloudpd.cli.run_with_configs") as run_with_configs:
            result = run_main(
                [
                    *["-d", "/tmp", "--username", "u1", "--ignore-indexing-state"],
                    *["--username", "u2", "--auto-delete"],
                    *["--username", "u3", "--ignore-indexing-state", "--auto-delete"],
                ]
            )
        self.assertEqual(result.exit_code, 2, "exit code")
        run_with_configs.assert_not_called()

    def test_option_alone_is_not_rejected(self) -> None:
        with mock.patch("icloudpd.cli.run_with_configs", return_value=0) as run_with_configs:
            result = run_main([*self.USER, "--ignore-indexing-state", "--dry-run"])
        self.assertEqual(result.exit_code, 0, "exit code")
        run_with_configs.assert_called_once()
        self.assertTrue(run_with_configs.call_args.args[1][0].ignore_indexing_state)

    def test_authenticator_passes_option_to_icloud_service(self) -> None:
        for ignore_indexing_state in [True, False]:
            with self.subTest(ignore_indexing_state=ignore_indexing_state):
                with mock.patch("icloudpd.authentication.PyiCloudService") as service_class:
                    service_class.return_value.requires_2fa = False
                    service_class.return_value.requires_2sa = False
                    authenticator(
                        logging.getLogger("test"),
                        "com",
                        {},
                        MFAProvider.CONSOLE,
                        StatusExchange(),
                        "user",
                        lambda: None,
                        ignore_indexing_state=ignore_indexing_state,
                    )
                self.assertEqual(
                    service_class.call_args.kwargs["ignore_indexing_state"],
                    ignore_indexing_state,
                )

    def test_run_passes_option_to_authenticator(self) -> None:
        global_config, configs = parse([*self.USER, "--ignore-indexing-state", "--auth-only"])
        with mock.patch("icloudpd.base.authenticator") as mocked_authenticator:
            core_single_run(
                logging.getLogger("test"),
                StatusExchange(),
                global_config,
                configs[0],
                {},
                lambda _photo: True,
                mock.MagicMock(),
                lambda: None,
                lp_filename_concatinator,
            )
        self.assertTrue(mocked_authenticator.call_args.args[-1])


class IgnoreIndexingStateEndOfRunTest(TestCase):
    """The last line of a run must not claim a complete download when the state was ignored"""

    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

    def run_with_ignored_state(self, base_dir: str, extra: List[str]) -> Any:
        original_init = PhotoLibrary.__init__

        # the recorded responses say FINISHED; mark the library as if every check had
        # answered RUNNING and the option let the run continue
        def init_with_ignored_state(self: PhotoLibrary, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)
            self.indexing_state_ignored = self.ignore_indexing_state

        with mock.patch.object(PhotoLibrary, "__init__", init_with_ignored_state):
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

    def test_end_of_run_says_the_listing_may_be_incomplete(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        result = self.run_with_ignored_state(base_dir, ["--ignore-indexing-state"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn(
            "All photos and videos that iCloud listed have been downloaded, but the listing "
            "may be incomplete",
            result.output,
        )
        self.assertIn("A later run without the option picks up what is missing", result.output)
        self.assertNotIn("All photos and videos have been downloaded", result.output)

    def test_end_of_run_unchanged_without_option(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        result = self.run_with_ignored_state(base_dir, [])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("All photos and videos have been downloaded", result.output)
        self.assertNotIn("the listing may be incomplete", result.output)
