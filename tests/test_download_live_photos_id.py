import inspect
import os
from unittest import TestCase

import pytest

from tests.helpers import (
    path_from_project_root,
    run_icloudpd_test,
)


class DownloadLivePhotoNameIDTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

    def test_skip_existing_downloads_for_live_photos_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [
            ("2020/11/04", "IMG_0516_QVcwekp.HEIC"),
            ("2020/11/04", "IMG_0514_QVZtSTE.HEIC"),
            ("2020/11/04", "IMG_0514_QVZtSTE_HEVC.MOV"),
            ("2020/11/04", "IMG_0512_QWRFR00.HEIC"),
            ("2020/11/04", "IMG_0512_QWRFR00_HEVC.MOV"),
        ]

        _, result = run_icloudpd_test(
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
                "--file-match-policy",
                "name-id7",
            ],
        )

        self.assertIn("All photos and videos have been downloaded", result.output)
        assert result.exit_code == 0

    def test_skip_existing_live_photodownloads_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2020/11/04", "IMG_0516_QVcwekp.HEIC", 1651485),
            ("2020/11/04", "IMG_0514_QVZtSTE_HEVC.MOV", 3951774),
        ]

        files_to_download = [
            ("2020/11/04", "IMG_0514_QVZtSTE.HEIC"),
            ("2020/11/04", "IMG_0512_QWRFR00.HEIC"),
            ("2020/11/04", "IMG_0512_QWRFR00_HEVC.MOV"),
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
                "--file-match-policy",
                "name-id7",
            ],
        )

        self.assertIn("Looking up all photos and videos...", result.output)
        self.assertIn(
            f"Downloading 3 original photos and videos to {data_dir} ...",
            result.output,
        )
        self.assertIn("All photos and videos have been downloaded", result.output)
        assert result.exit_code == 0

    def test_skip_existing_live_photo_print_filenames_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2020/11/04", "IMG_0516_QVcwekp.HEIC", 1651485),
            ("2020/11/04", "IMG_0514_QVZtSTE_HEVC.MOV", 3951774),
        ]

        # files_to_download = [
        #     ("2020/11/04","IMG_0514_QVZtSTE.HEIC"),
        #     ("2020/11/04","IMG_0512_QWRFR00.HEIC"),
        #     ("2020/11/04","IMG_0512_QWRFR00_HEVC.MOV")
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
                "--file-match-policy",
                "name-id7",
                "--only-print-filenames",
            ],
        )

        filenames = result.output.splitlines()

        print(filenames)

        assert len(filenames) == 3

        self.assertEqual(
            os.path.join(data_dir, os.path.normpath("2020/11/04/IMG_0514_QVZtSTE.HEIC")),
            filenames[0],
        )
        self.assertEqual(
            os.path.join(data_dir, os.path.normpath("2020/11/04/IMG_0512_QWRFR00.HEIC")),
            filenames[1],
        )
        self.assertEqual(
            os.path.join(data_dir, os.path.normpath("2020/11/04/IMG_0512_QWRFR00_HEVC.MOV")),
            filenames[2],
        )

        # Double check that a mocked file does not get listed again. It's already there!
        assert "2020/11/04/IMG_0514_QVZtSTE_HEVC.MOV" not in filenames

        assert result.exit_code == 0
