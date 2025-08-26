import argparse
import copy
import datetime
import pathlib
import sys
from dataclasses import dataclass
from typing import Any, Callable, Container, Iterable, List, Mapping, Sequence, Tuple, TypeVar

from foundation.core import compose, flip, map_, partial_1_1
from icloudpd.base import skip_created_generator
from icloudpd.mfa_provider import MFAProvider
from icloudpd.password_provider import PasswordProvider
from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.live_photo_mov_filename_policy import LivePhotoMovFilenamePolicy
from pyicloud_ipd.raw_policy import RawTreatmentPolicy
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize

_T = TypeVar("_T")
_T2 = TypeVar("_T2")


def split(splitter: Container[_T], inp: Iterable[_T]) -> Sequence[Sequence[_T]]:
    """Breaks incoming sequence into subsequences based on supplied slitter. Splitter is supported as sequence of alternatives.
    >>> split([2, 4], [1, 2, 3, 2, 5, 4, 6])
    [[1], [2, 3], [2, 5], [4, 6]]
    """
    result: List[List[_T]] = [[]]
    for item in inp:
        if item in splitter:
            #  add group
            result.append([])
        else:
            pass
        group_index = len(result) - 1
        result[group_index].append(item)
    return result


def add_options_for_user(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    cloned = copy.deepcopy(parser)
    cloned.add_argument("-d", "--directory")
    cloned.add_argument(
        "--auth-only", action="store_true", help="Create/Update cookie and session tokens only."
    )
    cloned.add_argument(
        "--cookie-directory",
        help="Directory to store cookies for authentication. Default: %(default)s",
        default="~/.pyicloud",
    )
    cloned.add_argument(
        "--size",
        help="Image size to download. `medium` and `thumb` will always be added as suffixes to filenames, `adjusted` and `alternative` only if conflicting, `original` - never. If `adjusted` or `alternative` specified and is missing, then `original` is used. Default: %(default)s",
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
        help="Download most recently added photos until we find x number of "
        "previously downloaded consecutive photos (default: download all photos)",
        type=int,
        default=None,
    )
    cloned.add_argument(
        "-a",
        "--album",
        help="Album(s) to download or whole collection if not specified",
        action="append",
        default=[],
        dest="albums",
    )
    cloned.add_argument(
        "-l",
        "--list-albums",
        help="Lists the available albums",
        action="store_true",
    )
    cloned.add_argument(
        "--library",
        help="Library to download. Default: %(default)s",
        default="PrimarySync",
    )
    cloned.add_argument(
        "--list-libraries",
        help="Lists the available libraries",
        action="store_true",
    )
    cloned.add_argument(
        "--skip-videos",
        help="Don't download any videos (default: Download all photos and videos)",
        action="store_true",
    )
    cloned.add_argument(
        "--skip-live-photos",
        help="Don't download any live photos (default: Download live photos)",
        action="store_true",
    )
    cloned.add_argument(
        "--xmp-sidecar",
        help="Export additional data as XMP sidecar files (default: don't export)",
        action="store_true",
    )
    cloned.add_argument(
        "--force-size",
        help="Only download the requested size (`adjusted` and `alternate` will not be forced). Default: download original if size is not available",
        action="store_true",
    )
    cloned.add_argument(
        "--auto-delete",
        help='Scans the "Recently Deleted" folder and deletes any files found in there. '
        + "(If you restore the photo in iCloud, it will be downloaded again.)",
        action="store_true",
    )
    cloned.add_argument(
        "--folder-structure",
        help="Folder structure. If set to `none` all photos will just be placed into the download directory. Default: %(default)s",
        default="{:%Y/%m/%d}",
        type=str,
    )
    cloned.add_argument(
        "--set-exif-datetime",
        help="Write the DateTimeOriginal exif tag from file creation date, if it doesn't exist.",
        action="store_true",
    )

    cloned.add_argument(
        "--smtp-username",
        help="SMTP username, for sending email notifications when two-step authentication expires.",
        default=None,
    )
    cloned.add_argument(
        "--smtp-password",
        help="SMTP password, for sending email notifications when two-step authentication expires.",
        default=None,
    )
    cloned.add_argument(
        "--smtp-host",
        help="SMTP server host for notification",
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
        help="Pass this flag to disable TLS for SMTP (TLS is required for Gmail)",
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
        help="Path to the external script to run when two factor authentication expires.",
        default=None,
    )
    deprecated_kwargs: dict[str, Any] = {}
    if sys.version_info >= (3, 13):
        deprecated_kwargs["deprecated"] = True
    else:
        pass
    cloned.add_argument(
        "--delete-after-download",
        help="Delete the photo/video after download it."
        + ' The deleted items will be appear in the "Recently Deleted".'
        + " Therefore, should not combine with --auto-delete option.",
        action="store_true",
        **deprecated_kwargs,
    )
    cloned.add_argument(
        "--keep-icloud-recent-days",
        help="Keep photos newer than this many days in iCloud. Deletes the rest. "
        + "If set to 0, all photos will be deleted from iCloud.",
        type=int,
        default=None,
    )
    cloned.add_argument(
        "--dry-run",
        help="Do not modify local system or iCloud",
        action="store_true",
        default=False,
    )
    cloned.add_argument(
        "--keep-unicode-in-filenames",
        help="Keep unicode chars in file names or remove non all ascii chars",
        action="store_true",
        default=False,
    )
    cloned.add_argument(
        "--live-photo-mov-filename-policy",
        help="How to produce filenames for video portion of live photos: `suffix` will add _HEVC suffix and `original` will keep filename as it is. Default: %(default)s",
        choices=["suffix", "original"],
        default="suffix",
        type=lower,
    )
    cloned.add_argument(
        "--align-raw",
        help="For photo assets with raw and jpeg, treat raw always in the specified size: `original` (raw+jpeg), `alternative` (jpeg+raw), or unchanged (as-is). It matters when choosing sizes to download. Default: %(default)s",
        choices=["as-is", "original", "alternative"],
        default="as-is",
        type=lower,
    )
    cloned.add_argument(
        "--file-match-policy",
        help="Policy to identify existing files and de-duplicate. `name-size-dedup-with-suffix` appends file size to deduplicate. `name-id7` adds asset id from iCloud to all file names and does not de-duplicate. Default: %(default)s",
        choices=["name-size-dedup-with-suffix", "name-id7"],
        default="name-size-dedup-with-suffix",
        type=lower,
    )
    cloned.add_argument(
        "--skip-created-before",
        help="Do not process assets created before specified timestamp in ISO format (2025-01-02) or interval from now (20d)",
        default=None,
        type=skip_created_before_generator,
    )
    cloned.add_argument(
        "--skip-created-after",
        help="Do not process assets created after specified timestamp in ISO format (2025-01-02) or interval from now (20d)",
        default=None,
        type=skip_created_after_generator,
    )
    cloned.add_argument(
        "--skip-photos",
        help="Don't download any photos (default: Download all photos and videos)",
        action="store_true",
    )
    return cloned


def add_user_option(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    cloned = copy.deepcopy(parser)
    cloned.add_argument("-u", "--username", help="AppleID email address")
    cloned.add_argument(
        "-p",
        "--password",
        help="iCloud password for the account if `--password-provider` includes `parameter`",
        default=None,
        type=str,
    )
    return cloned


def lower(inp: str) -> str:
    return inp.lower()


def two_tuple(k: _T, v: _T2) -> Tuple[_T, _T2]:
    return (k, v)


def unique(inp: Iterable[_T]) -> Sequence[_T]:
    """Unique values from iterable
    >>> unique(["abc", "def", "abc", "ghi"])
    ['abc', 'def', 'ghi']
    >>> unique([1, 2, 1, 3])
    [1, 2, 3]
    """
    to_kv = partial_1_1(map_, partial_1_1(flip(two_tuple), None))
    to_dict: Callable[[Iterable[_T]], Mapping[_T, None]] = compose(dict, to_kv)
    return list(to_dict(inp).keys())


def parse_mfa_provider(provider: str) -> MFAProvider:
    if provider.lower() == "console":
        return MFAProvider.CONSOLE
    elif provider.lower() == "webui":
        return MFAProvider.WEBUI
    else:
        raise ValueError(f"Only `console` and `webui` are supported, but `{provider}` was supplied")


def add_global_options(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    cloned = copy.deepcopy(parser)
    cloned.add_argument(
        "--use-os-locale", help="Use locale of the host OS to format dates", action="store_true"
    )
    group = cloned.add_mutually_exclusive_group()
    group.add_argument("--help", "-h", "-?", action="store_true")
    group.add_argument(
        "--version", help="Show the version, commit hash and timestamp", action="store_true"
    )
    cloned.add_argument(
        "--only-print-filenames",
        help="Only prints the filenames of all files that will be downloaded "
        "(not including files that are already downloaded.)"
        + "(Does not download or delete any files.)",
        action="store_true",
    )
    cloned.add_argument(
        "--log-level",
        help="Log level. Default: %(default)s",
        choices=["debug", "info", "error"],
        default="debug",
    )
    cloned.add_argument(
        "--no-progress-bar",
        help="Disables the one-line progress bar and prints log messages on separate lines "
        "(Progress bar is disabled by default if there is no tty attached)",
        action="store_true",
    )
    deprecated_kwargs: dict[str, Any] = {}
    if sys.version_info >= (3, 13):
        deprecated_kwargs["deprecated"] = True
    else:
        pass
    cloned.add_argument(
        "--threads-num",
        help="Number of cpu threads - deprecated & always 1. To be removed in future version",
        type=int,
        default=1,
        **deprecated_kwargs,
    )
    cloned.add_argument(
        "--domain",
        help="What iCloud root domain to use. Use 'cn' for mainland China. Default: %(default)s",
        choices=["com", "cn"],
        default="com",
    )
    cloned.add_argument(
        "--watch-with-interval",
        help="Run downloading in a infinite cycle, waiting specified seconds between runs",
        type=int,
        default=None,
    )
    cloned.add_argument(
        "--password-provider",
        dest="password_providers",
        help="Specifies passwords provider to check in the given order. Default: [`parameter`, `keyring`, `console`]",
        choices=["console", "keyring", "parameter", "webui"],
        default=None,
        action="append",
        type=lower,
    )
    cloned.add_argument(
        "--mfa-provider",
        help="Specified where to get MFA code from",
        choices=["console", "webui"],
        default="console",
        type=lower,
    )
    return cloned


def format_help() -> str:
    # create fake parser and return it's help
    global_help = add_global_options(
        argparse.ArgumentParser(exit_on_error=False, add_help=False)
    ).format_help()
    default_help = add_options_for_user(
        argparse.ArgumentParser(exit_on_error=False, add_help=False)
    ).format_help()
    user_help = add_options_for_user(
        add_user_option(argparse.ArgumentParser(exit_on_error=False, add_help=False))
    ).format_help()
    return "\n".join([global_help, default_help, user_help])


@dataclass(kw_only=True)
class _DefaultConfig:
    directory: str
    auth_only: bool
    cookie_directory: str
    sizes: Sequence[AssetVersionSize]
    live_photo_size: LivePhotoVersionSize
    recent: int | None
    until_found: int | None
    albums: Sequence[str]
    list_albums: bool
    library: str
    list_libraries: bool
    skip_videos: bool
    skip_live_photos: bool
    xmp_sidecar: bool
    force_size: bool
    auto_delete: bool
    folder_structure: str
    set_exif_datetime: bool
    smtp_username: str | None
    smtp_password: str | None
    smtp_host: str
    smtp_port: int
    smtp_no_tls: bool
    notification_email: str | None
    notification_email_from: str | None
    notification_script: pathlib.Path | None
    delete_after_download: bool
    keep_icloud_recent_days: int | None
    dry_run: bool
    keep_unicode_in_filenames: bool
    live_photo_mov_filename_policy: LivePhotoMovFilenamePolicy
    align_raw: RawTreatmentPolicy
    file_match_policy: FileMatchPolicy
    skip_created_before: datetime.datetime | datetime.timedelta | None
    skip_created_after: datetime.datetime | datetime.timedelta | None
    skip_photos: bool


@dataclass(kw_only=True)
class Config(_DefaultConfig):
    username: str
    password: str | None


@dataclass(kw_only=True)
class GlobalConfig:
    help: bool
    version: bool
    use_os_locale: bool
    only_print_filenames: bool
    log_level: str
    no_progress_bar: bool
    threads_num: int
    domain: str
    watch_with_interval: int | None
    password_providers: Sequence[PasswordProvider]
    mfa_provider: MFAProvider


skip_created_before_generator = partial_1_1(skip_created_generator, "--skip-created-before")
skip_created_after_generator = partial_1_1(skip_created_generator, "--skip-created-after")


def map_to_config(user_ns: argparse.Namespace) -> Config:
    return Config(
        username=user_ns.username,
        password=user_ns.password,
        directory=user_ns.directory,
        auth_only=user_ns.auth_only,
        cookie_directory=user_ns.cookie_directory,
        sizes=list(map_(AssetVersionSize, unique(user_ns.sizes or ["original"]))),
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
        align_raw=RawTreatmentPolicy(user_ns.align_raw),
        file_match_policy=FileMatchPolicy(user_ns.file_match_policy),
        skip_created_before=user_ns.skip_created_before,
        skip_created_after=user_ns.skip_created_after,
        skip_photos=user_ns.skip_photos,
    )


def parse(args: Sequence[str]) -> Tuple[GlobalConfig, Sequence[Config]]:
    # default --help
    if len(args) == 0:
        args = ["--help"]
    else:
        pass

    splitted_args = split(["-u", "--username"], args)
    global_and_default_args = splitted_args[0]
    global_parser: argparse.ArgumentParser = add_global_options(
        argparse.ArgumentParser(exit_on_error=False, add_help=False)
    )
    global_ns, rest_args = global_parser.parse_known_args(global_and_default_args)

    default_parser: argparse.ArgumentParser = add_options_for_user(
        argparse.ArgumentParser(exit_on_error=False, add_help=False)
    )

    default_ns = default_parser.parse_args(rest_args)

    user_parser: argparse.ArgumentParser = add_user_option(
        add_options_for_user(argparse.ArgumentParser(exit_on_error=False, add_help=False))
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
            log_level=global_ns.log_level,
            no_progress_bar=global_ns.no_progress_bar,
            threads_num=global_ns.threads_num,
            domain=global_ns.domain,
            watch_with_interval=global_ns.watch_with_interval,
            password_providers=list(
                map_(
                    PasswordProvider,
                    unique(global_ns.password_providers or ["parameter", "keyring", "console"]),
                )
            ),
            mfa_provider=MFAProvider(global_ns.mfa_provider),
        ),
        user_nses,
    )


def cli() -> int:
    global_ns, user_nses = parse(sys.argv[1:])
    if global_ns.help:
        print(format_help())
        return 0
    elif global_ns.version:
        print("version printed here")
        return 0
    else:
        print(f"global_ns={global_ns}")
        for user_ns in user_nses:
            print(f"user_ns={user_ns}")
    return 0
