from unittest import TestCase
from vcr import VCR
from mock import patch
import smtplib
import os
import click
from click.testing import CliRunner
from icloudpd.base import main

import pyicloud_ipd

vcr = VCR(decode_compressed_response=True)

class EmailNotificationsTestCase(TestCase):
    def test_2sa_required_email_notification(self):
        with vcr.use_cassette('tests/vcr_cassettes/auth_requires_2sa.yml'):
            with patch('smtplib.SMTP') as smtp:
                # Pass fixed client ID via environment variable
                os.environ['CLIENT_ID'] = 'EC5646DE-9423-11E8-BF21-14109FE0B321'
                runner = CliRunner()
                result = runner.invoke(main, [
                    '--username', 'jdoe@gmail.com',
                    '--password', 'password1',
                    '--smtp-username', 'jdoe+smtp@gmail.com',
                    '--smtp-password', 'password1',
                    '--notification-email', 'jdoe+notifications@gmail.com',
                    'tests/fixtures/Photos'
                ])
                print(result.output)
                assert result.exit_code == 1
            smtp_instance = smtp()
            smtp_instance.connect.assert_called_once()
            smtp_instance.starttls.assert_called_once()
            smtp_instance.sendmail.assert_called_once_with(
                u'jdoe+smtp@gmail.com', u'jdoe+notifications@gmail.com',
                u'From: iCloud Photos Downloader <jdoe+smtp@gmail.com>\nTo: jdoe+notifications@gmail.com\nSubject: icloud_photos_downloader: Two step authentication has expired\nDate: 31/07/2018 06:27\n\nHello,\n\nTwo-step authentication has expired for the icloud_photos_downloader script.\nPlease log in to your server and run the script manually to update two-step authentication.')
