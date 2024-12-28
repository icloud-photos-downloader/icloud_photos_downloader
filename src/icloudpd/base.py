#!/usr/bin/env python
"""Main script that uses Click to parse command-line arguments"""

from multiprocessing import freeze_support

import foundation
from foundation.core import compose, constant, identity
from icloudpd.mfa_provider import MFAProvider
from pyicloud_ipd.item_type import AssetItemType  # fmt: skip

freeze_support()  # fmt: skip # fixing tqdm on macos

import datetime
import itertools
import json
import logging
import os
import subprocess
import sys
import time
import typing
import urllib
from functools import partial
from logging import Logger
from threading import Thread
from typing import (
    Callable,
    Dict,
    Iterable,
    NoReturn,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    cast,
)

import click
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from tzlocal import get_localzone

from icloudpd import constants, download, exif_datetime
from icloudpd.authentication import TwoStepAuthRequiredError, authenticator
from icloudpd.autodelete import autodelete_photos
from icloudpd.config import Config
from icloudpd.counter import Counter
from icloudpd.email_notifications import send_2sa_notification
from icloudpd.paths import clean_filename, local_download_path, remove_unicode_chars
from icloudpd.server import serve_app
from icloudpd.status import Status, StatusExchange
from icloudpd.string_helpers import truncate_middle
from icloudpd.xmp_sidecar import generate_xmp_file
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.exceptions import PyiCloudAPIResponseException
from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.raw_policy import RawTreatmentPolicy
from pyicloud_ipd.services.photos import PhotoAsset, PhotoLibrary, PhotosService
from pyicloud_ipd.utils import (
    add_suffix_to_filename,
    disambiguate_filenames,
    get_password_from_keyring,
    size_to_suffix,
    store_password_in_keyring,
)
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize


def build_filename_cleaner(
    _ctx: click.Context, _param: click.Parameter, is_keep_unicode: bool
) -> Callable[[str], str]:
    """Map keep_unicode parameter for function for cleaning filenames"""
    # redefining typed vars instead of using in ternary directly is a mypy hack
    r: Callable[[str], str] = remove_unicode_chars
    i: Callable[[str], str] = identity
    return compose(
        (r if not is_keep_unicode else i),
        clean_filename,
    )


def lp_filename_concatinator(filename: str) -> str:
    name, ext = os.path.splitext(filename)
    if not ext:
        return filename
    return name + ("_HEVC.MOV" if ext.lower().endswith(".heic") else ".MOV")


def lp_filename_original(filename: str) -> str:
    name, ext = os.path.splitext(filename)
    if not ext:
        return filename
    return name + ".MOV"


def build_lp_filename_generator(
    _ctx: click.Context, _param: click.Parameter, lp_filename_policy: str
) -> Callable[[str], str]:
    # redefining typed vars instead of using in ternary directly is a mypy hack
    return lp_filename_original if lp_filename_policy == "original" else lp_filename_concatinator


def raw_policy_generator(
    _ctx: click.Context, _param: click.Parameter, raw_policy: str
) -> RawTreatmentPolicy:
    # redefining typed vars instead of using in ternary directly is a mypy hack
    if raw_policy == "as-is":
        return RawTreatmentPolicy.AS_IS
    elif raw_policy == "original":
        return RawTreatmentPolicy.AS_ORIGINAL
    elif raw_policy == "alternative":
        return RawTreatmentPolicy.AS_ALTERNATIVE
    else:
        raise ValueError(f"policy was provided with unsupported value of '{raw_policy}'")


def size_generator(
    _ctx: click.Context, _param: click.Parameter, sizes: Sequence[str]
) -> Sequence[AssetVersionSize]:
    def _map(size: str) -> AssetVersionSize:
        if size == "original":
            return AssetVersionSize.ORIGINAL
        elif size == "adjusted":
            return AssetVersionSize.ADJUSTED
        elif size == "alternative":
            return AssetVersionSize.ALTERNATIVE
        elif size == "medium":
            return AssetVersionSize.MEDIUM
        elif size == "thumb":
            return AssetVersionSize.THUMB
        else:
            raise ValueError(f"size was provided with unsupported value of '{size}'")

    return [_map(_s) for _s in sizes]


def mfa_provider_generator(
    _ctx: click.Context, _param: click.Parameter, provider: str
) -> MFAProvider:
    if provider == "console":
        return MFAProvider.CONSOLE
    elif provider == "webui":
        return MFAProvider.WEBUI
    else:
        raise ValueError(f"mfa provider has unsupported value of '{provider}'")


def ask_password_in_console(_user: str) -> Optional[str]:
    return typing.cast(Optional[str], click.prompt("iCloud Password", hide_input=True))
    # return getpass.getpass(
    #         f'iCloud Password for {_user}:'
    #     )


def get_password_from_webui(
    logger: Logger, status_exchange: StatusExchange
) -> Callable[[str], Optional[str]]:
    def _intern(_user: str) -> Optional[str]:
        """Request two-factor authentication through Webui."""
        if not status_exchange.replace_status(Status.NO_INPUT_NEEDED, Status.NEED_PASSWORD):
            logger.error("Expected NO_INPUT_NEEDED, but got something else")
            return None

        # wait for input
        while True:
            status = status_exchange.get_status()
            if status == Status.NEED_PASSWORD:
                time.sleep(1)
            else:
                break
        if status_exchange.replace_status(Status.SUPPLIED_PASSWORD, Status.CHECKING_PASSWORD):
            password = status_exchange.get_payload()
            if not password:
                logger.error("Internal error: did not get password for SUPPLIED_PASSWORD status")
                status_exchange.replace_status(
                    Status.CHECKING_PASSWORD, Status.NO_INPUT_NEEDED
                )  # TODO Error
                return None
            return password

        return None  # TODO

    return _intern


