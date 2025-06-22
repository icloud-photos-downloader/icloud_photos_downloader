import datetime
import glob
import inspect
import logging
import os
import shutil
from typing import Any, NoReturn
from unittest import TestCase, mock

import pytest
import pytz
from click.testing import CliRunner
from tzlocal import get_localzone
from vcr import VCR

from icloudpd import constants
from icloudpd.base import main
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.exceptions import PyiCloudAPIResponseException
from pyicloud_ipd.services.photos import PhotoAsset, PhotoLibrary, PhotosService
from tests.helpers import path_from_project_root, print_result_exception, recreate_path

vcr = VCR(decode_compressed_response=True, record_mode="none")


class AutodeletePhotosTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog: pytest.LogCaptureFixture) -> None:
        self._caplog = caplog
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")
        self.vcr_path = os.path.join(self.root_path, "vcr_cassettes")

    def test_autodelete_invalid_creation_date(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")
        cookie_master_path = os.path.join(self.root_path, "cookie")

        for dir in [base_dir, data_dir]:
            recreate_path(dir)

        shutil.copytree(cookie_master_path, cookie_dir)

        files = ["2018/01/01/IMG_3589.JPG"]

        with mock.patch.object(PhotoAsset, "created", new_callable=mock.PropertyMock) as dt_mock:
            # Can't mock `astimezone` because it's a readonly property, so have to
            # create a new class that inherits from datetime.datetime
            class NewDateTime(datetime.datetime):
                def astimezone(self, _tz: (Any | None) = None) -> NoReturn:
                    raise ValueError("Invalid date")

            dt_mock.return_value = NewDateTime(2018, 1, 1, 0, 0, 0)

            with vcr.use_cassette(os.path.join(self.vcr_path, "download_autodelete_photos.yml")):
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
                        "1",
                        "--delete-after-download",
                        "-d",
                        data_dir,
                        "--cookie-directory",
                        cookie_dir,
                    ],
                )
                print_result_exception(result)

                self.assertIn(
                    "DEBUG    Looking up all photos and videos...",
                    self._caplog.text,
                )
                self.assertIn(
                    #                   f"INFO     Downloading the first original photo or video to {data_dir} ...",
                    "INFO     Downloading the first original photo or video",
                    self._caplog.text,
                )
                self.assertIn(
                    "ERROR    Could not convert photo created date to local timezone (2018-01-01 00:00:00)",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     Downloaded {os.path.join(data_dir, os.path.normpath('2018/01/01/IMG_3589.JPG'))}",
                    self._caplog.text,
                )
                self.assertIn(
                    "INFO     Deleted IMG_3589.JPG",
                    self._caplog.text,
                )
                self.assertIn("INFO     All photos have been downloaded", self._caplog.text)

                # check files
                for file_name in files:
                    assert os.path.exists(os.path.join(data_dir, file_name)), (
                        f"{file_name} expected, but missing"
                    )

                result = runner.invoke(
                    main,
                    [
                        "--username",
                        "jdoe@gmail.com",
                        "--password",
                        "password1",
                        "--recent",
                        "0",
                        "--auto-delete",
                        "-d",
                        data_dir,
                        "--cookie-directory",
                        cookie_dir,
                    ],
                )
                print_result_exception(result)

                self.assertIn(
                    "DEBUG    Looking up all photos and videos...",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     Downloading 0 original photos and videos to {data_dir} ...",
                    self._caplog.text,
                )
                self.assertIn("INFO     All photos have been downloaded", self._caplog.text)
                self.assertIn(
                    "INFO     Deleting any files found in 'Recently Deleted'...",
                    self._caplog.text,
                )

                self.assertIn(
                    f"INFO     Deleted {os.path.join(data_dir, os.path.normpath('2018/01/01/IMG_3589.JPG'))}",
                    self._caplog.text,
                )

                for file_name in files:
                    assert not os.path.exists(os.path.join(data_dir, file_name)), (
                        f"{file_name} not expected, but present"
                    )

    def test_download_autodelete_photos(self) -> None:
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

        with vcr.use_cassette(os.path.join(self.vcr_path, "download_autodelete_photos.yml")):
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
                    "1",
                    "--delete-after-download",
                    "-d",
                    data_dir,
                    "--cookie-directory",
                    cookie_dir,
                ],
            )
            print_result_exception(result)

            self.assertIn(
                "DEBUG    Looking up all photos and videos...",
                self._caplog.text,
            )
            self.assertIn(
                #                f"INFO     Downloading the first original photo or video to {data_dir} ...",
                "INFO     Downloading the first original photo or video",
                self._caplog.text,
            )
            self.assertIn(
                f"DEBUG    Downloading {os.path.join(data_dir, os.path.normpath(files[0]))}",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     Deleted IMG_3589.JPG",
                self._caplog.text,
            )
            self.assertIn("INFO     All photos have been downloaded", self._caplog.text)

            # check files
            for file_name in files:
                assert os.path.exists(os.path.join(data_dir, file_name)), (
                    f"{file_name} expected, but missing"
                )

            result = runner.invoke(
                main,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "0",
                    "--auto-delete",
                    "-d",
                    data_dir,
                    "--cookie-directory",
                    cookie_dir,
                ],
            )
            print_result_exception(result)

            self.assertIn(
                "DEBUG    Looking up all photos and videos...",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Downloading 0 original photos and videos to {data_dir} ...",
                self._caplog.text,
            )
            self.assertIn("INFO     All photos have been downloaded", self._caplog.text)
            self.assertIn(
                "INFO     Deleting any files found in 'Recently Deleted'...",
                self._caplog.text,
            )

            self.assertIn(
                f"INFO     Deleted {os.path.join(data_dir, os.path.normpath(files[0]))}",
                self._caplog.text,
            )

            for file_name in files:
                assert not os.path.exists(os.path.join(data_dir, file_name)), (
                    f"{file_name} not expected, but present"
                )

    def test_autodelete_photos(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")
        cookie_master_path = os.path.join(self.root_path, "cookie")

        for dir in [base_dir, data_dir]:
            recreate_path(dir)

        shutil.copytree(cookie_master_path, cookie_dir)

        files_to_create = ["2018/07/30/IMG_7407.JPG", "2018/07/30/IMG_7407-original.JPG"]

        files_to_delete = [
            f"{f'{datetime.datetime.fromtimestamp(1532940539000.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()):%Y/%m/%d}'}/IMG_7406.MOV",
            f"{f'{datetime.datetime.fromtimestamp(1532618424000.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()):%Y/%m/%d}'}/IMG_7383.PNG",
            f"{f'{datetime.datetime.fromtimestamp(1531371164630.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()):%Y/%m/%d}'}/IMG_7190.JPG",
            f"{f'{datetime.datetime.fromtimestamp(1531371164630.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()):%Y/%m/%d}'}/IMG_7190-medium.JPG",
        ]

        os.makedirs(
            os.path.join(
                data_dir,
                f"{f'{datetime.datetime.fromtimestamp(1532940539000.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()):%Y/%m/%d}'}/",
            )
        )
        os.makedirs(
            os.path.join(
                data_dir,
                f"{f'{datetime.datetime.fromtimestamp(1532618424000.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()):%Y/%m/%d}'}/",
            )
        )
        os.makedirs(
            os.path.join(
                data_dir,
                f"{f'{datetime.datetime.fromtimestamp(1531371164630.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()):%Y/%m/%d}'}/",
            )
        )

        # create some empty files
        for file_name in files_to_create + files_to_delete:
            open(os.path.join(data_dir, file_name), "a").close()

        with vcr.use_cassette(os.path.join(self.vcr_path, "autodelete_photos.yml")):
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
                    "0",
                    "--skip-videos",
                    "--auto-delete",
                    "-d",
                    data_dir,
                    "--cookie-directory",
                    cookie_dir,
                ],
            )
            self.assertIn("DEBUG    Looking up all photos...", self._caplog.text)
            self.assertIn(
                f"INFO     Downloading 0 original photos to {data_dir} ...",
                self._caplog.text,
            )
            self.assertIn("INFO     All photos have been downloaded", self._caplog.text)
            self.assertIn(
                "INFO     Deleting any files found in 'Recently Deleted'...",
                self._caplog.text,
            )

            self.assertIn(
                f"INFO     Deleted {os.path.join(data_dir, os.path.normpath(files_to_delete[0]))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Deleted {os.path.join(data_dir, os.path.normpath(files_to_delete[1]))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Deleted {os.path.join(data_dir, os.path.normpath(files_to_delete[2]))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Deleted {os.path.join(data_dir, os.path.normpath(files_to_delete[3]))}",
                self._caplog.text,
            )

            self.assertNotIn("IMG_7407.JPG", self._caplog.text)
            self.assertNotIn("IMG_7407-original.JPG", self._caplog.text)

            assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_create)

        # check files
        for file_name in files_to_create:
            assert os.path.exists(os.path.join(data_dir, file_name)), (
                f"{file_name} expected, but missing"
            )

        for file_name in files_to_delete:
            assert not os.path.exists(os.path.join(data_dir, file_name)), (
                f"{file_name} not expected, but present"
            )

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

        with vcr.use_cassette(os.path.join(self.vcr_path, "download_autodelete_photos.yml")):

            def mock_raise_response_error(
                a1_: logging.Logger, a2_: PhotosService, a3_: PhotoLibrary, a4_: PhotoAsset
            ) -> None:
                if not hasattr(self, f"already_raised_session_exception{inspect.stack()[0][3]}"):
                    setattr(self, f"already_raised_session_exception{inspect.stack()[0][3]}", True)  # noqa: B010
                    raise PyiCloudAPIResponseException("Invalid global session", "100")

            with mock.patch("time.sleep") as sleep_mock:  # noqa: SIM117
                with mock.patch("icloudpd.base.delete_photo") as pa_delete:
                    pa_delete.side_effect = mock_raise_response_error

                    # Let the initial authenticate() call succeed,
                    # but do nothing on the second try.
                    orig_authenticate = PyiCloudService.authenticate

                    def mocked_authenticate(self: PyiCloudService) -> None:
                        if not hasattr(self, f"already_authenticated{inspect.stack()[0][3]}"):
                            orig_authenticate(self)
                            setattr(self, f"already_authenticated{inspect.stack()[0][3]}", True)  # noqa: B010

                    with mock.patch.object(
                        PyiCloudService, "authenticate", new=mocked_authenticate
                    ):
                        # Pass fixed client ID via environment variable
                        runner = CliRunner(
                            env={"CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"}
                        )
                        result = runner.invoke(
                            main,
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
                        print_result_exception(result)

                        self.assertIn(
                            "DEBUG    Looking up all photos and videos...",
                            self._caplog.text,
                        )
                        self.assertIn(
                            f"INFO     Downloading the first original photo or video to {data_dir} ...",
                            self._caplog.text,
                        )
                        self.assertIn(
                            f"DEBUG    Downloading {os.path.join(data_dir, os.path.normpath(files[0]))}",
                            self._caplog.text,
                        )

                        # Error msg should be repeated 5 times
                        self.assertEqual(
                            self._caplog.text.count("Session error, re-authenticating..."),
                            1,
                            "Re-auth message count",
                        )

                        self.assertEqual(pa_delete.call_count, 2, "delete call count")
                        # Make sure we only call sleep 4 times (skip the first retry)
                        self.assertEqual(sleep_mock.call_count, 0, "Sleep call count")
                        self.assertEqual(result.exit_code, 0, "Exit code")

        # check files
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

        with vcr.use_cassette(os.path.join(self.vcr_path, "download_autodelete_photos.yml")):

            def mock_raise_response_error(
                a1_: logging.Logger, a2_: PhotosService, a3_: PhotoLibrary, a4_: PhotoAsset
            ) -> None:
                raise PyiCloudAPIResponseException("Invalid global session", "100")

            with mock.patch("time.sleep") as sleep_mock:  # noqa: SIM117
                with mock.patch("icloudpd.base.delete_photo") as pa_delete:
                    pa_delete.side_effect = mock_raise_response_error

                    # Let the initial authenticate() call succeed,
                    # but do nothing on the second try.
                    orig_authenticate = PyiCloudService.authenticate

                    def mocked_authenticate(self: PyiCloudService) -> None:
                        if not hasattr(self, f"already_authenticated{inspect.stack()[0][3]}"):
                            orig_authenticate(self)
                            setattr(self, f"already_authenticated{inspect.stack()[0][3]}", True)  # noqa: B010

                    with mock.patch.object(
                        PyiCloudService, "authenticate", new=mocked_authenticate
                    ):
                        # Pass fixed client ID via environment variable
                        runner = CliRunner(
                            env={"CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"}
                        )
                        result = runner.invoke(
                            main,
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
                        print_result_exception(result)

                        self.assertIn(
                            "DEBUG    Looking up all photos and videos...",
                            self._caplog.text,
                        )
                        self.assertIn(
                            f"INFO     Downloading the first original photo or video to {data_dir} ...",
                            self._caplog.text,
                        )
                        self.assertIn(
                            f"DEBUG    Downloading {os.path.join(data_dir, os.path.normpath(files[0]))}",
                            self._caplog.text,
                        )

                        # Error msg should be repeated 5 times
                        self.assertEqual(
                            self._caplog.text.count("Session error, re-authenticating..."),
                            constants.MAX_RETRIES,
                            "Re-auth message count",
                        )

                        self.assertEqual(
                            pa_delete.call_count, constants.MAX_RETRIES + 1, "delete call count"
                        )
                        # Make sure we only call sleep 4 times (skip the first retry)
                        self.assertEqual(
                            sleep_mock.call_count, constants.MAX_RETRIES - 1, "Sleep call count"
                        )
                        self.assertEqual(result.exit_code, 1, "Exit code")

        # check files
        for file_name in files:
            assert os.path.exists(os.path.join(data_dir, file_name)), (
                f"{file_name} expected, but missing"
            )

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 1

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

        with vcr.use_cassette(os.path.join(self.vcr_path, "download_autodelete_photos.yml")):

            def mock_raise_response_error(
                a1_: logging.Logger, a2_: PhotosService, a3_: PhotoLibrary, a4_: PhotoAsset
            ) -> None:
                if not hasattr(self, f"already_raised_session_exception{inspect.stack()[0][3]}"):
                    setattr(self, f"already_raised_session_exception{inspect.stack()[0][3]}", True)  # noqa: B010
                    raise PyiCloudAPIResponseException("INTERNAL_ERROR", "INTERNAL_ERROR")

            with mock.patch("time.sleep") as sleep_mock:  # noqa: SIM117
                with mock.patch("icloudpd.base.delete_photo") as pa_delete:
                    pa_delete.side_effect = mock_raise_response_error

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
                            "1",
                            "--delete-after-download",
                            "-d",
                            data_dir,
                            "--cookie-directory",
                            cookie_dir,
                        ],
                    )
                    print_result_exception(result)

                    self.assertIn(
                        "DEBUG    Looking up all photos and videos...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        f"INFO     Downloading the first original photo or video to {data_dir} ...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        f"DEBUG    Downloading {os.path.join(data_dir, os.path.normpath(files[0]))}",
                        self._caplog.text,
                    )

                    # Error msg should be repeated 5 times
                    self.assertEqual(
                        self._caplog.text.count("Internal Error at Apple, retrying..."),
                        1,
                        "Retry message count",
                    )

                    self.assertEqual(pa_delete.call_count, 2, "delete call count")
                    # Make sure we only call sleep 4 times (skip the first retry)
                    self.assertEqual(sleep_mock.call_count, 1, "Sleep call count")
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

        with vcr.use_cassette(os.path.join(self.vcr_path, "download_autodelete_photos.yml")):

            def mock_raise_response_error(
                a1_: logging.Logger, a2_: PhotosService, a3_: PhotoLibrary, a4_: PhotoAsset
            ) -> None:
                raise PyiCloudAPIResponseException("INTERNAL_ERROR", "INTERNAL_ERROR")

            with mock.patch("time.sleep") as sleep_mock:  # noqa: SIM117
                with mock.patch("icloudpd.base.delete_photo") as pa_delete:
                    pa_delete.side_effect = mock_raise_response_error

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
                            "1",
                            "--delete-after-download",
                            "-d",
                            data_dir,
                            "--cookie-directory",
                            cookie_dir,
                        ],
                    )
                    print_result_exception(result)

                    self.assertIn(
                        "DEBUG    Looking up all photos and videos...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        f"INFO     Downloading the first original photo or video to {data_dir} ...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        f"DEBUG    Downloading {os.path.join(data_dir, os.path.normpath(files[0]))}",
                        self._caplog.text,
                    )

                    # Error msg should be repeated 5 times
                    self.assertEqual(
                        self._caplog.text.count("Internal Error at Apple, retrying..."),
                        constants.MAX_RETRIES,
                        "Retry message count",
                    )

                    self.assertEqual(
                        pa_delete.call_count, constants.MAX_RETRIES + 1, "delete call count"
                    )
                    # Make sure we only call sleep N times (skip the first retry)
                    self.assertEqual(
                        sleep_mock.call_count, constants.MAX_RETRIES, "Sleep call count"
                    )
                    self.assertEqual(result.exit_code, 1, "Exit code")

        # check files
        for file_name in files:
            assert os.path.exists(os.path.join(data_dir, file_name)), (
                f"{file_name} expected, but missing"
            )

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 1

    def test_autodelete_photos_dry_run(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")
        cookie_master_path = os.path.join(self.root_path, "cookie")

        for dir in [base_dir, data_dir]:
            recreate_path(dir)

        shutil.copytree(cookie_master_path, cookie_dir)

        files_to_create = ["2018/07/30/IMG_7407.JPG", "2018/07/30/IMG_7407-original.JPG"]

        files_to_delete = [
            f"{f'{datetime.datetime.fromtimestamp(1532940539000.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()):%Y/%m/%d}'}/IMG_7406.MOV",
            f"{f'{datetime.datetime.fromtimestamp(1532618424000.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()):%Y/%m/%d}'}/IMG_7383.PNG",
            f"{f'{datetime.datetime.fromtimestamp(1531371164630.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()):%Y/%m/%d}'}/IMG_7190.JPG",
            f"{f'{datetime.datetime.fromtimestamp(1531371164630.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()):%Y/%m/%d}'}/IMG_7190-medium.JPG",
        ]

        os.makedirs(
            os.path.join(
                data_dir,
                f"{f'{datetime.datetime.fromtimestamp(1532940539000.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()):%Y/%m/%d}'}/",
            )
        )
        os.makedirs(
            os.path.join(
                data_dir,
                f"{f'{datetime.datetime.fromtimestamp(1532618424000.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()):%Y/%m/%d}'}/",
            )
        )
        os.makedirs(
            os.path.join(
                data_dir,
                f"{f'{datetime.datetime.fromtimestamp(1531371164630.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()):%Y/%m/%d}'}/",
            )
        )

        # create some empty files
        for file_name in files_to_create + files_to_delete:
            open(os.path.join(data_dir, file_name), "a").close()

        with vcr.use_cassette(os.path.join(self.vcr_path, "autodelete_photos.yml")):
            # Pass fixed client ID via environment variable
            runner = CliRunner(env={"CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"})
            result = runner.invoke(
                main,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--dry-run",
                    "--recent",
                    "0",
                    "--skip-videos",
                    "--auto-delete",
                    "-d",
                    data_dir,
                    "--cookie-directory",
                    cookie_dir,
                ],
            )
            print_result_exception(result)

            self.assertIn("DEBUG    Looking up all photos...", self._caplog.text)
            self.assertIn(
                f"INFO     Downloading 0 original photos to {data_dir} ...",
                self._caplog.text,
            )
            self.assertIn("INFO     All photos have been downloaded", self._caplog.text)
            self.assertIn(
                "INFO     Deleting any files found in 'Recently Deleted'...",
                self._caplog.text,
            )

            self.assertIn(
                f"INFO     [DRY RUN] Would delete {os.path.join(data_dir, os.path.normpath(files_to_delete[0]))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     [DRY RUN] Would delete {os.path.join(data_dir, os.path.normpath(files_to_delete[1]))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     [DRY RUN] Would delete {os.path.join(data_dir, os.path.normpath(files_to_delete[2]))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     [DRY RUN] Would delete {os.path.join(data_dir, os.path.normpath(files_to_delete[3]))}",
                self._caplog.text,
            )

            self.assertNotIn("IMG_7407.JPG", self._caplog.text)
            self.assertNotIn("IMG_7407-original.JPG", self._caplog.text)

            self.assertEqual(result.exit_code, 0, "Exit code")

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

        self.assertEqual(
            sum(1 for _ in files_in_result),
            len(files_to_create) + len(files_to_delete),
            "Files in the result",
        )

        # check files
        for file_name in files_to_create:
            assert os.path.exists(os.path.join(data_dir, file_name)), (
                f"{file_name} expected, but missing"
            )

        for file_name in files_to_delete:
            assert os.path.exists(os.path.join(data_dir, file_name)), (
                f"{file_name} expected to stay, but missing"
            )

    def test_autodelete_photos_folder_none(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")
        cookie_master_path = os.path.join(self.root_path, "cookie")

        for dir in [base_dir, data_dir]:
            recreate_path(dir)

        shutil.copytree(cookie_master_path, cookie_dir)

        files_to_create = ["IMG_7407.JPG", "IMG_7407-original.JPG"]

        files_to_delete = [
            "IMG_7406.MOV",
            "IMG_7383.PNG",
            "IMG_7190.JPG",
            "IMG_7190-medium.JPG",
        ]

        # create some empty files
        for file_name in files_to_create + files_to_delete:
            open(os.path.join(data_dir, file_name), "a").close()

        with vcr.use_cassette(os.path.join(self.vcr_path, "autodelete_photos.yml")):
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
                    "0",
                    "--skip-videos",
                    "--auto-delete",
                    "--folder-structure",
                    "none",
                    "-d",
                    data_dir,
                    "--cookie-directory",
                    cookie_dir,
                ],
            )
            self.assertIn("DEBUG    Looking up all photos...", self._caplog.text)
            self.assertIn(
                f"INFO     Downloading 0 original photos to {data_dir} ...",
                self._caplog.text,
            )
            self.assertIn("INFO     All photos have been downloaded", self._caplog.text)
            self.assertIn(
                "INFO     Deleting any files found in 'Recently Deleted'...",
                self._caplog.text,
            )

            self.assertIn(
                f"INFO     Deleted {os.path.join(data_dir, os.path.normpath(files_to_delete[0]))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Deleted {os.path.join(data_dir, os.path.normpath(files_to_delete[1]))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Deleted {os.path.join(data_dir, os.path.normpath(files_to_delete[2]))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Deleted {os.path.join(data_dir, os.path.normpath(files_to_delete[3]))}",
                self._caplog.text,
            )

            self.assertNotIn("IMG_7407.JPG", self._caplog.text)
            self.assertNotIn("IMG_7407-original.JPG", self._caplog.text)

            assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_create)

        # check files
        for file_name in files_to_create:
            assert os.path.exists(os.path.join(data_dir, file_name)), (
                f"{file_name} expected, but missing"
            )

        for file_name in files_to_delete:
            assert not os.path.exists(os.path.join(data_dir, file_name)), (
                f"{file_name} not expected, but present"
            )

    def test_autodelete_photos_lp(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")
        cookie_master_path = os.path.join(self.root_path, "cookie")

        for dir in [base_dir, data_dir]:
            recreate_path(dir)

        shutil.copytree(cookie_master_path, cookie_dir)

        files_to_create = ["2018/07/30/IMG_7407.JPG", "2018/07/30/IMG_7407-original.JPG"]

        files_to_delete = [
            "2018/07/30/IMG_7406.MOV",
            "2018/07/26/IMG_7383.PNG",
            "2018/07/12/IMG_7190.JPG",
            "2018/07/12/IMG_7190-medium.JPG",
            "2018/07/12/IMG_7190.MOV",  # Live Photo for JPG
        ]

        # create some empty files
        for file_name in files_to_create + files_to_delete:
            path_name, _ = os.path.split(file_name)
            os.makedirs(os.path.join(data_dir, path_name), exist_ok=True)
            open(os.path.join(data_dir, file_name), "a").close()

        with vcr.use_cassette(os.path.join(self.vcr_path, "autodelete_photos.yml")):
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
                    "0",
                    "--skip-videos",
                    "--auto-delete",
                    "-d",
                    data_dir,
                    "--cookie-directory",
                    cookie_dir,
                ],
            )
            self.assertIn("DEBUG    Looking up all photos...", self._caplog.text)
            self.assertIn(
                f"INFO     Downloading 0 original photos to {data_dir} ...",
                self._caplog.text,
            )
            self.assertIn("INFO     All photos have been downloaded", self._caplog.text)
            self.assertIn(
                "INFO     Deleting any files found in 'Recently Deleted'...",
                self._caplog.text,
            )

            self.assertIn(
                f"INFO     Deleted {os.path.join(data_dir, os.path.normpath(files_to_delete[0]))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Deleted {os.path.join(data_dir, os.path.normpath(files_to_delete[1]))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Deleted {os.path.join(data_dir, os.path.normpath(files_to_delete[2]))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Deleted {os.path.join(data_dir, os.path.normpath(files_to_delete[3]))}",
                self._caplog.text,
            )

            self.assertNotIn("IMG_7407.JPG", self._caplog.text)
            self.assertNotIn("IMG_7407-original.JPG", self._caplog.text)

            assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_create)

        # check files
        for file_name in files_to_create:
            assert os.path.exists(os.path.join(data_dir, file_name)), (
                f"{file_name} expected, but missing"
            )

        for file_name in files_to_delete:
            assert not os.path.exists(os.path.join(data_dir, file_name)), (
                f"{file_name} not expected, but present"
            )

    def test_autodelete_photos_lp_heic(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")
        cookie_master_path = os.path.join(self.root_path, "cookie")

        for dir in [base_dir, data_dir]:
            recreate_path(dir)

        shutil.copytree(cookie_master_path, cookie_dir)

        files_to_create = ["2018/07/30/IMG_7407.JPG", "2018/07/30/IMG_7407-original.JPG"]

        files_to_delete = [
            "2018/07/30/IMG_7406.MOV",
            "2018/07/26/IMG_7383.PNG",
            "2018/07/12/IMG_7190.HEIC",  # SU1HXzcxOTAuSlBH -> SU1HXzcxOTAuSEVJQw==
            "2018/07/12/IMG_7190-medium.JPG",
            "2018/07/12/IMG_7190_HEVC.MOV",  # Live Photo for HEIC
        ]

        # create some empty files
        for file_name in files_to_create + files_to_delete:
            path_name, _ = os.path.split(file_name)
            os.makedirs(os.path.join(data_dir, path_name), exist_ok=True)
            open(os.path.join(data_dir, file_name), "a").close()

        with vcr.use_cassette(os.path.join(self.vcr_path, "autodelete_photos_heic.yml")):
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
                    "0",
                    "--skip-videos",
                    "--auto-delete",
                    "-d",
                    data_dir,
                    "--cookie-directory",
                    cookie_dir,
                ],
            )
            self.assertIn("DEBUG    Looking up all photos...", self._caplog.text)
            self.assertIn(
                f"INFO     Downloading 0 original photos to {data_dir} ...",
                self._caplog.text,
            )
            self.assertIn("INFO     All photos have been downloaded", self._caplog.text)
            self.assertIn(
                "INFO     Deleting any files found in 'Recently Deleted'...",
                self._caplog.text,
            )

            self.assertIn(
                f"INFO     Deleted {os.path.join(data_dir, os.path.normpath(files_to_delete[0]))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Deleted {os.path.join(data_dir, os.path.normpath(files_to_delete[1]))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Deleted {os.path.join(data_dir, os.path.normpath(files_to_delete[2]))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Deleted {os.path.join(data_dir, os.path.normpath(files_to_delete[3]))}",
                self._caplog.text,
            )

            self.assertNotIn("IMG_7407.JPG", self._caplog.text)
            self.assertNotIn("IMG_7407-original.JPG", self._caplog.text)

            assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_create)

        # check files
        for file_name in files_to_create:
            assert os.path.exists(os.path.join(data_dir, file_name)), (
                f"{file_name} expected, but missing"
            )

        for file_name in files_to_delete:
            assert not os.path.exists(os.path.join(data_dir, file_name)), (
                f"{file_name} not expected, but present"
            )
