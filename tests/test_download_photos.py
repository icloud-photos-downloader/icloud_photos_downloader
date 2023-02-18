from unittest import TestCase
from vcr import VCR
import os
import sys
import shutil
import pytest
import mock
import datetime
from mock import call, ANY
from click.testing import CliRunner
import piexif
from piexif._exceptions import InvalidImageDataError
from pyicloud_ipd.services.photos import PhotoAsset, PhotoAlbum, PhotosService
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.exceptions import PyiCloudAPIResponseError
from requests.exceptions import ConnectionError
from icloudpd.base import main
from tests.helpers.print_result_exception import print_result_exception
import inspect
import glob

vcr = VCR(decode_compressed_response=True)

class DownloadPhotoTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    def test_download_and_skip_existing_photos(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        files_to_create = [
            ("2018/07/30/IMG_7408.JPG", 1151066),
            ("2018/07/30/IMG_7407.JPG", 656257),
        ]

        files_to_download = [
            '2018/07/31/IMG_7409.JPG'
        ]

        os.makedirs(os.path.join(base_dir, "2018/07/30/"))
        for (file_name, file_size) in files_to_create:
            with open(os.path.join(base_dir, file_name), "a") as f:
                f.truncate(file_size)

        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
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
                    "5",
                    "--skip-videos",
                    "--skip-live-photos",
                    "--set-exif-datetime",
                    "--no-progress-bar",
                    "--threads-num",
                    1,
                    "-d",
                    base_dir,
                ],
            )
            print_result_exception(result)

            self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
            self.assertIn(
                f"INFO     Downloading 5 original photos to {base_dir} ...",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Downloading {os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}",
                self._caplog.text,
            )
            self.assertNotIn(
                "IMG_7409.MOV",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     {os.path.join(base_dir, os.path.normpath('2018/07/30/IMG_7408.JPG'))} already exists.",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     {os.path.join(base_dir, os.path.normpath('2018/07/30/IMG_7407.JPG'))} already exists.",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     Skipping IMG_7405.MOV, only downloading photos.",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     Skipping IMG_7404.MOV, only downloading photos.",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     All photos have been downloaded!", self._caplog.text
            )

            assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_create) + len(files_to_download)

        for file_name in files_to_download + ([file_name for (file_name, _) in files_to_create]):
            assert os.path.exists(os.path.join(base_dir, os.path.normpath(file_name))), f"File {file_name} expected, but does not exist"

        # Check that file was downloaded
        # Check that mtime was updated to the photo creation date
        photo_mtime = os.path.getmtime(os.path.join(base_dir, os.path.normpath("2018/07/31/IMG_7409.JPG")))
        photo_modified_time = datetime.datetime.utcfromtimestamp(photo_mtime)
        self.assertEqual(
            "2018-07-31 07:22:24",
            photo_modified_time.strftime('%Y-%m-%d %H:%M:%S'))


    def test_download_photos_and_set_exif(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        files_to_create = [
            ("2018/07/30/IMG_7408.JPG", 1151066),
            ("2018/07/30/IMG_7407.JPG", 656257),
        ]

        files_to_download = [
            '2018/07/30/IMG_7405.MOV',
            '2018/07/30/IMG_7407.MOV',
            '2018/07/30/IMG_7408.MOV',
            '2018/07/31/IMG_7409.JPG',
            '2018/07/31/IMG_7409.MOV',
        ]

        os.makedirs(os.path.join(base_dir, "2018/07/30/"))
        for (file_name, file_size) in files_to_create:
            with open(os.path.join(base_dir, file_name), "a") as f:
                f.truncate(file_size)

        # Download the first photo, but mock the video download
        orig_download = PhotoAsset.download

        def mocked_download(self, size):
            if not hasattr(PhotoAsset, "already_downloaded"):
                response = orig_download(self, size)
                setattr(PhotoAsset, "already_downloaded", True)
                return response
            return mock.MagicMock()

        with mock.patch.object(PhotoAsset, "download", new=mocked_download):
            with mock.patch(
                "icloudpd.exif_datetime.get_photo_exif"
            ) as get_exif_patched:
                get_exif_patched.return_value = False
                with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
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
                            "4",
                            "--set-exif-datetime",
                            # '--skip-videos',
                            # "--skip-live-photos",
                            "--no-progress-bar",
                            "--threads-num",
                            1,
                            "-d",
                            base_dir,
                        ],
                    )
                    print_result_exception(result)

                    self.assertIn(
                        "DEBUG    Looking up all photos and videos from album All Photos...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        f"INFO     Downloading 4 original photos and videos to {base_dir} ...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        f"INFO     Downloading {os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}",
                        self._caplog.text,
                    )
                    # 2018:07:31 07:22:24 utc
                    expectedDatetime = datetime.datetime(2018,7,31,7,22,24,tzinfo=datetime.timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S%z")
                    self.assertIn(
                        f"DEBUG    Setting EXIF timestamp for {os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}: {expectedDatetime}",
                        self._caplog.text,
                    )
                    self.assertIn(
                        "INFO     All photos have been downloaded!", self._caplog.text
                    )
                    assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_create) + len(files_to_download)

        for file_name in files_to_download + ([file_name for (file_name, _) in files_to_create]):
            assert os.path.exists(os.path.join(base_dir, os.path.normpath(file_name))), f"File {file_name} expected, but does not exist"

    def test_download_photos_and_get_exif_exceptions(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        files_to_download = [
            '2018/07/31/IMG_7409.JPG'
        ]

        with mock.patch.object(piexif, "load") as piexif_patched:
            piexif_patched.side_effect = InvalidImageDataError

            with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
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
                        "--skip-videos",
                        "--skip-live-photos",
                        "--set-exif-datetime",
                        "--no-progress-bar",
                        "--threads-num",
                        1,
                        "-d",
                        base_dir,
                    ],
                )
                print_result_exception(result)

                self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
                self.assertIn(
                    f"INFO     Downloading the first original photo to {base_dir} ...",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     Downloading {os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}",
                    self._caplog.text,
                )
                self.assertIn(
                    f"DEBUG    Error fetching EXIF data for {os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}",
                    self._caplog.text,
                )
                self.assertIn(
                    f"DEBUG    Error setting EXIF data for {os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}",
                    self._caplog.text,
                )
                self.assertIn(
                    "INFO     All photos have been downloaded!", self._caplog.text
                )
                assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_download)

        for file_name in files_to_download:
            assert os.path.exists(os.path.join(base_dir, os.path.normpath(file_name))), f"File {file_name} expected, but does not exist"

    def test_skip_existing_downloads(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        files_to_create = [
            ("2018/07/31/IMG_7409.JPG", 1884695),
            ("2018/07/31/IMG_7409.MOV", 3294075),
        ]

        files_to_download = [
        ]

        os.makedirs(os.path.join(base_dir, "2018/07/31/"))
        for (file_name, file_size) in files_to_create:
            with open(os.path.join(base_dir, file_name), "a") as f:
                f.truncate(file_size)

        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
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
                    # '--skip-videos',
                    # "--skip-live-photos",
                    "--no-progress-bar",
                    "--threads-num",
                    1,
                    "-d",
                    base_dir,
                ],
            )
            print_result_exception(result)

            self.assertIn(
                "DEBUG    Looking up all photos and videos from album All Photos...", self._caplog.text
            )
            self.assertIn(
                f"INFO     Downloading the first original photo or video to {base_dir} ...",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     {os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))} already exists.",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     {os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409.MOV'))} already exists.",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     All photos have been downloaded!", self._caplog.text
            )
            assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_download) + len(files_to_create)

        for file_name in files_to_download + ([file_name for (file_name, _) in files_to_create]):
            assert os.path.exists(os.path.join(base_dir, os.path.normpath(file_name))), f"File {file_name} expected, but does not exist"

    def test_until_found(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        os.makedirs(os.path.join(base_dir, "2018/07/30/"))
        os.makedirs(os.path.join(base_dir, "2018/07/31/"))

        files_to_download = []
        files_to_skip = []

        files_to_download.append(("2018/07/31/IMG_7409.JPG", "photo"))
        files_to_download.append(("2018/07/31/IMG_7409-medium.MOV", "photo"))
        files_to_skip.append(("2018/07/30/IMG_7408.JPG", "photo", 1151066))
        files_to_skip.append(("2018/07/30/IMG_7408-medium.MOV", "photo", 894467))
        files_to_download.append(("2018/07/30/IMG_7407.JPG", "photo"))
        files_to_download.append(("2018/07/30/IMG_7407-medium.MOV", "photo"))
        files_to_skip.append(("2018/07/30/IMG_7405.MOV", "video", 36491351))
        files_to_skip.append(("2018/07/30/IMG_7404.MOV", "video", 225935003))
        files_to_download.append(("2018/07/30/IMG_7403.MOV", "video"))
        files_to_download.append(("2018/07/30/IMG_7402.MOV", "video"))
        files_to_skip.append(("2018/07/30/IMG_7401.MOV", "photo", 565699696))   # TODO large files on Windows times out
        files_to_skip.append(("2018/07/30/IMG_7400.JPG", "photo", 2308885))
        files_to_skip.append(("2018/07/30/IMG_7400-medium.MOV", "photo", 1238639))
        files_to_skip.append(("2018/07/30/IMG_7399.JPG", "photo", 2251047))
        files_to_download.append(("2018/07/30/IMG_7399-medium.MOV", "photo"))

        for f in files_to_skip:
            with open(os.path.join(base_dir, f[0]), "a") as fi:
                fi.truncate(f[2])

        with mock.patch("icloudpd.download.download_media") as dp_patched:
            dp_patched.return_value = True
            with mock.patch("icloudpd.download.os.utime") as ut_patched:
                ut_patched.return_value = None
                with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
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
                            "--live-photo-size",
                            "medium",
                            "--until-found",
                            "3",
                            "--recent",
                            "20",
                            "--no-progress-bar",
                            "--threads-num",
                            1,
                            "-d",
                            base_dir,
                        ],
                    )
                    print_result_exception(result)

                    expected_calls = list(
                        map(
                            lambda f: call(
                                ANY, ANY, os.path.join(base_dir, os.path.normpath(f[0])),
                                "mediumVideo" if (
                                    f[1] == 'photo' and f[0].endswith('.MOV')
                                ) else "original"),
                            files_to_download,
                        )
                    )
                    dp_patched.assert_has_calls(expected_calls)

                    self.assertIn(
                        "DEBUG    Looking up all photos and videos from album All Photos...", self._caplog.text
                    )
                    self.assertIn(
                        f"INFO     Downloading ??? original photos and videos to {base_dir} ...",
                        self._caplog.text,
                    )

                    for f in files_to_skip:
                        expected_message = f"INFO     {os.path.join(base_dir, os.path.normpath(f[0]))} already exists." 
                        self.assertIn(expected_message, self._caplog.text)

                    self.assertIn(
                        "INFO     Found 3 consecutive previously downloaded photos. Exiting",
                        self._caplog.text,
                    )
                    self.assertNotIn(
                        f"INFO     {os.path.join(base_dir, os.path.normpath('2018/07/30/IMG_7399-medium.MOV'))} already exists.", 
                        self._caplog.text
                    )

                    assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_skip) # we faked downloading

        for file_name in ([file_name for (file_name, _, _) in files_to_skip]):
            assert os.path.exists(os.path.join(base_dir, os.path.normpath(file_name))), f"File {file_name} expected, but does not exist"

    def test_handle_io_error(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
            with mock.patch("icloudpd.download.open", create=True) as m:
                # Raise IOError when we try to write to the destination file
                m.side_effect = IOError

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
                        "--skip-videos",
                        "--skip-live-photos",
                        "--no-progress-bar",
                        "--threads-num",
                        1,
                        "-d",
                        base_dir,
                    ],
                )
                print_result_exception(result)

                self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
                self.assertIn(
                    f"INFO     Downloading the first original photo to {base_dir} ...",
                    self._caplog.text,
                )
                self.assertIn(
                    "ERROR    IOError while writing file to "
                    f"{os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}! "
                    "You might have run out of disk space, or the file might "
                    "be too large for your OS. Skipping this file...",
                    self._caplog.text,
                )
                assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 0

    def test_handle_session_error_during_download(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):

            def mock_raise_response_error(arg):
                raise PyiCloudAPIResponseError("Invalid global session", 100)

            with mock.patch("time.sleep") as sleep_mock:
                with mock.patch.object(PhotoAsset, "download") as pa_download:
                    pa_download.side_effect = mock_raise_response_error

                    # Let the initial authenticate() call succeed,
                    # but do nothing on the second try.
                    orig_authenticate = PyiCloudService.authenticate

                    def mocked_authenticate(self):
                        if not hasattr(self, "already_authenticated"):
                            orig_authenticate(self)
                            setattr(self, "already_authenticated", True)

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
                                "--skip-videos",
                                "--skip-live-photos",
                                "--no-progress-bar",
                                "--threads-num",
                                1,
                                "-d",
                                base_dir,
                            ],
                        )
                        print_result_exception(result)

                        # Error msg should be repeated 5 times
                        assert (
                            self._caplog.text.count(
                                "Session error, re-authenticating..."
                            )
                            == 5
                        )

                        self.assertIn(
                            "INFO     Could not download IMG_7409.JPG! Please try again later.",
                            self._caplog.text,
                        )

                        # Make sure we only call sleep 4 times (skip the first retry)
                        self.assertEqual(sleep_mock.call_count, 4)
                        assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 0

    def test_handle_session_error_during_photo_iteration(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):

            def mock_raise_response_error(offset):
                raise PyiCloudAPIResponseError("Invalid global session", 100)

            with mock.patch("time.sleep") as sleep_mock:
                with mock.patch.object(PhotoAlbum, "photos_request") as pa_photos_request:
                    pa_photos_request.side_effect = mock_raise_response_error

                    # Let the initial authenticate() call succeed,
                    # but do nothing on the second try.
                    orig_authenticate = PyiCloudService.authenticate

                    def mocked_authenticate(self):
                        if not hasattr(self, "already_authenticated"):
                            orig_authenticate(self)
                            setattr(self, "already_authenticated", True)

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
                                "--skip-videos",
                                "--skip-live-photos",
                                "--no-progress-bar",
                                "--threads-num",
                                1,
                                "-d",
                                base_dir,
                            ],
                        )
                        print_result_exception(result)

                        # Error msg should be repeated 5 times
                        assert (
                            self._caplog.text.count(
                                "Session error, re-authenticating..."
                            )
                            == 5
                        )

                        self.assertIn(
                            "INFO     iCloud re-authentication failed! Please try again later.",
                            self._caplog.text,
                        )
                        # Make sure we only call sleep 4 times (skip the first retry)
                        self.assertEqual(sleep_mock.call_count, 4)

                        assert result.exit_code == 1

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 0

    def test_handle_connection_error(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
            # Pass fixed client ID via environment variable

            def mock_raise_response_error(arg):
                raise ConnectionError("Connection Error")

            with mock.patch.object(PhotoAsset, "download") as pa_download:
                pa_download.side_effect = mock_raise_response_error

                # Let the initial authenticate() call succeed,
                # but do nothing on the second try.
                orig_authenticate = PyiCloudService.authenticate

                def mocked_authenticate(self):
                    if not hasattr(self, "already_authenticated"):
                        orig_authenticate(self)
                        setattr(self, "already_authenticated", True)

                with mock.patch("icloudpd.constants.WAIT_SECONDS", 0):
                    with mock.patch.object(
                        PyiCloudService, "authenticate", new=mocked_authenticate
                    ):
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
                                "--skip-videos",
                                "--skip-live-photos",
                                "--no-progress-bar",
                                "--threads-num",
                                1,
                                "-d",
                                base_dir,
                            ],
                        )
                        print_result_exception(result)

                        # Error msg should be repeated 5 times
                        assert (
                            self._caplog.text.count(
                                "Error downloading IMG_7409.JPG, retrying after 0 seconds..."
                            )
                            == 5
                        )

                        self.assertIn(
                            "INFO     Could not download IMG_7409.JPG! Please try again later.",
                            self._caplog.text,
                        )
                        assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 0

    def test_handle_albums_error(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
            # Pass fixed client ID via environment variable

            def mock_raise_response_error():
                raise PyiCloudAPIResponseError("Api Error", 100)

            with mock.patch.object(PhotosService, "_fetch_folders") as pa_photos_request:
                pa_photos_request.side_effect = mock_raise_response_error

                # Let the initial authenticate() call succeed,
                # but do nothing on the second try.
                orig_authenticate = PyiCloudService.authenticate

                def mocked_authenticate(self):
                    if not hasattr(self, "already_authenticated"):
                        orig_authenticate(self)
                        setattr(self, "already_authenticated", True)

                with mock.patch("icloudpd.constants.WAIT_SECONDS", 0):
                    with mock.patch.object(
                        PyiCloudService, "authenticate", new=mocked_authenticate
                    ):
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
                                "--skip-videos",
                                "--skip-live-photos",
                                "--no-progress-bar",
                                "--threads-num",
                                1,
                                "-d",
                                base_dir,
                            ],
                        )
                        print_result_exception(result)

                        assert result.exit_code == 1

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 0

    def test_missing_size(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        with mock.patch.object(PhotoAsset, "download") as pa_download:
            pa_download.return_value = False

            with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
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
                        "3",
                        "--no-progress-bar",
                        "--threads-num",
                        1,
                        "-d",
                        base_dir,
                    ],
                )
                print_result_exception(result)

                self.assertIn(
                    "DEBUG    Looking up all photos and videos from album All Photos...", self._caplog.text
                )
                self.assertIn(
                    f"INFO     Downloading 3 original photos and videos to {base_dir} ...",
                    self._caplog.text,
                )

                # These error messages should not be repeated more than once
                assert (
                    self._caplog.text.count(
                        "ERROR    Could not find URL to download IMG_7409.JPG for size original!"
                    )
                    == 1
                )
                assert (
                    self._caplog.text.count(
                        "ERROR    Could not find URL to download IMG_7408.JPG for size original!"
                    )
                    == 1
                )
                assert (
                    self._caplog.text.count(
                        "ERROR    Could not find URL to download IMG_7407.JPG for size original!"
                    )
                    == 1
                )

                self.assertIn(
                    "INFO     All photos have been downloaded!", self._caplog.text
                )
                assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 0

    def test_size_fallback_to_original(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        with mock.patch("icloudpd.download.download_media") as dp_patched:
            dp_patched.return_value = True

            with mock.patch("icloudpd.download.os.utime") as ut_patched:
                ut_patched.return_value = None

                with mock.patch.object(PhotoAsset, "versions") as pa:
                    pa.return_value = ["original", "medium"]

                    with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
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
                                "--size",
                                "thumb",
                                "--no-progress-bar",
                                "--threads-num",
                                1,
                                "-d",
                                base_dir,
                            ],
                        )
                        print_result_exception(result)
                        self.assertIn(
                            "DEBUG    Looking up all photos and videos from album All Photos...",
                            self._caplog.text,
                        )
                        self.assertIn(
                            f"INFO     Downloading the first thumb photo or video to {base_dir} ...",
                            self._caplog.text,
                        )
                        self.assertIn(
                            f"INFO     Downloading {os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}",
                            self._caplog.text,
                        )
                        self.assertIn(
                            "INFO     All photos have been downloaded!", self._caplog.text
                        )
                        dp_patched.assert_called_once_with(
                            ANY,
                            ANY,
                            f"{os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}",
                            "original",
                        )

                        assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 0

    def test_force_size(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        with mock.patch("icloudpd.download.download_media") as dp_patched:
            dp_patched.return_value = True

            with mock.patch.object(PhotoAsset, "versions") as pa:
                pa.return_value = ["original", "medium"]

                with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
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
                            "--size",
                            "thumb",
                            "--force-size",
                            "--no-progress-bar",
                            "--threads-num",
                            1,
                            "-d",
                            base_dir,
                        ],
                    )
                    print_result_exception(result)

                    self.assertIn(
                        "DEBUG    Looking up all photos and videos from album All Photos...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        f"INFO     Downloading the first thumb photo or video to {base_dir} ...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        "ERROR    thumb size does not exist for IMG_7409.JPG. Skipping...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        "INFO     All photos have been downloaded!", self._caplog.text
                    )
                    dp_patched.assert_not_called

                    assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 0

    def test_invalid_creation_date(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        files_to_download = [
            '2018/01/01/IMG_7409.JPG'
        ]

        with mock.patch.object(PhotoAsset, "created", new_callable=mock.PropertyMock) as dt_mock:
            # Can't mock `astimezone` because it's a readonly property, so have to
            # create a new class that inherits from datetime.datetime
            class NewDateTime(datetime.datetime):
                def astimezone(self, tz=None):
                    raise ValueError('Invalid date')
            dt_mock.return_value = NewDateTime(2018,1,1,0,0,0)

            with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
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
                        "--skip-live-photos",
                        "--no-progress-bar",
                        "--threads-num",
                        1,
                        "-d",
                        base_dir,
                    ],
                )
                print_result_exception(result)

                self.assertIn(
                    "DEBUG    Looking up all photos and videos from album All Photos...",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     Downloading the first original photo or video to {base_dir} ...",
                    self._caplog.text,
                )
                self.assertIn(
                    "ERROR    Could not convert photo created date to local timezone (2018-01-01 00:00:00)",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     Downloading {os.path.join(base_dir, os.path.normpath('2018/01/01/IMG_7409.JPG'))}",
                    self._caplog.text,
                )
                self.assertIn(
                    "INFO     All photos have been downloaded!", self._caplog.text
                )
                assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_download)

        for file_name in files_to_download:
            assert os.path.exists(os.path.join(base_dir, os.path.normpath(file_name))), f"File {file_name} expected, but does not exist"

    @pytest.mark.skipif(sys.platform == 'win32',
                    reason="does not run on windows")
    @pytest.mark.skipif(sys.platform == 'darwin',
                    reason="does not run on mac")
    def test_invalid_creation_year(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        files_to_download = [
            '5/01/01/IMG_7409.JPG'
        ]

        with mock.patch.object(PhotoAsset, "created", new_callable=mock.PropertyMock) as dt_mock:
            # Can't mock `astimezone` because it's a readonly property, so have to
            # create a new class that inherits from datetime.datetime
            class NewDateTime(datetime.datetime):
                def astimezone(self, tz=None):
                    raise ValueError('Invalid date')
            dt_mock.return_value = NewDateTime(5,1,1,0,0,0)

            with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
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
                        "--skip-live-photos",
                        "--no-progress-bar",
                        "--threads-num",
                        1,
                        "-d",
                        base_dir,
                    ],
                )
                print_result_exception(result)

                self.assertIn(
                    "DEBUG    Looking up all photos and videos from album All Photos...",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     Downloading the first original photo or video to {base_dir} ...",
                    self._caplog.text,
                )
                self.assertIn(
                    "ERROR    Could not convert photo created date to local timezone (0005-01-01 00:00:00)",
                    self._caplog.text,
                )
                self.assertIn(
                        f"INFO     Downloading {os.path.join(base_dir, os.path.normpath('5/01/01/IMG_7409.JPG'))}",
                        self._caplog.text,
                )
                self.assertIn(
                    "INFO     All photos have been downloaded!", self._caplog.text
                )
                assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_download)

        for file_name in files_to_download:
            assert os.path.exists(os.path.join(base_dir, os.path.normpath(file_name))), f"File {file_name} expected, but does not exist"

    def test_unknown_item_type(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        with mock.patch("icloudpd.download.download_media") as dp_patched:
            dp_patched.return_value = True

            with mock.patch.object(PhotoAsset, "item_type", new_callable=mock.PropertyMock) as it_mock:
                it_mock.return_value = 'unknown'

                with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
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
                            "--no-progress-bar",
                            "--threads-num",
                            1,
                            "-d",
                            base_dir,
                        ],
                    )
                    print_result_exception(result)

                    self.assertIn(
                        "DEBUG    Looking up all photos and videos from album All Photos...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        f"INFO     Downloading the first original photo or video to {base_dir} ...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        "INFO     Skipping IMG_7409.JPG, only downloading photos and videos. (Item type was: unknown)",
                        self._caplog.text,
                    )
                    self.assertIn(
                        "INFO     All photos have been downloaded!", self._caplog.text
                    )
                    dp_patched.assert_not_called

                    assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 0

    def test_download_and_dedupe_existing_photos(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        os.makedirs(os.path.join(base_dir, os.path.normpath("2018/07/31/")))
        with open(os.path.join(base_dir, os.path.normpath("2018/07/31/IMG_7409.JPG")), "a") as f:
            f.truncate(1)
        with open(os.path.join(base_dir, os.path.normpath("2018/07/31/IMG_7409.MOV")), "a") as f:
            f.truncate(1)
        os.makedirs(os.path.join(base_dir, os.path.normpath("2018/07/30/")))
        with open(os.path.join(base_dir, os.path.normpath("2018/07/30/IMG_7408.JPG")), "a") as f:
            f.truncate(1151066)
        with open(os.path.join(base_dir, os.path.normpath("2018/07/30/IMG_7408.MOV")), "a") as f:
            f.truncate(1606512)

        # Download the first photo, but mock the video download
        orig_download = PhotoAsset.download

        def mocked_download(self, size):
            if not hasattr(PhotoAsset, "already_downloaded"):
                response = orig_download(self, size)
                setattr(PhotoAsset, "already_downloaded", True)
                return response
            return mock.MagicMock()

        with mock.patch.object(PhotoAsset, "download", new=mocked_download):
            with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
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
                        "5",
                        "--skip-videos",
                        # "--set-exif-datetime",
                        "--no-progress-bar",
                        "-d",
                        base_dir,
                        "--threads-num",
                        "1"
                    ],
                )
                print_result_exception(result)

                self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
                self.assertIn(
                    f"INFO     Downloading 5 original photos to {base_dir} ...",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     {os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409-1884695.JPG'))} deduplicated.",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     Downloading {os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409-1884695.JPG'))}",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     {os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409-3294075.MOV'))} deduplicated.",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     Downloading {os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409-3294075.MOV'))}",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     {os.path.join(base_dir, os.path.normpath('2018/07/30/IMG_7408.JPG'))} already exists.",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     {os.path.join(base_dir, os.path.normpath('2018/07/30/IMG_7408.MOV'))} already exists.",
                    self._caplog.text,
                )
                self.assertIn(
                    "INFO     Skipping IMG_7405.MOV, only downloading photos.", self._caplog.text
                )
                self.assertIn(
                    "INFO     Skipping IMG_7404.MOV, only downloading photos.", self._caplog.text
                )
                self.assertIn(
                    "INFO     All photos have been downloaded!", self._caplog.text
                )

                # Check that file was downloaded
                self.assertTrue(
                    os.path.exists(os.path.join(base_dir, os.path.normpath("2018/07/31/IMG_7409-1884695.JPG"))))
                # Check that mtime was updated to the photo creation date
                photo_mtime = os.path.getmtime(os.path.join(base_dir, os.path.normpath("2018/07/31/IMG_7409-1884695.JPG")))
                photo_modified_time = datetime.datetime.utcfromtimestamp(photo_mtime)
                self.assertEqual(
                    "2018-07-31 07:22:24",
                    photo_modified_time.strftime('%Y-%m-%d %H:%M:%S'))
                self.assertTrue(
                    os.path.exists(os.path.join(base_dir, os.path.normpath("2018/07/31/IMG_7409-3294075.MOV"))))
                photo_mtime = os.path.getmtime(os.path.join(base_dir, os.path.normpath("2018/07/31/IMG_7409-3294075.MOV")))
                photo_modified_time = datetime.datetime.utcfromtimestamp(photo_mtime)
                self.assertEqual(
                    "2018-07-31 07:22:24",
                    photo_modified_time.strftime('%Y-%m-%d %H:%M:%S'))

                assert result.exit_code == 0


    def test_download_photos_and_set_exif_exceptions(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        files_to_download = [
            '2018/07/31/IMG_7409.JPG'   
        ]

        with mock.patch.object(piexif, "insert") as piexif_patched:
            piexif_patched.side_effect = InvalidImageDataError
            with mock.patch(
                "icloudpd.exif_datetime.get_photo_exif"
            ) as get_exif_patched:
                get_exif_patched.return_value = False
                with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
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
                            "--skip-videos",
                            "--skip-live-photos",
                            "--set-exif-datetime",
                            "--no-progress-bar",
                            "--threads-num",
                            1,
                            "-d",
                            base_dir,
                        ],
                    )
                    print_result_exception(result)

                    self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
                    self.assertIn(
                        f"INFO     Downloading the first original photo to {base_dir} ...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        f"INFO     Downloading {os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}",
                        self._caplog.text,
                    )
                    # 2018:07:31 07:22:24 utc
                    expectedDatetime = datetime.datetime(2018,7,31,7,22,24,tzinfo=datetime.timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S%z")
                    self.assertIn(
                        f"DEBUG    Setting EXIF timestamp for {os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}: {expectedDatetime}",
                        self._caplog.text,
                    )
                    self.assertIn(
                        f"DEBUG    Error setting EXIF data for {os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}",
                        self._caplog.text,
                    )
                    self.assertIn(
                        "INFO     All photos have been downloaded!", self._caplog.text
                    )
                    assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_download)

        for file_name in files_to_download:
            assert os.path.exists(os.path.join(base_dir, os.path.normpath(file_name))), f"File {file_name} expected, but does not exist"

    def test_download_chinese(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}/中文")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        files_to_download = [
            '2018/07/31/IMG_7409.JPG'
        ]

        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
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
                    "--skip-videos",
                    "--skip-live-photos",
                    "--set-exif-datetime",
                    "--no-progress-bar",
                    "--threads-num",
                    1,
                    "-d",
                    base_dir,
                ],
            )
            print_result_exception(result)

            self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
            self.assertIn(
                f'INFO     Downloading the first original photo to {base_dir} ...',
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Downloading {os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}",
                self._caplog.text,
            )
            self.assertNotIn(
                "IMG_7409.MOV",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     All photos have been downloaded!", self._caplog.text
            )

            # Check that file was downloaded
            self.assertTrue(
                os.path.exists(os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))))
            # Check that mtime was updated to the photo creation date
            photo_mtime = os.path.getmtime(os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409.JPG')))
            photo_modified_time = datetime.datetime.utcfromtimestamp(photo_mtime)
            self.assertEqual(
                "2018-07-31 07:22:24",
                photo_modified_time.strftime('%Y-%m-%d %H:%M:%S'))

            assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_download)

        for file_name in files_to_download:
            assert os.path.exists(os.path.join(base_dir, os.path.normpath(file_name))), f"File {file_name} expected, but does not exist"

    def test_download_after_delete(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        files_to_download = [
            '2018/07/31/IMG_7409.JPG'
        ]

        with mock.patch.object(piexif, "insert") as piexif_patched:
            piexif_patched.side_effect = InvalidImageDataError
            with mock.patch(
                "icloudpd.exif_datetime.get_photo_exif"
            ) as get_exif_patched:
                get_exif_patched.return_value = False
                with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
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
                            "--skip-videos",
                            "--skip-live-photos",
                            "--no-progress-bar",
                            "--threads-num",
                            1,
                            "--delete-after-download",
                            "-d",
                            base_dir,
                        ],
                    )
                    print_result_exception(result)

                    self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
                    self.assertIn(
                        f"INFO     Downloading the first original photo to {base_dir} ...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        f"INFO     Downloading {os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}",
                        self._caplog.text,
                    )
                    self.assertIn(
                        "INFO     Deleting IMG_7409.JPG", self._caplog.text
                    )
                    self.assertIn(
                        "INFO     All photos have been downloaded!", self._caplog.text
                    )
                    assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_download)

        for file_name in files_to_download:
            assert os.path.exists(os.path.join(base_dir, os.path.normpath(file_name))), f"File {file_name} expected, but does not exist"

    def test_download_over_old_original_photos(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        files_to_create = [
            ("2018/07/30/IMG_7408-original.JPG",1151066),
            ("2018/07/30/IMG_7407.JPG",656257)
        ]

        files_to_download = [
            '2018/07/31/IMG_7409.JPG'
        ]

        os.makedirs(os.path.join(base_dir, "2018/07/30/"))
        for (file_name, file_size) in files_to_create:
            with open(os.path.join(base_dir, file_name), "a") as f:
                f.truncate(file_size)

        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
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
                    "5",
                    "--skip-videos",
                    "--skip-live-photos",
                    "--set-exif-datetime",
                    "--no-progress-bar",
                    "--threads-num",
                    1,
                    "-d",
                    base_dir,
                ],
            )
            print_result_exception(result)

            self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
            self.assertIn(
                f"INFO     Downloading 5 original photos to {base_dir} ...",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Downloading {os.path.join(base_dir, os.path.normpath('2018/07/31/IMG_7409.JPG'))}",
                self._caplog.text,
            )
            self.assertNotIn(
                "IMG_7409.MOV",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     {os.path.join(base_dir, os.path.normpath('2018/07/30/IMG_7408.JPG'))} already exists.",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     {os.path.join(base_dir, os.path.normpath('2018/07/30/IMG_7407.JPG'))} already exists.",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     Skipping IMG_7405.MOV, only downloading photos.",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     Skipping IMG_7404.MOV, only downloading photos.",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     All photos have been downloaded!", self._caplog.text
            )

            # Check that file was downloaded
            self.assertTrue(
                os.path.exists(os.path.join(base_dir, os.path.normpath("2018/07/31/IMG_7409.JPG"))))
            # Check that mtime was updated to the photo creation date
            photo_mtime = os.path.getmtime(os.path.join(base_dir, os.path.normpath("2018/07/31/IMG_7409.JPG")))
            photo_modified_time = datetime.datetime.utcfromtimestamp(photo_mtime)
            self.assertEqual(
                "2018-07-31 07:22:24",
                photo_modified_time.strftime('%Y-%m-%d %H:%M:%S'))

            assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_download) + len(files_to_create)

        for file_name in files_to_download + ([file_name for (file_name, _) in files_to_create]):
            assert os.path.exists(os.path.join(base_dir, os.path.normpath(file_name))), f"File {file_name} expected, but does not exist"

    def test_download_normalized_names(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        files_to_create = [
            ("2018/07/30/IMG_7408.JPG", 1151066),
            ("2018/07/30/IMG_7407.JPG", 656257),
        ]

        files_to_download = [
            # <>:"/\|?*  -- windows
            # / & \0x00 -- linux
            '2018/07/31/i_n v_a_l_i_d_p_a_t_h_.JPG' #SU1HXzc0MDkuSlBH -> i/n v:a\0l*i?d\p<a>t"h|.JPG -> aS9uIHY6YQBsKmk/ZFxwPGE+dCJofC5KUEc=
        ]

        os.makedirs(os.path.join(base_dir, "2018/07/30/"))
        for (file_name, file_size) in files_to_create:
            with open(os.path.join(base_dir, file_name), "a") as f:
                f.truncate(file_size)

        with vcr.use_cassette("tests/vcr_cassettes/listing_photos_bad_filename.yml"):
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
                    "5",
                    "--skip-videos",
                    "--skip-live-photos",
                    "--set-exif-datetime",
                    "--no-progress-bar",
                    "--threads-num",
                    1,
                    "-d",
                    base_dir,
                ],
            )
            print_result_exception(result)

            assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_create) + len(files_to_download)

        for file_name in files_to_download + ([file_name for (file_name, _) in files_to_create]):
            assert os.path.exists(os.path.join(base_dir, os.path.normpath(file_name))), f"File {file_name} expected, but does not exist"

    @pytest.mark.skip("not ready yet. may be not needed")
    def test_download_watch(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        files_to_create = [
            ("2018/07/30/IMG_7408.JPG", 1151066),
            ("2018/07/30/IMG_7407.JPG", 656257),
        ]

        files_to_download = [
            '2018/07/31/IMG_7409.JPG'
        ]

        os.makedirs(os.path.join(base_dir, "2018/07/30/"))
        for (file_name, file_size) in files_to_create:
            with open(os.path.join(base_dir, file_name), "a") as f:
                f.truncate(file_size)

        def my_sleep(target_duration):
            counter = 0
            def sleep_(duration):
                if counter > duration:
                    raise ValueError("SLEEP MOCK")
                counter = counter + 1
            return sleep_

        with mock.patch("time.sleep") as sleep_patched:
            # import random
            target_duration = 1
            sleep_patched.side_effect = my_sleep(target_duration)
            with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
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
                        "5",
                        "--skip-videos",
                        "--skip-live-photos",
                        "--set-exif-datetime",
                        "--no-progress-bar",
                        "--threads-num",
                        1,
                        "-d",
                        base_dir,
                        "--watch-with-interval",
                        target_duration
                    ],
                )
                print_result_exception(result)

                assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_create) + len(files_to_download)

        for file_name in files_to_download + ([file_name for (file_name, _) in files_to_create]):
            assert os.path.exists(os.path.join(base_dir, os.path.normpath(file_name))), f"File {file_name} expected, but does not exist"