def update_password_status_in_webui(status_exchange: StatusExchange) -> Callable[[str, str], None]:
    def _intern(_u: str, _p: str) -> None:
        # TODO we are not handling wrong passwords...
        status_exchange.replace_status(Status.CHECKING_PASSWORD, Status.NO_INPUT_NEEDED)
        return None

    return _intern


# def get_click_param_by_name(_name: str, _params: List[Parameter]) -> Optional[Parameter]:
#     _with_password = [_p for _p in _params if _name in _p.name]
#     if len(_with_password) == 0:
#         return None
#     return _with_password[0]


def dummy_password_writter(_u: str, _p: str) -> None:
    pass


def keyring_password_writter(logger: Logger) -> Callable[[str, str], None]:
    def _intern(username: str, password: str) -> None:
        try:
            store_password_in_keyring(username, password)
        except Exception:
            logger.warning("Password was not saved to keyring")

    return _intern


def password_provider_generator(
    _ctx: click.Context, _param: click.Parameter, providers: Sequence[str]
) -> Dict[str, Tuple[Callable[[str], Optional[str]], Callable[[str, str], None]]]:
    def _map(provider: str) -> Tuple[Callable[[str], Optional[str]], Callable[[str, str], None]]:
        if provider == "webui":
            return (ask_password_in_console, dummy_password_writter)
        if provider == "console":
            return (ask_password_in_console, dummy_password_writter)
        elif provider == "keyring":
            return (get_password_from_keyring, dummy_password_writter)
        elif provider == "parameter":
            # TODO get from parameter
            # _param: Optional[Parameter] = get_click_param_by_name("password", _ctx.command.params)
            # if _param:
            #     _password: str = _param.consume_value(_ctx, {})
            #     return constant(_password)
            return (constant(None), dummy_password_writter)
        else:
            raise ValueError(f"password provider was given an unsupported value of '{provider}'")

    return dict([(_s, _map(_s)) for _s in providers])


def lp_size_generator(
    _ctx: click.Context, _param: click.Parameter, size: str
) -> LivePhotoVersionSize:
    if size == "original":
        return LivePhotoVersionSize.ORIGINAL
    elif size == "medium":
        return LivePhotoVersionSize.MEDIUM
    elif size == "thumb":
        return LivePhotoVersionSize.THUMB
    else:
        raise ValueError(f"size was provided with unsupported value of '{size}'")


def file_match_policy_generator(
    _ctx: click.Context, _param: click.Parameter, policy: str
) -> FileMatchPolicy:
    if policy == "name-size-dedup-with-suffix":
        return FileMatchPolicy.NAME_SIZE_DEDUP_WITH_SUFFIX
    elif policy == "name-id7":
        return FileMatchPolicy.NAME_ID7
    else:
        raise ValueError(f"policy was provided with unsupported value of '{policy}'")


def locale_setter(_ctx: click.Context, _param: click.Parameter, use_os_locale: bool) -> bool:
    # set locale
    if use_os_locale:
        from locale import LC_ALL, setlocale

        setlocale(LC_ALL, "")
    return use_os_locale


def report_version(ctx: click.Context, _param: click.Parameter, value: bool) -> bool:
    if not value:
        return value
    vi = foundation.version_info_formatted()
    click.echo(vi)
    ctx.exit()


