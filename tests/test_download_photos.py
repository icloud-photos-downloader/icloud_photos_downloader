import datetime
import inspect
import os
import shutil
import sys
from typing import Any, List, NoReturn, Tuple
from unittest import TestCase, mock

import piexif
import pytest
import pytz
from piexif._exceptions import InvalidImageDataError

from pyicloud_ipd.services.photos import PhotoAsset
from tests.helpers import (
    calc_data_dir,
    create_files,
    path_from_project_root,
    print_result_exception,
    recreate_path,
    run_cassette,
    run_icloudpd_test,
)


class DownloadPhotoTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

    def test_download_and_skip_existing_photos(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2018/07/30", "IMG_7408.JPG", 1151066),
            ("2018/07/30", "IMG_7407.JPG", 656257),
        ]

        files_to_download = [("2018/07/31", "IMG_7409.JPG")]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos.yml",
            files_to_create,
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "5",
                "--skip-videos",
                "--skip-live-photos",
                "--set-exif-datetime",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        assert result.exit_code == 0

        self.assertIn("Looking up all photos...", result.output)
        self.assertIn(
            f"Downloading 5 original photos to {data_dir} ...",
            result.output,
        )
        for dir_name, file_name in files_to_download:
            file_path = os.path.normpath(os.path.join(dir_name, file_name))
            self.assertIn(
                f"Downloading {os.path.join(data_dir, file_path)}",
                result.output,
            )
        self.assertNotIn(
            "IMG_7409.MOV",
            result.output,
        )
        for dir_name, file_name in [
            (dir_name, file_name) for (dir_name, file_name, _) in files_to_create
        ]:
            file_path = os.path.normpath(os.path.join(dir_name, file_name))
            self.assertIn(
                f"{os.path.join(data_dir, file_path)} already exists",
                result.output,
            )

        self.assertIn(
            "Skipping IMG_7405.MOV, only downloading photos.",
            result.output,
        )
        self.assertIn(
            "Skipping IMG_7404.MOV, only downloading photos.",
            result.output,
        )
        self.assertIn("All photos have been downloaded", result.output)

        # Check that file was downloaded
        # Check that mtime was updated to the photo creation date
        photo_mtime = os.path.getmtime(
            os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409.JPG"))
        )
        photo_modified_time = datetime.datetime.fromtimestamp(photo_mtime, datetime.timezone.utc)
        self.assertEqual("2018-07-31 07:22:24", photo_modified_time.strftime("%Y-%m-%d %H:%M:%S"))

    def test_download_photos_and_set_exif(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        # files_to_create = [
        #     # ("2018/07/30", "IMG_7408.JPG", 1151066),
        #     # ("2018/07/30", "IMG_7407.JPG", 656257),
        # ]

        files_to_download = [
            # ("2018/07/30", "IMG_7405.MOV"),
            # ("2018/07/30", "IMG_7407.MOV"),
            # ("2018/07/30", "IMG_7408.MOV"),
            ("2018/07/31", "IMG_7409.JPG"),
            # ("2018/07/31", "IMG_7409.MOV"),
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_4_recent_all.yml",
            [],
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "1",
                "--set-exif-datetime",
                "--skip-videos",
                "--skip-live-photos",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )
        assert result.exit_code == 0

        self.assertIn(
            "Looking up all photos...",
            result.output,
        )
        self.assertIn(
            f"Downloading the first original photo to {data_dir} ...",
            result.output,
        )
        self.assertIn(
            f"Downloading {os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}",
            result.output,
        )
        # 2018:07:31 07:22:24 utc
        expectedDatetime = (
            datetime.datetime(2018, 7, 31, 7, 22, 24, tzinfo=datetime.timezone.utc)
            .astimezone()
            .strftime("%Y-%m-%d %H:%M:%S%z")
        )
        self.assertIn(
            f"Setting EXIF timestamp for {os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}: {expectedDatetime}",
            result.output,
        )
        self.assertIn("All photos have been downloaded", result.output)

    def test_download_photos_and_get_exif_exceptions(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [("2018/07/31", "IMG_7409.JPG")]

        with mock.patch.object(piexif, "load") as piexif_patched:
            piexif_patched.side_effect = InvalidImageDataError

            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos.yml",
                [],
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
                    "--set-exif-datetime",
                    "--no-progress-bar",
                    "--threads-num",
                    "1",
                ],
            )
            assert result.exit_code == 0

        self.assertIn("Looking up all photos...", result.output)
        self.assertIn(
            f"Downloading the first original photo to {data_dir} ...",
            result.output,
        )
        self.assertIn(
            f"Downloading {os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}",
            result.output,
        )
        # 2018:07:31 07:22:24 utc
        expectedDatetime = (
            datetime.datetime(2018, 7, 31, 7, 22, 24, tzinfo=datetime.timezone.utc)
            .astimezone()
            .strftime("%Y-%m-%d %H:%M:%S%z")
        )
        # When piexif.load fails, write_exif_metadata creates a minimal EXIF structure
        # and continues, so the EXIF timestamp is successfully set
        self.assertIn(
            f"Setting EXIF timestamp for {os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}: {expectedDatetime}",
            result.output,
        )
        self.assertIn("All photos have been downloaded", result.output)

    def test_skip_existing_downloads(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2018/07/31", "IMG_7409.JPG", 1884695),
            ("2018/07/31", "IMG_7409.MOV", 3294075),
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos.yml",
            files_to_create,
            [],
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "1",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )
        assert result.exit_code == 0

        self.assertIn("Looking up all photos and videos...", result.output)
        self.assertIn(
            f"Downloading the first original photo or video to {data_dir} ...",
            result.output,
        )
        self.assertIn(
            f"{os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))} already exists",
            result.output,
        )
        self.assertIn(
            f"{os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409.MOV'))} already exists",
            result.output,
        )
        self.assertIn("All photos and videos have been downloaded", result.output)

    def test_until_found(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        # Files that will be attempted to download (until finding 3 consecutive existing)
        files_to_download = [
            ("2018/07/31", "IMG_7409.JPG"),
            ("2018/07/31", "IMG_7409-medium.MOV"),
            ("2018/07/30", "IMG_7407.JPG"),
            ("2018/07/30", "IMG_7407-medium.MOV"),
            ("2018/07/30", "IMG_7403.MOV"),
            ("2018/07/30", "IMG_7402.MOV"),
        ]

        # Files to create locally (will trigger --until-found after 3 consecutive)
        files_to_create = [
            ("2018/07/30", "IMG_7408.JPG", 161),  # Using small size like our one-pixel JPEG
            ("2018/07/30", "IMG_7408-medium.MOV", 161),
            ("2018/07/30", "IMG_7405.MOV", 161),
            ("2018/07/30", "IMG_7404.MOV", 161),
            ("2018/07/30", "IMG_7401.MOV", 161),
            ("2018/07/30", "IMG_7400.JPG", 161),
            ("2018/07/30", "IMG_7400-medium.MOV", 161),
            ("2018/07/30", "IMG_7399.JPG", 161),
            ("2018/07/30", "IMG_7399-medium.MOV", 161),
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_until_found.yml",  # New cassette with proper downloads
            files_to_create,
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--live-photo-size",
                "medium",
                "--until-found",
                "3",
                "--recent",
                "20",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        self.assertIn(
            "Looking up all photos and videos...",
            result.output,
        )

        # Should download the first 4 files before hitting 3 consecutive existing
        for dir_name, file_name in files_to_download:
            file_path = os.path.join(data_dir, os.path.normpath(dir_name), file_name)
            self.assertIn(
                f"Downloading {file_path}",
                result.output,
            )

        # Should recognize existing files
        for dir_name, file_name, _ in files_to_create[:3]:  # First 3 that trigger until-found
            file_path = os.path.join(data_dir, os.path.normpath(dir_name), file_name)
            self.assertIn(
                f"{file_path} already exists",
                result.output,
            )

        self.assertIn(
            "Found 3 consecutive previously downloaded photos. Exiting",
            result.output,
        )
        assert result.exit_code == 0

    def test_handle_io_error(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        with mock.patch("icloudpd.download.open", create=True) as m:
            # Raise IOError when we try to write to the destination file
            m.side_effect = IOError

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
                    "1",
                    "--skip-videos",
                    "--skip-live-photos",
                    "--no-progress-bar",
                    "--threads-num",
                    "1",
                ],
            )

            self.assertIn("Looking up all photos...", result.output)
            self.assertIn(
                f"Downloading the first original photo to {data_dir} ...",
                result.output,
            )
            # self.assertIn(
            #     "IOError while writing file to "
            #     f"{os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}. "
            #     "You might have run out of disk space, or the file might "
            #     "be too large for your OS. Skipping this file...",
            #     result.output,
            # )
            self.assertIn(
                "IOError",
                result.output,
            )
            assert result.exit_code == 1

    def test_handle_session_error_during_download(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        # The cassette listing_photos_session_error_download.yml contains:
        # 1. Initial authentication
        # 2. Photo listing
        # 3. Download attempt that returns session error (401 with "Invalid global session")
        # 4. Re-authentication (second validate call)
        # 5. Second download attempt that succeeds (200 with binary data)
        # No mocks needed - the cassette has all the necessary responses

        # Pass fixed client ID via environment variable
        _, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_session_error_download.yml",
            [],
            [("2018/07/31/", "IMG_7409.JPG")],  # File is downloaded successfully after re-auth
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
            ],
        )

        # Check that re-authentication happened after session error
        auth_count = result.output.count("Authenticating...")
        self.assertGreaterEqual(
            auth_count,
            2,
            f"Expected at least 2 authentications, got {auth_count}",
        )

        # Check that session error was raised from cassette
        self.assertIn(
            "Invalid global session",
            result.output,
        )

        # Cassette contains successful download after re-auth,
        # proving that session errors are properly handled with retry
        assert result.exit_code == 0

    def test_handle_session_error_during_photo_iteration(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        # The cassette listing_photos_session_error_iteration.yml contains:
        # 1. Initial authentication
        # 2. Photo listing attempt that returns session error (401 with "Invalid global session")
        # 3. Re-authentication happens automatically
        # 4. Photo downloads successfully after re-auth
        # No mocks needed - the cassette has all the necessary responses

        _, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_session_error_iteration.yml",
            [],
            [("2018/07/31", "IMG_7409.JPG")],
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
            ],
        )

        # Verify re-authentication happened
        self.assertEqual(
            result.output.count("Authenticating..."),
            2,
            "should authenticate twice - initial and after session error",
        )

        self.assertIn(
            "Invalid global session",
            result.output,
        )

    def test_handle_albums_error(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        # The cassette listing_albums_error.yml contains:
        # 1. Initial authentication
        # 2. Albums fetch that returns API error (200 with error in JSON payload)
        # No mocks needed - the cassette has the error response

        _, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_albums_error.yml",
            [],
            [],
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
            ],
        )

        assert result.exit_code == 1

    def test_missing_size(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_404.yml",
            [],
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
            ],
        )

        self.assertIn(
            "Looking up all photos and videos...",
            result.output,
        )
        self.assertIn(
            f"Downloading 3 original photos and videos to {data_dir} ...",
            result.output,
        )

        # These error messages should not be repeated more than once for each size
        for filename in ["IMG_7409.JPG", "IMG_7408.JPG", "IMG_7407.JPG"]:
            for size in ["original"]:
                self.assertEqual(
                    sum(
                        1
                        for line in result.output.splitlines()
                        if line == f"Could not find URL to download {filename} for size {size}"
                    ),
                    1,
                    f"Errors for {filename} size {size}",
                )

        for filename in ["IMG_7409.MOV", "IMG_7408.MOV", "IMG_7407.MOV"]:
            for size in ["original"]:
                self.assertEqual(
                    sum(
                        1
                        for line in result.output.splitlines()
                        if line == f"Could not find URL to download {filename} for size {size}"
                    ),
                    1,
                    f"Errors for {filename} size {size}",
                )

        self.assertIn("All photos and videos have been downloaded", result.output)
        self.assertEqual(result.exit_code, 0, "Exit code")

    def test_size_fallback_to_original(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [
            ("2018/07/31", "IMG_7409.JPG"),
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_fallback_to_original.yml",
            [],
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "1",
                "--size",
                "thumb",
                "--skip-live-photos",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )
        self.assertIn(
            "Looking up all photos and videos...",
            result.output,
        )
        self.assertIn(
            f"Downloading the first thumb photo or video to {data_dir} ...",
            result.output,
        )
        self.assertIn(
            f"Downloading {os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}",
            result.output,
        )
        self.assertIn("All photos and videos have been downloaded", result.output)

        assert result.exit_code == 0

    def test_adjusted_size_fallback_to_original(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_fallback_to_original.yml",
            [],
            [("2018/07/31", "IMG_7409.JPG"), ("2018/07/31", "IMG_7409.MOV")],
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "1",
                "--size",
                "adjusted",
                "--size",
                "alternative",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )
        self.assertIn(
            "Looking up all photos and videos...",
            result.output,
        )
        self.assertIn(
            f"Downloading the first adjusted,alternative photo or video to {data_dir} ...",
            result.output,
        )
        self.assertIn(
            f"Downloading {os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}",
            result.output,
        )
        self.assertIn("All photos and videos have been downloaded", result.output)

        assert result.exit_code == 0

    def test_force_size(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_two_sizes_forced.yml",  # Use the same cassette as test_download_two_sizes_with_force_size
            [],
            [],  # No files downloaded because thumb size doesn't exist
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "1",
                "--size",
                "thumb",
                "--skip-live-photos",
                "--force-size",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        self.assertIn(
            "Looking up all photos and videos...",
            result.output,
        )
        self.assertIn(
            f"Downloading the first thumb photo or video to {data_dir} ...",
            result.output,
        )
        self.assertIn(
            "thumb size does not exist for IMG_7409.JPG. Skipping...",
            result.output,
        )
        self.assertIn("All photos and videos have been downloaded", result.output)

        assert result.exit_code == 0

    def test_download_two_sizes_with_force_size(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_two_sizes_forced.yml",
            [],
            [("2018/07/31", "IMG_7409-medium.JPG")],  # thumb is missing in cassette
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "1",
                "--size",
                "medium",
                "--size",
                "thumb",
                "--skip-live-photos",
                "--force-size",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        self.assertIn(
            "Looking up all photos and videos...",
            result.output,
        )
        self.assertIn(
            f"Downloading the first medium,thumb photo or video to {data_dir} ...",
            result.output,
        )
        self.assertIn(
            "thumb size does not exist for IMG_7409.JPG. Skipping...",
            result.output,
        )
        self.assertIn("All photos and videos have been downloaded", result.output)

        assert result.exit_code == 0

    def test_invalid_creation_date(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [("2018/01/01", "IMG_7409.JPG")]

        with mock.patch.object(PhotoAsset, "created", new_callable=mock.PropertyMock) as dt_mock:
            # Can't mock `astimezone` because it's a readonly property, so have to
            # create a new class that inherits from datetime.datetime
            class NewDateTime(datetime.datetime):
                def astimezone(self, _tz: (Any | None) = None) -> NoReturn:
                    raise ValueError("Invalid date")

            dt_mock.return_value = NewDateTime(2018, 1, 1, 0, 0, 0)

            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos.yml",
                [],
                files_to_download,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "1",
                    "--skip-live-photos",
                    "--no-progress-bar",
                    "--threads-num",
                    "1",
                ],
            )

            self.assertIn(
                "Looking up all photos and videos...",
                result.output,
            )
            self.assertIn(
                f"Downloading the first original photo or video to {data_dir} ...",
                result.output,
            )
            self.assertIn(
                "Could not convert photo created date to local timezone (2018-01-01 00:00:00)",
                result.output,
            )
            self.assertIn(
                f"Downloading {os.path.join(data_dir, os.path.normpath('2018/01/01/IMG_7409.JPG'))}",
                result.output,
            )
            self.assertIn("All photos and videos have been downloaded", result.output)
            assert result.exit_code == 0

    @pytest.mark.skipif(sys.platform == "win32", reason="does not run on windows")
    @pytest.mark.skipif(sys.platform == "darwin", reason="does not run on mac")
    def test_creation_date_without_century(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [("5/01/01", "IMG_7409.JPG")]

        with mock.patch.object(PhotoAsset, "created", new_callable=mock.PropertyMock) as dt_mock:
            # Can't mock `astimezone` because it's a readonly property, so have to
            # create a new class that inherits from datetime.datetime
            # class NewDateTime(datetime.datetime):
            #     def astimezone(self, _tz: (Optional[Any]) = None) -> NoReturn:
            #         raise ValueError("Invalid date")

            dt_mock.return_value = datetime.datetime(
                5, 1, 1, 0, 0, 0, tzinfo=pytz.timezone("America/Los_Angeles")
            )

            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos.yml",
                [],
                files_to_download,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "1",
                    "--skip-live-photos",
                    "--no-progress-bar",
                    "--threads-num",
                    "1",
                ],
            )

            self.assertIn(
                "Looking up all photos and videos...",
                result.output,
            )
            self.assertIn(
                f"Downloading the first original photo or video to {data_dir} ...",
                result.output,
            )
            # self.assertIn(
            #     "Could not convert photo created date to local timezone (0005-01-01 00:00:00)",
            #     result.output,
            # )
            self.assertIn(
                f"Downloading {os.path.join(data_dir, os.path.normpath('5/01/01/IMG_7409.JPG'))}",
                result.output,
            )
            self.assertIn("All photos and videos have been downloaded", result.output)
            assert result.exit_code == 0

    def test_creation_date_prior_1970(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [("1965/01/01", "IMG_7409.JPG")]

        with mock.patch.object(PhotoAsset, "created", new_callable=mock.PropertyMock) as dt_mock:
            # Can't mock `astimezone` because it's a readonly property, so have to
            # create a new class that inherits from datetime.datetime
            # class NewDateTime(datetime.datetime):
            #     def astimezone(self, _tz: (Optional[Any]) = None) -> NoReturn:
            #         raise ValueError("Invalid date")

            dt_mock.return_value = datetime.datetime(1965, 1, 1, 0, 0, 0)

            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos.yml",
                [],
                files_to_download,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "1",
                    "--skip-live-photos",
                    "--no-progress-bar",
                ],
            )

            self.assertIn(
                "Looking up all photos and videos...",
                result.output,
            )
            self.assertIn(
                f"Downloading the first original photo or video to {data_dir} ...",
                result.output,
            )
            self.assertIn(
                f"Downloading {os.path.join(data_dir, os.path.normpath('1965/01/01/IMG_7409.JPG'))}",
                result.output,
            )
            self.assertIn("All photos and videos have been downloaded", result.output)
            assert result.exit_code == 0

    def test_missing_item_type(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [
            ("2018/07/31", "IMG_7409.JPG"),
        ]

        _, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_missing_item_type.yml",
            [],
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "1",
                "--no-progress-bar",
                "--skip-live-photos",
            ],
        )

        assert result.exit_code == 0

    def test_missing_item_type_value(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [
            ("2018/07/31", "IMG_7409.JPG"),
        ]

        _, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_missing_item_type_value.yml",
            [],
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "1",
                "--no-progress-bar",
                "--skip-live-photos",
            ],
        )

        assert result.exit_code == 0

    def test_download_and_dedupe_existing_photos(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2018/07/31", "IMG_7409.JPG", 1),
            ("2018/07/31", "IMG_7409.MOV", 1),
            ("2018/07/30", "IMG_7408.JPG", 161),
            ("2018/07/30", "IMG_7408.MOV", 161),
        ]

        files_to_download = [
            ("2018/07/31", "IMG_7409-161.JPG"),
            ("2018/07/31", "IMG_7409-161.MOV"),
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_dedup.yml",
            files_to_create,
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "2",
                "--skip-videos",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        self.assertIn("Looking up all photos...", result.output)
        self.assertIn(
            f"Downloading 2 original photos to {data_dir} ...",
            result.output,
        )
        self.assertIn(
            f"{os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409-161.JPG'))} deduplicated",
            result.output,
        )
        self.assertIn(
            f"{os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409-161.MOV'))} deduplicated",
            result.output,
        )
        # self.assertIn("Skipping IMG_7405.MOV, only downloading photos.", result.output)
        # self.assertIn("Skipping IMG_7404.MOV, only downloading photos.", result.output)
        self.assertIn("All photos have been downloaded", result.output)

        # Check that mtime was updated to the photo creation date
        photo_mtime = os.path.getmtime(
            os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409-161.JPG"))
        )
        photo_modified_time = datetime.datetime.fromtimestamp(photo_mtime, datetime.timezone.utc)
        self.assertEqual("2018-07-31 07:22:24", photo_modified_time.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertTrue(
            os.path.exists(os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409-161.MOV")))
        )
        photo_mtime = os.path.getmtime(
            os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409-161.MOV"))
        )
        photo_modified_time = datetime.datetime.fromtimestamp(photo_mtime, datetime.timezone.utc)
        self.assertEqual("2018-07-31 07:22:24", photo_modified_time.strftime("%Y-%m-%d %H:%M:%S"))

        assert result.exit_code == 0

    def test_download_photos_and_set_exif_exceptions(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [("2018/07/31", "IMG_7409.JPG")]

        with mock.patch.object(piexif, "insert") as piexif_patched:
            piexif_patched.side_effect = InvalidImageDataError
            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos.yml",
                [],
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
                    "--set-exif-datetime",
                    "--no-progress-bar",
                    "--threads-num",
                    "1",
                ],
            )

            self.assertIn("Looking up all photos...", result.output)
            self.assertIn(
                f"Downloading the first original photo to {data_dir} ...",
                result.output,
            )
            # 2018:07:31 07:22:24 utc
            expectedDatetime = (
                datetime.datetime(2018, 7, 31, 7, 22, 24, tzinfo=datetime.timezone.utc)
                .astimezone()
                .strftime("%Y-%m-%d %H:%M:%S%z")
            )
            self.assertIn(
                f"Setting EXIF timestamp for {os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}: {expectedDatetime}",
                result.output,
            )
            self.assertIn(
                f"Error writing EXIF data for {os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}",
                result.output,
            )
            self.assertIn("All photos have been downloaded", result.output)
            assert result.exit_code == 0

    def test_download_chinese(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3], "中文")

        files_to_download = [("2018/07/31", "IMG_7409.JPG")]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos.yml",
            [],
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
                "--set-exif-datetime",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        self.assertIn("Looking up all photos...", result.output)
        self.assertIn(
            f"Downloading the first original photo to {data_dir} ...",
            result.output,
        )
        self.assertNotIn(
            "IMG_7409.MOV",
            result.output,
        )
        self.assertIn("All photos have been downloaded", result.output)

        # Check that mtime was updated to the photo creation date
        photo_mtime = os.path.getmtime(
            os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409.JPG"))
        )
        photo_modified_time = datetime.datetime.fromtimestamp(photo_mtime, datetime.timezone.utc)
        self.assertEqual("2018-07-31 07:22:24", photo_modified_time.strftime("%Y-%m-%d %H:%M:%S"))

        assert result.exit_code == 0

    def test_download_one_recent_live_photo(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [
            ("2018/07/31", "IMG_7409.JPG"),
            ("2018/07/31", "IMG_7409.MOV"),
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_recent_live.yml",
            [],
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "1",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        self.assertIn(
            "Looking up all photos and videos...",
            result.output,
        )
        self.assertIn(
            f"Downloading the first original photo or video to {data_dir} ...",
            result.output,
        )
        self.assertIn("All photos and videos have been downloaded", result.output)
        assert result.exit_code == 0

    def test_download_one_recent_live_photo_chinese(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [
            ("2018/07/31", "IMG_中文_7409.JPG"),  # SU1HX+S4reaWh183NDA5LkpQRw==
            ("2018/07/31", "IMG_中文_7409.MOV"),
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_recent_live_chinese.yml",
            [],
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "1",
                "--no-progress-bar",
                "--keep-unicode-in-filenames",
                "true",
                "--threads-num",
                "1",
            ],
        )

        self.assertIn(
            "Looking up all photos and videos...",
            result.output,
        )
        self.assertIn(
            f"Downloading the first original photo or video to {data_dir} ...",
            result.output,
        )
        self.assertIn("All photos and videos have been downloaded", result.output)
        assert result.exit_code == 0

    def test_download_and_delete_after(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [("2018/07/31", "IMG_7409.JPG")]

        with mock.patch.object(piexif, "insert") as piexif_patched:
            piexif_patched.side_effect = InvalidImageDataError
            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos.yml",
                [],
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
                    "--delete-after-download",
                ],
            )

            self.assertIn("Looking up all photos...", result.output)
            self.assertIn(
                f"Downloading the first original photo to {data_dir} ...",
                result.output,
            )
            self.assertIn("Deleted IMG_7409.JPG in iCloud", result.output)
            self.assertIn("All photos have been downloaded", result.output)
            # TODO assert cass.all_played
            assert result.exit_code == 0

    def test_download_and_not_delete_after_when_exists(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [("2018/07/31", "IMG_7409.JPG", 1884695)]

        with mock.patch.object(piexif, "insert") as piexif_patched:
            piexif_patched.side_effect = InvalidImageDataError
            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos.yml",
                files_to_create,
                [],
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
                    "--delete-after-download",
                ],
            )

            self.assertIn("Looking up all photos...", result.output)
            self.assertIn(
                f"Downloading the first original photo to {data_dir} ...",
                result.output,
            )
            self.assertNotIn("Deleted IMG_7409.JPG in iCloud", result.output)
            self.assertIn("All photos have been downloaded", result.output)
            # TODO assert cass.all_played
            assert result.exit_code == 0

    def test_download_and_delete_after_fail(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_no_delete.yml",
            [],
            [],
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
                "--delete-after-download",
            ],
        )

        self.assertIn("Looking up all photos...", result.output)
        self.assertIn(
            f"Downloading the first original photo to {data_dir} ...",
            result.output,
        )
        self.assertNotIn("Deleted IMG_7409.JPG in iCloud", result.output)
        self.assertIn("All photos have been downloaded", result.output)
        # TODO assert cass.all_played
        assert result.exit_code == 0

    def test_download_over_old_original_photos(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2018/07/30", "IMG_7408-original.JPG", 1151066),
            ("2018/07/30", "IMG_7407.JPG", 656257),
        ]

        files_to_download = [("2018/07/31", "IMG_7409.JPG")]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos.yml",
            files_to_create,
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "5",
                "--skip-videos",
                "--skip-live-photos",
                "--set-exif-datetime",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        self.assertIn("Looking up all photos...", result.output)
        self.assertIn(
            f"Downloading 5 original photos to {data_dir} ...",
            result.output,
        )
        self.assertNotIn(
            "IMG_7409.MOV",
            result.output,
        )
        self.assertIn(
            "Skipping IMG_7405.MOV, only downloading photos.",
            result.output,
        )
        self.assertIn(
            "Skipping IMG_7404.MOV, only downloading photos.",
            result.output,
        )
        self.assertIn("All photos have been downloaded", result.output)

        # Check that mtime was updated to the photo creation date
        photo_mtime = os.path.getmtime(
            os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409.JPG"))
        )
        photo_modified_time = datetime.datetime.fromtimestamp(photo_mtime, datetime.timezone.utc)
        self.assertEqual("2018-07-31 07:22:24", photo_modified_time.strftime("%Y-%m-%d %H:%M:%S"))

        assert result.exit_code == 0

    def test_download_normalized_names(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2018/07/30", "IMG_7408.JPG", 1151066),
            ("2018/07/30", "IMG_7407.JPG", 656257),
        ]

        files_to_download = [
            # <>:"/\|?*  -- windows
            # / & \0x00 -- linux
            # SU1HXzc0MDkuSlBH -> i/n v:a\0l*i?d\p<a>t"h|.JPG -> aS9uIHY6YQBsKmk/ZFxwPGE+dCJofC5KUEc=
            ("2018/07/31", "i_n v_a_l_i_d_p_a_t_h_.JPG")
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_bad_filename.yml",
            files_to_create,
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "5",
                "--skip-videos",
                "--skip-live-photos",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        assert result.exit_code == 0

    def test_handle_internal_error_during_download(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        # The cassette listing_photos_internal_error_download.yml contains:
        # 1. Initial authentication
        # 2. Photo listing
        # 3. Download attempt that returns HTTP 500 error
        # The download_media function now raises PyiCloudAPIResponseException for 500 errors,
        # matching the behavior of the original mock test

        _, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_internal_error_download.yml",
            [],
            [],
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
            ],
        )

        # With HTTP 500, session raises PyiCloudAPIResponseException
        # which is caught and causes exit code 1
        self.assertIn("Authentication required for Account", result.output)
        self.assertEqual(result.exit_code, 1, "Exit Code")

    def test_handle_internal_error_during_photo_iteration(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        # The cassette listing_photos_iteration_error.yml contains:
        # 1. Initial authentication
        # 2. Photos query that returns HTTP 500 with "Internal Error at Apple."
        # No mocks needed - the cassette simulates the error

        _, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_iteration_error.yml",
            [],
            [],
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
            ],
        )

        # The session converts 500 errors to "Authentication required"
        self.assertIn(
            "Authentication required for Account",
            result.output,
        )

        self.assertEqual(result.exit_code, 1, "Exit Code")

    def test_handle_io_error_mkdir(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        original_makedirs = os.makedirs
        with mock.patch("os.makedirs", create=True) as m:
            # Raise IOError when we try to write to the destination file
            def my_makedirs(name: str, mode: int = 511, exist_ok: bool = False) -> None:
                if name > calc_data_dir(base_dir):
                    raise OSError
                original_makedirs(name, mode, exist_ok)

            m.side_effect = my_makedirs
            _, result = run_icloudpd_test(
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
                    "1",
                    "--skip-videos",
                    "--skip-live-photos",
                    "--no-progress-bar",
                    "--threads-num",
                    "1",
                ],
            )
            self.assertEqual(result.exit_code, 0, "Exit code")

    def test_dry_run(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        _, result = run_icloudpd_test(
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
                "1",
                "--skip-videos",
                "--skip-live-photos",
                "--set-exif-datetime",
                "--no-progress-bar",
                "--dry-run",
                "--threads-num",
                "1",
            ],
        )

        self.assertIn("Looking up all photos...", result.output)
        # self.assertIn(
        #     f"Downloading 2 original photos to {data_dir} ...",
        #     result.output,
        # )
        self.assertNotIn(
            "IMG_7409.MOV",
            result.output,
        )
        self.assertNotIn(
            "ERROR",
            result.output,
        )
        self.assertIn("All photos have been downloaded", result.output)

        assert result.exit_code == 0

    def test_download_after_delete_dry_run(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_recent_live.yml",
            [],
            [],
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
                "--dry-run",
                "--threads-num",
                "1",
                "--delete-after-download",
            ],
        )

        self.assertIn("Looking up all photos...", result.output)
        self.assertIn(
            f"Downloading the first original photo to {data_dir} ...",
            result.output,
        )
        self.assertIn("[DRY RUN] Would delete IMG_7409.JPG in iCloud", result.output)
        self.assertIn("All photos have been downloaded", result.output)
        # TDOO self.assertEqual(
        #     cass.all_played, False, "All mocks played")
        self.assertEqual(result.exit_code, 0, "Exit code")

    def test_download_raw_photos(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [
            ("2018/07/31", "IMG_7409.DNG")  # SU1HXzc0MDkuSlBH -> SU1HXzc0MDkuRE5H
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_raw.yml",
            [],
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
            ],
        )

        self.assertIn("Looking up all photos...", result.output)
        self.assertIn(
            f"Downloading the first original photo to {data_dir} ...",
            result.output,
        )
        self.assertNotIn(
            "IMG_7409.MOV",
            result.output,
        )
        self.assertIn("All photos have been downloaded", result.output)

        assert result.exit_code == 0

    def test_download_two_sizes(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        files_to_download = [("2018/07/31", "IMG_7409.JPG"), ("2018/07/31", "IMG_7409-thumb.JPG")]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_two_sizes.yml",
            [],
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
                "--size",
                "original",
                "--size",
                "thumb",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        self.assertIn("Looking up all photos...", result.output)
        self.assertIn(
            f"Downloading the first original,thumb photo to {data_dir} ...",
            result.output,
        )
        self.assertNotIn(
            "IMG_7409.MOV",
            result.output,
        )
        self.assertIn("All photos have been downloaded", result.output)

        assert result.exit_code == 0

    def test_download_raw_alt_photos(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [
            (
                "2018/07/31",
                "IMG_7409.CR2",
            ),  # SU1HXzc0MDkuSlBH -> SU1HXzc0MDkuRE5H -> SU1HXzc0MDkuQ1Iy
            ("2018/07/31", "IMG_7409.JPG"),
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_raw_alt.yml",
            [],
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
                "--size",
                "original",
                "--size",
                "alternative",
                "--threads-num",
                "1",
            ],
        )

        self.assertIn("Looking up all photos...", result.output)
        self.assertIn(
            f"Downloading the first original,alternative photo to {data_dir} ...",
            result.output,
        )
        self.assertNotIn(
            "IMG_7409.MOV",
            result.output,
        )
        self.assertIn("All photos have been downloaded", result.output)

        assert result.exit_code == 0

    def test_download_raw_photos_policy_alt_with_adj(self) -> None:
        """raw+jpeg does not have adj and we do not need raw, just jpeg (orig)"""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [
            # '2018/07/31/IMG_7409.CR2', # SU1HXzc0MDkuSlBH -> SU1HXzc0MDkuRE5H -> SU1HXzc0MDkuQ1Iy
            ("2018/07/31", "IMG_7409.JPG")
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_raw_alt_adj.yml",
            [],
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
                "--size",
                "adjusted",
                "--align-raw",
                "alternative",
                "--threads-num",
                "1",
            ],
        )

        self.assertIn("Looking up all photos...", result.output)
        self.assertIn(
            f"Downloading the first adjusted photo to {data_dir} ...",
            result.output,
        )
        self.assertNotIn(
            "IMG_7409.MOV",
            result.output,
        )
        self.assertIn("All photos have been downloaded", result.output)

        assert result.exit_code == 0

    def test_download_raw_photos_policy_orig(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [
            (
                "2018/07/31",
                "IMG_7409.CR2",
            ),  # SU1HXzc0MDkuSlBH -> SU1HXzc0MDkuRE5H -> SU1HXzc0MDkuQ1Iy
            # '2018/07/31/IMG_7409.JPG'
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_raw_alt.yml",
            [],
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
                # "--size",
                # "original",
                "--align-raw",
                "original",
                "--threads-num",
                "1",
            ],
        )

        self.assertIn("Looking up all photos...", result.output)
        self.assertIn(
            f"Downloading the first original photo to {data_dir} ...",
            result.output,
        )
        self.assertNotIn(
            "IMG_7409.MOV",
            result.output,
        )
        self.assertIn("All photos have been downloaded", result.output)

        assert result.exit_code == 0

    def test_download_raw_photos_policy_as_is(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [
            (
                "2018/07/31",
                "IMG_7409.CR2",
            ),  # SU1HXzc0MDkuSlBH -> SU1HXzc0MDkuRE5H -> SU1HXzc0MDkuQ1Iy
            # '2018/07/31/IMG_7409.JPG'
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_raw_alt.yml",
            [],
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
                # "--size",
                # "original",
                "--align-raw",
                "as-is",
                "--threads-num",
                "1",
            ],
        )

        self.assertIn("Looking up all photos...", result.output)
        self.assertIn(
            f"Downloading the first original photo to {data_dir} ...",
            result.output,
        )
        self.assertNotIn(
            "IMG_7409.MOV",
            result.output,
        )
        self.assertIn("All photos have been downloaded", result.output)

        assert result.exit_code == 0

    def test_download_bad_filename_base64_encoding(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2018/07/30", "IMG_7408.JPG", 1151066),
            ("2018/07/30", "IMG_7407.JPG", 656257),
        ]

        files_to_download: List[Tuple[str, str]] = [
            # <>:"/\|?*  -- windows
            # / & \0x00 -- linux
            # aS9uIHY6YQBsKmk/ZFxwPGE+dCJofC5KUE
            # ("2018/07/31", "i_n v_a_l_i_d_p_a_t_h_.JPG")
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_bad_filename_base64_encoding.yml",
            files_to_create,
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "5",
                "--skip-videos",
                "--skip-live-photos",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        self.assertIsInstance(result.exception, ValueError)
        # self.assertEqual(result.exception, ValueError("Invalid Input: 'aS9uIHY6YQBsKmk/ZFxwPGE+dCJofC5KUE'"))

    def test_download_bad_filename_utf8_encoding(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2018/07/30", "IMG_7408.JPG", 1151066),
            ("2018/07/30", "IMG_7407.JPG", 656257),
        ]

        files_to_download: List[Tuple[str, str]] = [
            # <>:"/\|?*  -- windows
            # / & \0x00 -- linux
            # aS9uIHY6YQBsKmk/ZFxwPGE+dCJofC5KUE -> abcdefgh
            # ("2018/07/31", "i_n v_a_l_i_d_p_a_t_h_.JPG")
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_bad_filename_utf8_encoding.yml",
            files_to_create,
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "5",
                "--skip-videos",
                "--skip-live-photos",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )

        self.assertIsInstance(result.exception, ValueError)
        # self.assertEqual(result.exception, ValueError("Invalid Input: b'i\\xb7\\x1dy\\xf8!'"))

    def test_download_filename_string_encoding(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2018/07/30", "IMG_7408.JPG", 1151066),
            ("2018/07/30", "IMG_7407.JPG", 656257),
        ]

        files_to_download: List[Tuple[str, str]] = [
            # SU1HXzc0MDkuSlBH -> IMG_7409.JPG
            ("2018/07/31", "IMG_7409.JPG")
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos_filename_string_encoding.yml",
            files_to_create,
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "5",
                "--skip-videos",
                "--skip-live-photos",
                "--no-progress-bar",
                "--threads-num",
                "1",
            ],
        )
        print_result_exception(result)

        self.assertEqual(result.exit_code, 0)

    def test_download_from_shared_library(self) -> None:
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
                "--library",
                "SharedSync-00000000-1111-2222-3333-444444444444",
                "--dry-run",
                "--no-progress-bar",
            ],
        )

        self.assertEqual(result.exit_code, 0)

        self.assertIn("Looking up all photos and videos...", result.output)
        self.assertIn(
            f"Downloading the first original photo or video to {data_dir} ...",
            result.output,
        )
        self.assertIn("All photos and videos have been downloaded", result.output)

    def test_download_and_skip_old(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create: List[Tuple[str, str, int]] = [
            # ("2018/07/30", "IMG_7408.JPG", 1151066),
            # ("2018/07/30", "IMG_7407.JPG", 656257),
        ]

        files_to_download = [("2018/07/31", "IMG_7409.JPG")]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos.yml",
            files_to_create,
            files_to_download,
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "5",
                "--skip-videos",
                "--skip-live-photos",
                "--set-exif-datetime",
                "--no-progress-bar",
                "--skip-created-before",
                "2018-07-31",
            ],
        )

        assert result.exit_code == 0

        self.assertIn("Looking up all photos...", result.output)
        self.assertIn(
            f"Downloading 5 original photos to {data_dir} ...",
            result.output,
        )
        for dir_name, file_name in files_to_download:
            file_path = os.path.normpath(os.path.join(dir_name, file_name))
            self.assertIn(
                f"Downloading {os.path.join(data_dir, file_path)}",
                result.output,
            )
        self.assertNotIn(
            "IMG_7409.MOV",
            result.output,
        )
        for dir_name, file_name in [
            (dir_name, file_name) for (dir_name, file_name, _) in files_to_create
        ]:
            file_path = os.path.normpath(os.path.join(dir_name, file_name))
            self.assertIn(
                f"{os.path.join(data_dir, file_path)} already exists",
                result.output,
            )

        self.assertIn(
            "Skipping IMG_7405.MOV, only downloading photos.",
            result.output,
        )
        self.assertIn(
            "Skipping IMG_7404.MOV, only downloading photos.",
            result.output,
        )
        self.assertIn(
            "Skipping IMG_7407.JPG, as it was created 2018-07-30 11:44:05.108000+00:00, before 2018-07-31 00:00:00+00:00.",
            result.output,
        )
        self.assertIn(
            "Skipping IMG_7408.JPG, as it was created 2018-07-30 11:44:10.176000+00:00, before 2018-07-31 00:00:00+00:00.",
            result.output,
        )
        self.assertIn("All photos have been downloaded", result.output)

        # Check that file was downloaded
        # Check that mtime was updated to the photo creation date
        photo_mtime = os.path.getmtime(
            os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409.JPG"))
        )
        photo_modified_time = datetime.datetime.fromtimestamp(photo_mtime, datetime.timezone.utc)
        self.assertEqual("2018-07-31 07:22:24", photo_modified_time.strftime("%Y-%m-%d %H:%M:%S"))

    def test_download_and_skip_new(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create: List[Tuple[str, str, int]] = [
            # ("2018/07/30", "IMG_7408.JPG", 1151066),
            # ("2018/07/30", "IMG_7407.JPG", 656257),
        ]

        files_to_download: List[Tuple[str, str]] = [
            # ("2018/07/30", "IMG_7408.JPG"),
            # ("2018/07/30", "IMG_7407.JPG"),
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos.yml",
            files_to_create,
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
                "--set-exif-datetime",
                "--no-progress-bar",
                "--skip-created-after",
                "2018-07-31",
            ],
        )

        assert result.exit_code == 0

        self.assertIn("Looking up all photos...", result.output)
        self.assertIn(
            f"Downloading the first original photo to {data_dir} ...",
            result.output,
        )
        for dir_name, file_name in files_to_download:
            file_path = os.path.normpath(os.path.join(dir_name, file_name))
            self.assertIn(
                f"Downloading {os.path.join(data_dir, file_path)}",
                result.output,
            )
        self.assertNotIn(
            "IMG_7409.MOV",
            result.output,
        )
        for dir_name, file_name in [
            (dir_name, file_name) for (dir_name, file_name, _) in files_to_create
        ]:
            file_path = os.path.normpath(os.path.join(dir_name, file_name))
            self.assertIn(
                f"{os.path.join(data_dir, file_path)} already exists",
                result.output,
            )

        self.assertIn(
            "Skipping IMG_7409.JPG, as it was created 2018-07-31 07:22:24.816000+00:00, after 2018-07-31 00:00:00+00:00",
            result.output,
        )
        self.assertIn("All photos have been downloaded", result.output)

    def test_resume_download(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")
        vcr_path = os.path.join(self.root_path, "vcr_cassettes")
        cookie_master_path = os.path.join(self.root_path, "cookie")

        for dir in [base_dir, data_dir]:
            recreate_path(dir)

        shutil.copytree(cookie_master_path, cookie_dir)

        files_to_create: List[Tuple[str, str, int]] = [
            ("2018/07/31", "AGHJZ6A3ATJDRWS7D5WZSUMJGNIPMVOBBY======.part", 1234),
        ]

        create_files(data_dir, files_to_create)

        result = run_cassette(
            os.path.join(vcr_path, "listing_photos_resume.yml"),
            [
                "-d",
                data_dir,
                "--cookie-directory",
                cookie_dir,
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "1",
                "--skip-videos",
                "--skip-live-photos",
                "--no-progress-bar",
            ],
        )

        assert result.exit_code == 0
        out_path = os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409.JPG"))
        self.assertIn("Looking up all photos...", result.output)
        self.assertIn(
            f"Downloading the first original photo to {data_dir} ...",
            result.output,
        )
        self.assertIn(
            f"Resuming downloading of {out_path} from 1234",
            result.output,
        )
        self.assertIn("All photos have been downloaded", result.output)

        # Check that file was downloaded
        # Check that mtime was updated to the photo creation date
        photo_mtime = os.path.getmtime(out_path)
        photo_modified_time = datetime.datetime.fromtimestamp(photo_mtime, datetime.timezone.utc)
        self.assertEqual(
            "2018-07-31 07:22:24",
            photo_modified_time.strftime("%Y-%m-%d %H:%M:%S"),
            "photo timestamp",
        )

        # check size
        photo_size = os.path.getsize(out_path)

        self.assertEqual(617 + 1234, photo_size, "photo size")
