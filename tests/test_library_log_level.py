import inspect
import logging
import os
from typing import List
from unittest import TestCase, mock

from icloudpd import base
from icloudpd.config import GlobalConfig
from tests.helpers import path_from_project_root, recreate_path, run_cassette


class RecordingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.records: List[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class LibraryLogLevelTestCase(TestCase):
    """--log-level also applies to the iCloud library's own loggers (#1488)"""

    def setUp(self) -> None:
        # Tests that call setup_logger() switch the logger class to IPDLogger, which gives each
        # new logger its own INFO level; the request loggers are created on the first request,
        # so reset them to inherit as they do in a fresh process
        for name, existing in logging.Logger.manager.loggerDict.items():
            if name.startswith("pyicloud_ipd.") and isinstance(existing, logging.Logger):
                existing.setLevel(logging.NOTSET)

    def run_auth(self, log_level: str) -> List[logging.LogRecord]:
        root_path = path_from_project_root(__file__)
        base_dir = os.path.join(root_path, "fixtures", inspect.stack()[1][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        recreate_path(base_dir)
        recreate_path(cookie_dir)

        # A handler on the library's root logger sees what passes the levels set by
        # --log-level, without changing those levels (assertLogs would)
        handler = RecordingHandler()
        library_logger = logging.getLogger("pyicloud_ipd")
        library_logger.addHandler(handler)
        try:
            result = run_cassette(
                os.path.join(root_path, "vcr_cassettes", "auth_non_2fa.yml"),
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "dummy",
                    "--cookie-directory",
                    cookie_dir,
                    "--log-level",
                    log_level,
                    "--auth-only",
                    "--no-progress-bar",
                ],
            )
        finally:
            library_logger.removeHandler(handler)
        self.assertEqual(result.exit_code, 0, result.output)
        return handler.records

    def test_debug_shows_library_debug_lines(self) -> None:
        records = self.run_auth("debug")
        self.assertIn(
            ("pyicloud_ipd.base", logging.DEBUG, "Authenticating as jdoe@gmail.com"),
            [(r.name, r.levelno, r.getMessage()) for r in records],
        )

    def test_debug_keeps_requests_and_session_saving_quiet(self) -> None:
        records = self.run_auth("debug")
        noisy = [
            r
            for r in records
            if r.levelno < logging.INFO
            and (r.name.startswith("pyicloud_ipd.http") or r.name == "pyicloud_ipd.session")
        ]
        self.assertEqual(noisy, [])
        for record in records:
            self.assertNotIn("X-Apple-Session-Token", record.getMessage())

    def test_info_hides_library_debug_lines(self) -> None:
        records = self.run_auth("info")
        self.assertTrue(records)
        self.assertEqual([r for r in records if r.levelno < logging.INFO], [])

    def test_error_hides_library_info_lines(self) -> None:
        records = self.run_auth("error")
        self.assertEqual([r for r in records if r.levelno < logging.ERROR], [])

    def test_request_lines_are_one_group(self) -> None:
        """The per-request lines can still be switched on together, e.g. when developing"""
        http_logger = logging.getLogger("pyicloud_ipd.http")
        create_logger = base.create_logger

        def create_logger_with_requests(config: GlobalConfig) -> logging.Logger:
            logger = create_logger(config)
            http_logger.setLevel(logging.DEBUG)
            return logger

        with mock.patch("icloudpd.base.create_logger", create_logger_with_requests):
            records = self.run_auth("debug")
        requests = [r for r in records if r.name.startswith("pyicloud_ipd.http")]
        self.assertTrue(requests)
        self.assertTrue(all(r.name.startswith("pyicloud_ipd.http.") for r in requests))