# Must import the constants object so that we can mock values in tests.

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.command(context_settings=CONTEXT_SETTINGS, options_metavar="<options>", no_args_is_help=True)
@click.option(
    "-d",
    "--directory",
    help="Local directory that should be used for download",
    type=click.Path(exists=True),
    metavar="<directory>",
)
@click.option(
    "-u",
    "--username",
    help="Your iCloud username or email address",
    metavar="<username>",
    prompt="iCloud username/email",
)
@click.option(
    "-p",
    "--password",
    help="Your iCloud password " "(default: use PyiCloud keyring or prompt for password)",
    metavar="<password>",
    # is_eager=True,
)
@click.option(
    "--auth-only",
    help="Create/Update cookie and session tokens only.",
    is_flag=True,
)
@click.option(
    "--cookie-directory",
    help="Directory to store cookies for authentication " "(default: ~/.pyicloud)",
    metavar="</cookie/directory>",
    default="~/.pyicloud",
)
@click.option(
    "--size",
    help="Image size to download. `medium` and `thumb` will always be added as suffixes to filenames, `adjusted` and `alternative` only if conflicting, `original` - never. If `adjusted` or `alternative` specified and is missing, then `original` is used.",
    type=click.Choice(["original", "medium", "thumb", "adjusted", "alternative"]),
    default=["original"],
    multiple=True,
    show_default=True,
    callback=size_generator,
)
@click.option(
    "--live-photo-size",
    help="Live Photo video size to download",
    type=click.Choice(["original", "medium", "thumb"]),
    default="original",
    show_default=True,
    callback=lp_size_generator,
)
@click.option(
    "--recent",
    help="Number of recent photos to download (default: download all photos)",
    type=click.IntRange(0),
)
@click.option(
    "--until-found",
    help="Download most recently added photos until we find x number of "
    "previously downloaded consecutive photos (default: download all photos)",
    type=click.IntRange(0),
)
@click.option(
    "-a",
    "--album",
    help="Album to download (default: All Photos)",
    metavar="<album>",
    default="All Photos",
)
@click.option(
    "-l",
    "--list-albums",
    help="Lists the available albums",
    is_flag=True,
)
@click.option(
    "--library",
    help="Library to download (default: Personal Library)",
    metavar="<library>",
    default="PrimarySync",
)
@click.option(
    "--list-libraries",
    help="Lists the available libraries",
    is_flag=True,
)
@click.option(
    "--skip-videos",
    help="Don't download any videos (default: Download all photos and videos)",
    is_flag=True,
)
@click.option(
    "--skip-live-photos",
    help="Don't download any live photos (default: Download live photos)",
    is_flag=True,
)
@click.option(
    "--xmp-sidecar",
    help="Export additional data as XMP sidecar files (default: don't export)",
    is_flag=True,
)
@click.option(
    "--force-size",
    help="Only download the requested size (`adjusted` and `alternate` will not be forced)"
    + "(default: download original if size is not available)",
    is_flag=True,
)
@click.option(
    "--auto-delete",
    help='Scans the "Recently Deleted" folder and deletes any files found in there. '
    + "(If you restore the photo in iCloud, it will be downloaded again.)",
    is_flag=True,
)
@click.option(
    "--only-print-filenames",
    help="Only prints the filenames of all files that will be downloaded "
    "(not including files that are already downloaded.)"
    + "(Does not download or delete any files.)",
    is_flag=True,
)
@click.option(
    "--folder-structure",
    help="Folder structure (default: {:%Y/%m/%d}). "
    "If set to 'none' all photos will just be placed into the download directory",
    metavar="<folder_structure>",
    default="{:%Y/%m/%d}",
)
@click.option(
    "--set-exif-datetime",
    help="Write the DateTimeOriginal exif tag from file creation date, " + "if it doesn't exist.",
    is_flag=True,
)
@click.option(
    "--smtp-username",
    help="Your SMTP username, for sending email notifications when "
    "two-step authentication expires.",
    metavar="<smtp_username>",
)
@click.option(
    "--smtp-password",
    help="Your SMTP password, for sending email notifications when "
    "two-step authentication expires.",
    metavar="<smtp_password>",
)
@click.option(
    "--smtp-host",
    help="Your SMTP server host. Defaults to: smtp.gmail.com",
    metavar="<smtp_host>",
    default="smtp.gmail.com",
)
@click.option(
    "--smtp-port",
    help="Your SMTP server port. Default: 587 (Gmail)",
    metavar="<smtp_port>",
    type=click.IntRange(0),
    default=587,
)
@click.option(
    "--smtp-no-tls",
    help="Pass this flag to disable TLS for SMTP (TLS is required for Gmail)",
    metavar="<smtp_no_tls>",
    is_flag=True,
)
@click.option(
    "--notification-email",
    help="Email address where you would like to receive email notifications. "
    "Default: SMTP username",
    metavar="<notification_email>",
)
@click.option(
    "--notification-email-from",
    help="Email address from which you would like to receive email notifications. "
    "Default: SMTP username or notification-email",
    metavar="<notification_email_from>",
)
@click.option(
    "--notification-script",
    type=click.Path(),
    help="Runs an external script when two factor authentication expires. "
    "(path required: /path/to/my/script.sh)",
)
@click.option(
    "--log-level",
    help="Log level (default: debug)",
    type=click.Choice(["debug", "info", "error"]),
    default="debug",
)
@click.option(
    "--no-progress-bar",
    help="Disables the one-line progress bar and prints log messages on separate lines "
    "(Progress bar is disabled by default if there is no tty attached)",
    is_flag=True,
)
@click.option(
    "--threads-num",
    help="Number of cpu threads - deprecated & always 1. To be removed in future version",
    type=click.IntRange(1),
    default=1,
)
@click.option(
    "--delete-after-download",
    help="Delete the photo/video after download it."
    + ' The deleted items will be appear in the "Recently Deleted".'
    + " Therefore, should not combine with --auto-delete option.",
    is_flag=True,
)
@click.option(
    "--domain",
    help="What iCloud root domain to use. Use 'cn' for mainland China (default: 'com')",
    type=click.Choice(["com", "cn"]),
    default="com",
)
@click.option(
    "--watch-with-interval",
    help="Run downloading in a infinite cycle, waiting specified seconds between runs",
    type=click.IntRange(1),
)
@click.option(
    "--dry-run",
    help="Do not modify local system or iCloud",
    is_flag=True,
    default=False,
)
@click.option(
    "--keep-unicode-in-filenames",
    "filename_cleaner",
    help="Keep unicode chars in file names or remove non all ascii chars",
    type=bool,
    default=False,
    callback=build_filename_cleaner,
)
@click.option(
    "--live-photo-mov-filename-policy",
    "lp_filename_generator",
    help="How to produce filenames for video portion of live photos: `suffix` will add _HEVC suffix and `original` will keep filename as it is.",
    type=click.Choice(["suffix", "original"], case_sensitive=False),
    default="suffix",
    callback=build_lp_filename_generator,
)
@click.option(
    "--align-raw",
    "raw_policy",
    help="For photo assets with raw and jpeg, treat raw always in the specified size: `original` (raw+jpeg), `alternative` (jpeg+raw), or unchanged (as-is). It matters when choosing sizes to download",
    type=click.Choice(["as-is", "original", "alternative"], case_sensitive=False),
    default="as-is",
    show_default=True,
    callback=raw_policy_generator,
)
@click.option(
    "--password-provider",
    "password_providers",
    help="Specifies passwords provider to check in the specified order",
    type=click.Choice(["console", "keyring", "parameter", "webui"], case_sensitive=False),
    default=["parameter", "keyring", "console"],
    show_default=True,
    multiple=True,
    callback=password_provider_generator,
)
@click.option(
    "--file-match-policy",
    "file_match_policy",
    help="Policy to identify existing files and de-duplicate. `name-size-dedup-with-suffix` appends file size to deduplicate. `name-id7` adds asset id from iCloud to all file names and does not de-duplicate.",
    type=click.Choice(["name-size-dedup-with-suffix", "name-id7"], case_sensitive=False),
    default="name-size-dedup-with-suffix",
    show_default=True,
    callback=file_match_policy_generator,
)
@click.option(
    "--mfa-provider",
    help="Specified where to get MFA code from",
    type=click.Choice(["console", "webui"], case_sensitive=False),
    default="console",
    show_default=True,
    callback=mfa_provider_generator,
)
@click.option(
    "--use-os-locale",
    help="Use locale of the host OS to format dates",
    is_flag=True,
    default=False,
    is_eager=True,
    callback=locale_setter,
)
@click.option(
    "--version",
    help="Show the version, commit hash and timestamp",
    is_flag=True,
    expose_value=False,
    is_eager=True,
    callback=report_version,
)
def main(
    directory: Optional[str],
    username: str,
    password: Optional[str],
    auth_only: bool,
    cookie_directory: str,
    size: Sequence[AssetVersionSize],
    live_photo_size: LivePhotoVersionSize,
    recent: Optional[int],
    until_found: Optional[int],
    album: str,
    list_albums: bool,
    library: str,
    list_libraries: bool,
    skip_videos: bool,
    skip_live_photos: bool,
    xmp_sidecar: bool,
    force_size: bool,
    auto_delete: bool,
    only_print_filenames: bool,
    folder_structure: str,
    set_exif_datetime: bool,
    smtp_username: Optional[str],
    smtp_password: Optional[str],
    smtp_host: str,
    smtp_port: int,
    smtp_no_tls: bool,
    notification_email: Optional[str],
    notification_email_from: Optional[str],
    log_level: str,
    no_progress_bar: bool,
    notification_script: Optional[str],
    threads_num: int,
    delete_after_download: bool,
    domain: str,
    watch_with_interval: Optional[int],
    dry_run: bool,
    filename_cleaner: Callable[[str], str],
    lp_filename_generator: Callable[[str], str],
    raw_policy: RawTreatmentPolicy,
    password_providers: Dict[
        str, Tuple[Callable[[str], Optional[str]], Callable[[str, str], None]]
    ],
    file_match_policy: FileMatchPolicy,
    mfa_provider: MFAProvider,
    use_os_locale: bool,
) -> NoReturn:
    """Download all iCloud photos to a local directory"""

    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    logger = logging.getLogger("icloudpd")
    if only_print_filenames:
        logger.disabled = True
    else:
        # Need to make sure disabled is reset to the correct value,
        # because the logger instance is shared between tests.
        logger.disabled = False
        if log_level == "debug":
            logger.setLevel(logging.DEBUG)
        elif log_level == "info":
            logger.setLevel(logging.INFO)
        elif log_level == "error":
            logger.setLevel(logging.ERROR)

    with logging_redirect_tqdm():
        # check required directory param only if not list albums
        if not list_albums and not list_libraries and not directory and not auth_only:
            print("--auth-only, --directory, --list-libraries or --list-albums are required")
            sys.exit(2)

        if auto_delete and delete_after_download:
            print("--auto-delete and --delete-after-download are mutually exclusive")
            sys.exit(2)

        if watch_with_interval and (list_albums or only_print_filenames):  # pragma: no cover
            print(
                "--watch_with_interval is not compatible with --list_albums, --only_print_filenames"
            )
            sys.exit(2)

        # hacky way to use one param in another
        if password and "parameter" in password_providers:
            # replace
            password_providers["parameter"] = (constant(password), lambda _r, _w: None)

        if len(password_providers) == 0:  # pragma: no cover
            print("You need to specify at least one --password-provider")
            sys.exit(2)

        if "console" in password_providers and "webui" in password_providers:
            print("Console and webui are not compatible in --password-provider")
            sys.exit(2)

        if "console" in password_providers and list(password_providers)[-1] != "console":
            print("Console must be the last --password-provider")
            sys.exit(2)

        if "webui" in password_providers and list(password_providers)[-1] != "webui":
            print("Webui must be the last --password-provider")
            sys.exit(2)

        if folder_structure != "none":
            try:
                folder_structure.format(datetime.datetime.now())
            except:  # noqa E722
                print("Format specified in --folder-structure is incorrect")
                sys.exit(2)

        status_exchange = StatusExchange()
        config = Config(
            directory=directory,
            username=username,
            auth_only=auth_only,
            cookie_directory=cookie_directory,
            primary_sizes=size,
            live_photo_size=live_photo_size,
            recent=recent,
            until_found=until_found,
            album=album,
            list_albums=list_albums,
            library=library,
            list_libraries=list_libraries,
            skip_videos=skip_videos,
            skip_live_photos=skip_live_photos,
            xmp_sidecar=xmp_sidecar,
            force_size=force_size,
            auto_delete=auto_delete,
            only_print_filenames=only_print_filenames,
            folder_structure=folder_structure,
            set_exif_datetime=set_exif_datetime,
            smtp_username=smtp_username,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_no_tls=smtp_no_tls,
            notification_email=notification_email,
            notification_email_from=notification_email_from,
            log_level=log_level,
            no_progress_bar=no_progress_bar,
            notification_script=notification_script,
            threads_num=threads_num,
            delete_after_download=delete_after_download,
            domain=domain,
            watch_with_interval=watch_with_interval,
            dry_run=dry_run,
            raw_policy=raw_policy,
            password_providers=password_providers,
            file_match_policy=file_match_policy,
            mfa_provider=mfa_provider,
            use_os_locale=use_os_locale,
        )
        status_exchange.set_config(config)

        # hacky way to use one param in another
        if "webui" in password_providers:
            # replace
            password_providers["webui"] = (
                get_password_from_webui(logger, status_exchange),
                update_password_status_in_webui(status_exchange),
            )

        # hacky way to inject logger
        if "keyring" in password_providers:
            # replace
            password_providers["keyring"] = (
                get_password_from_keyring,
                keyring_password_writter(logger),
            )

        # start web server
        if mfa_provider == MFAProvider.WEBUI:
            server_thread = Thread(target=serve_app, daemon=True, args=[logger, status_exchange])
            server_thread.start()

        result = core(
            download_builder(
                logger,
                skip_videos,
                folder_structure,
                directory,
                size,
                force_size,
                only_print_filenames,
                set_exif_datetime,
                skip_live_photos,
                live_photo_size,
                dry_run,
                file_match_policy,
                xmp_sidecar,
            )
            if directory is not None
            else (lambda _s: lambda _c, _p: False),
            directory,
            username,
            auth_only,
            cookie_directory,
            size,
            recent,
            until_found,
            album,
            list_albums,
            library,
            list_libraries,
            skip_videos,
            auto_delete,
            only_print_filenames,
            folder_structure,
            smtp_username,
            smtp_password,
            smtp_host,
            smtp_port,
            smtp_no_tls,
            notification_email,
            notification_email_from,
            no_progress_bar,
            notification_script,
            delete_after_download,
            domain,
            logger,
            watch_with_interval,
            dry_run,
            filename_cleaner,
            lp_filename_generator,
            raw_policy,
            file_match_policy,
            password_providers,
            mfa_provider,
            status_exchange,
        )
        sys.exit(result)


