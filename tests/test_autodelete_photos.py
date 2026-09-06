import datetime
import glob
import inspect
import logging
import os
import shutil
from unittest import TestCase, mock

import pytest
import pytz
from tzlocal import get_localzone
from vcr import VCR

from icloudpd import constants
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.exceptions import PyiCloudAPIResponseException
from pyicloud_ipd.services.photos import PhotoAsset, PhotoLibrary, PhotosService
from tests.helpers import (
    path_from_project_root,
    recreate_path,
    run_cassette,
)

vcr = VCR(decode_compressed_response=True, record_mode="none")


class AutodeletePhotosTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self) -> None:
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")
        self.vcr_path = os.path.join(self.root_path, "vcr_cassettes")

    @pytest.mark.skipif(constants.MAX_RETRIES == 0, reason="Disabled when MAX_RETRIES set to 0")
    def test_retry_delete_after_download_session_error(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")
        cookie_master_path = os.path.join(self.root_path, "cookie")

        for dir in [base_dir, data_dir]:
            recreate_path(dir)

        shutil.copytree(cookie_master_path, cookie_dir)

        files = [
            f"{f'{datetime.datetime.fromtimestamp(1686106167436.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()):%Y/%m/%d}'}/IMG_3589.JPG"
        ]

        def mock_raise_response_error(
            a1_: logging.Logger, a2_: PhotosService, a3_: PhotoLibrary, a4_: PhotoAsset
        ) -> None:
            if not hasattr(self, f"already_raised_session_exception{inspect.stack()[0][3]}"):
                setattr(self, f"already_raised_session_exception{inspect.stack()[0][3]}", True)  # noqa: B010
                raise PyiCloudAPIResponseException("Invalid global session", "100")

        # Let the initial authenticate() call succeed, but do nothing on the retry.
        orig_authenticate = PyiCloudService.authenticate

        def mocked_authenticate(self: PyiCloudService) -> None:
            if not hasattr(self, f"already_authenticated{inspect.stack()[0][3]}"):
                orig_authenticate(self)
                setattr(self, f"already_authenticated{inspect.stack()[0][3]}", True)  # noqa: B010

        with mock.patch("time.sleep") as sleep_mock:  # noqa: SIM117
            with mock.patch("icloudpd.base.delete_photo") as pa_delete:
                pa_delete.side_effect = mock_raise_response_error

                with mock.patch.object(PyiCloudService, "authenticate", new=mocked_authenticate):
                    result = run_cassette(
                        os.path.join(self.vcr_path, "download_autodelete_photos.yml"),
                        [
                            "--username",
                            "jdoe@gmail.com",
                            "--password",
                            "password1",
                            "--recent",
                            "1",
                            "--delete-after-download",
                            "-d",
                            data_dir,
                            "--cookie-directory",
                            cookie_dir,
                        ],
                    )

                    self.assertIn("Looking up all photos and videos...", result.output)
                    self.assertIn(
                        f"Downloading the first original photo or video to {data_dir} ...",
                        result.output,
                    )
                    self.assertIn(
                        f"Downloading {os.path.join(data_dir, os.path.normpath(files[0]))}",
                        result.output,
                    )
                    self.assertEqual(
                        result.output.count("Session error, re-authenticating..."),
                        1,
                        "retry count",
                    )
                    self.assertEqual(
                        pa_delete.call_count,
                        1 + min(1, constants.MAX_RETRIES),
                        "delete call count",
                    )
                    self.assertEqual(sleep_mock.call_count, 0, "sleep count")
                    self.assertEqual(result.exit_code, 0, "Exit code")

        for file_name in files:
            assert os.path.exists(os.path.join(data_dir, file_name)), (
                f"{file_name} expected, but missing"
            )

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)
        assert sum(1 for _ in files_in_result) == 1

    def test_retry_fail_delete_after_download_session_error(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")
        cookie_master_path = os.path.join(self.root_path, "cookie")

        for dir in [base_dir, data_dir]:
            recreate_path(dir)

        shutil.copytree(cookie_master_path, cookie_dir)

        files = [
            f"{f'{datetime.datetime.fromtimestamp(1686106167436.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()):%Y/%m/%d}'}/IMG_3589.JPG"
        ]

        def mock_raise_response_error(
            a1_: logging.Logger, a3_: PhotoLibrary, a4_: PhotoAsset
        ) -> None:
            raise PyiCloudAPIResponseException("Invalid global session", "100")

        # Let the initial authenticate() call succeed,
        # but do nothing on the second try.
        orig_authenticate = PyiCloudService.authenticate

        def mocked_authenticate(self: PyiCloudService) -> None:
            if not hasattr(self, f"already_authenticated{inspect.stack()[0][3]}"):
                orig_authenticate(self)
                setattr(self, f"already_authenticated{inspect.stack()[0][3]}", True)  # noqa: B010

        with mock.patch("time.sleep") as sleep_mock:  # noqa: SIM117
            with mock.patch("icloudpd.base.delete_photo") as pa_delete:
                pa_delete.side_effect = mock_raise_response_error

                with mock.patch.object(PyiCloudService, "authenticate", new=mocked_authenticate):
                    result = run_cassette(
                        os.path.join(self.vcr_path, "download_autodelete_photos_part1.yml"),
                        [
                            "--username",
                            "jdoe@gmail.com",
                            "--password",
                            "password1",
                            "--recent",
                            "1",
                            "--delete-after-download",
                            "-d",
                            data_dir,
                            "--cookie-directory",
                            cookie_dir,
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
                        f"Downloading {os.path.join(data_dir, os.path.normpath(files[0]))}",
                        result.output,
                    )

                    # Error msg should be repeated MAX_RETRIES times
                    self.assertEqual(
                        result.output.count("Session error, re-authenticating..."),
                        max(0, constants.MAX_RETRIES),
                        "retry count",
                    )

                    self.assertEqual(
                        pa_delete.call_count, constants.MAX_RETRIES + 1, "delete call count"
                    )
                    # Make sure we only call sleep MAX_RETRIES-1 times (skip the first retry)
                    self.assertEqual(
                        sleep_mock.call_count,
                        max(0, constants.MAX_RETRIES - 1),
                        "sleep count",
                    )
                    self.assertEqual(result.exit_code, 1, "Exit code")

        # check files
        for file_name in files:
            assert os.path.exists(os.path.join(data_dir, file_name)), (
                f"{file_name} expected, but missing"
            )

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 1

    @pytest.mark.skipif(constants.MAX_RETRIES == 0, reason="Disabled when MAX_RETRIES set to 0")
    def test_retry_delete_after_download_internal_error(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")
        cookie_master_path = os.path.join(self.root_path, "cookie")

        for dir in [base_dir, data_dir]:
            recreate_path(dir)

        shutil.copytree(cookie_master_path, cookie_dir)

        files = [
            f"{f'{datetime.datetime.fromtimestamp(1686106167436.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()):%Y/%m/%d}'}/IMG_3589.JPG"
        ]

        def mock_raise_response_error(
            a1_: logging.Logger, a2_: PhotosService, a3_: PhotoLibrary, a4_: PhotoAsset
        ) -> None:
            if not hasattr(self, f"already_raised_session_exception{inspect.stack()[0][3]}"):
                setattr(self, f"already_raised_session_exception{inspect.stack()[0][3]}", True)  # noqa: B010
                raise PyiCloudAPIResponseException("INTERNAL_ERROR", "INTERNAL_ERROR")

        with mock.patch("time.sleep") as sleep_mock:  # noqa: SIM117
            with mock.patch("icloudpd.base.delete_photo") as pa_delete:
                pa_delete.side_effect = mock_raise_response_error

                result = run_cassette(
                    os.path.join(self.vcr_path, "download_autodelete_photos_part1.yml"),
                    [
                        "--username",
                        "jdoe@gmail.com",
                        "--password",
                        "password1",
                        "--recent",
                        "1",
                        "--delete-after-download",
                        "-d",
                        data_dir,
                        "--cookie-directory",
                        cookie_dir,
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
                    f"Downloading {os.path.join(data_dir, os.path.normpath(files[0]))}",
                    result.output,
                )

                # Error msg should be repeated MAX_RETRIES times
                self.assertEqual(
                    result.output.count("Internal Error at Apple, retrying..."),
                    min(1, constants.MAX_RETRIES),
                    "retry count",
                )

                self.assertEqual(
                    pa_delete.call_count, 1 + min(1, constants.MAX_RETRIES), "delete count"
                )
                # Make sure we only call sleep 4 times (skip the first retry)
                self.assertEqual(
                    sleep_mock.call_count, min(1, constants.MAX_RETRIES), "sleep count"
                )
                self.assertEqual(result.exit_code, 0, "Exit code")

        # check files
        for file_name in files:
            assert os.path.exists(os.path.join(data_dir, file_name)), (
                f"{file_name} expected, but missing"
            )

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 1

    def test_retry_fail_delete_after_download_internal_error(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")
        cookie_master_path = os.path.join(self.root_path, "cookie")

        for dir in [base_dir, data_dir]:
            recreate_path(dir)

        shutil.copytree(cookie_master_path, cookie_dir)

        files = [
            f"{f'{datetime.datetime.fromtimestamp(1686106167436.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()):%Y/%m/%d}'}/IMG_3589.JPG"
        ]

        def mock_raise_response_error(
            a1_: logging.Logger, a2_: PhotosService, a3_: PhotoLibrary, a4_: PhotoAsset
        ) -> None:
            raise PyiCloudAPIResponseException("INTERNAL_ERROR", "INTERNAL_ERROR")

        with mock.patch("time.sleep") as sleep_mock:  # noqa: SIM117
            with mock.patch("icloudpd.base.delete_photo") as pa_delete:
                pa_delete.side_effect = mock_raise_response_error

                result = run_cassette(
                    os.path.join(self.vcr_path, "download_autodelete_photos_part1.yml"),
                    [
                        "--username",
                        "jdoe@gmail.com",
                        "--password",
                        "password1",
                        "--recent",
                        "1",
                        "--delete-after-download",
                        "-d",
                        data_dir,
                        "--cookie-directory",
                        cookie_dir,
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
                    f"Downloading {os.path.join(data_dir, os.path.normpath(files[0]))}",
                    result.output,
                )

                # Error msg should be repeated 5 times
                self.assertEqual(
                    result.output.count("Internal Error at Apple, retrying..."),
                    constants.MAX_RETRIES,
                    "retry count",
                )

                self.assertEqual(pa_delete.call_count, constants.MAX_RETRIES + 1, "delete count")
                # Make sure we only call sleep N times (skip the first retry)
                self.assertEqual(sleep_mock.call_count, constants.MAX_RETRIES, "sleep count")
                self.assertEqual(result.exit_code, 1, "Exit code")

        # check files
        for file_name in files:
            assert os.path.exists(os.path.join(data_dir, file_name)), (
                f"{file_name} expected, but missing"
            )

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 1
