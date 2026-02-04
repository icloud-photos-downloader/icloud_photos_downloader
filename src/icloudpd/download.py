"""Handles file downloads with retries and error handling"""

import base64
import datetime
import logging
import os
import time
from functools import partial
from typing import Callable

from requests import Response
from tzlocal import get_localzone

# Import the constants object so that we can mock WAIT_SECONDS in tests
from icloudpd import constants
from icloudpd.metrics import MetricsCollector, NoOpCollector
from pyicloud_ipd.asset_version import AssetVersion, calculate_version_filename
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
    try:
        ctime = time.mktime(created_date.timetuple())
    except OverflowError:
        ctime = time.mktime(datetime.datetime(1970, 1, 1, 0, 0, 0).timetuple())
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
    response: Response,
    temp_download_path: str,
    append_mode: bool,
    download_path: str,
    created_date: datetime.datetime,
) -> bool:
    """Saves response content into file with desired created date"""
    with open(temp_download_path, ("ab" if append_mode else "wb")) as file_obj:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                file_obj.write(chunk)
    os.rename(temp_download_path, download_path)
    update_mtime(created_date, download_path)
    return True


def download_response_to_path_dry_run(
    logger: logging.Logger,
    _response: Response,
    _temp_download_path: str,
    _append_mode: bool,
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
    filename_builder: Callable[[PhotoAsset], str],
    metrics: MetricsCollector | None = None,
) -> bool:
    """Download the photo to path, with retries and error handling"""

    # Use NoOpCollector if no metrics provided for backwards compatibility
    if metrics is None:
        metrics = NoOpCollector()

    size_label = size.value if hasattr(size, "value") else str(size)

    mkdirs_local = mkdirs_for_path_dry_run if dry_run else mkdirs_for_path
    if not mkdirs_local(logger, download_path):
        metrics.inc("downloads_total", labels={"status": "failure", "size": size_label})
        return False

    checksum = base64.b64decode(version.checksum)
    checksum32 = base64.b32encode(checksum).decode()
    download_dir = os.path.dirname(download_path)
    temp_download_path = os.path.join(download_dir, checksum32) + ".part"

    download_local = (
        partial(download_response_to_path_dry_run, logger) if dry_run else download_response_to_path
    )

    retries = 0
    download_start_time = time.perf_counter()
    while True:
        try:
            append_mode = os.path.exists(temp_download_path)
            current_size = os.path.getsize(temp_download_path) if append_mode else 0
            if append_mode:
                logger.debug(f"Resuming downloading of {download_path} from {current_size}")

            photo_response = photo.download(icloud.photos.session, version.url, current_size)
            if photo_response.ok:
                result = download_local(
                    photo_response, temp_download_path, append_mode, download_path, photo.created
                )
                if result:
                    # Record successful download metrics
                    download_duration = time.perf_counter() - download_start_time
                    metrics.observe(
                        "download_duration_seconds", download_duration, labels={"size": size_label}
                    )
                    metrics.inc("downloads_total", labels={"status": "success", "size": size_label})
                    # Track bytes downloaded (version.size is the file size)
                    if hasattr(version, "size") and version.size:
                        metrics.inc(
                            "download_bytes_total",
                            value=float(version.size),
                            labels={"size": size_label},
                        )
                return result
            else:
                # Use the standard original filename generator for error logging
                from icloudpd.base import lp_filename_original as simple_lp_filename_generator

                # Get the proper filename using filename_builder
                base_filename = filename_builder(photo)
                version_filename = calculate_version_filename(
                    base_filename, version, size, simple_lp_filename_generator, photo.item_type
                )
                logger.error(
                    "Could not find URL to download %s for size %s",
                    version_filename,
                    size.value,
                )
                metrics.inc("downloads_total", labels={"status": "failure", "size": size_label})
                break

        except PyiCloudAPIResponseException as ex:
            if "Invalid global session" in str(ex):
                logger.error("Session error, re-authenticating...")
                metrics.inc("download_retries_total", labels={"reason": "session"})
                if retries > 0:
                    # If the first re-authentication attempt failed,
                    # start waiting a few seconds before retrying in case
                    # there are some issues with the Apple servers
                    time.sleep(constants.WAIT_SECONDS)

                icloud.authenticate()
            else:
                # short circuiting 0 retries
                if retries == constants.MAX_RETRIES:
                    break
                # you end up here when p.e. throttling by Apple happens
                metrics.inc("download_retries_total", labels={"reason": "throttle"})
                wait_time = (retries + 1) * constants.WAIT_SECONDS
                # Get the proper filename for error messages
                error_filename = filename_builder(photo)
                logger.error(
                    "Error downloading %s, retrying after %s seconds...", error_filename, wait_time
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
            metrics.inc("download_retries_total", labels={"reason": "io"})
            metrics.inc("downloads_total", labels={"status": "failure", "size": size_label})
            break
        retries = retries + 1
        if retries >= constants.MAX_RETRIES:
            break
    if retries >= constants.MAX_RETRIES:
        # Get the proper filename for error messages
        error_filename = filename_builder(photo)
        logger.error(
            "Could not download %s. Please try again later.",
            error_filename,
        )
        metrics.inc("downloads_total", labels={"status": "failure", "size": size_label})

    return False