def download_builder(
    logger: logging.Logger,
    skip_videos: bool,
    folder_structure: str,
    directory: str,
    primary_sizes: Sequence[AssetVersionSize],
    force_size: bool,
    only_print_filenames: bool,
    set_exif_datetime: bool,
    skip_live_photos: bool,
    live_photo_size: LivePhotoVersionSize,
    dry_run: bool,
    file_match_policy: FileMatchPolicy,
    xmp_sidecar: bool,
) -> Callable[[PyiCloudService], Callable[[Counter, PhotoAsset], bool]]:
    """factory for downloader"""

    def state_(icloud: PyiCloudService) -> Callable[[Counter, PhotoAsset], bool]:
        def download_photo_(counter: Counter, photo: PhotoAsset) -> bool:
            """internal function for actually downloading the photos"""

            if skip_videos and photo.item_type == AssetItemType.MOVIE:
                logger.debug(
                    "Skipping %s, only downloading photos." + "(Item type was: %s)",
                    photo.filename,
                    photo.item_type,
                )
                return False
            # Throwing error now
            # if not photo.item_type:
            #     logger.debug(
            #         "Skipping %s, only downloading photos and videos. " + "(Item type was: %s)",
            #         photo.filename,
            #         photo.item_type,
            #     )
            #     return False
            try:
                created_date = photo.created.astimezone(get_localzone())
            except (ValueError, OSError):
                logger.error(
                    "Could not convert photo created date to local timezone (%s)", photo.created
                )
                created_date = photo.created

            if folder_structure.lower() == "none":
                date_path = ""
            else:
                try:
                    date_path = folder_structure.format(created_date)
                except ValueError:  # pragma: no cover
                    # This error only seems to happen in Python 2
                    logger.error("Photo created date was not valid (%s)", photo.created)
                    # e.g. ValueError: year=5 is before 1900
                    # (https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/122)
                    # Just use the Unix epoch
                    created_date = datetime.datetime.fromtimestamp(0)
                    date_path = folder_structure.format(created_date)

            try:
                versions = disambiguate_filenames(photo.versions, primary_sizes)
            except KeyError as ex:
                print(f"KeyError: {ex} attribute was not found in the photo fields.")
                with open(file="icloudpd-photo-error.json", mode="w", encoding="utf8") as outfile:
                    json.dump(
                        {
                            "master_record": photo._master_record,
                            "asset_record": photo._asset_record,
                        },
                        outfile,
                    )
                print("icloudpd has saved the photo record to: " "./icloudpd-photo-error.json")
                print(
                    "Please create a Gist with the contents of this file: "
                    "https://gist.github.com"
                )
                print(
                    "Then create an issue on GitHub: "
                    "https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues"
                )
                print(
                    "Include a link to the Gist in your issue, so that we can "
                    "see what went wrong.\n"
                )
                return False

            download_dir = os.path.normpath(os.path.join(directory, date_path))
            success = False

            for download_size in primary_sizes:
                if download_size not in versions and download_size != AssetVersionSize.ORIGINAL:
                    if force_size:
                        logger.error(
                            "%s size does not exist for %s. Skipping...",
                            download_size.value,
                            photo.filename,
                        )
                        continue
                    if AssetVersionSize.ORIGINAL in primary_sizes:
                        continue  # that should avoid double download for original
                    download_size = AssetVersionSize.ORIGINAL

                version = versions[download_size]
                filename = version.filename

                download_path = local_download_path(filename, download_dir)

                original_download_path = None
                file_exists = os.path.isfile(download_path)
                if not file_exists and download_size == AssetVersionSize.ORIGINAL:
                    # Deprecation - We used to download files like IMG_1234-original.jpg,
                    # so we need to check for these.
                    # Now we match the behavior of iCloud for Windows: IMG_1234.jpg
                    original_download_path = add_suffix_to_filename("-original", download_path)
                    file_exists = os.path.isfile(original_download_path)

                if file_exists:
                    if file_match_policy == FileMatchPolicy.NAME_SIZE_DEDUP_WITH_SUFFIX:
                        # for later: this crashes if download-size medium is specified
                        file_size = os.stat(original_download_path or download_path).st_size
                        photo_size = version.size
                        if file_size != photo_size:
                            download_path = (f"-{photo_size}.").join(download_path.rsplit(".", 1))
                            logger.debug("%s deduplicated", truncate_middle(download_path, 96))
                            file_exists = os.path.isfile(download_path)
                    if file_exists:
                        counter.increment()
                        logger.debug("%s already exists", truncate_middle(download_path, 96))

                if not file_exists:
                    counter.reset()
                    if only_print_filenames:
                        print(download_path)
                    else:
                        truncated_path = truncate_middle(download_path, 96)
                        logger.debug("Downloading %s...", truncated_path)

                        download_result = download.download_media(
                            logger, dry_run, icloud, photo, download_path, version, download_size
                        )
                        success = download_result

                        if download_result:
                            if (
                                not dry_run
                                and set_exif_datetime
                                and filename.lower().endswith((".jpg", ".jpeg"))
                                and not exif_datetime.get_photo_exif(logger, download_path)
                            ):
                                # %Y:%m:%d looks wrong, but it's the correct format
                                date_str = created_date.strftime("%Y-%m-%d %H:%M:%S%z")
                                logger.debug(
                                    "Setting EXIF timestamp for %s: %s", download_path, date_str
                                )
                                exif_datetime.set_photo_exif(
                                    logger,
                                    download_path,
                                    created_date.strftime("%Y:%m:%d %H:%M:%S"),
                                )
                            if not dry_run:
                                download.set_utime(download_path, created_date)
                            logger.info("Downloaded %s", truncated_path)

                if xmp_sidecar:
                    generate_xmp_file(logger, download_path, photo._asset_record)

            # Also download the live photo if present
            if not skip_live_photos:
                lp_size = live_photo_size
                if lp_size in photo.versions:
                    version = photo.versions[lp_size]
                    lp_filename = version.filename
                    if live_photo_size != LivePhotoVersionSize.ORIGINAL:
                        # Add size to filename if not original
                        lp_filename = add_suffix_to_filename(
                            size_to_suffix(live_photo_size),
                            lp_filename,
                        )
                    else:
                        pass
                    lp_download_path = os.path.join(download_dir, lp_filename)

                    lp_file_exists = os.path.isfile(lp_download_path)

                    if only_print_filenames and not lp_file_exists:
                        print(lp_download_path)
                    else:
                        if lp_file_exists:
                            if file_match_policy == FileMatchPolicy.NAME_SIZE_DEDUP_WITH_SUFFIX:
                                lp_file_size = os.stat(lp_download_path).st_size
                                lp_photo_size = version.size
                                if lp_file_size != lp_photo_size:
                                    lp_download_path = (f"-{lp_photo_size}.").join(
                                        lp_download_path.rsplit(".", 1)
                                    )
                                    logger.debug(
                                        "%s deduplicated", truncate_middle(lp_download_path, 96)
                                    )
                                    lp_file_exists = os.path.isfile(lp_download_path)
                            if lp_file_exists:
                                logger.debug(
                                    "%s already exists", truncate_middle(lp_download_path, 96)
                                )
                        if not lp_file_exists:
                            truncated_path = truncate_middle(lp_download_path, 96)
                            logger.debug("Downloading %s...", truncated_path)
                            download_result = download.download_media(
                                logger, dry_run, icloud, photo, lp_download_path, version, lp_size
                            )
                            success = download_result and success
                            if download_result:
                                logger.info("Downloaded %s", truncated_path)
            return success

        return download_photo_

    return state_


