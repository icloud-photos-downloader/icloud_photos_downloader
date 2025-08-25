import inspect
import os
import shutil
from typing import Sequence, Tuple
from unittest import TestCase

import pytest

from icloudpd.cli import Config, GlobalConfig, format_help, parse
from icloudpd.mfa_provider import MFAProvider
from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.raw_policy import RawTreatmentPolicy
from pyicloud_ipd.version_size import LivePhotoVersionSize
from tests.helpers import (
    path_from_project_root,
    run_icloudpd_test,
    run_main,
)


class CliTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog: pytest.LogCaptureFixture) -> None:
        self._caplog = caplog
        self.root_path = path_from_project_root(__file__)
        self.fixtures_path = os.path.join(self.root_path, "fixtures")

    def test_cli_help(self) -> None:
        _result = format_help()
        # TODO validate result
        # self.assertEqual("abc", format_help(), "help")

    def test_cli_parser(self) -> None:
        self.assertEqual(
            parse(["--help"]),
            (
                GlobalConfig(
                    help=True,
                    version=False,
                    use_os_locale=False,
                    only_print_filenames=False,
                    log_level="debug",
                    no_progress_bar=False,
                    threads_num=1,
                    domain="com",
                    watch_with_interval=None,
                    password_providers=["parameter", "keyring", "console"],
                    mfa_provider=MFAProvider.CONSOLE,
                ),
                [],
            ),
            "--help",
        )
        self.assertEqual(
            parse(["--mfa-provider", "weBui"]),
            (
                GlobalConfig(
                    help=False,
                    version=False,
                    use_os_locale=False,
                    only_print_filenames=False,
                    log_level="debug",
                    no_progress_bar=False,
                    threads_num=1,
                    domain="com",
                    watch_with_interval=None,
                    password_providers=["parameter", "keyring", "console"],
                    mfa_provider=MFAProvider.WEBUI,
                ),
                [],
            ),
            "--mfa-provider weBui",
        )
        self.assertEqual(
            parse(
                [
                    "--password-provider",
                    "weBui",
                    "--password-provider",
                    "CoNSoLe",
                    "--password-provider",
                    "WeBuI",
                ]
            ),
            (
                GlobalConfig(
                    help=False,
                    version=False,
                    use_os_locale=False,
                    only_print_filenames=False,
                    log_level="debug",
                    no_progress_bar=False,
                    threads_num=1,
                    domain="com",
                    watch_with_interval=None,
                    password_providers=["webui", "console"],
                    mfa_provider=MFAProvider.CONSOLE,
                ),
                [],
            ),
            "password-providers",
        )
        self.assertEqual(
            parse(["--version", "--use-os-locale"]),
            (
                GlobalConfig(
                    help=False,
                    version=True,
                    use_os_locale=True,
                    only_print_filenames=False,
                    log_level="debug",
                    no_progress_bar=False,
                    threads_num=1,
                    domain="com",
                    watch_with_interval=None,
                    password_providers=["parameter", "keyring", "console"],
                    mfa_provider=MFAProvider.CONSOLE,
                ),
                [],
            ),
            "--version --use-os-locale",
        )
        self.assertEqual(
            parse(
                ["--directory", "abc", "--username", "u1", "--username", "u2", "--directory", "def"]
            ),
            (
                GlobalConfig(
                    help=False,
                    version=False,
                    use_os_locale=False,
                    only_print_filenames=False,
                    log_level="debug",
                    no_progress_bar=False,
                    threads_num=1,
                    domain="com",
                    watch_with_interval=None,
                    password_providers=["parameter", "keyring", "console"],
                    mfa_provider=MFAProvider.CONSOLE,
                ),
                [
                    Config(
                        directory="abc",
                        username="u1",
                        auth_only=False,
                        cookie_directory="~/.pyicloud",
                        password=None,
                        sizes=["original"],
                        live_photo_size=LivePhotoVersionSize.ORIGINAL,
                        recent=None,
                        until_found=None,
                        albums=[],
                        list_albums=False,
                        library="PrimarySync",
                        list_libraries=False,
                        skip_videos=False,
                        skip_live_photos=False,
                        xmp_sidecar=False,
                        force_size=False,
                        auto_delete=False,
                        folder_structure="{:%Y/%m/%d}",
                        set_exif_datetime=False,
                        smtp_username=None,
                        smtp_password=None,
                        smtp_host="smtp.gmail.com",
                        smtp_port=587,
                        smtp_no_tls=False,
                        notification_email=None,
                        notification_email_from=None,
                        notification_script=None,
                        delete_after_download=False,
                        keep_icloud_recent_days=None,
                        dry_run=False,
                        keep_unicode_in_filenames=False,
                        live_photo_mov_filename_policy="suffix",
                        align_raw=RawTreatmentPolicy.AS_IS,
                        file_match_policy=FileMatchPolicy.NAME_SIZE_DEDUP_WITH_SUFFIX,
                        skip_created_before=None,
                        skip_created_after=None,
                        skip_photos=False,
                    ),
                    Config(
                        directory="def",
                        auth_only=False,
                        cookie_directory="~/.pyicloud",
                        username="u2",
                        password=None,
                        sizes=["original"],
                        live_photo_size=LivePhotoVersionSize.ORIGINAL,
                        recent=None,
                        until_found=None,
                        albums=[],
                        list_albums=False,
                        library="PrimarySync",
                        list_libraries=False,
                        skip_videos=False,
                        skip_live_photos=False,
                        xmp_sidecar=False,
                        force_size=False,
                        auto_delete=False,
                        folder_structure="{:%Y/%m/%d}",
                        set_exif_datetime=False,
                        smtp_username=None,
                        smtp_password=None,
                        smtp_host="smtp.gmail.com",
                        smtp_port=587,
                        smtp_no_tls=False,
                        notification_email=None,
                        notification_email_from=None,
                        notification_script=None,
                        delete_after_download=False,
                        keep_icloud_recent_days=None,
                        dry_run=False,
                        keep_unicode_in_filenames=False,
                        live_photo_mov_filename_policy="suffix",
                        align_raw=RawTreatmentPolicy.AS_IS,
                        file_match_policy=FileMatchPolicy.NAME_SIZE_DEDUP_WITH_SUFFIX,
                        skip_created_before=None,
                        skip_created_after=None,
                        skip_photos=False,
                    ),
                ],
            ),
            "defaults propagated and overwritten",
        )

    def test_cli(self) -> None:
        result = run_main(["--help"])
        self.assertEqual(result.exit_code, 0, "exit code")

    def test_log_levels(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        parameters: Sequence[Tuple[str, Sequence[str], Sequence[str]]] = [
            ("debug", ["DEBUG", "INFO"], []),
            ("info", ["INFO"], ["DEBUG"]),
            ("error", [], ["DEBUG", "INFO"]),
        ]
        for log_level, expected, not_expected in parameters:
            self._caplog.clear()
            _, result = run_icloudpd_test(
                self.assertEqual,
                self.root_path,
                base_dir,
                "listing_photos.yml",
                [],
                [],
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "0",
                    "--log-level",
                    log_level,
                ],
            )
            self.assertEqual(result.exit_code, 0, "exit code")
            for text in expected:
                self.assertIn(text, self._caplog.text)
            for text in not_expected:
                self.assertNotIn(text, self._caplog.text)

    def test_tqdm(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        _, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos.yml",
            [],
            [],
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "0",
            ],
            additional_env={"FORCE_TQDM": "yes"},
        )
        self.assertEqual(result.exit_code, 0, "exit code")

    def test_unicode_directory(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])

        _, result = run_icloudpd_test(
            self.assertEqual,
            self.root_path,
            base_dir,
            "listing_photos.yml",
            [],
            [],
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "0",
                "--log-level",
                "info",
            ],
        )
        self.assertEqual(result.exit_code, 0, "exit code")

    def test_missing_directory(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        # need path removed
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)

        result = run_main(
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "0",
                "--log-level",
                "info",
                "-d",
                base_dir,
            ],
        )
        self.assertEqual(result.exit_code, 2, "exit code")

        self.assertFalse(os.path.exists(base_dir), f"{base_dir} exists")

    def test_missing_directory_param(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        result = run_main(
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "--recent",
                "0",
                "--log-level",
                "info",
            ],
        )
        self.assertEqual(result.exit_code, 2, "exit code")

        self.assertFalse(os.path.exists(base_dir), f"{base_dir} exists")

    def test_conflict_options_delete_after_download_and_auto_delete(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        result = run_main(
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "-d",
                "/tmp",
                "--delete-after-download",
                "--auto-delete",
            ],
        )
        self.assertEqual(result.exit_code, 2, "exit code")

        self.assertFalse(os.path.exists(base_dir), f"{base_dir} exists")

    def test_conflict_options_delete_after_download_and_keep_icloud_recent_days(self) -> None:
        base_dir = os.path.join(self.fixtures_path, inspect.stack()[0][3])
        result = run_main(
            [
                "--username",
                "jdoe@gmail.com",
                "--password",
                "password1",
                "-d",
                "/tmp",
                "--delete-after-download",
                "--keep-icloud-recent-days",
                "1",
            ],
        )
        self.assertEqual(result.exit_code, 2, "exit code")

        self.assertFalse(os.path.exists(base_dir), f"{base_dir} exists")
