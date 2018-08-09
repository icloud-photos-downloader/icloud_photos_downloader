#!/usr/bin/env python
"""Main script that uses Click to parse command-line arguments"""
from __future__ import print_function
import os
import sys
import time
import logging
import itertools
import click
from tqdm import tqdm
from tzlocal import get_localzone

from icloudpd.logger import setup_logger
from icloudpd.authentication import authenticate, TwoStepAuthRequiredError
from icloudpd import download
from icloudpd.email_notifications import send_2sa_notification
from icloudpd.string_helpers import truncate_middle
from icloudpd.autodelete import autodelete_photos
from icloudpd.paths import local_download_path
from icloudpd import exif_datetime
from icloudpd.constants import MAX_RETRIES

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS, options_metavar="<options>")
@click.argument(
    "directory",
    type=click.Path(
        exists=True),
    metavar="<directory>")
@click.option(
    "--username",
    help="Your iCloud username or email address",
    metavar="<username>",
    prompt="iCloud username/email",
)
@click.option(
    "--password",
    help="Your iCloud password "
    "(default: use PyiCloud keyring or prompt for password)",
    metavar="<password>",
)
@click.option(
    "--size",
    help="Image size to download (default: original)",
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
    "--skip-videos",
    help="Don't download any videos (default: Download both photos and videos)",
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
    help="Folder structure (default: {:%Y/%m/%d})",
    metavar="<folder_structure>",
    default="{:%Y/%m/%d}",
)
@click.option(
    "--set-exif-datetime",
    help="Write the DateTimeOriginal exif tag from file creation date, if it doesn't exist.",
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
@click.version_option()
# pylint: disable-msg=too-many-arguments,too-many-statements
# pylint: disable-msg=too-many-branches,too-many-locals
def main(
        directory,
        username,
        password,
        size,
        recent,
        until_found,
        skip_videos,
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

    should_send_2sa_notification = smtp_username is not None
    try:
        icloud = authenticate(
            username,
            password,
            should_send_2sa_notification,
            client_id=os.environ.get("CLIENT_ID"),
        )
    except TwoStepAuthRequiredError:
        send_2sa_notification(
            smtp_username,
            smtp_password,
            smtp_host,
            smtp_port,
            smtp_no_tls,
            notification_email,
        )
        exit(1)

    # For Python 2.7
    if hasattr(directory, "decode"):
        directory = directory.decode("utf-8")  # pragma: no cover
    directory = os.path.normpath(directory)

    logger.debug(
        "Looking up all photos%s...",
        "" if skip_videos else " and videos")
    photos = icloud.photos.all
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
        "Downloading %s %s photo%s%s to %s/ ...",
        photos_count_str, size, plural_suffix, video_suffix, directory
    )

    consecutive_files_found = 0

    # Use only ASCII characters in progress bar
    tqdm_kwargs["ascii"] = True

    # Skip the one-line progress bar if we're only printing the filenames,
    # progress bar is explicity disabled,
    # or if this is not a terminal (e.g. cron or piping output to file)
    if not os.environ.get("FORCE_TQDM") and (
            only_print_filenames or no_progress_bar or not sys.stdout.isatty()
    ):
        photos_enumerator = photos
        logger.set_tqdm(None)
    else:
        photos_enumerator = tqdm(photos, **tqdm_kwargs)
        logger.set_tqdm(photos_enumerator)

    # pylint: disable-msg=too-many-nested-blocks
    for photo in photos_enumerator:
        for _ in range(MAX_RETRIES):
            if skip_videos and photo.item_type != "image":
                logger.set_tqdm_description(
                    "Skipping %s, only downloading photos." % photo.filename
                )
                break
            if photo.item_type != "image" and photo.item_type != "movie":
                logger.set_tqdm_description(
                    "Skipping %s, only downloading photos and videos. "
                    "(Item type was: %s)" % (photo.filename, photo.item_type)
                )
                break
            try:
                created_date = photo.created.astimezone(get_localzone())
            except ValueError:
                logger.set_tqdm_description(
                    "Could not convert photo created date to local timezone (%s)" %
                    photo.created, logging.ERROR)
                created_date = photo.created

            date_path = folder_structure.format(created_date)
            download_dir = os.path.join(directory, date_path)

            if not os.path.exists(download_dir):
                os.makedirs(download_dir)

            download_size = size
            # Fall back to original if requested size is not available
            if size not in photo.versions and size != "original":
                if force_size:
                    filename = photo.filename.encode(
                        "utf-8").decode("ascii", "ignore")
                    logger.set_tqdm_description(
                        "%s size does not exist for %s. Skipping..." %
                        (size, filename), logging.ERROR)
                    break
                download_size = "original"

            download_path = local_download_path(
                photo, download_size, download_dir)
            download_path_without_size = local_download_path(
                photo, None, download_dir)
            # add a check if the "simple" name of the file is found if the size
            # is original
            if os.path.isfile(download_path) or (
                    download_size == "original" and
                    os.path.isfile(download_path_without_size)
            ):
                if until_found is not None:
                    consecutive_files_found += 1
                logger.set_tqdm_description(
                    "%s already exists." % truncate_middle(download_path, 96)
                )
                break

            if only_print_filenames:
                print(download_path)
            else:
                truncated_path = truncate_middle(download_path, 96)
                logger.set_tqdm_description("Downloading %s" % truncated_path)

                download_result = download.download_photo(
                    icloud, photo, download_path, download_size
                )

                if download_result and set_exif_datetime:
                    if photo.filename.lower().endswith((".jpg", ".jpeg")):
                        if not exif_datetime.get_photo_exif(download_path):
                            # %Y:%m:%d looks wrong but it's the correct format
                            date_str = created_date.strftime(
                                "%Y:%m:%d %H:%M:%S")
                            logger.debug(
                                "Setting EXIF timestamp for %s: %s",
                                download_path, date_str
                            )
                            exif_datetime.set_photo_exif(
                                download_path,
                                created_date.strftime("%Y:%m:%d %H:%M:%S"),
                            )
                    else:
                        timestamp = time.mktime(created_date.timetuple())
                        os.utime(download_path, (timestamp, timestamp))

            if until_found is not None:
                consecutive_files_found = 0
            break

        if until_found is not None and consecutive_files_found >= until_found:
            logger.tqdm_write(
                "Found %d consecutive previously downloaded photos. Exiting"
                % until_found
            )
            if hasattr(photos_enumerator, "close"):
                photos_enumerator.close()
            break

    if only_print_filenames:
        exit(0)

    logger.info("All photos have been downloaded!")

    if auto_delete:
        autodelete_photos(icloud, folder_structure, directory)