def delete_photo(
    logger: logging.Logger,
    photo_service: PhotosService,
    library_object: PhotoLibrary,
    photo: PhotoAsset,
) -> None:
    """Delete a photo from the iCloud account."""
    clean_filename_local = photo.filename
    logger.debug("Deleting %s in iCloud...", clean_filename_local)
    url = (
        f"{photo_service._service_endpoint}/records/modify?"
        f"{urllib.parse.urlencode(photo_service.params)}"
    )
    post_data = json.dumps(
        {
            "atomic": True,
            "desiredKeys": ["isDeleted"],
            "operations": [
                {
                    "operationType": "update",
                    "record": {
                        "fields": {"isDeleted": {"value": 1}},
                        "recordChangeTag": photo._asset_record["recordChangeTag"],
                        "recordName": photo._asset_record["recordName"],
                        "recordType": "CPLAsset",
                    },
                }
            ],
            "zoneID": library_object.zone_id,
        }
    )
    photo_service.session.post(url, data=post_data, headers={"Content-type": "application/json"})
    logger.info("Deleted %s in iCloud", clean_filename_local)


def delete_photo_dry_run(
    logger: logging.Logger,
    _photo_service: PhotosService,
    library_object: PhotoLibrary,
    photo: PhotoAsset,
) -> None:
    """Dry run for deleting a photo from the iCloud"""
    logger.info(
        "[DRY RUN] Would delete %s in iCloud library %s",
        photo.filename,
        library_object.zone_id["zoneName"],
    )


