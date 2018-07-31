from unittest import TestCase
from vcr import VCR
import os
import shutil
import click
import pytest
import mock
from click.testing import CliRunner
import piexif
from icloudpd.base import main
import icloudpd.exif_datetime

vcr = VCR(decode_compressed_response=True)

class DownloadPhotoTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    def test_download_photos(self):
        shutil.rmtree('tests/fixtures/Photos')
        os.makedirs('tests/fixtures/Photos')

        with vcr.use_cassette('tests/vcr_cassettes/listing_photos.yml'):
            # Pass fixed client ID via environment variable
            os.environ['CLIENT_ID'] = 'DE309E26-942E-11E8-92F5-14109FE0B321'
            runner = CliRunner()
            result = runner.invoke(main, [
                '--username', 'jdoe@gmail.com',
                '--password', 'password1',
                '--recent', '1',
                '--skip-videos',
                '--set-exif-datetime',
                '--no-progress-bar',
                'tests/fixtures/Photos'
            ])
            self.assertIn(
                'DEBUG    Looking up all photos...',
                self._caplog.text)
            self.assertIn(
                'INFO     Downloading 1 original photos to tests/fixtures/Photos/ ...',
                self._caplog.text)
            self.assertIn(
                'INFO     Downloading tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG',
                self._caplog.text)
            self.assertIn(
                'INFO     All photos have been downloaded!',
                self._caplog.text)
            assert result.exit_code == 0

    def test_download_photos_and_set_exif(self):
        shutil.rmtree('tests/fixtures/Photos')
        os.makedirs('tests/fixtures/Photos')
        with mock.patch.object(icloudpd.exif_datetime, 'get_photo_exif') as get_exif_patched:
            get_exif_patched.return_value = False
            with vcr.use_cassette('tests/vcr_cassettes/listing_photos.yml'):
                # Pass fixed client ID via environment variable
                os.environ['CLIENT_ID'] = 'DE309E26-942E-11E8-92F5-14109FE0B321'
                runner = CliRunner()
                result = runner.invoke(main, [
                    '--username', 'jdoe@gmail.com',
                    '--password', 'password1',
                    '--recent', '1',
                    '--skip-videos',
                    '--set-exif-datetime',
                    '--no-progress-bar',
                    'tests/fixtures/Photos'
                ])
                self.assertIn(
                    'DEBUG    Looking up all photos...',
                    self._caplog.text)
                self.assertIn(
                    'INFO     Downloading 1 original photos to tests/fixtures/Photos/ ...',
                    self._caplog.text)
                self.assertIn(
                    'INFO     Downloading tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG',
                    self._caplog.text)
                self.assertIn(
                    'DEBUG    Setting EXIF timestamp for tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG: 2018:07:31 14:22:24',
                    self._caplog.text)
                self.assertIn(
                    'INFO     All photos have been downloaded!',
                    self._caplog.text)
                assert result.exit_code == 0

    def test_download_photos_and_exif_exceptions(self):
        shutil.rmtree('tests/fixtures/Photos')
        os.makedirs('tests/fixtures/Photos')

        with mock.patch.object(piexif, 'load') as piexif_patched:
            piexif_patched.side_effect = Exception

            with vcr.use_cassette('tests/vcr_cassettes/listing_photos.yml'):
                # Pass fixed client ID via environment variable
                os.environ['CLIENT_ID'] = 'DE309E26-942E-11E8-92F5-14109FE0B321'
                runner = CliRunner()
                result = runner.invoke(main, [
                    '--username', 'jdoe@gmail.com',
                    '--password', 'password1',
                    '--recent', '1',
                    '--skip-videos',
                    '--set-exif-datetime',
                    '--no-progress-bar',
                    'tests/fixtures/Photos'
                ])
                self.assertIn(
                    'DEBUG    Looking up all photos...',
                    self._caplog.text)
                self.assertIn(
                    'INFO     Downloading 1 original photos to tests/fixtures/Photos/ ...',
                    self._caplog.text)
                self.assertIn(
                    'INFO     Downloading tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG',
                    self._caplog.text)
                self.assertIn(
                    'DEBUG    Error fetching EXIF data for tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG',
                    self._caplog.text)
                self.assertIn(
                    'DEBUG    Error setting EXIF data for tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG',
                    self._caplog.text)
                self.assertIn(
                    'INFO     All photos have been downloaded!',
                    self._caplog.text)
                assert result.exit_code == 0


    def test_skip_existing_downloads(self):
        shutil.rmtree('tests/fixtures/Photos')
        os.makedirs('tests/fixtures/Photos/2018/07/31/')
        shutil.copyfile(
            'tests/fixtures/IMG_7409-original.JPG',
            'tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG')

        with vcr.use_cassette('tests/vcr_cassettes/listing_photos.yml'):
            # Pass fixed client ID via environment variable
            os.environ['CLIENT_ID'] = 'DE309E26-942E-11E8-92F5-14109FE0B321'
            runner = CliRunner()
            result = runner.invoke(main, [
                '--username', 'jdoe@gmail.com',
                '--password', 'password1',
                '--recent', '1',
                '--skip-videos',
                '--no-progress-bar',
                'tests/fixtures/Photos'
            ])
            self.assertIn(
                'DEBUG    Looking up all photos...',
                self._caplog.text)
            self.assertIn(
                'INFO     Downloading 1 original photos to tests/fixtures/Photos/ ...',
                self._caplog.text)
            self.assertIn(
                'INFO     tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG already exists.',
                self._caplog.text)
            self.assertIn(
                'INFO     All photos have been downloaded!',
                self._caplog.text)
            assert result.exit_code == 0

    def test_until_found(self):
        shutil.rmtree('tests/fixtures/Photos')
        os.makedirs('tests/fixtures/Photos/2018/07/31/')
        shutil.copyfile(
            'tests/fixtures/IMG_7409-original.JPG',
            'tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG')

        with vcr.use_cassette('tests/vcr_cassettes/listing_photos.yml'):
            # Pass fixed client ID via environment variable
            os.environ['CLIENT_ID'] = 'DE309E26-942E-11E8-92F5-14109FE0B321'
            runner = CliRunner()
            result = runner.invoke(main, [
                '--username', 'jdoe@gmail.com',
                '--password', 'password1',
                '--until-found', '1',
                '--recent', '1',
                '--skip-videos',
                '--no-progress-bar',
                'tests/fixtures/Photos'
            ])
            self.assertIn(
                'DEBUG    Looking up all photos...',
                self._caplog.text)
            self.assertIn(
                'INFO     Downloading ??? original photos to tests/fixtures/Photos/ ...',
                self._caplog.text)
            self.assertIn(
                'INFO     tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG already exists.',
                self._caplog.text)
            self.assertIn(
                'INFO     Found 1 consecutive previusly downloaded photos. Exiting',
                self._caplog.text)
            assert result.exit_code == 0
