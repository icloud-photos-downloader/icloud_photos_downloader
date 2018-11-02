#!/usr/bin/env python
"""Main script that uses Click to parse command-line arguments"""
from __future__ import print_function
import os
import sys
import time
import logging
import itertools
import subprocess
import click
import pickle
import signal

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
# Must import the constants object so that we can mock values in tests.
from icloudpd import constants

from concurrent.futures import ThreadPoolExecutor
import concurrent.futures.thread

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
    help="Only download the requested size " +
         "(default: download original if size is not available)",
    is_flag=True,
)
@click.option(
    "--auto-delete",
    help='Scans the "Recently Deleted" folder and deletes any files found in there. ' +
         "(If you restore the photo in iCloud, it will be downloaded again.)",
    is_flag=True,
)
@click.option(
    "--only-print-filenames",
    help="Only prints the filenames of all files that will be downloaded "
         "(not including files that are already downloaded.)" +
         "(Does not download or delete any files.)",
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
    "--clear-cache",
    help="Clears the downloaded files cache and will re-check for all physical files",
    is_flag=True,
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
        clear_cache,
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

    raise_error_on_2sa = (
        smtp_username is not None or
        notification_email is not None or
        notification_script is not None
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
        exit(1)

    # For Python 2.7
    if hasattr(directory, "decode"):
        directory = directory.decode("utf-8")  # pragma: no cover
    directory = os.path.normpath(directory)

    logger.debug(
        "Looking up all photos%s...",
        "" if skip_videos else " and videos")
    photos = icloud.photos.all

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
                time.sleep(constants.WAIT_SECONDS)
            icloud.authenticate()

    photos.exception_handler = photos_exception_handler

    photos_count = len(photos)

    # Optional: Only download the x most recent photos.
    if recent is not None:
        photos_count = recent
        photos = itertools.islice(photos, recent)

    tqdm_kwargs = {"total": photos_count}

    plural_suffix = "" if photos_count == 1 else "s"
    video_suffix = ""
    photos_count_str = "the first" if photos_count == 1 else photos_count
    if not skip_videos:
        video_suffix = " or video" if photos_count == 1 else " and videos"
    logger.info(
        "Downloading %s %s photo%s%s to %s/ ...",
        photos_count_str,
        size,
        plural_suffix,
        video_suffix,
        directory,
    )

    # Configure the caches, either by loading from disk or creating a new one

    def load_cache(cache_file):
        cache_object = set()  # cache of photos we've already downloaded
        if os.path.exists(cache_file):
            if clear_cache:
                os.remove(cache_file)
                logger.info("Found and removed cache file.")
            else:
                cache_object = pickle.load(open(cache_file, "rb"))
                logger.info("Cache shows %s files previously downloaded.", len(cache_object), )
        else:
            logger.info("No cache found, starting one.")

        return cache_object

    cache_file = "downloaded_photos_cache.p"
    downloaded_photos = load_cache(cache_file)
    # cached_ids_file = "downloaded_ids_cache.p"
    # downloaded_ids = load_cache(cached_ids_file)

    def add_to_cache(download_path, photo_id):
        downloaded_photos.add(download_path)
        # downloaded_ids.add(photo_id)

    def save_caches():
        pickle.dump(downloaded_photos, open(cache_file, 'wb'))
        # pickle.dump(downloaded_ids, open(cached_ids_file, 'wb'))

    # register handler to save cache on ctrl-c, should let you ctrl-c no matter which thread catches it
    # this doesn't always work to actuall stop it on ctrl-c, but it does seem to at least save the cache
    def signal_handler(sig, frame):
        print("\nCtrl-C detected, saving cache and exiting...")
        save_caches()
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

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

    # internal function for actually downloading the photos
    def download_photo(photo):
        for _ in range(constants.MAX_RETRIES):
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
                    photo.created, logging.ERROR, )
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
                        (size, filename), logging.ERROR, )
                    break
                download_size = "original"

            download_path = local_download_path(
                photo, download_size, download_dir)

            in_cache = download_path in downloaded_photos

            if in_cache:
                logger.set_tqdm_description(
                    "%s is in the cache." % truncate_middle(download_path, 96)
                )
            else:
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
                    logger.set_tqdm_description(
                        "%s already exists." % truncate_middle(download_path, 96)
                    )
                    add_to_cache(download_path, photo.id)  # add to cache so we don't check next time
                else:
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

                        # cache that we downloaded this file
                        if download_result:
                            add_to_cache(download_path, photo.id)  # add to cache so we don't check next time

                        if download_result and set_exif_datetime:
                            if photo.filename.lower().endswith((".jpg", ".jpeg")):
                                if not exif_datetime.get_photo_exif(download_path):
                                    # %Y:%m:%d looks wrong but it's the correct format
                                    date_str = created_date.strftime(
                                        "%Y:%m:%d %H:%M:%S")
                                    logger.debug(
                                        "Setting EXIF timestamp for %s: %s",
                                        download_path,
                                        date_str,
                                    )
                                    exif_datetime.set_photo_exif(
                                        download_path,
                                        created_date.strftime("%Y:%m:%d %H:%M:%S"),
                                    )
                            else:
                                timestamp = time.mktime(created_date.timetuple())
                                os.utime(download_path, (timestamp, timestamp))

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

                    if only_print_filenames:
                        print(lp_download_path)
                    else:
                        if lp_download_path in downloaded_photos or os.path.isfile(lp_download_path):
                            logger.set_tqdm_description(
                                "%s already exists."
                                % truncate_middle(lp_download_path, 96)
                            )
                            add_to_cache(lp_download_path, photo.id)  # add to cache so we don't check next time
                            break

                        truncated_path = truncate_middle(lp_download_path, 96)
                        logger.set_tqdm_description(
                            "Downloading %s" % truncated_path)
                        download_result = download.download_media(
                            icloud, photo, lp_download_path, lp_size
                        )
                        # add to cache
                        if download_result:
                            add_to_cache(download_path, photo.id)  # add to cache so we don't check next time

            break

    # pylint: disable-msg=too-many-nested-blocks
    with ThreadPoolExecutor() as executor:
        for photo in photos_enumerator:
            executor.submit(download_photo, photo)
            # download_photo(photo)

    if only_print_filenames:
        exit(0)

    logger.info("All photos have been downloaded!")

    if auto_delete:
        autodelete_photos(icloud, folder_structure, directory)

    # save the caches
    save_caches()