RetrierT = TypeVar("RetrierT")


def retrier(
    func: Callable[[], RetrierT], error_handler: Callable[[Exception, int], None]
) -> RetrierT:
    """Run main func and retry helper if receive session error"""
    attempts = 0
    while True:
        try:
            return func()
        except Exception as ex:
            attempts += 1
            error_handler(ex, attempts)
            if attempts > constants.MAX_RETRIES:
                raise


def session_error_handle_builder(
    logger: Logger, icloud: PyiCloudService
) -> Callable[[Exception, int], None]:
    """Build handler for session error"""

    def session_error_handler(ex: Exception, attempt: int) -> None:
        """Handles session errors in the PhotoAlbum photos iterator"""
        if "Invalid global session" in str(ex):
            if attempt > constants.MAX_RETRIES:
                logger.error("iCloud re-authentication failed. Please try again later.")
                raise ex
            logger.error("Session error, re-authenticating...")
            if attempt > 1:
                # If the first re-authentication attempt failed,
                # start waiting a few seconds before retrying in case
                # there are some issues with the Apple servers
                time.sleep(constants.WAIT_SECONDS * attempt)
            icloud.authenticate()

    return session_error_handler


def internal_error_handle_builder(logger: logging.Logger) -> Callable[[Exception, int], None]:
    """Build handler for internal error"""

    def internal_error_handler(ex: Exception, attempt: int) -> None:
        """Handles session errors in the PhotoAlbum photos iterator"""
        if "INTERNAL_ERROR" in str(ex):
            if attempt > constants.MAX_RETRIES:
                logger.error("Internal Error at Apple.")
                raise ex
            logger.error("Internal Error at Apple, retrying...")
            # start waiting a few seconds before retrying in case
            # there are some issues with the Apple servers
            time.sleep(constants.WAIT_SECONDS * attempt)

    return internal_error_handler


