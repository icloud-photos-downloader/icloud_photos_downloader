import logging
import os
import tempfile
from unittest import TestCase, mock

import waitress

from icloudpd.activity import ActivityLog
from icloudpd.server import serve_app
from icloudpd.status import StatusExchange


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


class ActivityApiTestCase(TestCase):
    def test_api_status_and_activity(self) -> None:
        captured = {}
        with mock.patch.object(waitress, "serve", lambda app, **kw: captured.setdefault("app", app)):
            serve_app(logging.getLogger("test"), StatusExchange())
        client = captured["app"].test_client()

        status = client.get("/api/status").get_json()
        self.assertIn("downloaded_total", status)

        activity = client.get("/api/activity").get_json()
        self.assertEqual(set(activity), {"total", "files"})
        self.assertIsInstance(activity["files"], list)
