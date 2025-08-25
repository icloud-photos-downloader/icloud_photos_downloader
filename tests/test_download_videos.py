import inspect
import os
from unittest import TestCase

import pytest

from tests.helpers import (
    path_from_project_root,
    run_icloudpd_test,
)


class DownloadVideoTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

    def test_download_and_skip_existing_videos(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create: list[tuple[str, str, int]] = [
            # ("2018/07/30", "IMG_7408.JPG", 1151066),
            # ("2018/07/30", "IMG_7407.JPG", 656257),
        ]

        files_to_download: list[tuple[str, str]] = [("2018/07/30", "IMG_7405.MOV")]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_videos.yml",
            files_to_create,
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "4",
                "--skip-photos",
                # "--skip-live-photos",
                "--set-exif-datetime",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        assert result.exit_code == 0

        self.assertIn("Looking up all videos...", result.output)
        self.assertIn(
            f"Downloading 4 original videos to {data_dir} ...",
            result.output,
        )
        # for dir_name, file_name in files_to_download:
        #     file_path = os.path.normpath(os.path.join(dir_name, file_name))
        #     self.assertIn(
        #         f"Downloading {os.path.join(data_dir, file_path)}",
        #         result.output,
        #     )
        # for dir_name, file_name in [
        #     (dir_name, file_name) for (dir_name, file_name, _) in files_to_create
        # ]:
        #     file_path = os.path.normpath(os.path.join(dir_name, file_name))
        #     self.assertIn(
        #         f"{os.path.join(data_dir, file_path)} already exists",
        #         result.output,
        #     )

        # self.assertIn(
        #     "Skipping IMG_7405.MOV, only downloading photos.",
        #     result.output,
        # )
        # self.assertIn(
        #     "Skipping IMG_7404.MOV, only downloading photos.",
        #     result.output,
        # )
        self.assertIn("All videos have been downloaded", result.output)

        # # Check that file was downloaded
        # # Check that mtime was updated to the photo creation date
        # photo_mtime = os.path.getmtime(
        #     os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409.JPG"))
        # )
        # photo_modified_time = datetime.datetime.fromtimestamp(photo_mtime, datetime.timezone.utc)
        # self.assertEqual("2018-07-31 07:22:24", photo_modified_time.strftime("%Y-%m-%d %H:%M:%S"))
