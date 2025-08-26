import datetime
import inspect
import os
import shutil
import zoneinfo
from argparse import ArgumentError
from typing import Sequence, Tuple
from unittest import TestCase

import pytest

from icloudpd.cli import Config, GlobalConfig, format_help, parse
from icloudpd.mfa_provider import MFAProvider
from icloudpd.password_provider import PasswordProvider
from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.live_photo_mov_filename_policy import LivePhotoMovFilenamePolicy
from pyicloud_ipd.raw_policy import RawTreatmentPolicy
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize
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
        result = format_help()
        self.assertEqual(
            """\
usage: icloudpd [GLOBAL] [COMMON] [<USER> [COMMON] <USER> [COMMON] ...]

GLOBAL options. Applied for all user settings.
  --help, -h            Show this info
  --version             Show the version, commit hash and timestamp
  --use-os-locale       Use locale of the host OS to format dates
  --only-print-filenames
                        Only prints the filenames of all files that will be downloaded (not including files that are already downloaded.)(Does not download or delete any files.)
  --log-level {debug,info,error}
                        Log level. Default: debug
  --no-progress-bar     Disables the one-line progress bar and prints log messages on separate lines (Progress bar is disabled by default if there is no tty attached)
  --threads-num THREADS_NUM
                        Number of cpu threads - deprecated & always 1. To be removed in future version
  --domain {com,cn}     What iCloud root domain to use. Use 'cn' for mainland China. Default: com
  --watch-with-interval WATCH_WITH_INTERVAL
                        Run downloading in a infinite cycle, waiting specified seconds between runs
  --password-provider {console,keyring,parameter,webui}
                        Specifies passwords provider to check in the given order. Default: [`parameter`, `keyring`, `console`]
  --mfa-provider {console,webui}
                        Specified where to get MFA code from

COMMON options. If specified before first username, then used as default for settings for all users.
  -d, --directory DIRECTORY
  --auth-only           Create/Update cookie and session tokens only.
  --cookie-directory COOKIE_DIRECTORY
                        Directory to store cookies for authentication. Default: ~/.pyicloud
  --size {original,medium,thumb,adjusted,alternative}
                        Image size to download. `medium` and `thumb` will always be added as suffixes to filenames, `adjusted` and `alternative` only if conflicting, `original` - never. If
                        `adjusted` or `alternative` specified and is missing, then `original` is used. Default: None
  --live-photo-size {original,medium,thumb}
                        Live Photo video size to download. Default: original
  --recent RECENT       Number of recent photos to download (default: download all photos)
  --until-found UNTIL_FOUND
                        Download most recently added photos until we find x number of previously downloaded consecutive photos (default: download all photos)
  -a, --album ALBUMS    Album(s) to download or whole collection if not specified
  -l, --list-albums     Lists the available albums
  --library LIBRARY     Library to download. Default: PrimarySync
  --list-libraries      Lists the available libraries
  --skip-videos         Don't download any videos (default: Download all photos and videos)
  --skip-live-photos    Don't download any live photos (default: Download live photos)
  --xmp-sidecar         Export additional data as XMP sidecar files (default: don't export)
  --force-size          Only download the requested size (`adjusted` and `alternate` will not be forced). Default: download original if size is not available
  --auto-delete         Scans the "Recently Deleted" folder and deletes any files found in there. (If you restore the photo in iCloud, it will be downloaded again.)
  --folder-structure FOLDER_STRUCTURE
                        Folder structure. If set to `none` all photos will just be placed into the download directory. Default: {:%Y/%m/%d}
  --set-exif-datetime   Write the DateTimeOriginal exif tag from file creation date, if it doesn't exist.
  --smtp-username SMTP_USERNAME
                        SMTP username, for sending email notifications when two-step authentication expires.
  --smtp-password SMTP_PASSWORD
                        SMTP password, for sending email notifications when two-step authentication expires.
  --smtp-host SMTP_HOST
                        SMTP server host for notification
  --smtp-port SMTP_PORT
                        SMTP server port. Default: 587
  --smtp-no-tls         Pass this flag to disable TLS for SMTP (TLS is required for Gmail)
  --notification-email NOTIFICATION_EMAIL
                        Email address where you would like to receive email notifications. Default: SMTP username
  --notification-email-from NOTIFICATION_EMAIL_FROM
                        Email address from which you would like to receive email notifications. Default: SMTP username or notification-email
  --notification-script NOTIFICATION_SCRIPT
                        Path to the external script to run when two factor authentication expires.
  --delete-after-download
                        Delete the photo/video after download it. The deleted items will be appear in the "Recently Deleted". Therefore, should not combine with --auto-delete option.
  --keep-icloud-recent-days KEEP_ICLOUD_RECENT_DAYS
                        Keep photos newer than this many days in iCloud. Deletes the rest. If set to 0, all photos will be deleted from iCloud.
  --dry-run             Do not modify local system or iCloud
  --keep-unicode-in-filenames
                        Keep unicode chars in file names or remove non all ascii chars
  --live-photo-mov-filename-policy {suffix,original}
                        How to produce filenames for video portion of live photos: `suffix` will add _HEVC suffix and `original` will keep filename as it is. Default: suffix
  --align-raw {as-is,original,alternative}
                        For photo assets with raw and jpeg, treat raw always in the specified size: `original` (raw+jpeg), `alternative` (jpeg+raw), or unchanged (as-is). It matters when
                        choosing sizes to download. Default: as-is
  --file-match-policy {name-size-dedup-with-suffix,name-id7}
                        Policy to identify existing files and de-duplicate. `name-size-dedup-with-suffix` appends file size to deduplicate. `name-id7` adds asset id from iCloud to all file names
                        and does not de-duplicate. Default: name-size-dedup-with-suffix
  --skip-created-before SKIP_CREATED_BEFORE
                        Do not process assets created before specified timestamp in ISO format (2025-01-02) or interval from now (20d)
  --skip-created-after SKIP_CREATED_AFTER
                        Do not process assets created after specified timestamp in ISO format (2025-01-02) or interval from now (20d)
  --skip-photos         Don't download any photos (default: Download all photos and videos)

USER options. Can be specified for setting user config only.
  -u, --username USERNAME
                        AppleID email address. Starts new configuration group.
  -p, --password PASSWORD
                        iCloud password for the account if `--password-provider` specifies `parameter`""",
            result,
            "help",
        )

    def test_cli_parser(self) -> None:
        self.assertEqual.__self__.maxDiff = None  # type: ignore[attr-defined]
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
                    password_providers=[
                        PasswordProvider.PARAMETER,
                        PasswordProvider.KEYRING,
                        PasswordProvider.CONSOLE,
                    ],
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
                    password_providers=[
                        PasswordProvider.PARAMETER,
                        PasswordProvider.KEYRING,
                        PasswordProvider.CONSOLE,
                    ],
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
                    password_providers=[PasswordProvider.WEBUI, PasswordProvider.CONSOLE],
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
                    password_providers=[
                        PasswordProvider.PARAMETER,
                        PasswordProvider.KEYRING,
                        PasswordProvider.CONSOLE,
                    ],
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
                    password_providers=[
                        PasswordProvider.PARAMETER,
                        PasswordProvider.KEYRING,
                        PasswordProvider.CONSOLE,
                    ],
                    mfa_provider=MFAProvider.CONSOLE,
                ),
                [
                    Config(
                        directory="abc",
                        username="u1",
                        auth_only=False,
                        cookie_directory="~/.pyicloud",
                        password=None,
                        sizes=[AssetVersionSize.ORIGINAL],
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
                        live_photo_mov_filename_policy=LivePhotoMovFilenamePolicy.SUFFIX,
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
                        sizes=[AssetVersionSize.ORIGINAL],
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
                        live_photo_mov_filename_policy=LivePhotoMovFilenamePolicy.SUFFIX,
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
        self.assertEqual(
            parse(
                [
                    "-d",
                    "abc",
                    "--username",
                    "u1",
                    "--skip-created-before",
                    "2025-01-02",
                    "--skip-created-after",
                    "2d",
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
                    password_providers=[
                        PasswordProvider.PARAMETER,
                        PasswordProvider.KEYRING,
                        PasswordProvider.CONSOLE,
                    ],
                    mfa_provider=MFAProvider.CONSOLE,
                ),
                [
                    Config(
                        directory="abc",
                        username="u1",
                        auth_only=False,
                        cookie_directory="~/.pyicloud",
                        password=None,
                        sizes=[AssetVersionSize.ORIGINAL],
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
                        live_photo_mov_filename_policy=LivePhotoMovFilenamePolicy.SUFFIX,
                        align_raw=RawTreatmentPolicy.AS_IS,
                        file_match_policy=FileMatchPolicy.NAME_SIZE_DEDUP_WITH_SUFFIX,
                        skip_created_before=datetime.datetime(
                            year=2025, month=1, day=2, tzinfo=zoneinfo.ZoneInfo(key="Etc/UTC")
                        ),
                        skip_created_after=datetime.timedelta(days=2),
                        skip_photos=False,
                    ),
                ],
            ),
            "valid skip-created parsed",
        )
        with pytest.raises(ArgumentError):
            _ = parse(
                [
                    "-d",
                    "abc",
                    "--username",
                    "u1",
                    "--skip-created-before",
                    "2025-01-33",
                    "--skip-created-after",
                    "2d",
                ]
            )
        with pytest.raises(ArgumentError):
            _ = parse(
                [
                    "-d",
                    "abc",
                    "--username",
                    "u1",
                    "--skip-created-before",
                    "2025-01-02",
                    "--skip-created-after",
                    "2",
                ]
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
