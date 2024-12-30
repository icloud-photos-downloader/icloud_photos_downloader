"""Handles file downloads with retries and error handling"""

import datetime
import logging
import os
import socket
import time

from requests import Response
from requests.exceptions import ConnectionError
from tzlocal import get_localzone

# Import the constants object so that we can mock WAIT_SECONDS in tests
from icloudpd import constants
from pyicloud_ipd.asset_version import AssetVersion
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.exceptions import PyiCloudAPIResponseException
from pyicloud_ipd.services.photos import PhotoAsset
from pyicloud_ipd.version_size import VersionSize


def update_mtime(created: datetime.datetime, download_path: str) -> None:
    """Set the modification time of the downloaded file to the photo creation date"""
    if created:
        created_date = None
        try:
            created_date = created.astimezone(get_localzone())
        except (ValueError, OSError):
            # We already show the timezone conversion error in base.py,
            # when generating the download directory.
            # So just return silently without touching the mtime.
            return
        set_utime(download_path, created_date)


def set_utime(download_path: str, created_date: datetime.datetime) -> None:
    """Set date & time of the file"""
    ctime = time.mktime(created_date.timetuple())
    os.utime(download_path, (ctime, ctime))


def mkdirs_for_path(logger: logging.Logger, download_path: str) -> bool:
    """Creates hierarchy of folders for file path if it needed"""
    try:
        # get back the directory for the file to be downloaded and create it if
        # not there already
        download_dir = os.path.dirname(download_path)
        os.makedirs(name=download_dir, exist_ok=True)
        return True
    except OSError:
        logger.error(
            "Could not create folder %s",
            download_dir,
        )
        return False


def mkdirs_for_path_dry_run(logger: logging.Logger, download_path: str) -> bool:
    """DRY Run for Creating hierarchy of folders for file path"""
    download_dir = os.path.dirname(download_path)
    if not os.path.exists(download_dir):
        logger.debug(
            "[DRY RUN] Would create folder hierarchy %s",
            download_dir,
        )
    return True


def download_response_to_path(
    _logger: logging.Logger, response: Response, download_path: str, created_date: datetime.datetime
) -> bool:
    """Saves response content into file with desired created date"""
    temp_download_path = download_path + ".part"
    with open(temp_download_path, "wb") as file_obj:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                file_obj.write(chunk)
    os.rename(temp_download_path, download_path)
    update_mtime(created_date, download_path)
    return True


def download_response_to_path_dry_run(
    logger: logging.Logger,
    _response: Response,
    download_path: str,
    _created_date: datetime.datetime,
) -> bool:
    """Pretends to save response content into a file with desired created date"""
    logger.info(
        "[DRY RUN] Would download %s",
        download_path,
    )
    return True


def download_media(
    logger: logging.Logger,
    dry_run: bool,
    icloud: PyiCloudService,
    photo: PhotoAsset,
    download_path: str,
    version: AssetVersion,
    size: VersionSize,
) -> bool:
    """Download the photo to path, with retries and error handling"""

    mkdirs_local = mkdirs_for_path_dry_run if dry_run else mkdirs_for_path
    download_local = download_response_to_path_dry_run if dry_run else download_response_to_path

    if not mkdirs_local(logger, download_path):
        return False

    for retries in range(constants.MAX_RETRIES):
        try:
            photo_response = photo.download(version.url)
            if photo_response:
                return download_local(logger, photo_response, download_path, photo.created)

            logger.error(
                "Could not find URL to download %s for size %s", version.filename, size.value
            )
            break

        except (ConnectionError, socket.timeout, PyiCloudAPIResponseException) as ex:
            if "Invalid global session" in str(ex):
                logger.error("Session error, re-authenticating...")
                if retries > 0:
                    # If the first re-authentication attempt failed,
                    # start waiting a few seconds before retrying in case
                    # there are some issues with the Apple servers
                    time.sleep(constants.WAIT_SECONDS)

                icloud.authenticate()
            else:
                # you end up here when p.e. throttling by Apple happens
                wait_time = (retries + 1) * constants.WAIT_SECONDS
                logger.error(
                    "Error downloading %s, retrying after %s seconds...", photo.filename, wait_time
                )
                time.sleep(wait_time)

        except OSError:
            logger.error(
                "IOError while writing file to %s. "
                + "You might have run out of disk space, or the file "
                + "might be too large for your OS. "
                + "Skipping this file...",
                download_path,
            )
            break
    else:
        logger.error(
            "Could not download %s. Please try again later.",
            photo.filename,
        )

    return False
