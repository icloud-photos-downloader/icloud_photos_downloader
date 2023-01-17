"""Handles file downloads with retries and error handling"""

import os
import socket
import time
import logging
from tzlocal import get_localzone
from requests.exceptions import ConnectionError  # pylint: disable=redefined-builtin
from pyicloud.exceptions import PyiCloudAPIResponseException
from icloudpd.logger import setup_logger

# Import the constants object so that we can mock WAIT_SECONDS in tests
from icloudpd import constants


def update_mtime(photo, download_path):
    """Set the modification time of the downloaded file to the photo creation date"""
    if photo.created:
        created_date = None
        try:
            created_date = photo.created.astimezone(
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

def download_media(icloud, photo, download_path, size):
    """Download the photo to path, with retries and error handling"""
    logger = setup_logger()

    # get back the directory for the file to be downloaded and create it if not there already
    download_dir = os.path.dirname(download_path)

    if not os.path.exists(download_dir):
        try:
            os.makedirs(download_dir)
        except OSError:  # pragma: no cover
            pass         # pragma: no cover

    for retries in range(constants.MAX_RETRIES):
        try:
            photo_response = photo.download(size)
            if photo_response:
                temp_download_path = download_path + ".part"
                with open(temp_download_path, "wb") as file_obj:
                    for chunk in photo_response.iter_content(chunk_size=1024):
                        if chunk:
                            file_obj.write(chunk)
                os.rename(temp_download_path, download_path)
                update_mtime(photo, download_path)
                return True

            logger.tqdm_write(
                "Could not find URL to download %s for size %s!"
                % (photo.filename, size),
                logging.ERROR,
            )
            break

        except (ConnectionError, socket.timeout, PyiCloudAPIResponseException) as ex:
            if "Invalid global session" in str(ex):
                logger.tqdm_write(
                    "Session error, re-authenticating...",
                    logging.ERROR)
                if retries > 0:
                    # If the first reauthentication attempt failed,
                    # start waiting a few seconds before retrying in case
                    # there are some issues with the Apple servers
                    time.sleep(constants.WAIT_SECONDS)

                icloud.authenticate()
            else:
                # you end up here when p.e. throttleing by Apple happens
                wait_time = (retries + 1) * constants.WAIT_SECONDS
                logger.tqdm_write(
                    "Error downloading %s, retrying after %d seconds..."
                    % (photo.filename, wait_time),
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
            "Could not download %s! Please try again later." % photo.filename
        )

    return False
