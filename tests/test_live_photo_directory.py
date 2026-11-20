"""--live-photo-directory keeps the video part of Live Photos apart from the photos (#94)"""

import inspect
import os
import shutil
from typing import List
from unittest import TestCase

from tests.helpers import (
    path_from_project_root,
    recreate_path,
    run_cassette,
    run_icloudpd_test,
    run_main,
)


def files_in(directory: str) -> List[str]:
    return sorted(
        os.path.relpath(os.path.join(root, name), directory).replace(os.sep, "/")
        for root, _, names in os.walk(directory)
        for name in names
    )


class LivePhotoDirectoryTestCase(TestCase):
    def setUp(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")
        self.vcr_path = os.path.join(self.root_path, "vcr_cassettes")

    def test_live_photo_videos_go_to_their_own_directory(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        live_dir = os.path.join(base_dir, "live")

        # only the photos end up in --directory
        _, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "download_live_photos.yml",
            [],
            [
                ("2020/11/04", "IMG_0516.HEIC"),
                ("2020/11/04", "IMG_0514.HEIC"),
                ("2020/11/04", "IMG_0512.HEIC"),
            ],
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
                "--live-photo-directory",
                live_dir,
            ],
        )

        self.assertEqual(0, result.exit_code)
        self.assertEqual(
            ["2020/11/04/IMG_0512_HEVC.MOV", "2020/11/04/IMG_0514_HEVC.MOV"], files_in(live_dir)
        )

    def test_auto_delete_finds_live_photo_videos_in_their_directory(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")
        live_dir = os.path.join(base_dir, "live")
        for directory in [base_dir, data_dir, live_dir]:
            recreate_path(directory)
        shutil.copytree(os.path.join(self.root_path, "cookie"), cookie_dir)

        # IMG_7190 is in Recently Deleted in the recording; IMG_7407 is not
        for directory, name in [
            (data_dir, "2018/07/12/IMG_7190.JPG"),
            (live_dir, "2018/07/12/IMG_7190.MOV"),
            (data_dir, "2018/07/30/IMG_7407.JPG"),
            (live_dir, "2018/07/30/IMG_7407.MOV"),
        ]:
            os.makedirs(os.path.dirname(os.path.join(directory, name)), exist_ok=True)
            open(os.path.join(directory, name), "a").close()

        result = run_cassette(
            os.path.join(self.vcr_path, "autodelete_photos.yml"),
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "0",
                "--skip-videos",
                "--auto-delete",
                "-d",
                data_dir,
                "--live-photo-directory",
                live_dir,
                "--cookie-directory",
                cookie_dir,
            ],
        )

        self.assertEqual(0, result.exit_code)
        self.assertIn(
            f"Deleted {os.path.join(live_dir, os.path.normpath('2018/07/12/IMG_7190.MOV'))}",
            result.output,
        )
        self.assertEqual(["2018/07/30/IMG_7407.MOV"], files_in(live_dir))
        self.assertEqual(["2018/07/30/IMG_7407.JPG"], files_in(data_dir))

    def test_combinations_that_cannot_work_are_rejected(self) -> None:
        for extra in (["--skip-live-photos"], ["--prune-orphans"]):
            result = run_main(
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--directory",
                    "photos",
                    "--live-photo-directory",
                    "live",
                    *extra,
                ]
            )
            self.assertEqual(2, result.exit_code, extra)
            self.assertIn(
                "--live-photo-directory can't be combined with --skip-live-photos or "
                "--prune-orphans",
                result.output,
            )
