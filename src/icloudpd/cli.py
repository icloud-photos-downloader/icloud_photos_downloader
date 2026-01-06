import argparse
import copy
import datetime
import pathlib
import sys
from itertools import dropwhile
from operator import eq, not_
from typing import Any, Callable, Iterable, Sequence, Tuple

from tzlocal import get_localzone

import foundation
from foundation.core import chain_from_iterable, compose, map_, partial_1_1, skip
from foundation.string_utils import lower
from icloudpd.base import ensure_tzinfo, run_with_configs
from icloudpd.config import GlobalConfig, UserConfig
from icloudpd.log_level import LogLevel
from icloudpd.mfa_provider import MFAProvider
from icloudpd.password_provider import PasswordProvider
from icloudpd.string_helpers import parse_timestamp_or_timedelta, splitlines
from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.live_photo_mov_filename_policy import LivePhotoMovFilenamePolicy
from pyicloud_ipd.raw_policy import RawTreatmentPolicy
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize


def map_align_raw_to_enum(align_raw_str: str) -> RawTreatmentPolicy:
    """Map user-friendly CLI strings to RawTreatmentPolicy enum values."""
    mapping = {
        "as-is": RawTreatmentPolicy.AS_IS,
        "original": RawTreatmentPolicy.AS_ORIGINAL,
        "alternative": RawTreatmentPolicy.AS_ALTERNATIVE,
    }
    return mapping[align_raw_str]


