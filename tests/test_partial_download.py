"""Downloads that end before the whole file has arrived (#1311)

iCloud sends a Content-Range such as `bytes 0-99/100` with every download, also with
status 200. A response that ends before that size, or a connection that drops halfway,
must not be saved as the complete file: the rest is requested from where it stopped, and
if no more data arrives the partial file is kept for the next run.
"""

import base64
import datetime
import io
import logging
import os
import tempfile
from typing import Iterator, List
from unittest import TestCase, mock

from requests import Response
from urllib3.exceptions import ProtocolError

from icloudpd.download import download_media
from pyicloud_ipd.asset_version import AssetVersion
from pyicloud_ipd.version_size import AssetVersionSize

CONTENT = bytes(range(100))
CHECKSUM = base64.b64encode(b"partial-download-test").decode()


def partial_response(start: int, end: int, total: int = len(CONTENT)) -> Response:
    response = Response()
    response.status_code = 200
    response.headers["Content-Range"] = f"bytes {start}-{end - 1}/{total}"
    response.raw = io.BytesIO(CONTENT[start:end])
    return response


class DroppedStream:
    """A response body that delivers some bytes and then loses the connection"""

    def __init__(self, data: bytes) -> None:
        self.data = data

    def stream(self, chunk_size: int, decode_content: bool) -> Iterator[bytes]:
        yield self.data
        raise ProtocolError("Connection broken: IncompleteRead")


def dropped_response(start: int, end: int, total: int = len(CONTENT)) -> Response:
    response = partial_response(start, total, total)
    response.raw = DroppedStream(CONTENT[start:end])
    return response


class PartialDownloadTestCase(TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.mkdtemp()
        self.download_path = os.path.join(self.directory, "IMG_0001.MOV")
        self.logger = logging.getLogger("icloudpd-test-partial-download")
        self.photo = mock.MagicMock()
        self.photo.created = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)

    def download(self, responses: List[Response]) -> bool:
        self.photo.download.side_effect = responses
        return download_media(
            self.logger,
            False,
            mock.MagicMock(),
            self.photo,
            self.download_path,
            AssetVersion(len(CONTENT), "https://example.com/file", "public.mpeg-4", CHECKSUM),
            AssetVersionSize.ORIGINAL,
            lambda _photo: "IMG_0001.MOV",
        )

    def starts(self) -> List[int]:
        return [call.args[2] for call in self.photo.download.call_args_list]

    def part_files(self) -> List[str]:
        return [name for name in os.listdir(self.directory) if name.endswith(".part")]

    def test_rest_is_requested_until_complete(self) -> None:
        self.assertTrue(
            self.download(
                [partial_response(0, 40), partial_response(40, 70), partial_response(70, 100)]
            )
        )
        with open(self.download_path, "rb") as file:
            self.assertEqual(CONTENT, file.read())
        self.assertEqual([0, 40, 70], self.starts())
        self.assertEqual([], self.part_files())

    def test_partial_file_is_kept_when_no_more_data_arrives(self) -> None:
        with self.assertLogs(self.logger, level="ERROR") as logs:
            self.assertFalse(self.download([partial_response(0, 40), partial_response(40, 40)]))
        self.assertFalse(os.path.exists(self.download_path))
        self.assertIn(
            f"Could not download all of {self.download_path} (40 of 100 bytes)", logs.output[0]
        )
        [part_file] = self.part_files()
        with open(os.path.join(self.directory, part_file), "rb") as file:
            self.assertEqual(CONTENT[:40], file.read())

    def test_next_run_resumes_the_partial_file(self) -> None:
        with self.assertLogs(self.logger, level="ERROR"):
            self.download([partial_response(0, 40), partial_response(40, 40)])
        self.photo.download.reset_mock()
        self.assertTrue(self.download([partial_response(40, 100)]))
        with open(self.download_path, "rb") as file:
            self.assertEqual(CONTENT, file.read())
        self.assertEqual([40], self.starts())

    def test_whole_file_in_one_partial_response(self) -> None:
        self.assertTrue(self.download([partial_response(0, 100)]))
        with open(self.download_path, "rb") as file:
            self.assertEqual(CONTENT, file.read())
        self.assertEqual([0], self.starts())

    def test_dropped_connection_is_resumed(self) -> None:
        self.assertTrue(self.download([dropped_response(0, 40), partial_response(40, 100)]))
        with open(self.download_path, "rb") as file:
            self.assertEqual(CONTENT, file.read())
        self.assertEqual([0, 40], self.starts())

    def test_dropped_connection_without_data_keeps_the_partial_file(self) -> None:
        with self.assertLogs(self.logger, level="ERROR") as logs:
            self.assertFalse(self.download([dropped_response(0, 40), dropped_response(40, 40)]))
        self.assertFalse(os.path.exists(self.download_path))
        self.assertIn(f"Connection lost while downloading {self.download_path}", logs.output[0])
        [part_file] = self.part_files()
        with open(os.path.join(self.directory, part_file), "rb") as file:
            self.assertEqual(CONTENT[:40], file.read())
