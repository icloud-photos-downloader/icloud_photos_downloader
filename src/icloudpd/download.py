"""Handles file downloads with retries and error handling"""

import os
import socket
import time
import logging
import datetime
from tzlocal import get_localzone
from requests.exceptions import ConnectionError  # pylint: disable=redefined-builtin
from pyicloud_ipd.exceptions import PyiCloudAPIResponseError

# Import the constants object so that we can mock WAIT_SECONDS in tests
from icloudpd import constants

def update_mtime(created: datetime.datetime, download_path):
    """Set the modification time of the downloaded file to the photo creation date"""
    if created:
        created_date = None
        try:
            created_date = created.astimezone(
                get_localzone())
        except (ValueError, OSError):
            # We already show the timezone conversion error in base.py,
            # when generating the download directory.
            # So just return silently without touching the mtime.
            return
        set_utime(download_path, created_date)


def set_utime(download_path, created_date):
    """Set date & time of the file"""
    ctime = time.mktime(created_date.timetuple())
    os.utime(download_path, (ctime, ctime))

def mkdirs_for_path(logger, download_path: str) -> bool:
    """ Creates hierarchy of folders for file path if it needed """
    try:
        # get back the directory for the file to be downloaded and create it if
        # not there already
        download_dir = os.path.dirname(download_path)
        os.makedirs(name = download_dir, exist_ok=True)
        return True
    except OSError:
        logger.tqdm_write(
            f"Could not create folder {download_dir}",
            logging.ERROR,
        )
        return False

def mkdirs_for_path_dry_run(logger, download_path: str) -> bool:
    """ DRY Run for Creating hierarchy of folders for file path """
    download_dir = os.path.dirname(download_path)
    if not os.path.exists(download_dir):
        logger.tqdm_write(
            f"DRY RUN: Would create folder hierarchy {download_dir}",
            logging.INFO,
        )
    return True

def download_response_to_path(
        _logger,
        response,
        download_path: str,
        created_date: datetime.datetime) -> bool:
    """ Saves response content into file with desired created date """
    temp_download_path = download_path + ".part"
    with open(temp_download_path, "wb") as file_obj:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                file_obj.write(chunk)
    os.rename(temp_download_path, download_path)
    update_mtime(created_date, download_path)
    return True

def download_response_to_path_dry_run(
        logger,
        _response,
        download_path: str,
        _created_date: datetime.datetime) -> bool:
    """ Pretends to save response content into a file with desired created date """
    logger.tqdm_write(
        f"DRY RUN: Would download {download_path}",
        logging.INFO,
    )

# pylint: disable-msg=too-many-arguments
def download_media(logger, dry_run, icloud, photo, download_path, size):
    """Download the photo to path, with retries and error handling"""

    mkdirs_local = mkdirs_for_path_dry_run if dry_run else mkdirs_for_path
    download_local = download_response_to_path_dry_run if dry_run else download_response_to_path

    if not mkdirs_local(logger, download_path):
        return False

    for retries in range(constants.MAX_RETRIES):
        try:
            photo_response = photo.download(size)
            if photo_response:
                return download_local(logger, photo_response, download_path, photo.created)

            logger.tqdm_write(
                f"Could not find URL to download {photo.filename} for size {size}!",
                logging.ERROR,
            )
            break

        except (ConnectionError, socket.timeout, PyiCloudAPIResponseError) as ex:
            if "Invalid global session" in str(ex):
                logger.tqdm_write(
                    "Session error, re-authenticating...",
                    logging.ERROR)
                if retries > 0:
                    # If the first re-authentication attempt failed,
                    # start waiting a few seconds before retrying in case
                    # there are some issues with the Apple servers
                    time.sleep(constants.WAIT_SECONDS)

                icloud.authenticate()
            else:
                # you end up here when p.e. throttling by Apple happens
                wait_time = (retries + 1) * constants.WAIT_SECONDS
                logger.tqdm_write(
                    f"Error downloading {photo.filename}, retrying after {wait_time} seconds...",
                    logging.ERROR,
                )
                time.sleep(wait_time)

        except IOError:
            logger.error(
                "IOError while writing file to %s! "
                "You might have run out of disk space, or the file "
                "might be too large for your OS. "
                "Skipping this file...", download_path
            )
            break
    else:
        logger.tqdm_write(
            f"Could not download {photo.filename}! Please try again later."
        )

    return False
