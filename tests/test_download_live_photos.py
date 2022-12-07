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
from pyicloud.services.photos import PhotoAsset, PhotoAlbum, PhotosService
from pyicloud.base import PyiCloudService
from pyicloud.exceptions import PyiCloudAPIResponseException
from requests.exceptions import ConnectionError
from icloudpd.base import main
from tests.helpers.print_result_exception import print_result_exception
import inspect

vcr = VCR(decode_compressed_response=True)

class DownloadLivePhotoTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    def test_skip_existing_downloads_for_live_photos(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        with vcr.use_cassette("tests/vcr_cassettes/download_live_photos.yml"):
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
                f"INFO     Downloading {os.path.join(base_dir, os.path.normpath('2020/11/04/IMG_0514_HEVC.MOV'))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Downloading {os.path.join(base_dir, os.path.normpath('2020/11/04/IMG_0514.HEIC'))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Downloading {os.path.join(base_dir, os.path.normpath('2020/11/04/IMG_0516.HEIC'))}",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     All photos have been downloaded!", self._caplog.text
            )
            assert result.exit_code == 0

    def test_skip_existing_live_photodownloads(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        # simulate that some of the expected files are there with corret sizes
        os.makedirs(os.path.join(base_dir, "2020/11/04"))
        # one photo and one movie are already there and should be skipped
        # Create dummies with the correct size
        with open(os.path.join(base_dir, "2020/11/04/IMG_0516.HEIC"), "a") as f:
            f.truncate(1651485)
        with open(os.path.join(base_dir, "2020/11/04/IMG_0514_HEVC.MOV"), "a") as f:
            f.truncate(3951774)

        with vcr.use_cassette("tests/vcr_cassettes/download_live_photos.yml"):
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
            self.assertIn(
                f"INFO     Downloading {os.path.join(base_dir, os.path.normpath('2020/11/04/IMG_0514.HEIC'))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     {os.path.join(base_dir, os.path.normpath('2020/11/04/IMG_0514_HEVC.MOV'))} already exists.",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Downloading {os.path.join(base_dir, os.path.normpath('2020/11/04/IMG_0514.HEIC'))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     {os.path.join(base_dir, os.path.normpath('2020/11/04/IMG_0516.HEIC'))} already exists.",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     All photos have been downloaded!", self._caplog.text
            )
            assert result.exit_code == 0

    def test_skip_existing_live_photo_print_filenames(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        # simulate that some of the expected files are there with corret sizes
        os.makedirs(os.path.join(base_dir, "2020/11/04"))
        # one photo and one movie are already there and should be skipped
        # Create dummies with the correct size
        with open(os.path.join(base_dir, "2020/11/04/IMG_0516.HEIC"), "a") as f:
            f.truncate(1651485)
        with open(os.path.join(base_dir, "2020/11/04/IMG_0514_HEVC.MOV"), "a") as f:
            f.truncate(3951774)

        with vcr.use_cassette("tests/vcr_cassettes/download_live_photos.yml"):
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
                    "--only-print-filenames",
                    "-d",
                    base_dir,
                ],
            )
            print_result_exception(result)

            filenames = result.output.splitlines()

            print (filenames)

            self.assertEqual(
                os.path.join(base_dir, os.path.normpath("2020/11/04/IMG_0514.HEIC")),
                filenames[0]
            )
            self.assertEqual(
                os.path.join(base_dir, os.path.normpath("2020/11/04/IMG_0512.HEIC")),
                filenames[1]
            )
            self.assertEqual(
                os.path.join(base_dir, os.path.normpath("2020/11/04/IMG_0512_HEVC.MOV")),
                filenames[2]
            )

            # Double check that a mocked file does not get listed again. Its already there!
            assert "2020/11/04/IMG_0514_HEVC.MOV" not in filenames

            assert result.exit_code == 0
