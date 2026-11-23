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
from pyicloud_ipd.exceptions import PyiCloudConnectionErrorException
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

    def close(self) -> None:
        pass


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

    def download(
        self,
        responses: List[Response | Exception],
        temp_suffix: str = ".part",
        icloud_size: int = len(CONTENT),
    ) -> bool:
        self.photo.download.side_effect = responses
        return download_media(
            self.logger,
            False,
            mock.MagicMock(),
            self.photo,
            self.download_path,
            AssetVersion(icloud_size, "https://example.com/file", "public.mpeg-4", CHECKSUM),
            AssetVersionSize.ORIGINAL,
            lambda _photo: "IMG_0001.MOV",
            temp_suffix,
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

    def test_temp_suffix(self) -> None:
        """The file of an interrupted download gets the suffix that was asked for (#1288)"""
        with self.assertLogs(self.logger, level="ERROR"):
            self.download([partial_response(0, 40), partial_response(40, 40)], ".icloudpd")
        self.assertEqual([], self.part_files())
        self.assertEqual(1, len([n for n in os.listdir(self.directory) if n.endswith(".icloudpd")]))

    def test_next_run_resumes_with_the_same_temp_suffix(self) -> None:
        with self.assertLogs(self.logger, level="ERROR"):
            self.download([partial_response(0, 40), partial_response(40, 40)], ".icloudpd")
        self.photo.download.reset_mock()
        self.assertTrue(self.download([partial_response(40, 100)], ".icloudpd"))
        with open(self.download_path, "rb") as file:
            self.assertEqual(CONTENT, file.read())
        self.assertEqual([40], self.starts())
        self.assertEqual(["IMG_0001.MOV"], os.listdir(self.directory))

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

    def test_connection_error_before_the_download_skips_the_file(self) -> None:
        with self.assertLogs(self.logger, level="ERROR") as logs:
            self.assertFalse(
                self.download(
                    [PyiCloudConnectionErrorException("Cannot connect to Apple iCloud service")]
                )
            )
        self.assertFalse(os.path.exists(self.download_path))
        self.assertIn(
            f"Could not connect to iCloud to download {self.download_path}: "
            "Cannot connect to Apple iCloud service",
            logs.output[0],
        )

    def test_connection_error_when_resuming_keeps_the_partial_file(self) -> None:
        with self.assertLogs(self.logger, level="ERROR"):
            self.assertFalse(
                self.download(
                    [
                        dropped_response(0, 40),
                        PyiCloudConnectionErrorException("Cannot connect to Apple iCloud service"),
                    ]
                )
            )
        self.assertFalse(os.path.exists(self.download_path))
        self.assertEqual([0, 40], self.starts())
        [part_file] = self.part_files()
        with open(os.path.join(self.directory, part_file), "rb") as file:
            self.assertEqual(CONTENT[:40], file.read())

    def whole_file_response(self, with_content_range: bool) -> Response:
        response = partial_response(0, 100) if with_content_range else Response()
        if not with_content_range:
            response.status_code = 200
            response.raw = io.BytesIO(CONTENT)
        return response

    def test_resume_starts_over_when_the_whole_file_is_sent(self) -> None:
        """iCloud's CDN can ignore the range of a resume and send the file from byte 0"""
        for with_content_range in (True, False):
            with self.subTest(with_content_range=with_content_range):
                self.setUp()
                with self.assertLogs(self.logger, level="ERROR"):
                    self.download([partial_response(0, 40), partial_response(40, 40)])
                self.photo.download.reset_mock()
                self.assertTrue(self.download([self.whole_file_response(with_content_range)]))
                with open(self.download_path, "rb") as file:
                    self.assertEqual(CONTENT, file.read())
                self.assertEqual([40], self.starts())
                self.assertEqual([], self.part_files())

    def test_resume_with_unexpected_start_keeps_the_partial_file(self) -> None:
        with self.assertLogs(self.logger, level="ERROR"):
            self.download([partial_response(0, 40), partial_response(40, 40)])
        self.photo.download.reset_mock()
        with self.assertLogs(self.logger, level="ERROR") as logs:
            self.assertFalse(self.download([partial_response(20, 100)]))
        self.assertIn(f"Got {self.download_path} from byte 20 instead of 40", logs.output[0])
        self.assertFalse(os.path.exists(self.download_path))
        [part_file] = self.part_files()
        with open(os.path.join(self.directory, part_file), "rb") as file:
            self.assertEqual(CONTENT[:40], file.read())

    def test_unreadable_content_range_on_resume_keeps_the_partial_file(self) -> None:
        with self.assertLogs(self.logger, level="ERROR"):
            self.download([partial_response(0, 40), partial_response(40, 40)])
        self.photo.download.reset_mock()
        response = partial_response(40, 100)
        response.headers["Content-Range"] = "bytes 40-99/*"
        with self.assertLogs(self.logger, level="ERROR") as logs:
            self.assertFalse(self.download([response]))
        self.assertIn(f"Got {self.download_path} from byte unknown instead of 40", logs.output[0])
        self.assertFalse(os.path.exists(self.download_path))

    def test_starts_over_only_once_when_the_range_keeps_being_ignored(self) -> None:
        """A CDN that ignores the range on a dropping connection must not loop forever"""
        with self.assertLogs(self.logger, level="ERROR"):
            self.download([partial_response(0, 40), partial_response(40, 40)])
        self.photo.download.reset_mock()
        with self.assertLogs(self.logger, level="ERROR") as logs:
            self.assertFalse(self.download([dropped_response(0, 60), dropped_response(0, 80)]))
        self.assertEqual([40, 60], self.starts())
        self.assertIn(f"Got {self.download_path} from byte 0 instead of 60", logs.output[0])
        self.assertFalse(os.path.exists(self.download_path))

    def test_resume_answered_206_without_content_range_keeps_the_partial_file(self) -> None:
        """A 206 must say where its body starts; without that it can't be appended or restarted"""
        with self.assertLogs(self.logger, level="ERROR"):
            self.download([partial_response(0, 40), partial_response(40, 40)])
        self.photo.download.reset_mock()
        response = Response()
        response.status_code = 206
        response.raw = io.BytesIO(CONTENT[40:])
        with self.assertLogs(self.logger, level="ERROR") as logs:
            self.assertFalse(self.download([response]))
        self.assertIn(f"Got {self.download_path} from byte unknown instead of 40", logs.output[0])
        self.assertFalse(os.path.exists(self.download_path))
        [part_file] = self.part_files()
        with open(os.path.join(self.directory, part_file), "rb") as file:
            self.assertEqual(CONTENT[:40], file.read())

    def test_restart_that_drops_is_then_resumed(self) -> None:
        with self.assertLogs(self.logger, level="ERROR"):
            self.download([partial_response(0, 40), partial_response(40, 40)])
        self.photo.download.reset_mock()
        self.assertTrue(self.download([dropped_response(0, 20), partial_response(20, 100)]))
        with open(self.download_path, "rb") as file:
            self.assertEqual(CONTENT, file.read())
        self.assertEqual([40, 20], self.starts())
        self.assertEqual([], self.part_files())

    def test_response_is_closed_when_its_body_is_left_unread(self) -> None:
        with self.assertLogs(self.logger, level="ERROR"):
            self.download([partial_response(0, 40), partial_response(40, 40)])
        self.photo.download.reset_mock()
        response = partial_response(20, 100)
        with self.assertLogs(self.logger, level="ERROR"):
            self.assertFalse(self.download([response]))
        self.assertTrue(response.raw.closed)

    def test_file_smaller_than_icloud_says_is_not_saved(self) -> None:
        """Also when the response itself looks complete: the size iCloud lists decides (#1493)"""
        with self.assertLogs(self.logger, level="ERROR") as logs:
            self.assertFalse(self.download([partial_response(0, 100)], icloud_size=120))
        self.assertIn(
            f"{self.download_path} has 100 bytes, but iCloud says it has 120; it wasn't saved "
            "and will be downloaded again on the next run",
            logs.output[0],
        )
        self.assertEqual([], os.listdir(self.directory))

    def test_file_larger_than_icloud_says_is_not_saved(self) -> None:
        with self.assertLogs(self.logger, level="ERROR") as logs:
            self.assertFalse(self.download([self.whole_file_response(False)], icloud_size=80))
        self.assertIn("has 100 bytes, but iCloud says it has 80", logs.output[0])
        self.assertEqual([], os.listdir(self.directory))

    def test_resumed_file_with_the_wrong_size_is_not_saved(self) -> None:
        with self.assertLogs(self.logger, level="ERROR"):
            self.download([partial_response(0, 40), partial_response(40, 40)], icloud_size=120)
        self.photo.download.reset_mock()
        with self.assertLogs(self.logger, level="ERROR") as logs:
            self.assertFalse(self.download([partial_response(40, 100)], icloud_size=120))
        self.assertIn("has 100 bytes, but iCloud says it has 120", logs.output[0])
        self.assertEqual([], os.listdir(self.directory))

    def test_next_run_downloads_again_from_the_start(self) -> None:
        with self.assertLogs(self.logger, level="ERROR"):
            self.download([partial_response(0, 100)], icloud_size=120)
        self.photo.download.reset_mock()
        self.assertTrue(self.download([partial_response(0, 100)]))
        self.assertEqual([0], self.starts())
        self.assertEqual(["IMG_0001.MOV"], os.listdir(self.directory))

    def test_file_without_a_size_from_icloud_is_saved(self) -> None:
        self.assertTrue(self.download([self.whole_file_response(False)], icloud_size=0))
        with open(self.download_path, "rb") as file:
            self.assertEqual(CONTENT, file.read())
