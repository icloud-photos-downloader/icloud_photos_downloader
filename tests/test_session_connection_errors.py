#!/usr/bin/env python3

import os
import socket
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from unittest.mock import MagicMock, patch

from requests import Timeout
from requests.exceptions import ConnectionError
from urllib3.exceptions import NewConnectionError

from pyicloud_ipd.exceptions import PyiCloudConnectionErrorException
from pyicloud_ipd.session import PyiCloudSession


class ConnectionTestHandler(BaseHTTPRequestHandler):
    """HTTP request handler that can simulate various connection errors."""

    error_type: str | None = None

    def do_GET(self) -> None:
        """Handle GET requests - simulate different error types."""
        if self.error_type == "connection_error":
            # Simulate a connection error by closing the connection abruptly
            self.connection.close()
            return
        elif self.error_type == "timeout":
            # Simulate a timeout by sleeping longer than the timeout setting
            time.sleep(2)
            return
        elif self.error_type == "new_connection_error":
            # This will be handled by mocking at a lower level
            pass
        elif self.error_type == "normal":
            # Return a normal response
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"success": true}')
            return

    def do_POST(self) -> None:
        """Handle POST requests the same way as GET."""
        self.do_GET()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: ARG002
        """Suppress server logging."""
        pass


class TestPyiCloudSessionConnectionErrors(unittest.TestCase):
    """Integration test for PyiCloudSession connection error handling."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.server: HTTPServer | None = None
        self.server_thread: threading.Thread | None = None
        self.port = self._find_free_port()
        self.base_url = f"http://localhost:{self.port}"

        # Create a mock service
        self.mock_service = MagicMock()
        self.mock_service.password_filter = None
        self.mock_service.http_timeout = 1  # 1 second timeout for testing
        self.mock_service.session_data = {}

        # Use cross-platform temporary directory
        temp_dir = tempfile.gettempdir()
        self.mock_service.session_path = os.path.join(temp_dir, "test_session.json")
        self.mock_service.cookiejar_path = os.path.join(temp_dir, "test_cookies.jar")

        # Mock the cookies.save method to avoid file operations
        self.session = PyiCloudSession(self.mock_service)
        self.session.cookies.save = MagicMock()  # type: ignore[attr-defined]

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        if self.server:
            self.server.shutdown()
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5)

    def _find_free_port(self) -> int:
        """Find a free port for the test server."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            s.listen(1)
            port: int = s.getsockname()[1]
        return port

    def _start_server(self, error_type: str = "normal") -> None:
        """Start the test HTTP server with specified error behavior."""
        ConnectionTestHandler.error_type = error_type
        self.server = HTTPServer(("localhost", self.port), ConnectionTestHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        # Give the server a moment to start
        time.sleep(0.1)

    def test_normal_request(self) -> None:
        """Test that normal requests work without connection error handling."""
        self._start_server("normal")

        response = self.session.get(self.base_url)
        self.assertEqual(response.status_code, 200)

    def test_connection_error_handling(self) -> None:
        """Test that ConnectionError is wrapped as PyiCloudConnectionErrorException."""
        self._start_server("connection_error")

        with self.assertRaises(PyiCloudConnectionErrorException) as context:
            self.session.get(self.base_url)

        self.assertEqual(str(context.exception), "Cannot connect to Apple iCloud service")
        self.assertIsInstance(context.exception.__cause__, ConnectionError)

    def test_timeout_error_handling(self) -> None:
        """Test that timeout errors are wrapped as PyiCloudConnectionErrorException."""
        self._start_server("timeout")

        with self.assertRaises(PyiCloudConnectionErrorException) as context:
            # Use a short timeout to ensure it times out
            self.session.get(self.base_url, timeout=0.5)

        self.assertEqual(str(context.exception), "Cannot connect to Apple iCloud service")
        # The underlying exception should be a timeout-related error
        self.assertTrue(
            isinstance(context.exception.__cause__, TimeoutError | Timeout)
            or "timeout" in str(context.exception.__cause__).lower()
        )

    def test_builtin_timeout_error_handling(self) -> None:
        """Test that built-in TimeoutError is wrapped as PyiCloudConnectionErrorException."""
        # Mock the underlying request to raise TimeoutError directly
        with patch.object(
            self.session.__class__.__bases__[0], "request", side_effect=TimeoutError("Test timeout")
        ):
            with self.assertRaises(PyiCloudConnectionErrorException) as context:
                self.session.get(self.base_url)

            self.assertEqual(str(context.exception), "Cannot connect to Apple iCloud service")
            self.assertIsInstance(context.exception.__cause__, TimeoutError)

    def test_new_connection_error_handling(self) -> None:
        """Test that NewConnectionError is wrapped as PyiCloudConnectionErrorException."""
        # Mock the underlying request to raise NewConnectionError
        with patch.object(
            self.session.__class__.__bases__[0],
            "request",
            side_effect=NewConnectionError(None, "Test new connection error"),
        ):
            with self.assertRaises(PyiCloudConnectionErrorException) as context:
                self.session.get(self.base_url)

            self.assertEqual(str(context.exception), "Cannot connect to Apple iCloud service")
            self.assertIsInstance(context.exception.__cause__, NewConnectionError)

    def test_other_exceptions_pass_through(self) -> None:
        """Test that other exceptions are not wrapped."""
        # Mock the underlying request to raise ValueError
        with patch.object(
            self.session.__class__.__bases__[0],
            "request",
            side_effect=ValueError("Test other error"),
        ):
            with self.assertRaises(ValueError) as context:
                self.session.get(self.base_url)

            self.assertEqual(str(context.exception), "Test other error")

    def test_all_http_methods_covered(self) -> None:
        """Test that all HTTP methods are covered by the connection error handling."""
        methods_to_test = ["get", "post", "put", "patch", "delete", "head", "options"]

        for method in methods_to_test:
            with (
                self.subTest(method=method),
                patch.object(
                    self.session.__class__.__bases__[0],
                    "request",
                    side_effect=ConnectionError(f"Test {method} connection error"),
                ),
                self.assertRaises(PyiCloudConnectionErrorException) as context,
            ):
                getattr(self.session, method)(self.base_url)

                self.assertEqual(str(context.exception), "Cannot connect to Apple iCloud service")
                self.assertIsInstance(context.exception.__cause__, ConnectionError)


if __name__ == "__main__":
    unittest.main()
