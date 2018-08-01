"""Handles file downloads with retries and error handling"""

import socket
import time
import logging
from requests.exceptions import ConnectionError  # pylint: disable=redefined-builtin
from pyicloud_ipd.exceptions import PyiCloudAPIResponseError
from icloudpd.logger import setup_logger

# Import the constants object so that we can mock WAIT_SECONDS in tests
from icloudpd import constants


def download_photo(icloud, photo, download_path, size):
    """Download the photo to path, with retries and error handling"""
    logger = setup_logger()

    for _ in range(constants.MAX_RETRIES):
        try:
            photo_response = photo.download(size)
            if photo_response:
                with open(download_path, "wb") as file_obj:
                    for chunk in photo_response.iter_content(chunk_size=1024):
                        if chunk:
                            file_obj.write(chunk)
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
                icloud.authenticate()
                # Wait a few seconds in case there are issues with Apple's
                # servers
                time.sleep(constants.WAIT_SECONDS)
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
