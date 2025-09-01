import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import requests
from requests import Response

from foundation.http import is_streaming_response, response_to_har_entry


class TestHttpUtils(unittest.TestCase):
    """Test HTTP utility functions"""

    def test_is_streaming_response_with_closed_connection(self) -> None:
        """Test that is_streaming_response returns False for closed connections"""
        response = Mock(spec=Response)
        response.raw = Mock()
        response.raw.isclosed.return_value = True

        result = is_streaming_response(response)

        self.assertFalse(result)

    def test_is_streaming_response_with_open_connection(self) -> None:
        """Test that is_streaming_response returns True for open connections"""
        response = Mock(spec=Response)
        response.raw = Mock()
        response.raw.isclosed.return_value = False

        result = is_streaming_response(response)

        self.assertTrue(result)

    def test_is_streaming_response_with_no_raw_attribute(self) -> None:
        """Test that is_streaming_response returns False when raw attribute is missing"""
        response = Mock(spec=Response)
        # Don't set raw attribute

        result = is_streaming_response(response)

        self.assertFalse(result)

    def test_is_streaming_response_with_exception(self) -> None:
        """Test that is_streaming_response returns False when exception occurs"""
        response = Mock(spec=Response)
        response.raw = Mock()
        response.raw.isclosed.side_effect = Exception("Connection error")

        result = is_streaming_response(response)

        self.assertFalse(result)

    def test_response_to_har_entry_with_json_response(self) -> None:
        """Test that response_to_har_entry creates content node for JSON responses"""
        # Create mock request and response
        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.url = "https://example.com/api"
        mock_request.headers = {"Accept": "application/json"}
        mock_request.body = None

        response = Mock(spec=Response)
        response.request = mock_request
        response.status_code = 200
        response.headers = {"Content-Type": "application/json"}
        response.cookies = []
        response.raw = Mock()
        response.raw.isclosed.return_value = True  # Non-streaming response
        response.json.return_value = {"result": "success"}

        har_entry = response_to_har_entry(response)

        self.assertIn("response", har_entry)
        self.assertIn("content", har_entry["response"])
        self.assertEqual(har_entry["response"]["content"], {"result": "success"})

    def test_response_to_har_entry_with_stream_response(self) -> None:
        """Test that response_to_har_entry skips content node for stream responses"""
        # Create mock request and response
        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.url = "https://example.com/stream"
        mock_request.headers = {"Accept": "*/*"}
        mock_request.body = None

        response = Mock(spec=Response)
        response.request = mock_request
        response.status_code = 200
        response.headers = {"Content-Type": "application/octet-stream"}
        response.cookies = []
        response.raw = Mock()
        response.raw.isclosed.return_value = False  # Streaming response

        har_entry = response_to_har_entry(response)

        self.assertIn("response", har_entry)
        self.assertIn("content", har_entry["response"])
        self.assertIsNone(har_entry["response"]["content"])


class HttpTestRequestHandler(BaseHTTPRequestHandler):
    """Test HTTP request handler for local server"""

    def log_message(self, format: str, *args: Any) -> None:  # noqa: ARG002
        """Suppress server log messages during tests"""
        pass

    def do_GET(self) -> None:
        if self.path == "/json":
            # JSON response
            response_data = {"message": "Hello, World!", "status": "success", "data": [1, 2, 3]}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode())

        elif self.path == "/text":
            # Plain text response
            response_text = "This is a plain text response for testing purposes."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(response_text.encode())

        elif self.path.startswith("/stream"):
            # Streaming binary response with optional size parameter
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)

            # Get size parameter (in MB), default to 5 chunks of ~100 bytes each (~500 bytes total)
            size_mb = float(query_params.get("size_mb", [0.0005])[0])  # Default ~500 bytes

            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()

            # Calculate chunks: each chunk is ~1MB for large sizes, or smaller for tiny sizes
            if size_mb >= 1:
                chunk_size_bytes = 1024 * 1024  # 1MB per chunk for large streams
                num_chunks = int(size_mb)
                remainder_bytes = int((size_mb - num_chunks) * 1024 * 1024)
            else:
                # For small sizes, use the original logic
                chunk_size_bytes = 100  # 100 bytes per chunk
                num_chunks = max(1, int(size_mb * 1024 * 1024 / chunk_size_bytes))
                remainder_bytes = 0

            # Send data in chunks, handle client disconnections gracefully
            try:
                for i in range(num_chunks):
                    chunk_data = f"chunk_{i}_".encode() + b"x" * (
                        chunk_size_bytes - len(f"chunk_{i}_".encode())
                    )
                    chunk_size_hex = hex(len(chunk_data))[2:].encode()
                    self.wfile.write(chunk_size_hex + b"\r\n" + chunk_data + b"\r\n")
                    self.wfile.flush()

                # Send remainder if any
                if remainder_bytes > 0:
                    chunk_data = b"remainder_" + b"x" * (remainder_bytes - len(b"remainder_"))
                    chunk_size_hex = hex(len(chunk_data))[2:].encode()
                    self.wfile.write(chunk_size_hex + b"\r\n" + chunk_data + b"\r\n")
                    self.wfile.flush()

                # End chunked transfer
                self.wfile.write(b"0\r\n\r\n")
            except (ConnectionResetError, BrokenPipeError, OSError):
                # Client closed connection early - this is expected for streaming tests
                # where we don't read all the data
                pass

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")