def add_options_for_user(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    cloned = copy.deepcopy(parser)
    cloned.add_argument(
        "-d",
        "--directory",
        metavar="DIRECTORY",
        help="Local directory to use for downloads",
    )
    cloned.add_argument(
        "--auth-only", action="store_true", help="Create/update cookie and session tokens only."
    )
    cloned.add_argument(
        "--cookie-directory",
        help="Directory to store cookies for authentication. Default: %(default)s",
        default="~/.pyicloud",
    )
    cloned.add_argument(
        "--size",
        help="Image size to download. `medium` and `thumb` will always be added as suffixes to filenames, `adjusted` and `alternative` only if conflicting, `original` never. If `adjusted` or `alternative` is specified and missing, then `original` is used. Default: %(default)s",
        choices=["original", "medium", "thumb", "adjusted", "alternative"],
        default=None,
        action="append",
        dest="sizes",
        type=lower,
    )
    cloned.add_argument(
        "--live-photo-size",
        help="Live Photo video size to download. Default: %(default)s",
        choices=["original", "medium", "thumb"],
        default="original",
        action="store",
        type=lower,
    )
    cloned.add_argument(
        "--recent",
        help="Number of recent photos to download (default: download all photos)",
        type=int,
        default=None,
    )
    cloned.add_argument(
        "--until-found",
        help="Download the most recently added photos until we find X number of "
        "previously downloaded consecutive photos (default: download all photos)",
        type=int,
        default=None,
    )
    cloned.add_argument(
        "-a",
        "--album",
        help="Album(s) to download, or the whole collection if not specified",
        action="append",
        default=[],
        dest="albums",
    )
    cloned.add_argument(
        "-l",
        "--list-albums",
        help="List the available albums",
        action="store_true",
    )
    cloned.add_argument(
        "--library",
        help="Library to download. Default: %(default)s",
        default="PrimarySync",
    )
    cloned.add_argument(
        "--list-libraries",
        help="List the available libraries",
        action="store_true",
    )
    cloned.add_argument(
        "--skip-videos",
        help="Don't download any videos (default: download all photos and videos)",
        action="store_true",
    )
    cloned.add_argument(
        "--skip-live-photos",
        help="Don't download any live photos (default: download live photos)",
        action="store_true",
    )
    cloned.add_argument(
        "--xmp-sidecar",
        help="Export additional data as XMP sidecar files (default: don't export)",
        action="store_true",
    )
    cloned.add_argument(
        "--force-size",
        help="Only download the requested size (`adjusted` and `alternative` will not be forced). Default: download original if size is not available",
        action="store_true",
    )
    cloned.add_argument(
        "--auto-delete",
        help='Scan the "Recently Deleted" folder and delete any files found there. '
        + "(If you restore the photo in iCloud, it will be downloaded again.)",
        action="store_true",
    )
    cloned.add_argument(
        "--folder-structure",
        help="Folder structure. If set to `none`, all photos will be placed into the download directory. Default: %(default)s",
        default="{:%Y/%m/%d}",
        type=validate_folder_structure,
    )
    cloned.add_argument(
        "--set-exif-datetime",
        help="Write the DateTimeOriginal EXIF tag from file creation date, if it doesn't exist.",
        action="store_true",
    )

    cloned.add_argument(
        "--smtp-username",
        help="SMTP username for sending email notifications when two-step authentication expires.",
        default=None,
    )
    cloned.add_argument(
        "--smtp-password",
        help="SMTP password for sending email notifications when two-step authentication expires.",
        default=None,
    )
    cloned.add_argument(
        "--smtp-host",
        help="SMTP server host for notifications",
        default="smtp.gmail.com",
    )
    cloned.add_argument(
        "--smtp-port",
        help="SMTP server port. Default: %(default)i",
        type=int,
        default=587,
    )
    cloned.add_argument(
        "--smtp-no-tls",
        help="Disable TLS for SMTP (TLS is required for Gmail)",
        action="store_true",
    )
    cloned.add_argument(
        "--notification-email",
        help="Email address where you would like to receive email notifications. "
        "Default: SMTP username",
        default=None,
        type=str,
    )
    cloned.add_argument(
        "--notification-email-from",
        help="Email address from which you would like to receive email notifications. "
        "Default: SMTP username or notification-email",
        default=None,
        type=str,
    )
    cloned.add_argument(
        "--notification-script",
        type=pathlib.Path,
        help="Path to external script to run when two-factor authentication expires.",
        default=None,
    )
    deprecated_kwargs: dict[str, Any] = {}
    if sys.version_info >= (3, 13):
        deprecated_kwargs["deprecated"] = True
    cloned.add_argument(
        "--delete-after-download",
        help="Delete the photo/video after downloading it."
        + ' The deleted items will appear in "Recently Deleted".'
        + " Therefore, should not be combined with --auto-delete option.",
        action="store_true",
        **deprecated_kwargs,
    )
    cloned.add_argument(
        "--keep-icloud-recent-days",
        help="Keep photos newer than this many days in iCloud. Delete the rest. "
        + "If set to 0, all photos will be deleted from iCloud.",
        type=int,
        default=None,
    )
    cloned.add_argument(
        "--dry-run",
        help="Do not modify the local system or iCloud",
        action="store_true",
        default=False,
    )
    cloned.add_argument(
        "--keep-unicode-in-filenames",
        help="Keep Unicode characters in filenames, or remove all non-ASCII characters",
        action="store_true",
        default=False,
    )
    cloned.add_argument(
        "--live-photo-mov-filename-policy",
        help="How to produce filenames for the video portion of live photos: `suffix` will add _HEVC suffix and `original` will keep the filename as is. Default: %(default)s",
        choices=["suffix", "original"],
        default="suffix",
        type=lower,
    )
    cloned.add_argument(
        "--align-raw",
        help="For photo assets with RAW and JPEG, always treat RAW in the specified size: `original` (RAW+JPEG), `alternative` (JPEG+RAW), or unchanged (as-is). This matters when choosing sizes to download. Default: %(default)s",
        choices=["as-is", "original", "alternative"],
        default="as-is",
        type=lower,
    )
    cloned.add_argument(
        "--file-match-policy",
        help="Policy to identify existing files and de-duplicate. `name-size-dedup-with-suffix` appends file size to de-duplicate. `name-id7` adds asset ID from iCloud to all filenames and does not de-duplicate. Default: %(default)s",
        choices=["name-size-dedup-with-suffix", "name-id7"],
        default="name-size-dedup-with-suffix",
        type=lower,
    )
    cloned.add_argument(
        "--skip-created-before",
        help="Do not process assets created before the specified timestamp in ISO format (2025-01-02) or interval backwards from now (20d = 20 days ago)",
        default=None,
        type=parse_timestamp_or_timedelta_tz_error,
    )
    cloned.add_argument(
        "--skip-created-after",
        help="Do not process assets created after the specified timestamp in ISO format (2025-01-02) or interval backwards from now (20d = 20 days ago)",
        default=None,
        type=parse_timestamp_or_timedelta_tz_error,
    )
    cloned.add_argument(
        "--skip-photos",
        help="Don't download any photos (default: download all photos and videos)",
        action="store_true",
    )
    return cloned


def add_user_option(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    cloned = copy.deepcopy(parser)
    cloned.add_argument(
        "-u",
        "--username",
        help="Apple ID email address. Starts a new configuration group.",
        type=lower,
    )
    cloned.add_argument(
        "-p",
        "--password",
        help="iCloud password for the account if `--password-provider` specifies `parameter`",
        default=None,
        type=str,
    )
    return cloned


def parse_mfa_provider(provider: str) -> MFAProvider:
    provider_map = {
        "console": MFAProvider.CONSOLE,
        "webui": MFAProvider.WEBUI,
        "telegram": MFAProvider.TELEGRAM,
    }

    normalized_provider = lower(provider)
    if normalized_provider in provider_map:
        return provider_map[normalized_provider]
    else:
        raise ValueError(f"Only `console` and `webui` are supported, but `{provider}` was provided")


def add_global_options(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    cloned = copy.deepcopy(parser)
    group = cloned.add_mutually_exclusive_group()
    group.add_argument("--help", "-h", action="store_true", help="Show this information")
    group.add_argument(
        "--version", help="Show the version, commit hash, and timestamp", action="store_true"
    )
    cloned.add_argument(
        "--use-os-locale", help="Use the locale of the host OS to format dates", action="store_true"
    )
    cloned.add_argument(
        "--only-print-filenames",
        help="Only print the filenames of all files that will be downloaded "
        "(not including files that are already downloaded). "
        + "(Does not download or delete any files.)",
        action="store_true",
    )
    cloned.add_argument(
        "--log-level",
        help="Log level. Default: %(default)s",
        choices=["debug", "info", "error"],
        default="debug",
        type=lower,
    )
    cloned.add_argument(
        "--no-progress-bar",
        help="Disable the one-line progress bar and print log messages on separate lines "
        "(progress bar is disabled by default if there is no TTY attached)",
        action="store_true",
    )
    deprecated_kwargs: dict[str, Any] = {}
    if sys.version_info >= (3, 13):
        deprecated_kwargs["deprecated"] = True
    cloned.add_argument(
        "--threads-num",
        help="Number of CPU threads - deprecated & always 1. To be removed in a future version",
        type=int,
        default=1,
        **deprecated_kwargs,
    )
    cloned.add_argument(
        "--domain",
        help="Which iCloud root domain to use. Use 'cn' for mainland China. Default: %(default)s",
        choices=["com", "cn"],
        default="com",
    )
    cloned.add_argument(
        "--watch-with-interval",
        help="Run downloading in an infinite cycle, waiting the specified seconds between runs",
        type=int,
        default=None,
    )
    cloned.add_argument(
        "--telegram-token",
        help="Telegram bot token for notifications and remote control",
        default=None,
        type=str,
    )
    cloned.add_argument(
        "--telegram-chat-id",
        help="Telegram chat ID for notifications and remote control",
        default=None,
        type=str,
    )
    cloned.add_argument(
        "--telegram-polling",
        action="store_true",
        help="Enable Telegram bot polling for remote control commands",
        default=False,
    )
    cloned.add_argument(
        "--telegram-polling-interval",
        help="Interval in seconds for Telegram bot polling (default: 30 seconds)",
        default=30,
        type=int,
    )
    cloned.add_argument(
        "--telegram-webhook-url",
        help="Webhook URL for Telegram bot (push notifications). If not set, uses polling.",
        default=None,
        type=str,
    )
    cloned.add_argument(
        "--telegram-webhook-port",
        help="Port for Telegram webhook server (default: 48080)",
        default=48080,
        type=int,
    )
    cloned.add_argument(
        "--password-provider",
        dest="password_providers",
        help="Specify password providers to check in the given order. Default: [`parameter`, `keyring`, `console`]",
        choices=["console", "keyring", "parameter", "webui"],
        default=None,
        action="append",
        type=lower,
    )
    cloned.add_argument(
        "--mfa-provider",
        help="Specify where to get the MFA code from",
        choices=["console", "webui", "telegram"],
        default="console",
        type=lower,
    )
    return cloned


def log_level(inp: str) -> LogLevel:
    if inp == "debug":
        return LogLevel.DEBUG
    elif inp == "info":
        return LogLevel.INFO
    elif inp == "error":
        return LogLevel.ERROR
    else:
        raise argparse.ArgumentTypeError(f"Unsupported log level {inp}")


def parse_timestamp_or_timedelta_tz_error(
    formatted: str | None,
) -> datetime.datetime | datetime.timedelta | None:
    """Convert ISO dates to datetime with tz and interval in days to time interval. Raise exception in case of error."""
    if formatted is None:
        return None
    result = parse_timestamp_or_timedelta(formatted)
    if result is None:
        raise argparse.ArgumentTypeError("Not an ISO timestamp or time interval in days")
    if isinstance(result, datetime.datetime):
        return ensure_tzinfo(get_localzone(), result)
    return result


def format_help_for_parser_(parser: argparse.ArgumentParser) -> str:
    return parser.format_help()


def format_help() -> str:
    # create fake parser and return it's help
    pre_options_predicate: Callable[[str], bool] = compose(not_, partial_1_1(eq, "options:"))
    skip_to_options_header: Callable[[Iterable[str]], Iterable[str]] = partial_1_1(
        dropwhile, pre_options_predicate
    )
    skip_to_options = compose(partial_1_1(skip, 1), skip_to_options_header)

    help_in_lines = compose(splitlines, format_help_for_parser_)

    extract_option_lines = compose(skip_to_options, help_in_lines)

    dummy_parser = argparse.ArgumentParser(exit_on_error=False, add_help=False, allow_abbrev=False)

    global_help = compose(extract_option_lines, add_global_options)(dummy_parser)

    default_help = compose(extract_option_lines, add_options_for_user)(dummy_parser)

    user_help = compose(extract_option_lines, add_user_option)(dummy_parser)

    all_help = chain_from_iterable(
        [
            ["usage: icloudpd [GLOBAL] [COMMON] [<USER> [COMMON] <USER> [COMMON] ...]", ""],
            ["GLOBAL options. Applied for all user settings."],
            global_help,
            [
                "",
                "COMMON options. If specified before the first username, then used as defaults for settings for all users.",
            ],
            default_help,
            ["", "USER options. Can be specified for setting user configuration only."],
            user_help,
        ]
    )

    return "\n".join(all_help)


def map_to_config(user_ns: argparse.Namespace) -> UserConfig:
    return UserConfig(
        username=user_ns.username,
        password=user_ns.password,
        directory=user_ns.directory,
        auth_only=user_ns.auth_only,
        cookie_directory=user_ns.cookie_directory,
        sizes=list(
            map_(AssetVersionSize, foundation.unique_sequence(user_ns.sizes or ["original"]))
        ),
        live_photo_size=LivePhotoVersionSize(user_ns.live_photo_size),
        recent=user_ns.recent,
        until_found=user_ns.until_found,
        albums=user_ns.albums,
        list_albums=user_ns.list_albums,
        library=user_ns.library,
        list_libraries=user_ns.list_libraries,
        skip_videos=user_ns.skip_videos,
        skip_live_photos=user_ns.skip_live_photos,
        xmp_sidecar=user_ns.xmp_sidecar,
        force_size=user_ns.force_size,
        auto_delete=user_ns.auto_delete,
        folder_structure=user_ns.folder_structure,
        set_exif_datetime=user_ns.set_exif_datetime,
        smtp_username=user_ns.smtp_username,
        smtp_password=user_ns.smtp_password,
        smtp_host=user_ns.smtp_host,
        smtp_port=user_ns.smtp_port,
        smtp_no_tls=user_ns.smtp_no_tls,
        notification_email=user_ns.notification_email,
        notification_email_from=user_ns.notification_email_from,
        notification_script=user_ns.notification_script,
        delete_after_download=user_ns.delete_after_download,
        keep_icloud_recent_days=user_ns.keep_icloud_recent_days,
        dry_run=user_ns.dry_run,
        keep_unicode_in_filenames=user_ns.keep_unicode_in_filenames,
        live_photo_mov_filename_policy=LivePhotoMovFilenamePolicy(
            user_ns.live_photo_mov_filename_policy
        ),
        align_raw=map_align_raw_to_enum(user_ns.align_raw),
        file_match_policy=FileMatchPolicy(user_ns.file_match_policy),
        skip_created_before=user_ns.skip_created_before,
        skip_created_after=user_ns.skip_created_after,
        skip_photos=user_ns.skip_photos,
    )


def parse(args: Sequence[str]) -> Tuple[GlobalConfig, Sequence[UserConfig]]:
    # default --help
    if len(args) == 0:
        args = ["--help"]
    else:
        pass

    # Extract global options first from anywhere in the args using parse_known_args
    global_parser: argparse.ArgumentParser = add_global_options(
        argparse.ArgumentParser(exit_on_error=False, add_help=False, allow_abbrev=False)
    )
    global_ns, non_global_args = global_parser.parse_known_args(args)

    # Now split the remaining non-global args by username boundaries
    splitted_args = foundation.split_with_alternatives(["-u", "--username"], non_global_args)
    default_args = splitted_args[0]

    default_parser: argparse.ArgumentParser = add_options_for_user(
        argparse.ArgumentParser(exit_on_error=False, add_help=False, allow_abbrev=False)
    )

    default_ns = default_parser.parse_args(default_args)

    user_parser: argparse.ArgumentParser = add_user_option(
        add_options_for_user(
            argparse.ArgumentParser(exit_on_error=False, add_help=False, allow_abbrev=False)
        )
    )
    user_nses = [
        map_to_config(user_parser.parse_args(user_args, copy.deepcopy(default_ns)))
        for user_args in splitted_args[1:]
    ]

    return (
        GlobalConfig(
            help=global_ns.help,
            version=global_ns.version,
            use_os_locale=global_ns.use_os_locale,
            only_print_filenames=global_ns.only_print_filenames,
            log_level=log_level(global_ns.log_level),
            no_progress_bar=global_ns.no_progress_bar,
            threads_num=global_ns.threads_num,
            domain=global_ns.domain,
            watch_with_interval=global_ns.watch_with_interval,
            password_providers=list(
                map_(
                    PasswordProvider,
                    foundation.unique_sequence(
                        global_ns.password_providers or ["parameter", "keyring", "console"]
                    ),
                )
            ),
            mfa_provider=MFAProvider(global_ns.mfa_provider),
            telegram_token=global_ns.telegram_token,
            telegram_chat_id=global_ns.telegram_chat_id,
            telegram_polling=global_ns.telegram_polling,
            telegram_polling_interval=global_ns.telegram_polling_interval,
            telegram_webhook_url=global_ns.telegram_webhook_url,
            telegram_webhook_port=global_ns.telegram_webhook_port,
        ),
        user_nses,
    )


def cli() -> int:
    try:
        global_ns, user_nses = parse(sys.argv[1:])
    except argparse.ArgumentError as error:
        print(error)
        return 2
    if global_ns.use_os_locale:
        from locale import LC_ALL, setlocale

        setlocale(LC_ALL, "")
    else:
        pass
    if global_ns.help:
        print(format_help())
        return 0
    elif global_ns.version:
        print(foundation.version_info_formatted())
        return 0
    else:
        # check param compatibility
        if [user_ns for user_ns in user_nses if user_ns.skip_videos and user_ns.skip_photos]:
            print(
                "Only one of --skip-videos and --skip-photos can be used at a time for each configuration"
            )
            return 2

        # check required directory param only if not list albums
        elif [
            user_ns
            for user_ns in user_nses
            if not user_ns.list_albums
            and not user_ns.list_libraries
            and not user_ns.directory
            and not user_ns.auth_only
        ]:
            print(
                "--auth-only, --directory, --list-libraries, or --list-albums are required for each configuration"
            )
            return 2

        elif [
            user_ns
            for user_ns in user_nses
            if user_ns.auto_delete and user_ns.delete_after_download
        ]:
            print(
                "--auto-delete and --delete-after-download are mutually exclusive per configuration"
            )
            return 2

        elif [
            user_ns
            for user_ns in user_nses
            if user_ns.keep_icloud_recent_days and user_ns.delete_after_download
        ]:
            print(
                "--keep-icloud-recent-days and --delete-after-download should not be used together in one configuration"
            )
            return 2

        elif global_ns.watch_with_interval and (
            [
                user_ns
                for user_ns in user_nses
                if user_ns.list_albums or user_ns.auth_only or user_ns.list_libraries
            ]
            or global_ns.only_print_filenames
        ):
            print(
                "--watch-with-interval is not compatible with --list-albums, --list-libraries, --only-print-filenames, and --auth-only"
            )
            return 2
        else:
            return run_with_configs(global_ns, user_nses)


def validate_folder_structure(folder_structure: str) -> str:
    if lower(folder_structure) == "none":
        return "none"
    else:
        try:
            folder_structure.format(datetime.datetime.now())
            return folder_structure
        except:  # noqa E722
            raise argparse.ArgumentTypeError(
                f"Format {folder_structure} specified in --folder-structure is incorrect"
            ) from None
