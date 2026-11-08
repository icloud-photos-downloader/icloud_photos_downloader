import logging
import os
import tempfile
from typing import Any, Tuple
from unittest import TestCase, mock

import waitress

from icloudpd.activity import ActivityLog, activity_log
from icloudpd.cli import parse
from icloudpd.server import serve_app
from icloudpd.status import Status, StatusExchange


def make_client(api: bool, with_config: bool = True) -> Tuple[StatusExchange, Any]:
    exchange = StatusExchange()
    if with_config:
        global_config, _ = parse((["--webui-api"] if api else []) + ["-d", "/x", "-u", "a@b.c"])
        exchange.set_global_config(global_config)
    captured: dict[str, Any] = {}
    with mock.patch.object(waitress, "serve", lambda app, **kwargs: captured.setdefault("app", app)):
        serve_app(logging.getLogger("test"), exchange)
    return exchange, captured["app"].test_client()


class WebuiApiOptionTestCase(TestCase):
    def test_off_by_default(self) -> None:
        global_config, _ = parse(["-d", "/x", "-u", "a@b.c"])
        self.assertFalse(global_config.webui_api)

    def test_option_is_parsed(self) -> None:
        global_config, _ = parse(["--webui-api", "-d", "/x", "-u", "a@b.c"])
        self.assertTrue(global_config.webui_api)


class StatusApiTestCase(TestCase):
    def test_endpoints_do_not_exist_without_the_option(self) -> None:
        _, client = make_client(api=False)
        self.assertEqual(client.get("/api/status").status_code, 404)
        self.assertEqual(client.get("/api/activity").status_code, 404)

    def test_endpoints_do_not_exist_before_the_configuration_is_known(self) -> None:
        _, client = make_client(api=True, with_config=False)
        self.assertEqual(client.get("/api/status").status_code, 404)

    def test_the_web_ui_pages_are_not_affected(self) -> None:
        _, client = make_client(api=False)
        self.assertEqual(client.post("/resume").status_code, 200)

    def test_idle(self) -> None:
        _, client = make_client(api=True)
        answer = client.get("/api/status").get_json()
        self.assertEqual(answer["state"], "idle")
        self.assertEqual(answer["status"], "no_input_needed")
        self.assertEqual(
            set(answer["progress"]),
            {"photos_count", "photos_counter", "photos_percent", "last_message", "waiting_seconds"},
        )

    def test_syncing_reports_the_progress(self) -> None:
        exchange, client = make_client(api=True)
        progress = exchange.get_progress()
        progress.photos_count = 40
        progress.photos_counter = 10
        answer = client.get("/api/status").get_json()
        self.assertEqual(answer["state"], "syncing")
        self.assertEqual(answer["progress"]["photos_percent"], 25)
        self.assertEqual(answer["progress"]["photos_counter"], 10)

    def test_waiting_reports_the_time_to_the_next_run(self) -> None:
        exchange, client = make_client(api=True)
        exchange.get_progress().waiting = 3600
        answer = client.get("/api/status").get_json()
        self.assertEqual(answer["state"], "waiting")
        self.assertEqual(answer["progress"]["waiting_seconds"], 3600)

    def test_waiting_for_input(self) -> None:
        exchange, client = make_client(api=True)
        exchange.replace_status(Status.NO_INPUT_NEEDED, Status.NEED_MFA)
        self.assertEqual(client.get("/api/status").get_json()["state"], "need_mfa")

    def test_the_apple_id_is_not_part_of_the_answer(self) -> None:
        exchange, client = make_client(api=True)
        exchange.set_current_user("someone@example.com")
        answer = client.get("/api/status")
        self.assertNotIn(b"someone@example.com", answer.data)
        self.assertNotIn("current_user", answer.get_json())

    def test_activity_lists_the_downloaded_files_newest_first(self) -> None:
        _, client = make_client(api=True)
        before = activity_log.total
        with tempfile.TemporaryDirectory() as directory:
            first = os.path.join(directory, "first.heic")
            second = os.path.join(directory, "second.heic")
            for path, size in ((first, 5), (second, 10)):
                with open(path, "wb") as f:
                    f.write(b"x" * size)
            activity_log.record_download(first)
            activity_log.record_download(second)
        answer = client.get("/api/activity").get_json()
        self.assertEqual(answer["total"], before + 2)
        self.assertEqual([f["name"] for f in answer["files"][:2]], ["second.heic", "first.heic"])
        self.assertEqual([f["size"] for f in answer["files"][:2]], [10, 5])
        self.assertEqual(client.get("/api/status").get_json()["downloaded_total"], before + 2)


class ActivityLogTestCase(TestCase):
    def test_records_newest_first_with_size(self) -> None:
        log = ActivityLog()
        with tempfile.TemporaryDirectory() as directory:
            first = os.path.join(directory, "a.heic")
            second = os.path.join(directory, "b.mov")
            with open(first, "wb") as f:
                f.write(b"12345")
            with open(second, "wb") as f:
                f.write(b"1234567890")
            log.record_download(first)
            log.record_download(second)
        files = log.snapshot()
        self.assertEqual([f["name"] for f in files], ["b.mov", "a.heic"])
        self.assertEqual([f["size"] for f in files], [10, 5])
        self.assertEqual(log.total, 2)

    def test_missing_file_has_no_size(self) -> None:
        log = ActivityLog()
        log.record_download("/nonexistent/x.jpg")
        self.assertIsNone(log.snapshot()[0]["size"])

    def test_keeps_only_the_newest_entries_but_counts_all(self) -> None:
        log = ActivityLog(maxlen=3)
        for i in range(5):
            log.record_download(f"/nonexistent/{i}.jpg")
        self.assertEqual([f["name"] for f in log.snapshot()], ["4.jpg", "3.jpg", "2.jpg"])
        self.assertEqual(log.total, 5)

    def test_snapshot_limit(self) -> None:
        log = ActivityLog()
        for i in range(10):
            log.record_download(f"/nonexistent/{i}.jpg")
        self.assertEqual(len(log.snapshot(limit=4)), 4)