def compose_handlers(
    handlers: Sequence[Callable[[Exception, int], None]],
) -> Callable[[Exception, int], None]:
    """Compose multiple error handlers"""

    def composed(ex: Exception, retries: int) -> None:
        for handler in handlers:
            handler(ex, retries)

    return composed


def core(
    downloader: Callable[[PyiCloudService], Callable[[Counter, PhotoAsset], bool]],
    directory: Optional[str],
    username: str,
    auth_only: bool,
    cookie_directory: str,
    primary_sizes: Sequence[AssetVersionSize],
    recent: Optional[int],
    until_found: Optional[int],
    album: str,
    list_albums: bool,
    library: str,
    list_libraries: bool,
    skip_videos: bool,
    auto_delete: bool,
    only_print_filenames: bool,
    folder_structure: str,
    smtp_username: Optional[str],
    smtp_password: Optional[str],
    smtp_host: str,
    smtp_port: int,
    smtp_no_tls: bool,
    notification_email: Optional[str],
    notification_email_from: Optional[str],
    no_progress_bar: bool,
    notification_script: Optional[str],
    delete_after_download: bool,
    domain: str,
    logger: logging.Logger,
    watch_interval: Optional[int],
    dry_run: bool,
    filename_cleaner: Callable[[str], str],
    lp_filename_generator: Callable[[str], str],
    raw_policy: RawTreatmentPolicy,
    file_match_policy: FileMatchPolicy,
    password_providers: Dict[
        str, Tuple[Callable[[str], Optional[str]], Callable[[str, str], None]]
    ],
    mfa_provider: MFAProvider,
    status_exchange: StatusExchange,
) -> int:
    """Download all iCloud photos to a local directory"""

    raise_error_on_2sa = (
        smtp_username is not None
        or notification_email is not None
        or notification_script is not None
    )
    try:
        icloud = authenticator(
            logger,
            domain,
            filename_cleaner,
            lp_filename_generator,
            raw_policy,
            file_match_policy,
            password_providers,
            mfa_provider,
            status_exchange,
        )(
            username,
            cookie_directory,
            raise_error_on_2sa,
            os.environ.get("CLIENT_ID"),
        )
    except TwoStepAuthRequiredError:
        if notification_script is not None:
            subprocess.call([notification_script])
        if smtp_username is not None or notification_email is not None:
            send_2sa_notification(
                logger,
                smtp_username,
                smtp_password,
                smtp_host,
                smtp_port,
                smtp_no_tls,
                notification_email,
                notification_email_from,
            )
        return 1

    if auth_only:
        logger.info("Authentication completed successfully")
        return 0

    download_photo = downloader(icloud)

    # Access to the selected library. Defaults to the primary photos object.
    library_object: PhotoLibrary = icloud.photos

    if list_libraries:
        libraries_dict = icloud.photos.libraries
        library_names = libraries_dict.keys()
        print(*library_names, sep="\n")

    else:
        while True:
            # Default album is "All Photos", so this is the same as
            # calling `icloud.photos.all`.
            # After 6 or 7 runs within 1h Apple blocks the API for some time. In that
            # case exit.
            try:
                if library:
                    try:
                        library_object = icloud.photos.libraries[library]
                    except KeyError:
                        logger.error("Unknown library: %s", library)
                        return 1
                photos = library_object.albums[album]
            except PyiCloudAPIResponseException as err:
                # For later: come up with a nicer message to the user. For now take the
                # exception text
                logger.error("error?? %s", err)
                return 1

            if list_albums:
                print("Albums:")
                albums_dict = library_object.albums
                albums = albums_dict.values()  # pragma: no cover
                album_titles = [str(a) for a in albums]
                print(*album_titles, sep="\n")
                return 0
            # casting is okay since we checked for list_albums and directory compatibily upstream
            # would be better to have that in types though
            directory = os.path.normpath(cast(str, directory))

            videos_phrase = "" if skip_videos else " and videos"
            logger.debug("Looking up all photos%s from album %s...", videos_phrase, album)

            session_exception_handler = session_error_handle_builder(logger, icloud)
            internal_error_handler = internal_error_handle_builder(logger)

            error_handler = compose_handlers([session_exception_handler, internal_error_handler])

            photos.exception_handler = error_handler

            photos_count: Optional[int] = len(photos)

            photos_enumerator: Iterable[PhotoAsset] = photos

            # Optional: Only download the x most recent photos.
            if recent is not None:
                photos_count = recent
                photos_enumerator = itertools.islice(photos_enumerator, recent)

            if until_found is not None:
                photos_count = None
                # ensure photos iterator doesn't have a known length
                photos_enumerator = (p for p in photos_enumerator)

            # Skip the one-line progress bar if we're only printing the filenames,
            # or if the progress bar is explicitly disabled,
            # or if this is not a terminal (e.g. cron or piping output to file)
            skip_bar = not os.environ.get("FORCE_TQDM") and (
                only_print_filenames or no_progress_bar or not sys.stdout.isatty()
            )
            if skip_bar:
                photos_enumerator = photos_enumerator
                # logger.set_tqdm(None)
            else:
                photos_enumerator = tqdm(
                    iterable=photos_enumerator,
                    total=photos_count,
                    leave=False,
                    dynamic_ncols=True,
                    ascii=True,
                )
                # logger.set_tqdm(photos_enumerator)

            if photos_count is not None:
                plural_suffix = "" if photos_count == 1 else "s"
                video_suffix = ""
                photos_count_str = "the first" if photos_count == 1 else photos_count

                if not skip_videos:
                    video_suffix = " or video" if photos_count == 1 else " and videos"
            else:
                photos_count_str = "???"
                plural_suffix = "s"
                video_suffix = " and videos" if not skip_videos else ""
            logger.info(
                ("Downloading %s %s" + " photo%s%s to %s ..."),
                photos_count_str,
                ",".join([_s.value for _s in primary_sizes]),
                plural_suffix,
                video_suffix,
                directory,
            )

            consecutive_files_found = Counter(0)

            def should_break(counter: Counter) -> bool:
                """Exit if until_found condition is reached"""
                return until_found is not None and counter.value() >= until_found

            status_exchange.get_progress().photos_count = (
                0 if photos_count is None else photos_count
            )
            photos_counter = 0

            photos_iterator = iter(photos_enumerator)
            while True:
                try:
                    if should_break(consecutive_files_found):
                        logger.info(
                            "Found %s consecutive previously downloaded photos. Exiting",
                            until_found,
                        )
                        break
                    item = next(photos_iterator)
                    if download_photo(consecutive_files_found, item) and delete_after_download:
                        delete_local = partial(
                            delete_photo_dry_run if dry_run else delete_photo,
                            logger,
                            icloud.photos,
                            library_object,
                            item,
                        )

                        retrier(delete_local, error_handler)

                    photos_counter += 1
                    status_exchange.get_progress().photos_counter = photos_counter

                    if status_exchange.get_progress().cancel:
                        break

                except StopIteration:
                    break

            if only_print_filenames:
                return 0

            if status_exchange.get_progress().cancel:
                logger.info("Iteration was cancelled")
                status_exchange.get_progress().photos_last_message = "Iteration was cancelled"
            else:
                logger.info("All photos have been downloaded")
                status_exchange.get_progress().photos_last_message = (
                    "All photos have been downloaded"
                )
            status_exchange.get_progress().reset()

            if auto_delete:
                autodelete_photos(
                    logger, dry_run, library_object, folder_structure, directory, primary_sizes
                )

            if watch_interval:  # pragma: no cover
                logger.info(f"Waiting for {watch_interval} sec...")
                interval: Sequence[int] = range(1, watch_interval)
                iterable: Sequence[int] = (
                    interval
                    if skip_bar
                    else typing.cast(
                        Sequence[int],
                        tqdm(
                            iterable=interval,
                            desc="Waiting...",
                            ascii=True,
                            leave=False,
                            dynamic_ncols=True,
                        ),
                    )
                )
                for counter in iterable:
                    status_exchange.get_progress().waiting = watch_interval - counter
                    if status_exchange.get_progress().resume:
                        status_exchange.get_progress().reset()
                        break
                    time.sleep(1)
            else:
                break  # pragma: no cover

    return 0
