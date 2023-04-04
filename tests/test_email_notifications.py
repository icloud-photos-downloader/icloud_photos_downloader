from unittest import TestCase
from vcr import VCR
from mock import patch
from freezegun import freeze_time
import os
from click.testing import CliRunner
from icloudpd.base import main
import inspect
import shutil

vcr = VCR(decode_compressed_response=True)


class EmailNotificationsTestCase(TestCase):
    @freeze_time("2018-01-01")
    def test_2sa_required_email_notification(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        with vcr.use_cassette("tests/vcr_cassettes/auth_requires_2sa.yml"):
            with patch("smtplib.SMTP") as smtp:
                # Pass fixed client ID via environment variable
                runner = CliRunner(env={
                    "CLIENT_ID": "EC5646DE-9423-11E8-BF21-14109FE0B321"
                })
                result = runner.invoke(
                    main,
                    [
                        "--username",
                        "jdoe@gmail.com",
                        "--password",
                        "password1",
                        "--smtp-username",
                        "jdoe+smtp@gmail.com",
                        "--smtp-password",
                        "password1",
                        "--notification-email",
                        "jdoe+notifications@gmail.com",
                        "-d",
                        base_dir,
                    ],
                )
                print(result.output)
                assert result.exit_code == 1
            smtp_instance = smtp()
            smtp_instance.connect.assert_called_once()
            smtp_instance.starttls.assert_called_once()
            smtp_instance.login.assert_called_once_with(
                "jdoe+smtp@gmail.com", "password1"
            )
            smtp_instance.sendmail.assert_called_once_with(
                "iCloud Photos Downloader <jdoe+smtp@gmail.com>",
                "jdoe+notifications@gmail.com",
                "From: iCloud Photos Downloader <jdoe+smtp@gmail.com>\n"
                "To: jdoe+notifications@gmail.com\n"
                "Subject: icloud_photos_downloader: Two step authentication has expired\n"
                "Date: 01/01/2018 00:00\n\nHello,\n\n"
                "Two-step authentication has expired for the icloud_photos_downloader script.\n"
                "Please log in to your server and run the script manually to update two-step "
                "authentication.",
            )

    @freeze_time("2018-01-01")
    def test_2sa_notification_without_smtp_login_and_tls(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        with vcr.use_cassette("tests/vcr_cassettes/auth_requires_2sa.yml"):
            with patch("smtplib.SMTP") as smtp:
                # Pass fixed client ID via environment variable
                runner = CliRunner(env={
                    "CLIENT_ID": "EC5646DE-9423-11E8-BF21-14109FE0B321"
                })
                result = runner.invoke(
                    main,
                    [
                        "--username",
                        "jdoe@gmail.com",
                        "--password",
                        "password1",
                        "--smtp-no-tls",
                        "--notification-email",
                        "jdoe+notifications@gmail.com",
                        "-d",
                        base_dir,
                    ],
                )
                print(result.output)
                assert result.exit_code == 1
            smtp_instance = smtp()
            smtp_instance.connect.assert_called_once()
            smtp_instance.starttls.assert_not_called()
            smtp_instance.login.assert_not_called()
            smtp_instance.sendmail.assert_called_once_with(
                "jdoe+notifications@gmail.com",
                "jdoe+notifications@gmail.com",
                "From: jdoe+notifications@gmail.com\n"
                "To: jdoe+notifications@gmail.com\n"
                "Subject: icloud_photos_downloader: Two step authentication has expired\n"
                "Date: 01/01/2018 00:00\n\nHello,\n\n"
                "Two-step authentication has expired for the icloud_photos_downloader script.\n"
                "Please log in to your server and run the script manually to update two-step "
                "authentication.",
            )

    @freeze_time("2018-01-01")
    def test_2sa_required_notification_script(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        with vcr.use_cassette("tests/vcr_cassettes/auth_requires_2sa.yml"):
            with patch("subprocess.call") as subprocess_patched:
                # Pass fixed client ID via environment variable
                runner = CliRunner(env={
                    "CLIENT_ID": "EC5646DE-9423-11E8-BF21-14109FE0B321"
                })
                result = runner.invoke(
                    main,
                    [
                        "--username",
                        "jdoe@gmail.com",
                        "--password",
                        "password1",
                        "--notification-script",
                        "./test_script.sh",
                        "-d",
                        base_dir,
                    ],
                )
                print(result.output)
                assert result.exit_code == 1
            subprocess_patched.assert_called_once_with(["./test_script.sh"])

    @freeze_time("2018-01-01")
    def test_2sa_required_email_notification_from(self):
        base_dir = os.path.normpath(f"tests/fixtures/Photos/{inspect.stack()[0][3]}")
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        with vcr.use_cassette("tests/vcr_cassettes/auth_requires_2sa.yml"):
            with patch("smtplib.SMTP") as smtp:
                # Pass fixed client ID via environment variable
                runner = CliRunner(env={
                    "CLIENT_ID": "EC5646DE-9423-11E8-BF21-14109FE0B321"
                })
                result = runner.invoke(
                    main,
                    [
                        "--username",
                        "jdoe@gmail.com",
                        "--password",
                        "password1",
                        "--smtp-username",
                        "jdoe+smtp@gmail.com",
                        "--smtp-password",
                        "password1",
                        "--notification-email",
                        "JD <jdoe+notifications@gmail.com>",
                        "--notification-email-from",
                        "JD <jdoe+notifications+from@gmail.com>",
                        "-d",
                        base_dir,
                    ],
                )
                print(result.output)
                assert result.exit_code == 1
            smtp_instance = smtp()
            smtp_instance.connect.assert_called_once()
            smtp_instance.starttls.assert_called_once()
            smtp_instance.login.assert_called_once_with(
                "jdoe+smtp@gmail.com", "password1"
            )
            smtp_instance.sendmail.assert_called_once_with(
                "JD <jdoe+notifications+from@gmail.com>",
                "JD <jdoe+notifications@gmail.com>",
                "From: JD <jdoe+notifications+from@gmail.com>\n"
                "To: JD <jdoe+notifications@gmail.com>\n"
                "Subject: icloud_photos_downloader: Two step authentication has expired\n"
                "Date: 01/01/2018 00:00\n\nHello,\n\n"
                "Two-step authentication has expired for the icloud_photos_downloader script.\n"
                "Please log in to your server and run the script manually to update two-step "
                "authentication.",
            )

