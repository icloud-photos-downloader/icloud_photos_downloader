"""--set-exif-datetime and the name-size check (#380)

Writing the date into a JPEG that has none makes the local file a little larger than the
one in iCloud. The next run used to take it for a different photo with the same name and
download it again as IMG_1234-<size>.JPG. A JPEG that is slightly larger and holds
exactly the date icloudpd would write is now recognised as the same photo.
"""

import inspect
import logging
import os
import struct
import tempfile
from typing import List, Sequence, Tuple
from unittest import TestCase, mock

import piexif

from icloudpd.exif_datetime import MAX_DATE_TAGS_SIZE, has_own_exif_date
from tests.helpers import path_from_project_root, run_icloudpd_test

# IMG_7409.JPG in listing_photos.yml: created 2018-07-31 07:22:24 UTC, 1884695 bytes in iCloud
ICLOUD_SIZE = 1884695
OWN_DATE = "2018:07:31 07:22:24"


def jpeg_with_date(date: str | None, size: int) -> bytes:
    """A JPEG of the given size whose DateTimeOriginal is date (none when date is None)"""
    exif: bytes = piexif.dump(
        {"Exif": {piexif.ExifIFD.DateTimeOriginal: date.encode()}} if date else {}
    )
    data = b"\xff\xd8\xff\xe1" + struct.pack(">H", len(exif) + 2) + exif
    data += b"\xff\xda\x00\x02\xff\xd9"
    return data + b"\x00" * (size - len(data))


class HasOwnExifDateTestCase(TestCase):
    def setUp(self) -> None:
        self.logger = logging.getLogger("icloudpd-test-own-exif-date")
        handle, self.path = tempfile.mkstemp(suffix=".JPG")
        os.close(handle)

    def tearDown(self) -> None:
        os.remove(self.path)

    def check(self, date: str | None, local_size: int, path: str | None = None) -> bool:
        with open(self.path, "wb") as file:
            file.write(jpeg_with_date(date, local_size))
        return has_own_exif_date(self.logger, path or self.path, OWN_DATE, local_size, 10000)

    def test_own_date_and_a_little_larger(self) -> None:
        self.assertTrue(self.check(OWN_DATE, 10072))
        self.assertTrue(self.check(OWN_DATE, 10000 + MAX_DATE_TAGS_SIZE))

    def test_other_date(self) -> None:
        self.assertFalse(self.check("2018:07:30 10:00:00", 10072))

    def test_no_date(self) -> None:
        self.assertFalse(self.check(None, 10072))

    def test_too_much_larger_or_smaller(self) -> None:
        self.assertFalse(self.check(OWN_DATE, 10000 + MAX_DATE_TAGS_SIZE + 1))
        self.assertFalse(self.check(OWN_DATE, 9990))

    def test_not_a_jpeg(self) -> None:
        self.assertFalse(self.check(OWN_DATE, 10072, path=self.path[:-4] + ".HEIC"))


class SetExifDatetimeDedupTestCase(TestCase):
    def setUp(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

    def run_with_local_file(
        self,
        test_name: str,
        date: str | None,
        local_size: int,
        files_to_download: List[Tuple[str, str]],
        set_exif_datetime: bool = True,
    ) -> str:
        def create_jpegs(data_dir: str, files: Sequence[Tuple[str, str, int]]) -> None:
            for dir_name, file_name, size in files:
                os.makedirs(os.path.join(data_dir, dir_name), exist_ok=True)
                with open(os.path.join(data_dir, dir_name, file_name), "wb") as file:
                    file.write(jpeg_with_date(date, size))

        with mock.patch("tests.helpers.create_files", new=create_jpegs):
            _, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                os.path.join(self.fixtures_path, test_name),
                "listing_photos.yml",
                [("2018/07/31", "IMG_7409.JPG", local_size)],
                files_to_download,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "1",
                    "--skip-videos",
                    "--skip-live-photos",
                    "--no-progress-bar",
                    "--threads-num",
                    "1",
                    *(["--set-exif-datetime"] if set_exif_datetime else []),
                ],
            )
        self.assertEqual(0, result.exit_code)
        return result.output

    def test_file_with_own_date_is_not_downloaded_again(self) -> None:
        output = self.run_with_local_file(inspect.stack()[0][3], OWN_DATE, ICLOUD_SIZE + 72, [])
        self.assertIn("IMG_7409.JPG already exists", output)
        self.assertNotIn("deduplicated", output)

    def test_file_with_other_date_is_a_different_photo(self) -> None:
        output = self.run_with_local_file(
            inspect.stack()[0][3],
            "2018:07:30 10:00:00",
            ICLOUD_SIZE + 72,
            [("2018/07/31", "IMG_7409-1884695.JPG")],
        )
        self.assertIn("IMG_7409-1884695.JPG deduplicated", output)

    def test_file_much_larger_is_a_different_photo(self) -> None:
        self.run_with_local_file(
            inspect.stack()[0][3],
            OWN_DATE,
            ICLOUD_SIZE + 5000,
            [("2018/07/31", "IMG_7409-1884695.JPG")],
        )

    def test_without_set_exif_datetime_nothing_changes(self) -> None:
        self.run_with_local_file(
            inspect.stack()[0][3],
            OWN_DATE,
            ICLOUD_SIZE + 72,
            [("2018/07/31", "IMG_7409-1884695.JPG")],
            set_exif_datetime=False,
        )
