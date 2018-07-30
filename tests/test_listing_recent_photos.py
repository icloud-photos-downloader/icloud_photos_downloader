from unittest import TestCase
from vcr import VCR
import os
import click
from click.testing import CliRunner
from icloudpd.base import main

vcr = VCR(decode_compressed_response=True)

class ListingRecentPhotosTestCase(TestCase):
    def test_cli(self):
        with vcr.use_cassette('tests/vcr_cassettes/listing_photos.yml'):
            # Pass fixed client ID via environment variable
            os.environ['CLIENT_ID'] = 'DE309E26-942E-11E8-92F5-14109FE0B321'
            runner = CliRunner()
            result = runner.invoke(main, [
                '--username', 'jdoe@gmail.com',
                '--password', 'password1',
                '--recent', '5',
                '--only-print-filenames',
                '--no-progress-bar',
                'tests/fixtures/Photos'
            ])
            filenames = result.output.splitlines()
            self.assertEqual(len(filenames), 5)
            self.assertEqual(filenames[0], 'tests/fixtures/Photos/2018/07/30/IMG_7408-original.JPG')
            self.assertEqual(filenames[1], 'tests/fixtures/Photos/2018/07/30/IMG_7407-original.JPG')
            self.assertEqual(filenames[2], 'tests/fixtures/Photos/2018/07/30/IMG_7405-original.MOV')
            self.assertEqual(filenames[3], 'tests/fixtures/Photos/2018/07/30/IMG_7404-original.MOV')
            self.assertEqual(filenames[4], 'tests/fixtures/Photos/2018/07/30/IMG_7403-original.MOV')

            assert result.exit_code == 0
