from unittest import TestCase
from vcr import VCR
import os
import shutil
import logging
import click
import pytest
import mock
from click.testing import CliRunner
import piexif
from pyicloud_ipd.services.photos import PhotoAsset
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.exceptions import PyiCloudAPIResponseError
from icloudpd.base import main
import icloudpd.exif_datetime

vcr = VCR(decode_compressed_response=True)

class DownloadPhotoTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    def test_download_photos(self):
        if os.path.exists('tests/fixtures/Photos'):
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
        if os.path.exists('tests/fixtures/Photos'):
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
                # YYYY:MM:DD is the correct format.
                self.assertIn(
                    'DEBUG    Setting EXIF timestamp for tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG: 2018:07:31',
                    self._caplog.text)
                self.assertIn(
                    'INFO     All photos have been downloaded!',
                    self._caplog.text)
                assert result.exit_code == 0

    def test_download_photos_and_exif_exceptions(self):
        if os.path.exists('tests/fixtures/Photos'):
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
        if os.path.exists('tests/fixtures/Photos'):
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
        if os.path.exists('tests/fixtures/Photos'):
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

    def test_handle_io_error(self):
        if os.path.exists('tests/fixtures/Photos'):
            shutil.rmtree('tests/fixtures/Photos')
        os.makedirs('tests/fixtures/Photos')

        with vcr.use_cassette('tests/vcr_cassettes/listing_photos.yml'):
            # Pass fixed client ID via environment variable
            os.environ['CLIENT_ID'] = 'DE309E26-942E-11E8-92F5-14109FE0B321'

            with mock.patch('icloudpd.base.open', create=True) as m:
                # Raise IOError when we try to write to the destination file
                m.side_effect = IOError

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
                    'ERROR    IOError while writing file to '
                    'tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG! '
                    'You might have run out of disk space, or the file might '
                    'be too large for your OS. Skipping this file...',
                    self._caplog.text)
                assert result.exit_code == 0

    def test_handle_session_error(self):
        if os.path.exists('tests/fixtures/Photos'):
            shutil.rmtree('tests/fixtures/Photos')
        os.makedirs('tests/fixtures/Photos')

        with vcr.use_cassette('tests/vcr_cassettes/listing_photos.yml'):
            # Pass fixed client ID via environment variable
            os.environ['CLIENT_ID'] = 'DE309E26-942E-11E8-92F5-14109FE0B321'

            def mock_raise_response_error(arg):
                raise PyiCloudAPIResponseError('Invalid global session', 100)

            with mock.patch.object(PhotoAsset, 'download') as pa:
                pa.side_effect = mock_raise_response_error

                # Let the initial authenticate() call succeed,
                # but do nothing on the second try.
                orig_authenticate = PyiCloudService.authenticate
                def mocked_authenticate(self):
                    if not hasattr(self, 'already_authenticated'):
                        orig_authenticate(self)
                        setattr(self, 'already_authenticated', True)

                with mock.patch.object(PyiCloudService, 'authenticate', new=mocked_authenticate):
                    runner = CliRunner()
                    result = runner.invoke(main, [
                        '--username', 'jdoe@gmail.com',
                        '--password', 'password1',
                        '--recent', '1',
                        '--skip-videos',
                        '--no-progress-bar',
                        'tests/fixtures/Photos'
                    ])
                    msg = 'Session error, re-authenticating...'
                    error_count = 0
                    for i, _ in enumerate(self._caplog.text):
                        if self._caplog.text[i:i + len(msg)] == msg:
                            error_count += 1
                    # Session error msg should be repeated 5 times
                    assert error_count == 5

                    self.assertIn(
                        'INFO     Could not download IMG_7409.JPG! Please try again later.',
                        self._caplog.text)
                    assert result.exit_code == 0
