#!/usr/bin/env python
"""Main script that uses Click to parse command-line arguments"""
from __future__ import print_function
from multiprocessing import freeze_support
freeze_support() # fixing tqdm on macos

import os
import sys
import time
import datetime
import logging
from logging import Logger
import itertools
import subprocess
import json
from typing import Callable, Optional, TypeVar, cast
import urllib
import click

from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from tzlocal import get_localzone
from pyicloud_ipd import PyiCloudService

from pyicloud_ipd.exceptions import PyiCloudAPIResponseException
from pyicloud_ipd.services.photos import PhotoAsset

from icloudpd.authentication import authenticator, TwoStepAuthRequiredError
from icloudpd import download
from icloudpd.email_notifications import send_2sa_notification
from icloudpd.string_helpers import truncate_middle
from icloudpd.autodelete import autodelete_photos
from icloudpd.paths import clean_filename, local_download_path
from icloudpd import exif_datetime
# Must import the constants object so that we can mock values in tests.
from icloudpd import constants
from icloudpd.counter import Counter

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.command(context_settings=CONTEXT_SETTINGS, options_metavar="<options>")
# @click.argument(
@click.option(
    "-d", "--directory",
    help="Local directory that should be used for download",
    type=click.Path(exists=True),
    metavar="<directory>")
