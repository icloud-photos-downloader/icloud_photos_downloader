from unittest import TestCase
from vcr import VCR
import os
import shutil
import pytest
import mock
import datetime
from click.testing import CliRunner
from pyicloud_ipd.services.photos import PhotoAsset
from icloudpd.base import main
from tests.helpers.print_result_exception import print_result_exception
import inspect
import glob

vcr = VCR(decode_compressed_response=True, record_mode="new_episodes")


class AutodeletePhotosTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    def test_autodelete_invalid_creation_date(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        files = [
            "2018/01/01/IMG_3589.JPG"
        ]
        
        with mock.patch.object(PhotoAsset, "created", new_callable=mock.PropertyMock) as dt_mock:
            # Can't mock `astimezone` because it's a readonly property, so have to
            # create a new class that inherits from datetime.datetime
            class NewDateTime(datetime.datetime):
                def astimezone(self, tz=None):
                    raise ValueError('Invalid date')
            dt_mock.return_value = NewDateTime(2018,1,1,0,0,0)

            with vcr.use_cassette("tests/vcr_cassettes/download_autodelete_photos.yml"):
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
                        base_dir,
                    ],
                )

                self.assertIn("DEBUG    Looking up all photos and videos from album All Photos...", self._caplog.text)
                self.assertIn(
                    f"INFO     Downloading the first original photo or video to {base_dir} ...",
                    self._caplog.text,
                )
                self.assertIn(
                    f"ERROR    Could not convert photo created date to local timezone (2018-01-01 00:00:00)",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     Downloading {os.path.join(base_dir, os.path.normpath('2018/01/01/IMG_3589.JPG'))}",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     Deleting IMG_3589.JPG",
                    self._caplog.text,
                )
                self.assertIn(
                    "INFO     All photos have been downloaded!", self._caplog.text
                )

                # check files
                for file_name in files:
                    assert os.path.exists(os.path.join(base_dir, file_name)), f"{file_name} expected, but missing"

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
                        base_dir,
                    ],
                )
                print_result_exception(result)

                self.assertIn("DEBUG    Looking up all photos and videos from album All Photos...", self._caplog.text)
                self.assertIn(
                    f"INFO     Downloading 0 original photos and videos to {base_dir} ...",
                    self._caplog.text,
                )
                self.assertIn(
                    f"INFO     All photos have been downloaded!", self._caplog.text
                )
                self.assertIn(
                    f"INFO     Deleting any files found in 'Recently Deleted'...",
                    self._caplog.text,
                )

                self.assertIn(
                    f"INFO     Deleting {os.path.join(base_dir, os.path.normpath('2018/01/01/IMG_3589.JPG'))}",
                    self._caplog.text,
                )

                for file_name in files:
                    assert not os.path.exists(
                        os.path.join(base_dir, file_name)), f"{file_name} not expected, but present"

    def test_download_autodelete_photos(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        files = [
            "2023/06/06/IMG_3589.JPG"
        ]
        
        with vcr.use_cassette("tests/vcr_cassettes/download_autodelete_photos.yml"):
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
                    base_dir,
                ],
            )

            self.assertIn("DEBUG    Looking up all photos and videos from album All Photos...", self._caplog.text)
            self.assertIn(
                f"INFO     Downloading the first original photo or video to {base_dir} ...",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Downloading {os.path.join(base_dir, os.path.normpath('2023/06/06/IMG_3589.JPG'))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Deleting IMG_3589.JPG",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     All photos have been downloaded!", self._caplog.text
            )
            
            #check files
            for file_name in files:
                assert os.path.exists(os.path.join(base_dir, file_name)), f"{file_name} expected, but missing"

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
                    base_dir,
                ],
            )

            self.assertIn("DEBUG    Looking up all photos and videos from album All Photos...", self._caplog.text)
            self.assertIn(
                f"INFO     Downloading 0 original photos and videos to {base_dir} ...",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     All photos have been downloaded!", self._caplog.text
            )
            self.assertIn(
                f"INFO     Deleting any files found in 'Recently Deleted'...",
                self._caplog.text,
            )

            self.assertIn(
                f"INFO     Deleting {os.path.join(base_dir, os.path.normpath('2023/06/06/IMG_3589.JPG'))}",
                self._caplog.text,
            )

            for file_name in files:
                assert not os.path.exists(os.path.join(base_dir, file_name)), f"{file_name} not expected, but present"

    def test_autodelete_photos(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        files_to_create = [
            "2018/07/30/IMG_7407.JPG",
            "2018/07/30/IMG_7407-original.JPG"
        ]
        files_to_delete = [
            "2018/07/30/IMG_7406.MOV",
            "2018/07/26/IMG_7383.PNG",
            "2018/07/11/IMG_7190.JPG",
            "2018/07/11/IMG_7190-medium.JPG"
        ]

        os.makedirs(os.path.join(base_dir, "2018/07/30/"))
        os.makedirs(os.path.join(base_dir, "2018/07/26/"))
        os.makedirs(os.path.join(base_dir, "2018/07/11/"))
    
        # create some empty files 
        for file_name in files_to_create + files_to_delete:
            open(os.path.join(base_dir, file_name), "a").close()

        with vcr.use_cassette("tests/vcr_cassettes/autodelete_photos.yml"):
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
                    base_dir,
                ],
            )
            self.assertIn("DEBUG    Looking up all photos from album All Photos...", self._caplog.text)
            self.assertIn(
                f"INFO     Downloading 0 original photos to {base_dir} ...",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     All photos have been downloaded!", self._caplog.text
            )
            self.assertIn(
                "INFO     Deleting any files found in 'Recently Deleted'...",
                self._caplog.text,
            )

            self.assertIn(
                "INFO     Deleting any files found in 'Recently Deleted'...",
                self._caplog.text,
            )

            self.assertIn(
                f"INFO     Deleting {os.path.join(base_dir, os.path.normpath('2018/07/30/IMG_7406.MOV'))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Deleting {os.path.join(base_dir, os.path.normpath('2018/07/26/IMG_7383.PNG'))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Deleting {os.path.join(base_dir, os.path.normpath('2018/07/11/IMG_7190.JPG'))}",
                self._caplog.text,
            )
            self.assertIn(
                f"INFO     Deleting {os.path.join(base_dir, os.path.normpath('2018/07/11/IMG_7190-medium.JPG'))}",
                self._caplog.text,
            )

            self.assertNotIn("IMG_7407.JPG", self._caplog.text)
            self.assertNotIn("IMG_7407-original.JPG", self._caplog.text)

            assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == len(files_to_create)

        #check files
        for file_name in files_to_create:
            assert os.path.exists(os.path.join(base_dir, file_name)), f"{file_name} expected, but missing"

        for file_name in files_to_delete:
            assert not os.path.exists(os.path.join(base_dir, file_name)), f"{file_name} not expected, but present"            