class TestHttpIntegration(unittest.TestCase):
    """Integration tests using real HTTP server"""

    server: HTTPServer
    port: int
    base_url: str
    server_thread: threading.Thread

    @classmethod
    def setUpClass(cls) -> None:
        """Start test server"""
        cls.server = HTTPServer(("localhost", 0), HttpTestRequestHandler)
        cls.port = cls.server.server_port
        cls.base_url = f"http://localhost:{cls.port}"

        # Start server in background thread
        cls.server_thread = threading.Thread(target=cls.server.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()

        # Wait for server to start
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        """Stop test server"""
        cls.server.shutdown()
        cls.server.server_close()

    def test_response_to_har_entry_with_real_json_response(self) -> None:
        """Test response_to_har_entry with real JSON response"""
        response = requests.get(f"{self.base_url}/json")

        har_entry = response_to_har_entry(response)

        # Verify structure
        self.assertIn("request", har_entry)
        self.assertIn("response", har_entry)

        # Verify request details
        self.assertEqual(har_entry["request"]["method"], "GET")
        self.assertIn("/json", har_entry["request"]["url"])

        # Verify response details
        self.assertEqual(har_entry["response"]["status_code"], 200)
        self.assertIn("content", har_entry["response"])

        # Verify JSON content is parsed correctly
        expected_content = {"message": "Hello, World!", "status": "success", "data": [1, 2, 3]}
        self.assertEqual(har_entry["response"]["content"], expected_content)

        # Verify it's not a streaming response
        self.assertFalse(is_streaming_response(response))

    def test_response_to_har_entry_with_real_text_response(self) -> None:
        """Test response_to_har_entry with real text response"""
        response = requests.get(f"{self.base_url}/text")

        har_entry = response_to_har_entry(response)

        # Verify structure
        self.assertIn("request", har_entry)
        self.assertIn("response", har_entry)

        # Verify request details
        self.assertEqual(har_entry["request"]["method"], "GET")
        self.assertIn("/text", har_entry["request"]["url"])

        # Verify response details
        self.assertEqual(har_entry["response"]["status_code"], 200)
        self.assertIn("content", har_entry["response"])

        # Verify text content is included
        expected_content = "This is a plain text response for testing purposes."
        self.assertEqual(har_entry["response"]["content"], expected_content)

        # Verify it's not a streaming response
        self.assertFalse(is_streaming_response(response))

    def test_response_to_har_entry_with_real_streaming_response(self) -> None:
        """Test response_to_har_entry with real streaming binary response"""
        response = requests.get(f"{self.base_url}/stream", stream=True)

        har_entry = response_to_har_entry(response)

        # Verify structure
        self.assertIn("request", har_entry)
        self.assertIn("response", har_entry)

        # Verify request details
        self.assertEqual(har_entry["request"]["method"], "GET")
        self.assertIn("/stream", har_entry["request"]["url"])

        # Verify response details
        self.assertEqual(har_entry["response"]["status_code"], 200)
        self.assertIn("content", har_entry["response"])

        # Verify streaming response has no content in HAR entry
        self.assertIsNone(har_entry["response"]["content"])

        # Verify it is detected as a streaming response
        self.assertTrue(is_streaming_response(response))

        # Clean up the response connection
        response.close()

    def test_streaming_vs_non_streaming_behavior(self) -> None:
        """Test the difference between streaming and non-streaming requests to same endpoint"""
        # Non-streaming request
        response_normal = requests.get(f"{self.base_url}/json")
        har_normal = response_to_har_entry(response_normal)

        # Streaming request to same endpoint
        response_stream = requests.get(f"{self.base_url}/json", stream=True)
        har_stream = response_to_har_entry(response_stream)

        # Normal response should have content
        self.assertIsNotNone(har_normal["response"]["content"])
        self.assertEqual(har_normal["response"]["content"]["message"], "Hello, World!")
        self.assertFalse(is_streaming_response(response_normal))

        # Streaming response should have no content
        self.assertIsNone(har_stream["response"]["content"])
        self.assertTrue(is_streaming_response(response_stream))

        # Clean up streaming response
        response_stream.close()

    def test_response_to_har_entry_with_large_streaming_response(self) -> None:
        """Test response_to_har_entry with multi-GB streaming response to verify no memory leaks"""
        # Request a 200.5GB stream (large enough to cause memory issues if not handled properly)
        size_gb = 200.5
        response = requests.get(f"{self.base_url}/stream?size_mb={size_gb * 1024}", stream=True)

        # This should complete quickly without loading all data into memory
        start_time = time.time()
        har_entry = response_to_har_entry(response)
        end_time = time.time()

        # Should complete in well under a second since we don't load the content
        self.assertLess(
            end_time - start_time, 1.0, "HAR entry creation took too long, possible memory leak"
        )

        # Verify structure
        self.assertIn("request", har_entry)
        self.assertIn("response", har_entry)

        # Verify request details
        self.assertEqual(har_entry["request"]["method"], "GET")
        self.assertIn("/stream", har_entry["request"]["url"])
        self.assertIn(f"size_mb={size_gb * 1024}", har_entry["request"]["url"])

        # Verify response details
        self.assertEqual(har_entry["response"]["status_code"], 200)
        self.assertIn("content", har_entry["response"])

        # Most importantly: streaming response should have NO content in HAR entry
        # This proves we didn't try to load 200.5GB into memory
        self.assertIsNone(har_entry["response"]["content"])

        # Verify it is detected as a streaming response
        self.assertTrue(is_streaming_response(response))

        # Clean up the response connection (important for large streams)
        response.close()


if __name__ == "__main__":
    unittest.main()