@click.option(
    "-u", "--username",
    help="Your iCloud username or email address",
    metavar="<username>",
    prompt="iCloud username/email",
)
@click.option(
    "-p", "--password",
    help="Your iCloud password "
    "(default: use PyiCloud keyring or prompt for password)",
    metavar="<password>",
)
@click.option(
    "--auth-only",
    help="Create/Update cookie and session tokens only.",
    is_flag=True,
)
@click.option(
    "--cookie-directory",
    help="Directory to store cookies for authentication "
    "(default: ~/.pyicloud)",
    metavar="</cookie/directory>",
    default="~/.pyicloud",
)
@click.option(
    "--size",
    help="Image size to download (default: original)",
    type=click.Choice(["original", "medium", "thumb"]),
    default="original",
)
@click.option(
    "--live-photo-size",
    help="Live Photo video size to download (default: original)",
    type=click.Choice(["original", "medium", "thumb"]),
    default="original",
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
    "-a", "--album",
    help="Album to download (default: All Photos)",
    metavar="<album>",
    default="All Photos",
)
@click.option(
    "-l", "--list-albums",
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
    "--force-size",
    help="Only download the requested size "
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
@click.option("--folder-structure",
              help="Folder structure (default: {:%Y/%m/%d}). "
              "If set to 'none' all photos will just be placed into the download directory",
              metavar="<folder_structure>",
              default="{:%Y/%m/%d}",
              )
@click.option(
    "--set-exif-datetime",
    help="Write the DateTimeOriginal exif tag from file creation date, " +
    "if it doesn't exist.",
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
@click.option("--notification-email-from",
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
@click.option("--no-progress-bar",
              help="Disables the one-line progress bar and prints log messages on separate lines "
              "(Progress bar is disabled by default if there is no tty attached)",
              is_flag=True,
              )
@click.option("--threads-num",
              help="Number of cpu threads - deprecated & always 1. To be removed in future version",
              type=click.IntRange(1),
              default=1,
              )
@click.option(
    "--delete-after-download",
    help='Delete the photo/video after download it.'
    + ' The deleted items will be appear in the "Recently Deleted".'
    + ' Therefore, should not combine with --auto-delete option.',
    is_flag=True,
)
@click.option(
    "--domain",
    help="What iCloud root domain to use. Use 'cn' for mainland China (default: 'com')",
    type=click.Choice(["com", "cn"]),
    default="com",
)
@click.option("--watch-with-interval",
              help="Run downloading in a infinite cycle, waiting specified seconds between runs",
              type=click.IntRange(1),
              )
@click.option("--dry-run",
              help="Do not modify local system or iCloud",
              is_flag=True,
              default=False,
              )
# a hacky way to get proper version because automatic detection does not
# work for some reason
@click.version_option(version="1.17.3")
# pylint: disable-msg=too-many-arguments,too-many-statements
# pylint: disable-msg=too-many-branches,too-many-locals
def main(
        directory: Optional[str],
        username: Optional[str],
        password: Optional[str],
        auth_only: bool,
        cookie_directory: str,
        size: str,
        live_photo_size: str,
        recent: Optional[int],
        until_found: Optional[int],
        album: str,
        list_albums: bool,
        library,
        list_libraries,
        skip_videos: bool,
        skip_live_photos: bool,
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
        threads_num: int,    # pylint: disable=W0613
        delete_after_download: bool,
        domain: str,
        watch_with_interval: Optional[int],
        dry_run: bool
):
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
            print(
                '--auth-only, --directory, --list-libraries or --list-albums are required')
            sys.exit(2)

        if auto_delete and delete_after_download:
            print('--auto-delete and --delete-after-download are mutually exclusive')
            sys.exit(2)

        if watch_with_interval and (
                list_albums or only_print_filenames):  # pragma: no cover
            print(
                '--watch_with_interval is not compatible with --list_albums, --only_print_filenames'
            )
            sys.exit(2)

        sys.exit(
            core(
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
                    dry_run) if directory is not None else (
                    lambda _s: lambda _c,
                    _p: False),
                directory,
                username,
                password,
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
                dry_run))


# pylint: disable-msg=too-many-arguments,too-many-statements
# pylint: disable-msg=too-many-branches,too-many-locals


def download_builder(
        logger: logging.Logger,
        skip_videos: bool,
        folder_structure: str,
        directory: str,
        size: str,
        force_size: bool,
        only_print_filenames: bool,
        set_exif_datetime: bool,
        skip_live_photos: bool,
        live_photo_size: str,
        dry_run: bool) -> Callable[[PyiCloudService], Callable[[Counter, PhotoAsset], bool]]:
    """factory for downloader"""
    def state_(
            icloud: PyiCloudService) -> Callable[[Counter, PhotoAsset], bool]:
        def download_photo_(counter: Counter, photo: PhotoAsset) -> bool:
            """internal function for actually downloading the photos"""
            filename = clean_filename(photo.filename)
            if skip_videos and photo.item_type != "image":
                logger.debug(
                    "Skipping %s, only downloading photos." +
                    "(Item type was: %s)",
                    filename,
                    photo.item_type
                )
                return False
            if photo.item_type not in ("image", "movie"):
                logger.debug(
                    "Skipping %s, only downloading photos and videos. " +
                    "(Item type was: %s)",
                    filename,
                    photo.item_type
                )
                return False
            try:
                created_date = photo.created.astimezone(get_localzone())
            except (ValueError, OSError):
                logger.error(
                    "Could not convert photo created date to local timezone (%s)",
                    photo.created)
                created_date = photo.created

            try:
                if folder_structure.lower() == "none":
                    date_path = ""
                else:
                    date_path = folder_structure.format(created_date)
            except ValueError:  # pragma: no cover
                # This error only seems to happen in Python 2
                logger.error(
                    "Photo created date was not valid (%s)", photo.created)
                # e.g. ValueError: year=5 is before 1900
                # (https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/122)
                # Just use the Unix epoch
                created_date = datetime.datetime.fromtimestamp(0)
                date_path = folder_structure.format(created_date)

            download_dir = os.path.normpath(os.path.join(directory, date_path))
            download_size = size
            success = False

            try:
                versions = photo.versions
            except KeyError as ex:
                print(
                    f"KeyError: {ex} attribute was not found in the photo fields."
                )
                with open(file='icloudpd-photo-error.json', mode='w', encoding='utf8') as outfile:
                    # pylint: disable=protected-access
                    json.dump({
                        "master_record": photo._master_record,
                        "asset_record": photo._asset_record
                    }, outfile)
                    # pylint: enable=protected-access
                print("icloudpd has saved the photo record to: "
                      "./icloudpd-photo-error.json")
                print("Please create a Gist with the contents of this file: "
                      "https://gist.github.com")
                print(
                    "Then create an issue on GitHub: "
                    "https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues")
                print(
                    "Include a link to the Gist in your issue, so that we can "
                    "see what went wrong.\n")
                return False

            if size not in versions and size != "original":
                if force_size:
                    logger.error(
                        "%s size does not exist for %s. Skipping...",
                        size,
                        filename
                    )
                    return False
                download_size = "original"

            download_path = local_download_path(
                photo, download_size, download_dir)

            original_download_path = None
            file_exists = os.path.isfile(download_path)
            if not file_exists and download_size == "original":
                # Deprecation - We used to download files like IMG_1234-original.jpg,
                # so we need to check for these.
                # Now we match the behavior of iCloud for Windows: IMG_1234.jpg
                original_download_path = (f"-{size}.").join(
                    download_path.rsplit(".", 1)
                )
                file_exists = os.path.isfile(original_download_path)

            if file_exists:
                # for later: this crashes if download-size medium is specified
                file_size = os.stat(
                    original_download_path or download_path).st_size
                version = photo.versions[download_size]
                photo_size = version["size"]
                if file_size != photo_size:
                    download_path = (f"-{photo_size}.").join(
                        download_path.rsplit(".", 1)
                    )
                    logger.debug(
                        "%s deduplicated",
                        truncate_middle(download_path, 96)
                    )
                    file_exists = os.path.isfile(download_path)
                if file_exists:
                    counter.increment()
                    logger.debug(
                        "%s already exists",
                        truncate_middle(download_path, 96)
                    )

            if not file_exists:
                counter.reset()
                if only_print_filenames:
                    print(download_path)
                else:
                    truncated_path = truncate_middle(download_path, 96)
                    logger.debug(
                        "Downloading %s...",
                        truncated_path
                    )

                    download_result = download.download_media(
                        logger, dry_run, icloud, photo, download_path, download_size)
                    success = download_result

                    if download_result:
                        if not dry_run and set_exif_datetime and clean_filename(
                                photo.filename) .lower() .endswith(
                                (".jpg", ".jpeg")) and not exif_datetime.get_photo_exif(
                                logger, download_path):
                            # %Y:%m:%d looks wrong, but it's the correct format
                            date_str = created_date.strftime(
                                "%Y-%m-%d %H:%M:%S%z")
                            logger.debug(
                                "Setting EXIF timestamp for %s: %s",
                                download_path,
                                date_str
                            )
                            exif_datetime.set_photo_exif(
                                logger,
                                download_path,
                                created_date.strftime("%Y:%m:%d %H:%M:%S"),
                            )
                        if not dry_run:
                            download.set_utime(download_path, created_date)
                        logger.info(
                            "Downloaded %s",
                            truncated_path
                        )

            # Also download the live photo if present
            if not skip_live_photos:
                lp_size = live_photo_size + "Video"
                if lp_size in photo.versions:
                    version = photo.versions[lp_size]
                    filename = version["filename"]
                    if live_photo_size != "original":
                        # Add size to filename if not original
                        filename = filename.replace(
                            ".MOV", f"-{live_photo_size}.MOV"
                        )
                    lp_download_path = os.path.join(download_dir, filename)

                    lp_file_exists = os.path.isfile(lp_download_path)

                    if only_print_filenames and not lp_file_exists:
                        print(lp_download_path)
                    else:
                        if lp_file_exists:
                            lp_file_size = os.stat(lp_download_path).st_size
                            lp_photo_size = version["size"]
                            if lp_file_size != lp_photo_size:
                                lp_download_path = (f"-{lp_photo_size}.").join(
                                    lp_download_path.rsplit(".", 1)
                                )
                                logger.debug(
                                    "%s deduplicated",
                                    truncate_middle(lp_download_path, 96)
                                )
                                lp_file_exists = os.path.isfile(
                                    lp_download_path)
                            if lp_file_exists:
                                logger.debug(
                                    "%s already exists",
                                    truncate_middle(lp_download_path, 96)
                                )
                        if not lp_file_exists:
                            truncated_path = truncate_middle(
                                lp_download_path, 96)
                            logger.debug(
                                "Downloading %s...",
                                truncated_path
                            )
                            download_result = download.download_media(
                                logger, dry_run, icloud, photo, lp_download_path, lp_size)
                            success = download_result and success
                            if download_result:
                                logger.info(
                                    "Downloaded %s",
                                    truncated_path
                                )
            return success
        return download_photo_
    return state_


def delete_photo(
        logger: logging.Logger,
        icloud: PyiCloudService,
        photo: PhotoAsset):
    """Delete a photo from the iCloud account."""
    clean_filename_local = clean_filename(photo.filename)
    logger.debug(
        "Deleting %s in iCloud...", clean_filename_local)
    # pylint: disable=W0212
    url = f"{icloud.photos._service_endpoint}/records/modify?"\
        f"{urllib.parse.urlencode(icloud.photos.params)}"
    post_data = json.dumps(
        {
            "atomic": True,
            "desiredKeys": ["isDeleted"],
            "operations": [{
                "operationType": "update",
                "record": {
                    "fields": {'isDeleted': {'value': 1}},
                    "recordChangeTag": photo._asset_record["recordChangeTag"],
                    "recordName": photo._asset_record["recordName"],
                    "recordType": "CPLAsset",
                }
            }],
            "zoneID": {"zoneName": "PrimarySync"}
        }
    )
    icloud.photos.session.post(
        url, data=post_data, headers={
            "Content-type": "application/json"})
    logger.info(
        "Deleted %s in iCloud", clean_filename_local)


def delete_photo_dry_run(
        logger: logging.Logger,
        _icloud: PyiCloudService,
        photo: PhotoAsset):
    """Dry run for deleting a photo from the iCloud"""
    logger.info(
        "[DRY RUN] Would delete %s in iCloud",
        clean_filename(photo.filename)
    )


RetrierT = TypeVar('RetrierT')


def retrier(
        func: Callable[[], RetrierT],
        error_handler: Callable[[Exception, int], None]) -> RetrierT:
    """Run main func and retry helper if receive session error"""
    attempts = 0
    while True:
        try:
            return func()
        # pylint: disable-msg=broad-except
        except Exception as ex:
            attempts += 1
            error_handler(ex, attempts)
            if attempts > constants.MAX_RETRIES:
                raise


def session_error_handle_builder(logger: Logger, icloud: PyiCloudService):
    """Build handler for session error"""
    def session_error_handler(ex, attempt):
        """Handles session errors in the PhotoAlbum photos iterator"""
        if "Invalid global session" in str(ex):
            if attempt > constants.MAX_RETRIES:
                logger.error(
                    "iCloud re-authentication failed. Please try again later."
                )
                raise ex
            logger.error("Session error, re-authenticating...")
            if attempt > 1:
                # If the first re-authentication attempt failed,
                # start waiting a few seconds before retrying in case
                # there are some issues with the Apple servers
                time.sleep(constants.WAIT_SECONDS * attempt)
            icloud.authenticate()
    return session_error_handler


def internal_error_handle_builder(logger: logging.Logger):
    """Build handler for internal error"""
    def internal_error_handler(ex: Exception, attempt: int) -> None:
        """Handles session errors in the PhotoAlbum photos iterator"""
        if "INTERNAL_ERROR" in str(ex):
            if attempt > constants.MAX_RETRIES:
                logger.error(
                    "Internal Error at Apple."
                )
                raise ex
            logger.error("Internal Error at Apple, retrying...")
            # start waiting a few seconds before retrying in case
            # there are some issues with the Apple servers
            time.sleep(constants.WAIT_SECONDS * attempt)
    return internal_error_handler


def compose_handlers(handlers):
    """Compose multiple error handlers"""
    def composed(ex, retries):
        for handler in handlers:
            handler(ex, retries)
    return composed

# pylint: disable-msg=too-many-arguments,too-many-statements
# pylint: disable-msg=too-many-branches,too-many-locals


def core(
        downloader: Callable[[PyiCloudService], Callable[[Counter, PhotoAsset], bool]],
        directory: Optional[str],
        username: Optional[str],
        password: Optional[str],
        auth_only: bool,
        cookie_directory: str,
        size: str,
        recent: Optional[int],
        until_found: Optional[int],
        album: str,
        list_albums: bool,
        library,
        list_libraries,
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
        dry_run: bool
):
    """Download all iCloud photos to a local directory"""

    raise_error_on_2sa = (
        smtp_username is not None
        or notification_email is not None
        or notification_script is not None
    )
    try:
        icloud = authenticator(logger, domain)(
            username,
            password,
            cookie_directory,
            raise_error_on_2sa,
            client_id=os.environ.get("CLIENT_ID"),
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
    library_object = icloud.photos

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
            logger.debug(
                "Looking up all photos%s from album %s...",
                videos_phrase,
                album
            )

            session_exception_handler = session_error_handle_builder(
                logger, icloud)
            internal_error_handler = internal_error_handle_builder(logger)

            error_handler = compose_handlers(
                [session_exception_handler, internal_error_handler])

            photos.exception_handler = error_handler

            photos_count: Optional[int] = len(photos)

            # Optional: Only download the x most recent photos.
            if recent is not None:
                photos_count = recent
                photos = itertools.islice(photos, recent)

            if until_found is not None:
                photos_count = None
                # ensure photos iterator doesn't have a known length
                photos = (p for p in photos)

            # Skip the one-line progress bar if we're only printing the filenames,
            # or if the progress bar is explicitly disabled,
            # or if this is not a terminal (e.g. cron or piping output to file)
            skip_bar = not os.environ.get("FORCE_TQDM") and (
                only_print_filenames or no_progress_bar or not sys.stdout.isatty())
            if skip_bar:
                photos_enumerator = photos
                # logger.set_tqdm(None)
            else:
                photos_enumerator = tqdm(
                    iterable=photos,
                    total=photos_count,
                    leave=False,
                    dynamic_ncols=True,
                    ascii=True)
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
                ("Downloading %s %s" +
                 " photo%s%s to %s ..."),
                photos_count_str,
                size,
                plural_suffix,
                video_suffix,
                directory
            )

            consecutive_files_found = Counter(0)

            def should_break(counter: Counter) -> bool:
                """Exit if until_found condition is reached"""
                return until_found is not None and counter.value() >= until_found

            photos_iterator = iter(photos_enumerator)
            while True:
                try:
                    if should_break(consecutive_files_found):
                        logger.info(
                            "Found %s consecutive previously downloaded photos. Exiting",
                            until_found)
                        break
                    item = next(photos_iterator)
                    if download_photo(
                            consecutive_files_found,
                            item) and delete_after_download:

                        def delete_cmd():
                            delete_local = delete_photo_dry_run if dry_run else delete_photo
                            delete_local(logger, icloud, item)

                        retrier(delete_cmd, error_handler)

                except StopIteration:
                    break

            if only_print_filenames:
                return 0

            logger.info("All photos have been downloaded")

            if auto_delete:
                autodelete_photos(logger, dry_run, library_object,
                                  folder_structure, directory)

            if watch_interval:  # pragma: no cover
                logger.info(f"Waiting for {watch_interval} sec...")
                interval = range(1, watch_interval)
                for _ in interval if skip_bar else tqdm(
                    interval,
                    desc="Waiting...",
                    ascii=True,
                    leave=False,
                    dynamic_ncols=True
                ):
                    time.sleep(1)
            else:
                break  # pragma: no cover

    return 0
