import inspect
import json
import os
from unittest import TestCase, mock

import pytest

from tests.helpers import (
    path_from_project_root,
    run_icloudpd_test,
)


class ListingRecentPhotosTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

    def test_listing_recent_photos(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        data_dir, result = run_icloudpd_test(
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
                "5",
                "--only-print-filenames",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )
        self.assertEqual(result.exit_code, 0, "exit code")

        filenames = result.output.splitlines()

        self.assertEqual(len(filenames), 8)
        self.assertIn(
            os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409.JPG")), filenames[0]
        )
        self.assertEqual(
            os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409.MOV")), filenames[1]
        )
        self.assertEqual(
            os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7408.JPG")), filenames[2]
        )
        self.assertEqual(
            os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7408.MOV")), filenames[3]
        )
        self.assertEqual(
            os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7407.JPG")), filenames[4]
        )
        self.assertEqual(
            os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7407.MOV")), filenames[5]
        )
        self.assertEqual(
            os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7405.MOV")), filenames[6]
        )
        self.assertEqual(
            os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7404.MOV")), filenames[7]
        )

    def test_listing_photos_does_not_create_folders(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        data_dir, result = run_icloudpd_test(
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
                "5",
                "--only-print-filenames",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )
        self.assertEqual(result.exit_code, 0, "exit code")
        # Should only be created after download, not after just --print-filenames
        self.assertFalse(os.path.exists(os.path.join(data_dir, os.path.normpath("2018/07/31"))))

    def test_listing_recent_photos_with_missing_filenameEnc(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_missing_filenameEnc.yml",
            [],
            [],
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "5",
                "--only-print-filenames",
                "--no-progress-bar",
            ],
        )
        self.assertEqual(result.exit_code, 0, "exit code")
        filenames = result.output.splitlines()

        # self.assertEqual(len(filenames), 5)
        self.assertEqual(
            os.path.join(data_dir, os.path.normpath("2018/07/31/AY6c_BsE0jja.JPG")),
            filenames[0],
        )
        self.assertEqual(
            os.path.join(data_dir, os.path.normpath("2018/07/31/AY6c_BsE0jja.MOV")),
            filenames[1],
        )
        self.assertEqual(
            os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7408.JPG")),
            filenames[2],
        )
        self.assertEqual(
            os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7408.MOV")),
            filenames[3],
        )
        self.assertEqual(
            os.path.join(data_dir, os.path.normpath("2018/07/30/AZ_wAGT9P6jh.JPG")),
            filenames[4],
        )

    # This was used to solve the missing filenameEnc error. I found
    # another case where it might crash. (Maybe Apple changes the downloadURL key)
    def test_listing_recent_photos_with_missing_downloadURL(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        with (
            mock.patch("icloudpd.base.open", create=True) as mock_open,
            mock.patch.object(json, "dump") as mock_json,
        ):
            _, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos_missing_downloadUrl.yml",
                [],
                [],
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "1",
                    "--only-print-filenames",
                    "--no-progress-bar",
                ],
            )
            self.assertEqual(result.exit_code, 0, "exit code")
            self.assertEqual.__self__.maxDiff = None  # type: ignore[attr-defined]
            self.assertEqual(
                """\
KeyError: 'downloadURL' attribute was not found in the photo fields.
icloudpd has saved the photo record to: ./icloudpd-photo-error.json
Please create a Gist with the contents of this file: https://gist.github.com
Then create an issue on GitHub: https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues
Include a link to the Gist in your issue, so that we can see what went wrong.
""",
                result.output,
            )
            mock_open.assert_called_once_with(
                file="icloudpd-photo-error.json", mode="w", encoding="utf8"
            )
            mock_json.assert_called()
            self.assertEqual(len(mock_json.call_args_list), 7)
            # Check a few keys in the dict
            first_arg = mock_json.call_args_list[6][0][0]
            self.assertEqual(
                first_arg["master_record"]["recordName"], "AY6c+BsE0jjaXx9tmVGJM1D2VcEO"
            )
            self.assertEqual(
                first_arg["master_record"]["fields"]["resVidSmallHeight"]["value"], 581
            )
            self.assertEqual(
                first_arg["asset_record"]["recordName"],
                "F2A23C38-0020-42FE-A273-2923ADE3CAED",
            )
            self.assertEqual(
                first_arg["asset_record"]["fields"]["assetDate"]["value"], 1533021744816
            )
