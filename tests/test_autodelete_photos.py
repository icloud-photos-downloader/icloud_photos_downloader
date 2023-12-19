from unittest import TestCase
from icloudpd import constants
from vcr import VCR
import os
import shutil
import pytest
import mock
import datetime
import pytz
from tzlocal import get_localzone
from click.testing import CliRunner
from pyicloud_ipd.services.photos import PhotoAsset
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.exceptions import PyiCloudAPIResponseException
from icloudpd.base import main
from tests.helpers import path_from_project_root, recreate_path, print_result_exception
import inspect
import glob

vcr = VCR(decode_compressed_response=True, record_mode="new_episodes")


class AutodeletePhotosTestCase(TestCase):

    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")
        self.vcr_path = os.path.join(self.root_path, "vcr_cassettes")

    def test_autodelete_invalid_creation_date(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)

        files = [
            "2018/01/01/IMG_3589.JPG"
        ]

        with mock.patch.object(PhotoAsset, "created", new_callable=mock.PropertyMock) as dt_mock:
            # Can't mock `astimezone` because it's a readonly property, so have to
            # create a new class that inherits from datetime.datetime
            class NewDateTime(datetime.datetime):
                def astimezone(self, tz=None):
                    raise ValueError('Invalid date')
            dt_mock.return_value = NewDateTime(2018, 1, 1, 0, 0, 0)

            with vcr.use_cassette(os.path.join(self.vcr_path, "download_autodelete_photos.yml")):
                # Pass fixed client ID via environment variable
                runner = CliRunner(env={
                    "CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"
                })
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

                self.assertIn(
                    "DEBUG    Looking up all photos and videos from album All Photos...", self._caplog.text)
                self.assertIn(
#                   f"INFO     Downloading the first original photo or video to {data_dir} ...",
                    f"INFO     Downloading the first original photo or video",
                    self._caplog.text,
                )
                self.assertIn(
                    f"ERROR    Could not convert photo created date to local timezone (2018-01-01 00:00:00)",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     Downloaded {os.path.join(data_dir, os.path.normpath('2018/01/01/IMG_3589.JPG'))}",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     Deleted IMG_3589.JPG",
                    self._caplog.text,
                )
                self.assertIn(
                    "INFO     All photos have been downloaded", self._caplog.text
                )

                # check files
                for file_name in files:
                    assert os.path.exists(os.path.join(
                        data_dir, file_name)), f"{file_name} expected, but missing"

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
                    "DEBUG    Looking up all photos and videos from album All Photos...", self._caplog.text)
                self.assertIn(
                    f"INFO     Downloading 0 original photos and videos to {data_dir} ...",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     All photos have been downloaded", self._caplog.text
                )
                self.assertIn(
                    f"INFO     Deleting any files found in 'Recently Deleted'...",
                    self._caplog.text,
                )

                self.assertIn(
                    f"INFO     Deleted {os.path.join(data_dir, os.path.normpath('2018/01/01/IMG_3589.JPG'))}",
                    self._caplog.text,
                )

                for file_name in files:
                    assert not os.path.exists(
                        os.path.join(data_dir, file_name)), f"{file_name} not expected, but present"

    def test_download_autodelete_photos(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)

        files = [
            f"{'{:%Y/%m/%d}'.format(datetime.datetime.fromtimestamp(1686106167436.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()))}/IMG_3589.JPG"
        ]

        with vcr.use_cassette(os.path.join(self.vcr_path, "download_autodelete_photos.yml")):
            # Pass fixed client ID via environment variable
            runner = CliRunner(env={
                "CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"
            })
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

            self.assertIn(
                "DEBUG    Looking up all photos and videos from album All Photos...", self._caplog.text)
            self.assertIn(
#                f"INFO     Downloading the first original photo or video to {data_dir} ...",
                f"INFO     Downloading the first original photo or video",
                self._caplog.text,
            )
            self.assertIn(
                f"DEBUG    Downloading {os.path.join(data_dir, os.path.normpath(files[0]))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Deleted IMG_3589.JPG",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     All photos have been downloaded", self._caplog.text
            )

            # check files
            for file_name in files:
                assert os.path.exists(os.path.join(
                    data_dir, file_name)), f"{file_name} expected, but missing"

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

            self.assertIn(
                "DEBUG    Looking up all photos and videos from album All Photos...", self._caplog.text)
            self.assertIn(
                f"INFO     Downloading 0 original photos and videos to {data_dir} ...",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     All photos have been downloaded", self._caplog.text
            )
            self.assertIn(
                f"INFO     Deleting any files found in 'Recently Deleted'...",
                self._caplog.text,
            )

            self.assertIn(
                f"INFO     Deleted {os.path.join(data_dir, os.path.normpath(files[0]))}",
                self._caplog.text,
            )

            for file_name in files:
                assert not os.path.exists(os.path.join(
                    data_dir, file_name)), f"{file_name} not expected, but present"

    def test_autodelete_photos(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)

        files_to_create = [
            "2018/07/30/IMG_7407.JPG",
            "2018/07/30/IMG_7407-original.JPG"
        ]

        files_to_delete = [
            f"{'{:%Y/%m/%d}'.format(datetime.datetime.fromtimestamp(1532940539000.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()))}/IMG_7406.MOV",
            f"{'{:%Y/%m/%d}'.format(datetime.datetime.fromtimestamp(1532618424000.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()))}/IMG_7383.PNG",
            f"{'{:%Y/%m/%d}'.format(datetime.datetime.fromtimestamp(1531371164630.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()))}/IMG_7190.JPG",
            f"{'{:%Y/%m/%d}'.format(datetime.datetime.fromtimestamp(1531371164630.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()))}/IMG_7190-medium.JPG"
        ]

        os.makedirs(os.path.join(
            data_dir, f"{'{:%Y/%m/%d}'.format(datetime.datetime.fromtimestamp(1532940539000.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()))}/"))
        os.makedirs(os.path.join(
            data_dir, f"{'{:%Y/%m/%d}'.format(datetime.datetime.fromtimestamp(1532618424000.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()))}/"))
        os.makedirs(os.path.join(
            data_dir, f"{'{:%Y/%m/%d}'.format(datetime.datetime.fromtimestamp(1531371164630.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()))}/"))

        # create some empty files
        for file_name in files_to_create + files_to_delete:
            open(os.path.join(data_dir, file_name), "a").close()

        with vcr.use_cassette(os.path.join(self.vcr_path, "autodelete_photos.yml")):
            # Pass fixed client ID via environment variable
            runner = CliRunner(env={
                "CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"
            })
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
            self.assertIn(
                "DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
            self.assertIn(
                f"INFO     Downloading 0 original photos to {data_dir} ...",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     All photos have been downloaded", self._caplog.text
            )
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

        files_in_result = glob.glob(os.path.join(
            data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_create)

        # check files
        for file_name in files_to_create:
            assert os.path.exists(os.path.join(
                data_dir, file_name)), f"{file_name} expected, but missing"

        for file_name in files_to_delete:
            assert not os.path.exists(os.path.join(
                data_dir, file_name)), f"{file_name} not expected, but present"

    def test_retry_delete_after_download_session_error(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)

        files = [
            f"{'{:%Y/%m/%d}'.format(datetime.datetime.fromtimestamp(1686106167436.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()))}/IMG_3589.JPG"
        ]

        with vcr.use_cassette(os.path.join(self.vcr_path, "download_autodelete_photos.yml")):

            def mock_raise_response_error(a0_, a1_, a2_):
                if not hasattr(self, f"already_raised_session_exception{inspect.stack()[0][3]}"):
                    setattr(self, f"already_raised_session_exception{inspect.stack()[0][3]}", True)
                    raise PyiCloudAPIResponseException(
                        "Invalid global session", 100)

            with mock.patch("time.sleep") as sleep_mock:
                with mock.patch("icloudpd.base.delete_photo") as pa_delete:
                    pa_delete.side_effect = mock_raise_response_error

                    # Let the initial authenticate() call succeed,
                    # but do nothing on the second try.
                    orig_authenticate = PyiCloudService.authenticate

                    def mocked_authenticate(self):
                        if not hasattr(self, f"already_authenticated{inspect.stack()[0][3]}"):
                            orig_authenticate(self)
                            setattr(self, f"already_authenticated{inspect.stack()[0][3]}", True)

                    with mock.patch.object(
                        PyiCloudService, "authenticate", new=mocked_authenticate
                    ):
                        # Pass fixed client ID via environment variable
                        runner = CliRunner(env={
                            "CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"
                        })
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
                            "DEBUG    Looking up all photos and videos from album All Photos...", self._caplog.text)
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
                            self._caplog.text.count(
                                "Session error, re-authenticating..."
                            ), 1, "Re-auth message count"
                        )

                        self.assertEqual(pa_delete.call_count,
                                         2, "delete call count")
                        # Make sure we only call sleep 4 times (skip the first retry)
                        self.assertEqual(sleep_mock.call_count,
                                         0, "Sleep call count")
                        self.assertEqual(result.exit_code, 0, "Exit code")

        # check files
        for file_name in files:
            assert os.path.exists(os.path.join(
                data_dir, file_name)), f"{file_name} expected, but missing"

        files_in_result = glob.glob(os.path.join(
            data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 1

    def test_retry_fail_delete_after_download_session_error(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)

        files = [
            f"{'{:%Y/%m/%d}'.format(datetime.datetime.fromtimestamp(1686106167436.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()))}/IMG_3589.JPG"
        ]

        with vcr.use_cassette(os.path.join(self.vcr_path, "download_autodelete_photos.yml")):

            def mock_raise_response_error(a0_, a1_, a2_):
                raise PyiCloudAPIResponseException("Invalid global session", 100)

            with mock.patch("time.sleep") as sleep_mock:
                with mock.patch("icloudpd.base.delete_photo") as pa_delete:
                    pa_delete.side_effect = mock_raise_response_error

                    # Let the initial authenticate() call succeed,
                    # but do nothing on the second try.
                    orig_authenticate = PyiCloudService.authenticate

                    def mocked_authenticate(self):
                        if not hasattr(self, f"already_authenticated{inspect.stack()[0][3]}"):
                            orig_authenticate(self)
                            setattr(self, f"already_authenticated{inspect.stack()[0][3]}", True)

                    with mock.patch.object(
                        PyiCloudService, "authenticate", new=mocked_authenticate
                    ):
                        # Pass fixed client ID via environment variable
                        runner = CliRunner(env={
                            "CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"
                        })
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
                            "DEBUG    Looking up all photos and videos from album All Photos...", self._caplog.text)
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
                            self._caplog.text.count(
                                "Session error, re-authenticating..."
                            ), constants.MAX_RETRIES, "Re-auth message count"
                        )

                        self.assertEqual(pa_delete.call_count,
                                         constants.MAX_RETRIES + 1, "delete call count")
                        # Make sure we only call sleep 4 times (skip the first retry)
                        self.assertEqual(sleep_mock.call_count,
                                         constants.MAX_RETRIES - 1, "Sleep call count")
                        self.assertEqual(result.exit_code, 1, "Exit code")

        # check files
        for file_name in files:
            assert os.path.exists(os.path.join(
                data_dir, file_name)), f"{file_name} expected, but missing"

        files_in_result = glob.glob(os.path.join(
            data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 1

    def test_retry_delete_after_download_internal_error(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)

        files = [
            f"{'{:%Y/%m/%d}'.format(datetime.datetime.fromtimestamp(1686106167436.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()))}/IMG_3589.JPG"
        ]

        with vcr.use_cassette(os.path.join(self.vcr_path, "download_autodelete_photos.yml")):

            def mock_raise_response_error(a0_, a1_, a2_):
                if not hasattr(self, f"already_raised_session_exception{inspect.stack()[0][3]}"):
                    setattr(self, f"already_raised_session_exception{inspect.stack()[0][3]}", True)
                    raise PyiCloudAPIResponseException(
                        "INTERNAL_ERROR", "INTERNAL_ERROR")

            with mock.patch("time.sleep") as sleep_mock:
                with mock.patch("icloudpd.base.delete_photo") as pa_delete:
                    pa_delete.side_effect = mock_raise_response_error

                    # Pass fixed client ID via environment variable
                    runner = CliRunner(env={
                        "CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"
                    })
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
                        "DEBUG    Looking up all photos and videos from album All Photos...", self._caplog.text)
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
                        self._caplog.text.count(
                            "Internal Error at Apple, retrying..."
                        ), 1, "Retry message count"
                    )

                    self.assertEqual(pa_delete.call_count,
                                        2, "delete call count")
                    # Make sure we only call sleep 4 times (skip the first retry)
                    self.assertEqual(sleep_mock.call_count,
                                        1, "Sleep call count")
                    self.assertEqual(result.exit_code, 0, "Exit code")

        # check files
        for file_name in files:
            assert os.path.exists(os.path.join(
                data_dir, file_name)), f"{file_name} expected, but missing"

        files_in_result = glob.glob(os.path.join(
            data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 1

    def test_retry_fail_delete_after_download_internal_error(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)

        files = [
            f"{'{:%Y/%m/%d}'.format(datetime.datetime.fromtimestamp(1686106167436.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()))}/IMG_3589.JPG"
        ]

        with vcr.use_cassette(os.path.join(self.vcr_path, "download_autodelete_photos.yml")):

            def mock_raise_response_error(a0_, a1_, a2_):
                raise PyiCloudAPIResponseException("INTERNAL_ERROR", "INTERNAL_ERROR")

            with mock.patch("time.sleep") as sleep_mock:
                with mock.patch("icloudpd.base.delete_photo") as pa_delete:
                    pa_delete.side_effect = mock_raise_response_error

                    # Pass fixed client ID via environment variable
                    runner = CliRunner(env={
                        "CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"
                    })
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
                        "DEBUG    Looking up all photos and videos from album All Photos...", self._caplog.text)
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
                        self._caplog.text.count(
                            "Internal Error at Apple, retrying..."
                        ), constants.MAX_RETRIES, "Retry message count"
                    )

                    self.assertEqual(pa_delete.call_count,
                                        constants.MAX_RETRIES + 1, "delete call count")
                    # Make sure we only call sleep N times (skip the first retry)
                    self.assertEqual(sleep_mock.call_count,
                                        constants.MAX_RETRIES, "Sleep call count")
                    self.assertEqual(result.exit_code, 1, "Exit code")

        # check files
        for file_name in files:
            assert os.path.exists(os.path.join(
                data_dir, file_name)), f"{file_name} expected, but missing"

        files_in_result = glob.glob(os.path.join(
            data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 1

    def test_autodelete_photos_dry_run(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)

        files_to_create = [
            "2018/07/30/IMG_7407.JPG",
            "2018/07/30/IMG_7407-original.JPG"
        ]

        files_to_delete = [
            f"{'{:%Y/%m/%d}'.format(datetime.datetime.fromtimestamp(1532940539000.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()))}/IMG_7406.MOV",
            f"{'{:%Y/%m/%d}'.format(datetime.datetime.fromtimestamp(1532618424000.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()))}/IMG_7383.PNG",
            f"{'{:%Y/%m/%d}'.format(datetime.datetime.fromtimestamp(1531371164630.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()))}/IMG_7190.JPG",
            f"{'{:%Y/%m/%d}'.format(datetime.datetime.fromtimestamp(1531371164630.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()))}/IMG_7190-medium.JPG"
        ]

        os.makedirs(os.path.join(
            data_dir, f"{'{:%Y/%m/%d}'.format(datetime.datetime.fromtimestamp(1532940539000.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()))}/"))
        os.makedirs(os.path.join(
            data_dir, f"{'{:%Y/%m/%d}'.format(datetime.datetime.fromtimestamp(1532618424000.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()))}/"))
        os.makedirs(os.path.join(
            data_dir, f"{'{:%Y/%m/%d}'.format(datetime.datetime.fromtimestamp(1531371164630.0 / 1000.0, tz=pytz.utc).astimezone(get_localzone()))}/"))

        # create some empty files
        for file_name in files_to_create + files_to_delete:
            open(os.path.join(data_dir, file_name), "a").close()

        with vcr.use_cassette(os.path.join(self.vcr_path, "autodelete_photos.yml")):
            # Pass fixed client ID via environment variable
            runner = CliRunner(env={
                "CLIENT_ID": "DE309E26-942E-11E8-92F5-14109FE0B321"
            })
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

            self.assertIn(
                "DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
            self.assertIn(
                f"INFO     Downloading 0 original photos to {data_dir} ...",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     All photos have been downloaded", self._caplog.text
            )
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

        files_in_result = glob.glob(os.path.join(
            data_dir, "**/*.*"), recursive=True)

        self.assertEqual(sum(1 for _ in files_in_result), len(files_to_create) + len(files_to_delete), "Files in the result")

        # check files
        for file_name in files_to_create:
            assert os.path.exists(os.path.join(
                data_dir, file_name)), f"{file_name} expected, but missing"

        for file_name in files_to_delete:
            assert os.path.exists(os.path.join(
                data_dir, file_name)), f"{file_name} expected to stay, but missing"
