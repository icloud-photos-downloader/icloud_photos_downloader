#!/usr/bin/env python
"""Main script that uses Click to parse command-line arguments"""
from __future__ import print_function
import os
import sys
import time
import datetime
import logging
import itertools
import subprocess
import json
import click

from tqdm import tqdm
from tzlocal import get_localzone

from pyicloud.exceptions import PyiCloudAPIResponseException

from icloudpd.logger import setup_logger
from icloudpd.authentication import authenticate, TwoStepAuthRequiredError
from icloudpd import download
from icloudpd.email_notifications import send_2sa_notification
from icloudpd.string_helpers import truncate_middle
from icloudpd.autodelete import autodelete_photos
from icloudpd.paths import local_download_path
from icloudpd import exif_datetime
# Must import the constants object so that we can mock values in tests.
from icloudpd import constants
from icloudpd.counter import Counter

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


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
    help="Lists the avaliable albums",
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
@click.option(
    "--folder-structure",
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
@click.option(
    "--threads-num",
    help="Number of cpu threads -- deprecated. To be removed in future version",
    type=click.IntRange(1),
    default=1,
)
@click.version_option()
# pylint: disable-msg=too-many-arguments,too-many-statements
# pylint: disable-msg=too-many-branches,too-many-locals
def main(
        directory,
        username,
        password,
        cookie_directory,
        size,
        live_photo_size,
        recent,
        until_found,
        album,
        list_albums,
        skip_videos,
        skip_live_photos,
        force_size,
        auto_delete,
        only_print_filenames,
        folder_structure,
        set_exif_datetime,
        smtp_username,
        smtp_password,
        smtp_host,
        smtp_port,
        smtp_no_tls,
        notification_email,
        log_level,
        no_progress_bar,
        notification_script,
        threads_num,    # pylint: disable=W0613
):
    """Download all iCloud photos to a local directory"""

    logger = setup_logger()
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

    # check required directory param only if not list albums
    if not list_albums and not directory:
        print('--directory or --list-albums are required')
        sys.exit(2)

    raise_error_on_2sa = (
        smtp_username is not None
        or notification_email is not None
        or notification_script is not None
    )
    try:
        icloud = authenticate(
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
                smtp_username,
                smtp_password,
                smtp_host,
                smtp_port,
                smtp_no_tls,
                notification_email,
            )
        sys.exit(1)

    # Default album is "All Photos", so this is the same as
    # calling `icloud.photos.all`.
    # After 6 or 7 runs within 1h Apple blocks the API for some time. In that
    # case exit.
    try:
        photos = icloud.photos.albums[album]
    except PyiCloudAPIResponseException as err:
        # For later: come up with a nicer message to the user. For now take the
        # exception text
        print(err)
        sys.exit(1)

    if list_albums:
        albums_dict = icloud.photos.albums
        albums = albums_dict.values()  # pragma: no cover
        album_titles = [str(a) for a in albums]
        print(*album_titles, sep="\n")
        sys.exit(0)

    directory = os.path.normpath(directory)

    logger.debug(
        "Looking up all photos%s from album %s...",
        "" if skip_videos else " and videos",
        album)

    def photos_exception_handler(ex, retries):
        """Handles session errors in the PhotoAlbum photos iterator"""
        if "Invalid global session" in str(ex):
            if retries > constants.MAX_RETRIES:
                logger.tqdm_write(
                    "iCloud re-authentication failed! Please try again later."
                )
                raise ex
            logger.tqdm_write(
                "Session error, re-authenticating...",
                logging.ERROR)
            if retries > 1:
                # If the first reauthentication attempt failed,
                # start waiting a few seconds before retrying in case
                # there are some issues with the Apple servers
                time.sleep(constants.WAIT_SECONDS * retries)
            icloud.authenticate()

    photos.exception_handler = photos_exception_handler

    photos_count = len(photos)

    # Optional: Only download the x most recent photos.
    if recent is not None:
        photos_count = recent
        photos = itertools.islice(photos, recent)

    tqdm_kwargs = {"total": photos_count}

    if until_found is not None:
        del tqdm_kwargs["total"]
        photos_count = "???"
        # ensure photos iterator doesn't have a known length
        photos = (p for p in photos)

    plural_suffix = "" if photos_count == 1 else "s"
    video_suffix = ""
    photos_count_str = "the first" if photos_count == 1 else photos_count
    if not skip_videos:
        video_suffix = " or video" if photos_count == 1 else " and videos"
    logger.info(
        "Downloading %s %s photo%s%s to %s ...",
        photos_count_str,
        size,
        plural_suffix,
        video_suffix,
        directory,
    )

    # Use only ASCII characters in progress bar
    tqdm_kwargs["ascii"] = True

    # Skip the one-line progress bar if we're only printing the filenames,
    # or if the progress bar is explicity disabled,
    # or if this is not a terminal (e.g. cron or piping output to file)
    if not os.environ.get("FORCE_TQDM") and (
            only_print_filenames or no_progress_bar or not sys.stdout.isatty()
    ):
        photos_enumerator = photos
        logger.set_tqdm(None)
    else:
        photos_enumerator = tqdm(photos, **tqdm_kwargs)
        logger.set_tqdm(photos_enumerator)

    def download_photo(counter, photo):
        """internal function for actually downloading the photos"""
        if skip_videos and photo.item_type != "image":
            logger.set_tqdm_description(
                "Skipping %s, only downloading photos." % photo.filename
            )
            return
        if photo.item_type != "image" and photo.item_type != "movie":
            logger.set_tqdm_description(
                "Skipping %s, only downloading photos and videos. "
                "(Item type was: %s)" % (photo.filename, photo.item_type)
            )
            return
        try:
            created_date = photo.created.astimezone(get_localzone())
        except (ValueError, OSError):
            logger.set_tqdm_description(
                "Could not convert photo created date to local timezone (%s)" %
                photo.created, logging.ERROR)
            created_date = photo.created

        try:
            if folder_structure.lower() == "none":
                date_path = ""
            else:
                date_path = folder_structure.format(created_date)
        except ValueError:  # pragma: no cover
            # This error only seems to happen in Python 2
            logger.set_tqdm_description(
                "Photo created date was not valid (%s)" %
                photo.created, logging.ERROR)
            # e.g. ValueError: year=5 is before 1900
            # (https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/122)
            # Just use the Unix epoch
            created_date = datetime.datetime.fromtimestamp(0)
            date_path = folder_structure.format(created_date)

        download_dir = os.path.normpath(os.path.join(directory, date_path))
        download_size = size

        try:
            versions = photo.versions
        except KeyError as ex:
            print(
                "KeyError: %s attribute was not found in the photo fields!" %
                ex)
            with open('icloudpd-photo-error.json', 'w') as outfile:
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
            return

        if size not in versions and size != "original":
            if force_size:
                filename = photo.filename.encode(
                    "utf-8").decode("ascii", "ignore")
                logger.set_tqdm_description(
                    "%s size does not exist for %s. Skipping..." %
                    (size, filename), logging.ERROR, )
                return
            download_size = "original"

        download_path = local_download_path(
            photo, download_size, download_dir)

        file_exists = os.path.isfile(download_path)
        if not file_exists and download_size == "original":
            # Deprecation - We used to download files like IMG_1234-original.jpg,
            # so we need to check for these.
            # Now we match the behavior of iCloud for Windows: IMG_1234.jpg
            original_download_path = ("-%s." % size).join(
                download_path.rsplit(".", 1)
            )
            file_exists = os.path.isfile(original_download_path)

        if file_exists:
            # for later: this crashes if download-size medium is specified
            file_size = os.stat(download_path).st_size
            version = photo.versions[download_size]
            photo_size = version["size"]
            if file_size != photo_size:
                download_path = ("-%s." % photo_size).join(
                    download_path.rsplit(".", 1)
                )
                logger.set_tqdm_description(
                    "%s deduplicated." % truncate_middle(download_path, 96)
                )
                file_exists = os.path.isfile(download_path)
            if file_exists:
                counter.increment()
                logger.set_tqdm_description(
                    "%s already exists." % truncate_middle(download_path, 96)
                )

        if not file_exists:
            counter.reset()
            if only_print_filenames:
                print(download_path)
            else:
                truncated_path = truncate_middle(download_path, 96)
                logger.set_tqdm_description(
                    "Downloading %s" %
                    truncated_path)

                download_result = download.download_media(
                    icloud, photo, download_path, download_size
                )

                if download_result:
                    if set_exif_datetime and photo.filename.lower().endswith(
                            (".jpg", ".jpeg")) and not exif_datetime.get_photo_exif(download_path):
                        # %Y:%m:%d looks wrong but it's the correct format
                        date_str = created_date.strftime(
                            "%Y-%m-%d %H:%M:%S%z")
                        logger.debug(
                            "Setting EXIF timestamp for %s: %s",
                            download_path,
                            date_str,
                        )
                        exif_datetime.set_photo_exif(
                            download_path,
                            created_date.strftime("%Y:%m:%d %H:%M:%S"),
                        )
                    download.set_utime(download_path, created_date)

        # Also download the live photo if present
        if not skip_live_photos:
            lp_size = live_photo_size + "Video"
            if lp_size in photo.versions:
                version = photo.versions[lp_size]
                filename = version["filename"]
                if live_photo_size != "original":
                    # Add size to filename if not original
                    filename = filename.replace(
                        ".MOV", "-%s.MOV" %
                        live_photo_size)
                lp_download_path = os.path.join(download_dir, filename)

                lp_file_exists = os.path.isfile(lp_download_path)

                if only_print_filenames and not lp_file_exists:
                    print(lp_download_path)
                else:
                    if lp_file_exists:
                        lp_file_size = os.stat(lp_download_path).st_size
                        lp_photo_size = version["size"]
                        if lp_file_size != lp_photo_size:
                            lp_download_path = ("-%s." % lp_photo_size).join(
                                lp_download_path.rsplit(".", 1)
                            )
                            logger.set_tqdm_description(
                                "%s deduplicated." %
                                truncate_middle(
                                    lp_download_path, 96))
                            lp_file_exists = os.path.isfile(lp_download_path)
                        if lp_file_exists:
                            logger.set_tqdm_description(
                                "%s already exists."
                                % truncate_middle(lp_download_path, 96)
                            )
                    if not lp_file_exists:
                        truncated_path = truncate_middle(lp_download_path, 96)
                        logger.set_tqdm_description(
                            "Downloading %s" % truncated_path)
                        download.download_media(
                            icloud, photo, lp_download_path, lp_size
                        )

    consecutive_files_found = Counter(0)

    def should_break(counter):
        """Exit if until_found condition is reached"""
        return until_found is not None and counter.value() >= until_found

    photos_iterator = iter(photos_enumerator)
    while True:
        try:
            if should_break(consecutive_files_found):
                logger.tqdm_write(
                    "Found %d consecutive previously downloaded photos. Exiting" %
                    until_found)
                break
            item = next(photos_iterator)
            download_photo(consecutive_files_found, item)
        except StopIteration:
            break

    if only_print_filenames:
        sys.exit(0)

    logger.info("All photos have been downloaded!")

    if auto_delete:
        autodelete_photos(icloud, folder_structure, directory)
