"""Handles file downloads with retries and error handling"""

import os
import socket
import time
import logging
from tzlocal import get_localzone
from requests.exceptions import ConnectionError  # pylint: disable=redefined-builtin
from pyicloud_ipd.exceptions import PyiCloudAPIResponseError
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
        ctime = time.mktime(created_date.timetuple())
        os.utime(download_path, (ctime, ctime))


def download_media(icloud, photo, download_path, size):
    """Download the photo to path, with retries and error handling"""
    logger = setup_logger()

    for retries in range(constants.MAX_RETRIES):
        try:
            photo_response = photo.download(size)
            if photo_response:
                with open(download_path, "wb") as file_obj:
                    for chunk in photo_response.iter_content(chunk_size=1024):
                        if chunk:
                            file_obj.write(chunk)
                update_mtime(photo, download_path)
                return True

            logger.tqdm_write(
                "Could not find URL to download %s for size %s!"
                % (photo.filename, size),
                logging.ERROR,
            )
            break

        except (ConnectionError, socket.timeout, PyiCloudAPIResponseError) as ex:
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
                logger.tqdm_write(
                    "Error downloading %s, retrying after %d seconds..."
                    % (photo.filename, constants.WAIT_SECONDS),
                    logging.ERROR,
                )
                time.sleep(constants.WAIT_SECONDS)

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
