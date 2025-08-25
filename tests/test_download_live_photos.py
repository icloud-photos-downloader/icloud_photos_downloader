import inspect
import os
from unittest import TestCase

import pytest

from icloudpd.base import lp_filename_concatinator, lp_filename_original
from tests.helpers import (
    path_from_project_root,
    run_icloudpd_test,
)


class DownloadLivePhotoTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

    def test_lp_filename_generator(self) -> None:
        self.assertEqual(
            lp_filename_concatinator("IMG_1234.HEIC"), "IMG_1234_HEVC.MOV", "happy path HEIC"
        )
        self.assertEqual(lp_filename_concatinator("IMG_1234.JPG"), "IMG_1234.MOV", "happy path JPG")
        self.assertEqual(lp_filename_concatinator("IMG_1234"), "IMG_1234", "no ext")
        self.assertEqual(lp_filename_concatinator("IMG.1234.HEIC"), "IMG.1234_HEVC.MOV", "dots")

        self.assertEqual(lp_filename_original("IMG_1234.HEIC"), "IMG_1234.MOV", "happy path HEIC")
        self.assertEqual(lp_filename_original("IMG_1234.JPG"), "IMG_1234.MOV", "happy path JPG")

    def test_skip_existing_downloads_for_live_photos(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [
            ("2020/11/04", "IMG_0516.HEIC"),
            ("2020/11/04", "IMG_0514.HEIC"),
            ("2020/11/04", "IMG_0514_HEVC.MOV"),
            ("2020/11/04", "IMG_0512.HEIC"),
            ("2020/11/04", "IMG_0512_HEVC.MOV"),
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "download_live_photos.yml",
            [],
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "3",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        self.assertIn("All photos and videos have been downloaded", result.output)
        assert result.exit_code == 0

    def test_skip_existing_live_photodownloads(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2020/11/04", "IMG_0516.HEIC", 1651485),
            ("2020/11/04", "IMG_0514_HEVC.MOV", 3951774),
        ]

        files_to_download = [
            ("2020/11/04", "IMG_0514.HEIC"),
            ("2020/11/04", "IMG_0512.HEIC"),
            ("2020/11/04", "IMG_0512_HEVC.MOV"),
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "download_live_photos.yml",
            files_to_create,
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "3",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        self.assertIn("Looking up all photos and videos...", result.output)
        self.assertIn(
            f"Downloading 3 original photos and videos to {data_dir} ...",
            result.output,
        )
        self.assertIn("All photos and videos have been downloaded", result.output)
        assert result.exit_code == 0

    def test_skip_existing_live_photo_print_filenames(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2020/11/04", "IMG_0516.HEIC", 1651485),
            ("2020/11/04", "IMG_0514_HEVC.MOV", 3951774),
        ]

        # files_to_download = [
        #     ("2020/11/04","IMG_0514.HEIC"),
        #     ("2020/11/04","IMG_0512.HEIC"),
        #     ("2020/11/04","IMG_0512_HEVC.MOV")
        # ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "download_live_photos.yml",
            files_to_create,
            [],
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "3",
                "--no-progress-bar",
                "--threads-num",
                "1",
                "--only-print-filenames",
            ],
        )

        filenames = result.output.splitlines()

        print(filenames)

        assert len(filenames) == 3

        self.assertEqual(
            os.path.join(data_dir, os.path.normpath("2020/11/04/IMG_0514.HEIC")), filenames[0]
        )
        self.assertEqual(
            os.path.join(data_dir, os.path.normpath("2020/11/04/IMG_0512.HEIC")), filenames[1]
        )
        self.assertEqual(
            os.path.join(data_dir, os.path.normpath("2020/11/04/IMG_0512_HEVC.MOV")), filenames[2]
        )

        # Double check that a mocked file does not get listed again. It's already there!
        assert "2020/11/04/IMG_0514_HEVC.MOV" not in filenames

        assert result.exit_code == 0
