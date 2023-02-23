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

vcr = VCR(decode_compressed_response=True)

class DownloadAndConvertHeicTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    def test_convert_heic_to_jpg(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        with vcr.use_cassette("tests/vcr_cassettes/download_one_heic_photo.yml"):
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
                    "--convert-jpg",
                ],
            )
            print_result_exception(result)

            self.assertIn("Converting IMG_3140.HEIC to JPG", self._caplog.text)

            self.assertIn(
                "INFO     All photos have been downloaded!", self._caplog.text
            )
            assert result.exit_code == 0

    def test_convert_heic_to_jpg_error(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        with vcr.use_cassette("tests/vcr_cassettes/download_one_heic_photo_error.yml"):
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
                    "--convert-jpg",
                ],
            )
            print_result_exception(result)

            self.assertIn("Error converting heif image IMG_3140.HEIC", self._caplog.text)

            self.assertIn(
                "INFO     All photos have been downloaded!", self._caplog.text
            )
            assert result.exit_code == 0

    def test_convert_heic_module_convert_error(self):
        """Test failure to import heif_to_jpg from convert."""
        import builtins

        real_import = builtins.__import__

        def my_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "icloudpd.convert" and "heif_to_jpg" in fromlist:
                raise ModuleNotFoundError
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = my_import

        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

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
                "--convert-jpg",
            ],
        )

        print_result_exception(result)
        assert result.exit_code == 1

    def test_convert_heic_module_pil_error(self):
        """Test missing PIL."""
        import builtins

        real_import = builtins.__import__

        def my_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "PIL" and "Image" in fromlist:
                raise ModuleNotFoundError(name="PIL")
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = my_import

        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

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
                "--convert-jpg",
            ],
        )

        print_result_exception(result)
        assert result.exit_code == 2

    def test_convert_heic_module_pyheif_error(self):
        """Test missing pyheif."""

        import builtins
        real_import = builtins.__import__

        def my_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "pyheif" and "read" in fromlist:
                raise ModuleNotFoundError(name="pyheif")
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = my_import

        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

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
                "--convert-jpg",
            ],
        )

        print_result_exception(result)
        assert result.exit_code == 2
