from unittest import TestCase
import os
import shutil
import json
import mock
import pytest
from vcr import VCR
from click.testing import CliRunner
from icloudpd.base import main
from tests.helpers import path_from_project_root, print_result_exception, recreate_path
import inspect
import glob

vcr = VCR(decode_compressed_response=True)

class ListingRecentPhotosTestCase(TestCase):

    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")
        self.vcr_path = os.path.join(self.root_path, "vcr_cassettes")

    def test_listing_recent_photos(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)

        # Note - This test uses the same cassette as test_download_photos.py
        with vcr.use_cassette(os.path.join(self.vcr_path, "listing_photos.yml")):
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
                    "--only-print-filenames",
                    "--no-progress-bar",
                    "--threads-num",
                    1,
                    "-d",
                    data_dir,
                    "--cookie-directory",
                    cookie_dir,
                ],
            )
            print_result_exception(result)
            filenames = result.output.splitlines()

            self.assertEqual(len(filenames), 8)
            self.assertIn(
                os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409.JPG")), filenames[0]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/07/31/IMG_7409.MOV")), filenames[1]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7408.JPG")), filenames[2]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7408.MOV")), filenames[3]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7407.JPG")), filenames[4]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7407.MOV")), filenames[5]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7405.MOV")), filenames[6]
            )
            self.assertEqual(
                os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7404.MOV")), filenames[7]
            )

            assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 0

    def test_listing_photos_does_not_create_folders(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)

        # make sure the directory does not exist yet.
        # Should only be created after download, not after just --print-filenames
        self.assertFalse(os.path.exists(os.path.join(data_dir, os.path.normpath("2018/07/31"))))

        # Note - This test uses the same cassette as test_download_photos.py
        with vcr.use_cassette(os.path.join(self.vcr_path, "listing_photos.yml")):
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
                    "--only-print-filenames",
                    "--no-progress-bar",
                    "--threads-num",
                    1,
                    "-d",
                    data_dir,
                    "--cookie-directory",
                    cookie_dir,
                ],
            )
            print_result_exception(result)
            # make sure the directory still does not exist.
            # Should only be created after download, not after just --print-filenames
            self.assertFalse(
                os.path.exists(os.path.join(data_dir, os.path.normpath("2018/07/31"))))

            assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 0

    def test_listing_recent_photos_with_missing_filenameEnc(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)

        # Note - This test uses the same cassette as test_download_photos.py
        with vcr.use_cassette(os.path.join(self.vcr_path, "listing_photos_missing_filenameEnc.yml")):
            with mock.patch("icloudpd.base.open", create=True) as mock_open:
                with mock.patch.object(json, "dump") as mock_json:
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
                            "--only-print-filenames",
                            "--no-progress-bar",
                            "--threads-num",
                            1,
                            "-d",
                            data_dir,
                            "--cookie-directory",
                            cookie_dir,
                        ],
                    )
                    print_result_exception(result)

                    self.assertEqual.__self__.maxDiff = None

                    filenames = result.output.splitlines()

                    # self.assertEqual(len(filenames), 5)
                    self.assertEqual(
                        os.path.join(data_dir, os.path.normpath("2018/07/31/AY6c_BsE0jja.JPG")),
                        filenames[0]
                    )
                    self.assertEqual(
                        os.path.join(data_dir, os.path.normpath("2018/07/31/AY6c_BsE0jja.MOV")),
                        filenames[1]
                    )
                    self.assertEqual(
                        os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7408.JPG")),
                        filenames[2]
                    )
                    self.assertEqual(
                        os.path.join(data_dir, os.path.normpath("2018/07/30/IMG_7408.MOV")),
                        filenames[3]
                    )
                    self.assertEqual(
                        os.path.join(data_dir, os.path.normpath("2018/07/30/AZ_wAGT9P6jh.JPG")),
                        filenames[4]
                    )
                    assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 0

    # This was used to solve the missing filenameEnc error. I found
    # another case where it might crash. (Maybe Apple changes the downloadURL key)
    def test_listing_recent_photos_with_missing_downloadURL(self):
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)

        # Note - This test uses the same cassette as test_download_photos.py
        with vcr.use_cassette(os.path.join(self.vcr_path, "listing_photos_missing_downloadUrl.yml")):
            with mock.patch("icloudpd.base.open", create=True) as mock_open:
                with mock.patch.object(json, "dump") as mock_json:
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
                            "--only-print-filenames",
                            "--no-progress-bar",
                            "--threads-num",
                            1,
                            "-d",
                            data_dir,
                            "--cookie-directory",
                            cookie_dir,
                        ],
                    )
                    print_result_exception(result)

                    self.assertEqual.__self__.maxDiff = None
                    self.assertEqual("""\
KeyError: 'downloadURL' attribute was not found in the photo fields.
icloudpd has saved the photo record to: ./icloudpd-photo-error.json
Please create a Gist with the contents of this file: https://gist.github.com
Then create an issue on GitHub: https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues
Include a link to the Gist in your issue, so that we can see what went wrong.

""" , result.output)
                    mock_open.assert_called_once_with(file='icloudpd-photo-error.json', mode='w', encoding='utf8')
                    # Multiple JSON "dumps" occur with the new pyicloud 1.0.0 implementation
                    # mock_json.assert_called_once()
                    # Check a few keys in the dict
                    first_arg = mock_json.call_args_list[8][0][0]
                    self.assertEqual(
                        first_arg['master_record']['recordName'],
                        'AY6c+BsE0jjaXx9tmVGJM1D2VcEO')
                    self.assertEqual(
                        first_arg['master_record']['fields']['resVidSmallHeight']['value'],
                        581)
                    self.assertEqual(
                        first_arg['asset_record']['recordName'],
                        'F2A23C38-0020-42FE-A273-2923ADE3CAED')
                    self.assertEqual(
                        first_arg['asset_record']['fields']['assetDate']['value'],
                        1533021744816)
                    assert result.exit_code == 0

        files_in_result = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)

        assert sum(1 for _ in files_in_result) == 0
