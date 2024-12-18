import inspect
import os
from unittest import TestCase
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from freezegun import freeze_time
from icloudpd.base import main
from vcr import VCR

from tests.helpers import path_from_project_root, recreate_path

vcr = VCR(decode_compressed_response=True, record_mode="none")


class EmailNotificationsTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog: pytest.LogCaptureFixture) -> None:
        self._caplog = caplog
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")
        self.vcr_path = os.path.join(self.root_path, "vcr_cassettes")

    @freeze_time("2018-01-01")
    def test_2sa_required_email_notification(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)

        with vcr.use_cassette(os.path.join(self.vcr_path, "auth_requires_2fa.yml")):
            with patch("smtplib.SMTP") as smtp:
                # Pass fixed client ID via environment variable
                runner = CliRunner(env={"CLIENT_ID": "EC5646DE-9423-11E8-BF21-14109FE0B321"})
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
                        data_dir,
                        "--cookie-directory",
                        cookie_dir,
                    ],
                )
                print(result.output)
                assert result.exit_code == 1
            smtp_instance = smtp()
            smtp_instance.connect.assert_called_once()
            smtp_instance.starttls.assert_called_once()
            smtp_instance.login.assert_called_once_with("jdoe+smtp@gmail.com", "password1")
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
    def test_2sa_notification_without_smtp_login_and_tls(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)

        with vcr.use_cassette(os.path.join(self.vcr_path, "auth_requires_2fa.yml")):
            with patch("smtplib.SMTP") as smtp:
                # Pass fixed client ID via environment variable
                runner = CliRunner(env={"CLIENT_ID": "EC5646DE-9423-11E8-BF21-14109FE0B321"})
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
                        data_dir,
                        "--cookie-directory",
                        cookie_dir,
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
    def test_2sa_required_notification_script(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)

        with vcr.use_cassette(os.path.join(self.vcr_path, "auth_requires_2fa.yml")):
            with patch("subprocess.call") as subprocess_patched:
                # Pass fixed client ID via environment variable
                runner = CliRunner(env={"CLIENT_ID": "EC5646DE-9423-11E8-BF21-14109FE0B321"})
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
                        data_dir,
                        "--cookie-directory",
                        cookie_dir,
                    ],
                )
                print(result.output)
                assert result.exit_code == 1
            subprocess_patched.assert_called_once_with(["./test_script.sh"])

    @freeze_time("2018-01-01")
    def test_2sa_required_email_notification_from(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        cookie_dir = os.path.join(base_dir, "cookie")
        data_dir = os.path.join(base_dir, "data")

        for dir in [base_dir, cookie_dir, data_dir]:
            recreate_path(dir)

        with vcr.use_cassette(os.path.join(self.vcr_path, "auth_requires_2fa.yml")):
            with patch("smtplib.SMTP") as smtp:
                # Pass fixed client ID via environment variable
                runner = CliRunner(env={"CLIENT_ID": "EC5646DE-9423-11E8-BF21-14109FE0B321"})
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
                        data_dir,
                        "--cookie-directory",
                        cookie_dir,
                    ],
                )
                print(result.output)
                assert result.exit_code == 1
            smtp_instance = smtp()
            smtp_instance.connect.assert_called_once()
            smtp_instance.starttls.assert_called_once()
            smtp_instance.login.assert_called_once_with("jdoe+smtp@gmail.com", "password1")
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
