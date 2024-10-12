import datetime
import glob
import inspect
import logging
import os
import sys
from typing import Any, List, NoReturn, Optional, Sequence, Tuple
from unittest import TestCase, mock
from unittest.mock import ANY, PropertyMock, call

import piexif
import pytest
from click.testing import CliRunner
from icloudpd import constants
from icloudpd.base import main
from icloudpd.string_helpers import truncate_middle
from piexif._exceptions import InvalidImageDataError
from pyicloud_ipd.asset_version import AssetVersion
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.exceptions import PyiCloudAPIResponseException
from pyicloud_ipd.services.photos import PhotoAlbum, PhotoAsset, PhotoLibrary
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize
from requests import Response
from requests.exceptions import ConnectionError
from vcr import VCR

from tests.helpers import (
    path_from_project_root,
    print_result_exception,
    recreate_path,
    run_icloudpd_test,
)

vcr = VCR(decode_compressed_response=True, record_mode="none")


class DownloadPhotoNameIDTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog: pytest.LogCaptureFixture) -> None:
        self._caplog = caplog
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")
        self.vcr_path = os.path.join(self.root_path, "vcr_cassettes")

    def test_download_and_skip_existing_photos_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2018/07/30", "IMG_7408_QVI4T2l.JPG", 1151066),
            ("2018/07/30", "IMG_7407_QVovd0F.JPG", 656257),
        ]

        files_to_download = [("2018/07/31", "IMG_7409_QVk2Yyt.JPG")]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.vcr_path,
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
                "--file-match-policy",
                "name-id7",
            ],
        )

        assert result.exit_code == 0

        self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
        self.assertIn(
            f"INFO     Downloading 5 original photos to {data_dir} ...",
            self._caplog.text,
        )
        for dir_name, file_name in files_to_download:
            file_path = os.path.normpath(os.path.join(dir_name, file_name))
            self.assertIn(
                f"DEBUG    Downloading {truncate_middle(os.path.join(data_dir, file_path), 96)}",
                self._caplog.text,
            )
        self.assertNotIn(
            "IMG_7409_QVk2Yyt.MOV",
            self._caplog.text,
        )
        for dir_name, file_name in [
            (dir_name, file_name) for (dir_name, file_name, _) in files_to_create
        ]:
            file_path = os.path.normpath(os.path.join(dir_name, file_name))
            self.assertIn(
                f"DEBUG    {truncate_middle(os.path.join(data_dir, file_path), 96)} already exists",
                self._caplog.text,
            )

        self.assertIn(
            "DEBUG    Skipping IMG_7405_QVkrUjN.MOV, only downloading photos.",
            self._caplog.text,
        )
        self.assertIn(
            "DEBUG    Skipping IMG_7404_QVI5TWx.MOV, only downloading photos.",
            self._caplog.text,
        )
        self.assertIn("INFO     All photos have been downloaded", self._caplog.text)

        # Check that file was downloaded
        # Check that mtime was updated to the photo creation date
        photo_mtime = os.path.getmtime(
            os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409_QVk2Yyt.JPG"))
        )
        photo_modified_time = datetime.datetime.fromtimestamp(photo_mtime, datetime.timezone.utc)
        self.assertEqual("2018-07-31 07:22:24", photo_modified_time.strftime("%Y-%m-%d %H:%M:%S"))

    def test_download_photos_and_set_exif_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2018/07/30", "IMG_7408_QVI4T2l.JPG", 1151066),
            ("2018/07/30", "IMG_7407_QVovd0F.JPG", 656257),
        ]

        files_to_download = [
            ("2018/07/30", "IMG_7405_QVkrUjN.MOV"),
            ("2018/07/30", "IMG_7407_QVovd0F.MOV"),
            ("2018/07/30", "IMG_7408_QVI4T2l.MOV"),
            ("2018/07/31", "IMG_7409_QVk2Yyt.JPG"),
            ("2018/07/31", "IMG_7409_QVk2Yyt.MOV"),
        ]

        # Download the first photo, but mock the video download
        orig_download = PhotoAsset.download

        def mocked_download(pa: PhotoAsset, _url: str) -> Response:
            if not hasattr(PhotoAsset, "already_downloaded"):
                response = orig_download(pa, _url)
                setattr(PhotoAsset, "already_downloaded", True)  # noqa: B010
                return response
            return mock.MagicMock()

        with mock.patch.object(PhotoAsset, "download", new=mocked_download):  # noqa: SIM117
            with mock.patch("icloudpd.exif_datetime.get_photo_exif") as get_exif_patched:
                get_exif_patched.return_value = False
                data_dir, result = run_icloudpd_test(
                    self.assertEqual,
                    self.vcr_path,
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
                        "4",
                        "--set-exif-datetime",
                        # '--skip-videos',
                        # "--skip-live-photos",
                        "--no-progress-bar",
                        "--file-match-policy",
                        "name-id7",
                    ],
                )
                assert result.exit_code == 0

        self.assertIn(
            "DEBUG    Looking up all photos and videos from album All Photos...",
            self._caplog.text,
        )
        self.assertIn(
            f"INFO     Downloading 4 original photos and videos to {data_dir} ...",
            self._caplog.text,
        )
        self.assertIn(
            f"DEBUG    Downloading {truncate_middle(os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409_QVk2Yyt.JPG')), 96)}",
            self._caplog.text,
        )
        # 2018:07:31 07:22:24 utc
        expectedDatetime = (
            datetime.datetime(2018, 7, 31, 7, 22, 24, tzinfo=datetime.timezone.utc)
            .astimezone()
            .strftime("%Y-%m-%d %H:%M:%S%z")
        )
        self.assertIn(
            f"DEBUG    Setting EXIF timestamp for {truncate_middle(os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409_QVk2Yyt.JPG')), 96)}: {expectedDatetime}",
            self._caplog.text,
        )
        self.assertIn("INFO     All photos have been downloaded", self._caplog.text)

    def test_download_photos_and_get_exif_exceptions_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [("2018/07/31", "IMG_7409_QVk2Yyt.JPG")]

        with mock.patch.object(piexif, "load") as piexif_patched:
            piexif_patched.side_effect = InvalidImageDataError

            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.vcr_path,
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
                    "--file-match-policy",
                    "name-id7",
                ],
            )
            assert result.exit_code == 0

        self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
        self.assertIn(
            f"INFO     Downloading the first original photo to {data_dir} ...",
            self._caplog.text,
        )
        # self.assertIn(
        #     f"DEBUG    Downloading {os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409_QVk2Yyt.JPG'))}",
        #     self._caplog.text,
        # )
        self.assertIn(
            f"DEBUG    Error fetching EXIF data for {os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409_QVk2Yyt.JPG'))}",
            self._caplog.text,
        )
        self.assertIn(
            f"DEBUG    Error setting EXIF data for {os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409_QVk2Yyt.JPG'))}",
            self._caplog.text,
        )
        self.assertIn("INFO     All photos have been downloaded", self._caplog.text)

    def test_skip_existing_downloads_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2018/07/31", "IMG_7409_QVk2Yyt.JPG", 1884695),
            ("2018/07/31", "IMG_7409_QVk2Yyt.MOV", 3294075),
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.vcr_path,
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
                # '--skip-videos',
                # "--skip-live-photos",
                "--no-progress-bar",
                "--file-match-policy",
                "name-id7",
            ],
        )
        assert result.exit_code == 0

        self.assertIn(
            "DEBUG    Looking up all photos and videos from album All Photos...", self._caplog.text
        )
        self.assertIn(
            f"INFO     Downloading the first original photo or video to {data_dir} ...",
            self._caplog.text,
        )
        self.assertIn(
            f"DEBUG    {truncate_middle(os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409_QVk2Yyt.JPG')), 96)} already exists",
            self._caplog.text,
        )
        self.assertIn(
            f"DEBUG    {truncate_middle(os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409_QVk2Yyt.MOV')), 96)} already exists",
            self._caplog.text,
        )
        self.assertIn("INFO     All photos have been downloaded", self._caplog.text)

    def test_until_found_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download_ext: Sequence[Tuple[str, str, str]] = [
            ("2018/07/31", "IMG_7409_QVk2Yyt.JPG", "photo"),
            ("2018/07/31", "IMG_7409_QVk2Yyt-medium.MOV", "photo"),
            ("2018/07/30", "IMG_7407_QVovd0F.JPG", "photo"),
            ("2018/07/30", "IMG_7407_QVovd0F-medium.MOV", "photo"),
            ("2018/07/30", "IMG_7403_QVc0VWt.MOV", "video"),
            ("2018/07/30", "IMG_7402_QVdYaDd.MOV", "video"),
            ("2018/07/30", "IMG_7399_QVVMcXN-medium.MOV", "photo"),
        ]
        files_to_create_ext: Sequence[Tuple[str, str, str, int]] = [
            ("2018/07/30", "IMG_7408_QVI4T2l.JPG", "photo", 1151066),
            ("2018/07/30", "IMG_7408_QVI4T2l-medium.MOV", "photo", 894467),
            ("2018/07/30", "IMG_7405_QVkrUjN.MOV", "video", 36491351),
            ("2018/07/30", "IMG_7404_QVI5TWx.MOV", "video", 225935003),
            # TODO large files on Windows times out
            ("2018/07/30", "IMG_7401_QVRJanZ.MOV", "photo", 565699696),
            ("2018/07/30", "IMG_7400_QVhFL01.JPG", "photo", 2308885),
            ("2018/07/30", "IMG_7400_QVhFL01-medium.MOV", "photo", 1238639),
            ("2018/07/30", "IMG_7399_QVVMcXN.JPG", "photo", 2251047),
        ]
        files_to_create = [
            (dir_name, file_name, size) for dir_name, file_name, _, size in files_to_create_ext
        ]

        with mock.patch("icloudpd.download.download_media") as dp_patched:
            dp_patched.return_value = True
            with mock.patch("icloudpd.download.os.utime") as ut_patched:
                ut_patched.return_value = None
                data_dir, result = run_icloudpd_test(
                    self.assertEqual,
                    self.vcr_path,
                    base_dir,
                    "listing_photos.yml",
                    files_to_create,
                    [],  # we fake downloading
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
                        "--file-match-policy",
                        "name-id7",
                    ],
                )

                expected_calls = list(
                    map(
                        lambda f: call(
                            ANY,
                            False,
                            ANY,
                            ANY,
                            os.path.join(data_dir, os.path.normpath(f[0]), f[1]),
                            ANY,
                            LivePhotoVersionSize.MEDIUM
                            if (f[2] == "photo" and f[1].endswith(".MOV"))
                            else AssetVersionSize.ORIGINAL,
                        ),
                        files_to_download_ext,
                    )
                )
                dp_patched.assert_has_calls(expected_calls)

                self.assertIn(
                    "DEBUG    Looking up all photos and videos from album All Photos...",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     Downloading ??? original photos and videos to {data_dir} ...",
                    self._caplog.text,
                )

                for s in files_to_create:
                    expected_message = f"DEBUG    {truncate_middle(os.path.join(data_dir, os.path.normpath(s[0]), s[1]), 96)} already exists"
                    self.assertIn(expected_message, self._caplog.text)

                for d in files_to_download_ext:
                    expected_message = f"DEBUG    {truncate_middle(os.path.join(data_dir, os.path.normpath(d[0]), d[1]), 96)} already exists"
                    self.assertNotIn(expected_message, self._caplog.text)

                self.assertIn(
                    "INFO     Found 3 consecutive previously downloaded photos. Exiting",
                    self._caplog.text,
                )
                assert result.exit_code == 0

    def test_handle_io_error_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        with mock.patch("icloudpd.download.open", create=True) as m:
            # Raise IOError when we try to write to the destination file
            m.side_effect = IOError

            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.vcr_path,
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
                    "--file-match-policy",
                    "name-id7",
                ],
            )

            self.assertIn(
                "DEBUG    Looking up all photos from album All Photos...", self._caplog.text
            )
            self.assertIn(
                f"INFO     Downloading the first original photo to {data_dir} ...",
                self._caplog.text,
            )
            self.assertIn(
                "ERROR    IOError while writing file to "
                f"{os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409_QVk2Yyt.JPG'))}. "
                "You might have run out of disk space, or the file might "
                "be too large for your OS. Skipping this file...",
                self._caplog.text,
            )
            assert result.exit_code == 0

    def test_handle_session_error_during_download_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        def mock_raise_response_error(_arg: Any) -> NoReturn:
            raise PyiCloudAPIResponseException("Invalid global session", "100")

        with mock.patch("time.sleep") as sleep_mock:  # noqa: SIM117
            with mock.patch.object(PhotoAsset, "download") as pa_download:
                pa_download.side_effect = mock_raise_response_error

                # Let the initial authenticate() call succeed,
                # but do nothing on the second try.
                orig_authenticate = PyiCloudService.authenticate

                def mocked_authenticate(self: PyiCloudService) -> None:
                    if not hasattr(self, "already_authenticated"):
                        orig_authenticate(self)
                        setattr(self, "already_authenticated", True)  # noqa: B010

                with mock.patch.object(PyiCloudService, "authenticate", new=mocked_authenticate):
                    # Pass fixed client ID via environment variable
                    _, result = run_icloudpd_test(
                        self.assertEqual,
                        self.vcr_path,
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
                            "--file-match-policy",
                            "name-id7",
                        ],
                    )

                    # Error msg should be repeated 5 times
                    assert self._caplog.text.count("Session error, re-authenticating...") == 5

                    self.assertIn(
                        "ERROR    Could not download IMG_7409_QVk2Yyt.JPG. Please try again later.",
                        self._caplog.text,
                    )

                    # Make sure we only call sleep 4 times (skip the first retry)
                    self.assertEqual(sleep_mock.call_count, 4)
                    assert result.exit_code == 0

    def test_handle_session_error_during_photo_iteration_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        def mock_raise_response_error(_offset: int) -> NoReturn:
            raise PyiCloudAPIResponseException("Invalid global session", "100")

        with mock.patch("time.sleep") as sleep_mock:  # noqa: SIM117
            with mock.patch.object(PhotoAlbum, "photos_request") as pa_photos_request:
                pa_photos_request.side_effect = mock_raise_response_error

                # Let the initial authenticate() call succeed,
                # but do nothing on the second try.
                orig_authenticate = PyiCloudService.authenticate

                def mocked_authenticate(self: PyiCloudService) -> None:
                    if not hasattr(self, "already_authenticated"):
                        orig_authenticate(self)
                        setattr(self, "already_authenticated", True)  # noqa: B010

                with mock.patch.object(PyiCloudService, "authenticate", new=mocked_authenticate):
                    # Pass fixed client ID via environment variable
                    _, result = run_icloudpd_test(
                        self.assertEqual,
                        self.vcr_path,
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
                            "--file-match-policy",
                            "name-id7",
                        ],
                    )

                    # Error msg should be repeated 5 times
                    assert self._caplog.text.count("Session error, re-authenticating...") == 5

                    self.assertIn(
                        "ERROR    iCloud re-authentication failed. Please try again later.",
                        self._caplog.text,
                    )
                    # Make sure we only call sleep 4 times (skip the first retry)
                    self.assertEqual(sleep_mock.call_count, 4)

                    assert result.exit_code == 1

    def test_handle_connection_error_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        def mock_raise_response_error(_arg: Any) -> NoReturn:
            raise ConnectionError("Connection Error")

        with mock.patch.object(PhotoAsset, "download") as pa_download:
            pa_download.side_effect = mock_raise_response_error

            # Let the initial authenticate() call succeed,
            # but do nothing on the second try.
            orig_authenticate = PyiCloudService.authenticate

            def mocked_authenticate(self: PyiCloudService) -> None:
                if not hasattr(self, "already_authenticated"):
                    orig_authenticate(self)
                    setattr(self, "already_authenticated", True)  # noqa: B010

            with mock.patch("icloudpd.constants.WAIT_SECONDS", 0):  # noqa: SIM117
                with mock.patch.object(PyiCloudService, "authenticate", new=mocked_authenticate):
                    _, result = run_icloudpd_test(
                        self.assertEqual,
                        self.vcr_path,
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
                            "--file-match-policy",
                            "name-id7",
                        ],
                    )

                    # Error msg should be repeated 5 times
                    assert (
                        self._caplog.text.count(
                            "Error downloading IMG_7409_QVk2Yyt.JPG, retrying after 0 seconds..."
                        )
                        == 5
                    )

                    self.assertIn(
                        "ERROR    Could not download IMG_7409_QVk2Yyt.JPG. Please try again later.",
                        self._caplog.text,
                    )
                    assert result.exit_code == 0

    def test_handle_albums_error_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        def mock_raise_response_error() -> None:
            raise PyiCloudAPIResponseException("Api Error", "100")

        with mock.patch.object(PhotoLibrary, "_fetch_folders") as pa_photos_request:
            pa_photos_request.side_effect = mock_raise_response_error

            # Let the initial authenticate() call succeed,
            # but do nothing on the second try.
            orig_authenticate = PyiCloudService.authenticate

            def mocked_authenticate(self: PyiCloudService) -> None:
                if not hasattr(self, "already_authenticated"):
                    orig_authenticate(self)
                    setattr(self, "already_authenticated", True)  # noqa: B010

            with mock.patch("icloudpd.constants.WAIT_SECONDS", 0):  # noqa: SIM117
                with mock.patch.object(PyiCloudService, "authenticate", new=mocked_authenticate):
                    _, result = run_icloudpd_test(
                        self.assertEqual,
                        self.vcr_path,
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
                            "--file-match-policy",
                            "name-id7",
                        ],
                    )

                    assert result.exit_code == 1

    def test_missing_size_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        with mock.patch.object(PhotoAsset, "download") as pa_download:
            pa_download.return_value = False

            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.vcr_path,
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
                    "3",
                    "--no-progress-bar",
                    "--file-match-policy",
                    "name-id7",
                ],
            )

            self.assertIn(
                "DEBUG    Looking up all photos and videos from album All Photos...",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Downloading 3 original photos and videos to {data_dir} ...",
                self._caplog.text,
            )

            # These error messages should not be repeated more than once for each size
            for filename in [
                "IMG_7409_QVk2Yyt.JPG",
                "IMG_7408_QVI4T2l.JPG",
                "IMG_7407_QVovd0F.JPG",
            ]:
                for size in ["original"]:
                    self.assertEqual(
                        sum(
                            1
                            for line in self._caplog.text.splitlines()
                            if line
                            == f"ERROR    Could not find URL to download {filename} for size {size}"
                        ),
                        1,
                        f"Errors for {filename} size {size}",
                    )

            for filename in [
                "IMG_7409_QVk2Yyt.MOV",
                "IMG_7408_QVI4T2l.MOV",
                "IMG_7407_QVovd0F.MOV",
            ]:
                for size in ["originalVideo"]:
                    self.assertEqual(
                        sum(
                            1
                            for line in self._caplog.text.splitlines()
                            if line
                            == f"ERROR    Could not find URL to download {filename} for size {size}"
                        ),
                        1,
                        f"Errors for {filename} size {size}",
                    )

            self.assertIn("INFO     All photos have been downloaded", self._caplog.text)
            self.assertEqual(result.exit_code, 0, "Exit code")

    def test_size_fallback_to_original_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        with mock.patch("icloudpd.download.download_media") as dp_patched:
            dp_patched.return_value = True

            with mock.patch("icloudpd.download.os.utime") as ut_patched:
                ut_patched.return_value = None

                with mock.patch.object(
                    PhotoAsset, "versions", new_callable=mock.PropertyMock
                ) as pa:
                    pa.return_value = {
                        AssetVersionSize.ORIGINAL: AssetVersion(
                            "IMG_7409_QVk2Yyt.JPG", 1, "http", "jpeg"
                        ),
                        AssetVersionSize.MEDIUM: AssetVersion(
                            "IMG_7409_QVk2Yyt.JPG", 2, "ftp", "movie"
                        ),
                    }

                    data_dir, result = run_icloudpd_test(
                        self.assertEqual,
                        self.vcr_path,
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
                            "--size",
                            "thumb",
                            "--no-progress-bar",
                            "--file-match-policy",
                            "name-id7",
                        ],
                    )
                    self.assertIn(
                        "DEBUG    Looking up all photos and videos from album All Photos...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        f"INFO     Downloading the first thumb photo or video to {data_dir} ...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        f"DEBUG    Downloading {truncate_middle(os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409_QVk2Yyt.JPG')), 96)}",
                        self._caplog.text,
                    )
                    self.assertIn("INFO     All photos have been downloaded", self._caplog.text)
                    dp_patched.assert_called_once_with(
                        ANY,
                        False,
                        ANY,
                        ANY,
                        f"{os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409_QVk2Yyt.JPG'))}",
                        ANY,
                        AssetVersionSize.ORIGINAL,
                    )

                    assert result.exit_code == 0

    def test_force_size_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        with mock.patch("icloudpd.download.download_media") as dp_patched:
            dp_patched.return_value = True

            with mock.patch.object(PhotoAsset, "versions", new_callable=PropertyMock) as pa:
                pa.return_value = {
                    AssetVersionSize.ORIGINAL: {"filename": "IMG1.JPG"},
                    AssetVersionSize.MEDIUM: {"filename": "IMG_1.JPG"},
                }

                data_dir, result = run_icloudpd_test(
                    self.assertEqual,
                    self.vcr_path,
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
                        "--size",
                        "thumb",
                        "--force-size",
                        "--no-progress-bar",
                        "--file-match-policy",
                        "name-id7",
                    ],
                )

                self.assertIn(
                    "DEBUG    Looking up all photos and videos from album All Photos...",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     Downloading the first thumb photo or video to {data_dir} ...",
                    self._caplog.text,
                )
                self.assertIn(
                    "ERROR    thumb size does not exist for IMG_7409_QVk2Yyt.JPG. Skipping...",
                    self._caplog.text,
                )
                self.assertIn("INFO     All photos have been downloaded", self._caplog.text)
                dp_patched.assert_not_called()

                assert result.exit_code == 0

    def test_invalid_creation_date_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [("2018/01/01", "IMG_7409_QVk2Yyt.JPG")]

        with mock.patch.object(PhotoAsset, "created", new_callable=mock.PropertyMock) as dt_mock:
            # Can't mock `astimezone` because it's a readonly property, so have to
            # create a new class that inherits from datetime.datetime
            class NewDateTime(datetime.datetime):
                def astimezone(self, _tz: (Optional[Any]) = None) -> NoReturn:
                    raise ValueError("Invalid date")

            dt_mock.return_value = NewDateTime(2018, 1, 1, 0, 0, 0)

            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.vcr_path,
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
                    "--file-match-policy",
                    "name-id7",
                ],
            )

            self.assertIn(
                "DEBUG    Looking up all photos and videos from album All Photos...",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Downloading the first original photo or video to {data_dir} ...",
                self._caplog.text,
            )
            self.assertIn(
                "ERROR    Could not convert photo created date to local timezone (2018-01-01 00:00:00)",
                self._caplog.text,
            )
            self.assertIn(
                f"DEBUG    Downloading {truncate_middle(os.path.join(data_dir, os.path.normpath('2018/01/01/IMG_7409_QVk2Yyt.JPG')), 96)}",
                self._caplog.text,
            )
            self.assertIn("INFO     All photos have been downloaded", self._caplog.text)
            assert result.exit_code == 0

    @pytest.mark.skipif(sys.platform == "win32", reason="does not run on windows")
    @pytest.mark.skipif(sys.platform == "darwin", reason="does not run on mac")
    def test_invalid_creation_year_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [("5/01/01", "IMG_7409_QVk2Yyt.JPG")]

        with mock.patch.object(PhotoAsset, "created", new_callable=mock.PropertyMock) as dt_mock:
            # Can't mock `astimezone` because it's a readonly property, so have to
            # create a new class that inherits from datetime.datetime
            class NewDateTime(datetime.datetime):
                def astimezone(self, _tz: (Optional[Any]) = None) -> NoReturn:
                    raise ValueError("Invalid date")

            dt_mock.return_value = NewDateTime(5, 1, 1, 0, 0, 0)

            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.vcr_path,
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
                    "--file-match-policy",
                    "name-id7",
                ],
            )

            self.assertIn(
                "DEBUG    Looking up all photos and videos from album All Photos...",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Downloading the first original photo or video to {data_dir} ...",
                self._caplog.text,
            )
            self.assertIn(
                "ERROR    Could not convert photo created date to local timezone (0005-01-01 00:00:00)",
                self._caplog.text,
            )
            self.assertIn(
                f"DEBUG    Downloading {truncate_middle(os.path.join(data_dir, os.path.normpath('5/01/01/IMG_7409_QVk2Yyt.JPG')), 96)}",
                self._caplog.text,
            )
            self.assertIn("INFO     All photos have been downloaded", self._caplog.text)
            assert result.exit_code == 0

    def test_unknown_item_type_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        with mock.patch("icloudpd.download.download_media") as dp_patched:
            dp_patched.return_value = True

            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.vcr_path,
                base_dir,
                "listing_photos_bad_item_type.yml",
                [],
                [],
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "1",
                    "--no-progress-bar",
                    "--file-match-policy",
                    "name-id7",
                ],
            )

            dp_patched.assert_not_called()

            self.assertIsInstance(result.exception, ValueError)

    def test_download_and_dedupe_existing_photos_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2018/07/30", "IMG_7408_QVI4T2l.JPG", 1),
            ("2018/07/30", "IMG_7408_QVI4T2l.MOV", 1),
            ("2018/07/30", "IMG_7407_QVovd0F.JPG", 1),
            ("2018/07/30", "IMG_7407_QVovd0F.MOV", 1),
        ]

        files_to_download = [
            ("2018/07/31", "IMG_7409_QVk2Yyt.JPG"),
            ("2018/07/31", "IMG_7409_QVk2Yyt.MOV"),
        ]

        # Download the first photo, but mock the video download
        orig_download = PhotoAsset.download

        def mocked_download(self: PhotoAsset, _url: str) -> Response:
            if not hasattr(PhotoAsset, "already_downloaded"):
                response = orig_download(self, _url)
                setattr(PhotoAsset, "already_downloaded", True)  # noqa: B010
                return response
            return mock.MagicMock()

        with mock.patch.object(PhotoAsset, "download", new=mocked_download):
            data_dir, result = run_icloudpd_test(
                self.assertEqual,
                self.vcr_path,
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
                    # "--set-exif-datetime",
                    "--no-progress-bar",
                    "--file-match-policy",
                    "name-id7",
                ],
            )

            self.assertIn(
                "DEBUG    Looking up all photos from album All Photos...", self._caplog.text
            )
            self.assertIn(
                f"INFO     Downloading 5 original photos to {data_dir} ...",
                self._caplog.text,
            )
            self.assertNotIn(
                "deduplicated",
                self._caplog.text,
            )
            self.assertIn(
                "DEBUG    Skipping IMG_7405_QVkrUjN.MOV, only downloading photos.",
                self._caplog.text,
            )
            self.assertIn(
                "DEBUG    Skipping IMG_7404_QVI5TWx.MOV, only downloading photos.",
                self._caplog.text,
            )
            self.assertIn("INFO     All photos have been downloaded", self._caplog.text)

            assert result.exit_code == 0

    def test_download_photos_and_set_exif_exceptions_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [("2018/07/31", "IMG_7409_QVk2Yyt.JPG")]

        with mock.patch.object(piexif, "insert") as piexif_patched:
            piexif_patched.side_effect = InvalidImageDataError
            with mock.patch("icloudpd.exif_datetime.get_photo_exif") as get_exif_patched:
                get_exif_patched.return_value = False
                data_dir, result = run_icloudpd_test(
                    self.assertEqual,
                    self.vcr_path,
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
                        "--file-match-policy",
                        "name-id7",
                    ],
                )

                self.assertIn(
                    "DEBUG    Looking up all photos from album All Photos...", self._caplog.text
                )
                self.assertIn(
                    f"INFO     Downloading the first original photo to {data_dir} ...",
                    self._caplog.text,
                )
                # 2018:07:31 07:22:24 utc
                expectedDatetime = (
                    datetime.datetime(2018, 7, 31, 7, 22, 24, tzinfo=datetime.timezone.utc)
                    .astimezone()
                    .strftime("%Y-%m-%d %H:%M:%S%z")
                )
                self.assertIn(
                    f"DEBUG    Setting EXIF timestamp for {os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409_QVk2Yyt.JPG'))}: {expectedDatetime}",
                    self._caplog.text,
                )
                self.assertIn(
                    f"DEBUG    Error setting EXIF data for {os.path.join(data_dir, os.path.normpath('2018/07/31/IMG_7409_QVk2Yyt.JPG'))}",
                    self._caplog.text,
                )
                self.assertIn("INFO     All photos have been downloaded", self._caplog.text)
                assert result.exit_code == 0

    def test_download_chinese_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3], "中文")

        files_to_download = [("2018/07/31", "IMG_7409_QVk2Yyt.JPG")]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.vcr_path,
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
                "--file-match-policy",
                "name-id7",
            ],
        )

        self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
        self.assertIn(
            f"INFO     Downloading the first original photo to {data_dir} ...",
            self._caplog.text,
        )
        self.assertNotIn(
            "IMG_7409_QVk2Yyt.MOV",
            self._caplog.text,
        )
        self.assertIn("INFO     All photos have been downloaded", self._caplog.text)

        # Check that mtime was updated to the photo creation date
        photo_mtime = os.path.getmtime(
            os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409_QVk2Yyt.JPG"))
        )
        photo_modified_time = datetime.datetime.fromtimestamp(photo_mtime, datetime.timezone.utc)
        self.assertEqual("2018-07-31 07:22:24", photo_modified_time.strftime("%Y-%m-%d %H:%M:%S"))

        assert result.exit_code == 0

    def test_download_one_recent_live_photo_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [
            ("2018/07/31", "IMG_7409_QVk2Yyt.JPG"),
            ("2018/07/31", "IMG_7409_QVk2Yyt.MOV"),
        ]

        # Download the first photo, but mock the video download
        orig_download = PhotoAsset.download

        def mocked_download(pa: PhotoAsset, _url: str) -> Response:
            if not hasattr(PhotoAsset, "already_downloaded"):
                response = orig_download(pa, _url)
                setattr(PhotoAsset, "already_downloaded", True)  # noqa: B010
                return response
            return mock.MagicMock()

        with mock.patch.object(PhotoAsset, "download", new=mocked_download):  # noqa: SIM117
            with mock.patch("icloudpd.exif_datetime.get_photo_exif") as get_exif_patched:
                get_exif_patched.return_value = False
                data_dir, result = run_icloudpd_test(
                    self.assertEqual,
                    self.vcr_path,
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
                        # "--set-exif-datetime",
                        # '--skip-videos',
                        # "--skip-live-photos",
                        "--no-progress-bar",
                        "--file-match-policy",
                        "name-id7",
                    ],
                )

                self.assertIn(
                    "DEBUG    Looking up all photos and videos from album All Photos...",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     Downloading the first original photo or video to {data_dir} ...",
                    self._caplog.text,
                )
                self.assertIn("INFO     All photos have been downloaded", self._caplog.text)
                assert result.exit_code == 0

    def test_download_one_recent_live_photo_chinese_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [
            ("2018/07/31", "IMG_中文_7409_QVk2Yyt.JPG"),  # SU1HX+S4reaWh183NDA5LkpQRw==
            ("2018/07/31", "IMG_中文_7409_QVk2Yyt.MOV"),
        ]

        # Download the first photo, but mock the video download
        orig_download = PhotoAsset.download

        def mocked_download(pa: PhotoAsset, _url: str) -> Response:
            if not hasattr(PhotoAsset, "already_downloaded"):
                response = orig_download(pa, _url)
                setattr(PhotoAsset, "already_downloaded", True)  # noqa: B010
                return response
            return mock.MagicMock()

        with mock.patch.object(PhotoAsset, "download", new=mocked_download):  # noqa: SIM117
            with mock.patch("icloudpd.exif_datetime.get_photo_exif") as get_exif_patched:
                get_exif_patched.return_value = False
                data_dir, result = run_icloudpd_test(
                    self.assertEqual,
                    self.vcr_path,
                    base_dir,
                    "listing_photos_chinese.yml",
                    [],
                    files_to_download,
                    [
                        "--username",
                        "jdoe@gmail.com",
                        "--password",
                        "password1",
                        "--recent",
                        "1",
                        # "--set-exif-datetime",
                        # '--skip-videos',
                        # "--skip-live-photos",
                        "--no-progress-bar",
                        "--keep-unicode-in-filenames",
                        "true",
                        "--file-match-policy",
                        "name-id7",
                    ],
                )

                self.assertIn(
                    "DEBUG    Looking up all photos and videos from album All Photos...",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     Downloading the first original photo or video to {data_dir} ...",
                    self._caplog.text,
                )
                self.assertIn("INFO     All photos have been downloaded", self._caplog.text)
                assert result.exit_code == 0

    def test_download_after_delete_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [("2018/07/31", "IMG_7409_QVk2Yyt.JPG")]

        with mock.patch.object(piexif, "insert") as piexif_patched:
            piexif_patched.side_effect = InvalidImageDataError
            with mock.patch("icloudpd.exif_datetime.get_photo_exif") as get_exif_patched:
                get_exif_patched.return_value = False
                data_dir, result = run_icloudpd_test(
                    self.assertEqual,
                    self.vcr_path,
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
                        "--file-match-policy",
                        "name-id7",
                        "--delete-after-download",
                    ],
                )

                self.assertIn(
                    "DEBUG    Looking up all photos from album All Photos...", self._caplog.text
                )
                self.assertIn(
                    f"INFO     Downloading the first original photo to {data_dir} ...",
                    self._caplog.text,
                )
                self.assertIn("INFO     Deleted IMG_7409_QVk2Yyt.JPG in iCloud", self._caplog.text)
                self.assertIn("INFO     All photos have been downloaded", self._caplog.text)
                # TODO assert cass.all_played
                assert result.exit_code == 0

    def test_download_after_delete_fail_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.vcr_path,
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
                "--file-match-policy",
                "name-id7",
                "--delete-after-download",
            ],
        )

        self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
        self.assertIn(
            f"INFO     Downloading the first original photo to {data_dir} ...",
            self._caplog.text,
        )
        self.assertNotIn("INFO     Deleted IMG_7409_QVk2Yyt.JPG in iCloud", self._caplog.text)
        self.assertIn("INFO     All photos have been downloaded", self._caplog.text)
        # TODO assert cass.all_played
        assert result.exit_code == 0

    def test_download_over_old_original_photos_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2018/07/30", "IMG_7408_QVI4T2l-original.JPG", 1151066),
            ("2018/07/30", "IMG_7407_QVovd0F.JPG", 656257),
        ]

        files_to_download = [("2018/07/31", "IMG_7409_QVk2Yyt.JPG")]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.vcr_path,
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
                "--file-match-policy",
                "name-id7",
            ],
        )

        self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
        self.assertIn(
            f"INFO     Downloading 5 original photos to {data_dir} ...",
            self._caplog.text,
        )
        self.assertNotIn(
            "IMG_7409_QVk2Yyt.MOV",
            self._caplog.text,
        )
        self.assertIn(
            "DEBUG    Skipping IMG_7405_QVkrUjN.MOV, only downloading photos.",
            self._caplog.text,
        )
        self.assertIn(
            "DEBUG    Skipping IMG_7404_QVI5TWx.MOV, only downloading photos.",
            self._caplog.text,
        )
        self.assertIn("INFO     All photos have been downloaded", self._caplog.text)

        # Check that mtime was updated to the photo creation date
        photo_mtime = os.path.getmtime(
            os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409_QVk2Yyt.JPG"))
        )
        photo_modified_time = datetime.datetime.fromtimestamp(photo_mtime, datetime.timezone.utc)
        self.assertEqual("2018-07-31 07:22:24", photo_modified_time.strftime("%Y-%m-%d %H:%M:%S"))

        assert result.exit_code == 0

    def test_download_normalized_names_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2018/07/30", "IMG_7408_QVI4T2l.JPG", 1151066),
            ("2018/07/30", "IMG_7407_QVovd0F.JPG", 656257),
        ]

        files_to_download = [
            # <>:"/\|?*  -- windows
            # / & \0x00 -- linux
            # SU1HXzc0MDkuSlBH -> i/n v:a\0l*i?d\p<a>t"h|.JPG -> aS9uIHY6YQBsKmk/ZFxwPGE+dCJofC5KUEc=
            ("2018/07/31", "i_n v_a_l_i_d_p_a_t_h__QVk2Yyt.JPG")
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.vcr_path,
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
                "--file-match-policy",
                "name-id7",
            ],
        )

        assert result.exit_code == 0

    @pytest.mark.skip("not ready yet. may be not needed")
    def test_download_watch_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)

        files_to_create = [
            ("2018/07/30/IMG_7408_QVI4T2l.JPG", 1151066),
            ("2018/07/30/IMG_7407_QVovd0F.JPG", 656257),
        ]

        files_to_download = ["2018/07/31/IMG_7409_QVk2Yyt.JPG"]

        os.makedirs(os.path.join(data_dir, "2018/07/30/"))
        for file_name, file_size in files_to_create:
            with open(os.path.join(data_dir, file_name), "a") as f:
                f.truncate(file_size)

        # def my_sleep(_target_duration: int) -> Callable[[int], None]:
        #     counter: int = 0

        #     def sleep_(duration: int) -> None:
        #         if counter > duration:
        #             raise ValueError("SLEEP MOCK")
        #         counter = counter + 1
        #     return sleep_

        with mock.patch("time.sleep"):
            # import random
            target_duration = 1
            # sleep_patched.side_effect = my_sleep(target_duration)
            with vcr.use_cassette(os.path.join(self.vcr_path, "listing_photos.yml")):
                # Pass fixed client ID via environment variable
                runner = CliRunner(env={"CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"})
                result = runner.invoke(
                    main,
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
                        "--file-match-policy",
                        "name-id7",
                        "-d",
                        data_dir,
                        "--watch-with-interval",
                        str(target_duration),
                        "--cookie-directory",
                        cookie_dir,
                    ],
                )
                print_result_exception(result)

                assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_create) + len(files_to_download)

        for file_name in files_to_download + ([file_name for (file_name, _) in files_to_create]):
            assert os.path.exists(
                os.path.join(data_dir, os.path.normpath(file_name))
            ), f"File {file_name} expected, but does not exist"

    def test_handle_internal_error_during_download_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        def mock_raise_response_error(_arg: Any) -> NoReturn:
            raise PyiCloudAPIResponseException("INTERNAL_ERROR", "INTERNAL_ERROR")

        with mock.patch("time.sleep") as sleep_mock:  # noqa: SIM117
            with mock.patch.object(PhotoAsset, "download") as pa_download:
                pa_download.side_effect = mock_raise_response_error

                # Pass fixed client ID via environment variable
                _, result = run_icloudpd_test(
                    self.assertEqual,
                    self.vcr_path,
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
                        "--file-match-policy",
                        "name-id7",
                    ],
                )

                # Error msg should be repeated 5 times
                # self.assertEqual(
                #     self._caplog.text.count(
                #         "Error downloading"
                #     ), constants.MAX_RETRIES, "Retry count"
                # )

                self.assertIn(
                    "ERROR    Could not download IMG_7409_QVk2Yyt.JPG. Please try again later.",
                    self._caplog.text,
                )

                # Make sure we only call sleep 4 times (skip the first retry)
                self.assertEqual(sleep_mock.call_count, 5)
                self.assertEqual(result.exit_code, 0, "Exit Code")

    def test_handle_internal_error_during_photo_iteration_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        def mock_raise_response_error(_offset: int) -> NoReturn:
            raise PyiCloudAPIResponseException("INTERNAL_ERROR", "INTERNAL_ERROR")

        with mock.patch("time.sleep") as sleep_mock:  # noqa: SIM117
            with mock.patch.object(PhotoAlbum, "photos_request") as pa_photos_request:
                pa_photos_request.side_effect = mock_raise_response_error

                _, result = run_icloudpd_test(
                    self.assertEqual,
                    self.vcr_path,
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
                        "--file-match-policy",
                        "name-id7",
                    ],
                )

                # Error msg should be repeated 5 times
                self.assertEqual(
                    self._caplog.text.count("Internal Error at Apple, retrying..."),
                    constants.MAX_RETRIES,
                    "Retry count",
                )

                self.assertIn(
                    "ERROR    Internal Error at Apple.",
                    self._caplog.text,
                )

                # Make sure we only call sleep 4 times (skip the first retry)
                self.assertEqual(sleep_mock.call_count, 5)

                self.assertEqual(result.exit_code, 1, "Exit Code")

    def test_handle_io_error_mkdir_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        # TODO remove code dup
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)  # this needs to happen before mock

        with vcr.use_cassette(os.path.join(self.vcr_path, "listing_photos.yml")):  # noqa: SIM117
            with mock.patch("os.makedirs", create=True) as m:
                # Raise IOError when we try to write to the destination file
                m.side_effect = IOError

                runner = CliRunner(env={"CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"})
                result = runner.invoke(
                    main,
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
                        "--file-match-policy",
                        "name-id7",
                        "-d",
                        data_dir,
                        "--cookie-directory",
                        cookie_dir,
                    ],
                )
                print_result_exception(result)

                self.assertIn(
                    "DEBUG    Looking up all photos from album All Photos...", self._caplog.text
                )
                self.assertIn(
                    f"INFO     Downloading the first original photo to {data_dir} ...",
                    self._caplog.text,
                )
                self.assertIn(
                    f"ERROR    Could not create folder {data_dir}",
                    self._caplog.text,
                )
                self.assertEqual(result.exit_code, 0, "Exit code")

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

        self.assertEqual(sum(1 for _ in files_in_result), 0, "Files at the end")

    def test_dry_run_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        _, result = run_icloudpd_test(
            self.assertEqual,
            self.vcr_path,
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
                "--file-match-policy",
                "name-id7",
            ],
        )

        self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
        # self.assertIn(
        #     f"INFO     Downloading 2 original photos to {data_dir} ...",
        #     self._caplog.text,
        # )
        self.assertNotIn(
            "IMG_7409_QVk2Yyt.MOV",
            self._caplog.text,
        )
        self.assertNotIn(
            "ERROR",
            self._caplog.text,
        )
        self.assertIn("INFO     All photos have been downloaded", self._caplog.text)

        assert result.exit_code == 0

    def test_download_after_delete_dry_run_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        def raise_response_error(
            a0_: logging.Logger, a1_: PyiCloudService, a2_: PhotoAsset
        ) -> NoReturn:
            raise Exception("Unexpected call to delete_photo")

        with mock.patch.object(piexif, "insert") as piexif_patched:
            piexif_patched.side_effect = InvalidImageDataError
            with mock.patch("icloudpd.exif_datetime.get_photo_exif") as get_exif_patched:
                get_exif_patched.return_value = False
                with mock.patch("icloudpd.base.delete_photo") as df_patched:
                    df_patched.side_effect = raise_response_error

                    data_dir, result = run_icloudpd_test(
                        self.assertEqual,
                        self.vcr_path,
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
                            "--dry-run",
                            "--file-match-policy",
                            "name-id7",
                            "--delete-after-download",
                        ],
                    )

                    self.assertIn(
                        "DEBUG    Looking up all photos from album All Photos...", self._caplog.text
                    )
                    self.assertIn(
                        f"INFO     Downloading the first original photo to {data_dir} ...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        "INFO     [DRY RUN] Would delete IMG_7409_QVk2Yyt.JPG in iCloud",
                        self._caplog.text,
                    )
                    self.assertIn("INFO     All photos have been downloaded", self._caplog.text)
                    # TDOO self.assertEqual(
                    #     cass.all_played, False, "All mocks played")
                    self.assertEqual(result.exit_code, 0, "Exit code")

    def test_download_raw_photos_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [
            ("2018/07/31", "IMG_7409_QVk2Yyt.DNG")  # SU1HXzc0MDkuSlBH -> SU1HXzc0MDkuRE5H
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.vcr_path,
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
                "--file-match-policy",
                "name-id7",
            ],
        )

        self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
        self.assertIn(
            f"INFO     Downloading the first original photo to {data_dir} ...",
            self._caplog.text,
        )
        self.assertNotIn(
            "IMG_7409_QVk2Yyt.MOV",
            self._caplog.text,
        )
        self.assertIn("INFO     All photos have been downloaded", self._caplog.text)

        assert result.exit_code == 0

    def test_download_two_sizes_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        files_to_download = [
            ("2018/07/31", "IMG_7409_QVk2Yyt.JPG"),
            ("2018/07/31", "IMG_7409_QVk2Yyt-thumb.JPG"),
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.vcr_path,
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
                "--file-match-policy",
                "name-id7",
            ],
        )

        self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
        self.assertIn(
            f"INFO     Downloading the first original,thumb photo to {data_dir} ...",
            self._caplog.text,
        )
        self.assertNotIn(
            "IMG_7409_QVk2Yyt.MOV",
            self._caplog.text,
        )
        self.assertIn("INFO     All photos have been downloaded", self._caplog.text)

        assert result.exit_code == 0

    def test_download_raw_alt_photos_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [
            (
                "2018/07/31",
                "IMG_7409_QVk2Yyt.CR2",
            ),  # SU1HXzc0MDkuSlBH -> SU1HXzc0MDkuRE5H -> SU1HXzc0MDkuQ1Iy
            ("2018/07/31", "IMG_7409_QVk2Yyt.JPG"),
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.vcr_path,
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
                "--file-match-policy",
                "name-id7",
            ],
        )

        self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
        self.assertIn(
            f"INFO     Downloading the first original,alternative photo to {data_dir} ...",
            self._caplog.text,
        )
        self.assertNotIn(
            "IMG_7409_QVk2Yyt.MOV",
            self._caplog.text,
        )
        self.assertIn("INFO     All photos have been downloaded", self._caplog.text)

        assert result.exit_code == 0

    def test_download_raw_photos_policy_alt_with_adj_name_id7(self) -> None:
        """raw+jpeg does not have adj and we do not need raw, just jpeg (orig)"""
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [
            # '2018/07/31/IMG_7409_QVk2Yyt.CR2', # SU1HXzc0MDkuSlBH -> SU1HXzc0MDkuRE5H -> SU1HXzc0MDkuQ1Iy
            ("2018/07/31", "IMG_7409_QVk2Yyt.JPG")
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.vcr_path,
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
                "--file-match-policy",
                "name-id7",
            ],
        )

        self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
        self.assertIn(
            f"INFO     Downloading the first adjusted photo to {data_dir} ...",
            self._caplog.text,
        )
        self.assertNotIn(
            "IMG_7409_QVk2Yyt.MOV",
            self._caplog.text,
        )
        self.assertIn("INFO     All photos have been downloaded", self._caplog.text)

        assert result.exit_code == 0

    def test_download_raw_photos_policy_orig_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [
            (
                "2018/07/31",
                "IMG_7409_QVk2Yyt.CR2",
            ),  # SU1HXzc0MDkuSlBH -> SU1HXzc0MDkuRE5H -> SU1HXzc0MDkuQ1Iy
            # '2018/07/31/IMG_7409_QVk2Yyt.JPG'
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.vcr_path,
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
                "--file-match-policy",
                "name-id7",
            ],
        )

        self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
        self.assertIn(
            f"INFO     Downloading the first original photo to {data_dir} ...",
            self._caplog.text,
        )
        self.assertNotIn(
            "IMG_7409_QVk2Yyt.MOV",
            self._caplog.text,
        )
        self.assertIn("INFO     All photos have been downloaded", self._caplog.text)

        assert result.exit_code == 0

    def test_download_raw_photos_policy_as_is_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_download = [
            (
                "2018/07/31",
                "IMG_7409_QVk2Yyt.CR2",
            ),  # SU1HXzc0MDkuSlBH -> SU1HXzc0MDkuRE5H -> SU1HXzc0MDkuQ1Iy
            # '2018/07/31/IMG_7409_QVk2Yyt.JPG'
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.vcr_path,
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
                "--file-match-policy",
                "name-id7",
            ],
        )

        self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
        self.assertIn(
            f"INFO     Downloading the first original photo to {data_dir} ...",
            self._caplog.text,
        )
        self.assertNotIn(
            "IMG_7409_QVk2Yyt.MOV",
            self._caplog.text,
        )
        self.assertIn("INFO     All photos have been downloaded", self._caplog.text)

        assert result.exit_code == 0

    def test_download_bad_filename_base64_encoding_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2018/07/30", "IMG_7408_QVI4T2l.JPG", 1151066),
            ("2018/07/30", "IMG_7407_QVovd0F.JPG", 656257),
        ]

        files_to_download: List[Tuple[str, str]] = [
            # <>:"/\|?*  -- windows
            # / & \0x00 -- linux
            # aS9uIHY6YQBsKmk/ZFxwPGE+dCJofC5KUE
            # ("2018/07/31", "i_n v_a_l_i_d_p_a_t_h_.JPG")
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.vcr_path,
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
                "--file-match-policy",
                "name-id7",
            ],
        )

        self.assertIsInstance(result.exception, ValueError)
        # ValueError("Invalid Input: 'aS9uIHY6YQBsKmk/ZFxwPGE+dCJofC5KUE'")

    def test_download_bad_filename_utf8_encoding_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2018/07/30", "IMG_7408_QVI4T2l.JPG", 1151066),
            ("2018/07/30", "IMG_7407_QVovd0F.JPG", 656257),
        ]

        files_to_download: List[Tuple[str, str]] = [
            # <>:"/\|?*  -- windows
            # / & \0x00 -- linux
            # aS9uIHY6YQBsKmk/ZFxwPGE+dCJofC5KUE -> abcdefgh
            # ("2018/07/31", "i_n v_a_l_i_d_p_a_t_h_.JPG")
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.vcr_path,
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
                "--file-match-policy",
                "name-id7",
            ],
        )

        self.assertIsInstance(result.exception, ValueError)
        # self.assertEqual(result.exception, ValueError("Invalid Input: b'i\\xb7\\x1dy\\xf8!'"))

    def test_download_filename_string_encoding_name_id7(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        files_to_create = [
            ("2018/07/30", "IMG_7408_QVI4T2l.JPG", 1151066),
            ("2018/07/30", "IMG_7407_QVovd0F.JPG", 656257),
        ]

        files_to_download: List[Tuple[str, str]] = [
            # SU1HXzc0MDkuSlBH -> IMG_7409.JPG
            ("2018/07/31", "IMG_7409_QVk2Yyt.JPG")
        ]

        data_dir, result = run_icloudpd_test(
            self.assertEqual,
            self.vcr_path,
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
                "--file-match-policy",
                "name-id7",
            ],
        )
        print_result_exception(result)

        self.assertEqual(result.exit_code, 0)
