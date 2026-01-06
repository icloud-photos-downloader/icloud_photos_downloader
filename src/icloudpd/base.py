#!/usr/bin/env python
"""Main script that uses Click to parse command-line arguments"""

import datetime
import getpass
import itertools
import json
import logging
import os
import subprocess
import sys
import time
import typing
import urllib
from functools import partial, singledispatch
from logging import Logger
from multiprocessing import freeze_support
from threading import Thread
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
)

from requests.exceptions import (
    ChunkedEncodingError,
    ContentDecodingError,
    StreamConsumedError,
    UnrewindableBodyError,
)
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from tzlocal import get_localzone

from foundation.core import compose, identity, map_, partial_1_1
from icloudpd import download, exif_datetime
from icloudpd.authentication import authenticator
from icloudpd.autodelete import autodelete_photos
from icloudpd.config import GlobalConfig, UserConfig
from icloudpd.counter import Counter
from icloudpd.email_notifications import send_2sa_notification
from icloudpd.filename_policies import build_filename_with_policies, create_filename_builder
from icloudpd.file_cache import FileCache
from icloudpd.log_level import LogLevel
from icloudpd.mfa_provider import MFAProvider
from icloudpd.password_provider import PasswordProvider
from icloudpd.paths import local_download_path, remove_unicode_chars
from icloudpd.server import serve_app
from icloudpd.status import Status, StatusExchange
from icloudpd.string_helpers import parse_timestamp_or_timedelta, truncate_middle
from icloudpd.xmp_sidecar import generate_xmp_file
from pyicloud_ipd.asset_version import add_suffix_to_filename, calculate_version_filename
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.exceptions import (
    PyiCloud2SARequiredException,
    PyiCloudAPIResponseException,
    PyiCloudConnectionErrorException,
    PyiCloudFailedLoginException,
    PyiCloudFailedMFAException,
    PyiCloudServiceNotActivatedException,
    PyiCloudServiceUnavailableException,
)
from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.item_type import AssetItemType  # fmt: skip
from pyicloud_ipd.live_photo_mov_filename_policy import LivePhotoMovFilenamePolicy
from pyicloud_ipd.raw_policy import RawTreatmentPolicy
from pyicloud_ipd.services.photos import (
    PhotoAlbum,
    PhotoAsset,
    PhotoLibrary,
)
from pyicloud_ipd.utils import (
    disambiguate_filenames,
    get_password_from_keyring,
    size_to_suffix,
    store_password_in_keyring,
)
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize

freeze_support()  # fmt: skip # fixing tqdm on macos


def build_filename_cleaner(keep_unicode: bool) -> Callable[[str], str]:
    """Build filename cleaner based on unicode preference.

    Args:
        keep_unicode: If True, preserve Unicode characters. If False, remove non-ASCII characters.

    Returns:
        Function that processes filenames according to unicode preference.
        Note: Basic filesystem character cleaning (clean_filename) is always applied in calculate_filename.
    """
    if keep_unicode:
        # Only basic cleaning is needed (already applied in calculate_filename)
        return identity
    else:
        # Apply unicode removal in addition to basic cleaning
        return remove_unicode_chars


def lp_filename_concatinator(filename: str) -> str:
    """Generate concatenator-style live photo filename, adding HEVC suffix for HEIC files"""
    import os

    from foundation.core import compose
    from foundation.string_utils import endswith, lower

    name, ext = os.path.splitext(filename)
    if not ext:
        return filename

    is_heic = compose(endswith(".heic"), lower)(ext)
    return name + ("_HEVC.MOV" if is_heic else ".MOV")


def lp_filename_original(filename: str) -> str:
    """Generate original-style live photo filename by replacing extension with .MOV"""
    from foundation.string_utils import replace_extension

    replace_with_mov = replace_extension(".MOV")
    return replace_with_mov(filename)


def ask_password_in_console(_user: str) -> str | None:
    return getpass.getpass(f"iCloud Password for {_user}:")


def get_password_from_webui(
    logger: Logger, status_exchange: StatusExchange, _user: str
) -> str | None:
    """Request two-factor authentication through Webui."""
    if not status_exchange.replace_status(Status.NO_INPUT_NEEDED, Status.NEED_PASSWORD):
        logger.error("Expected NO_INPUT_NEEDED, but got something else")
        return None

    # wait for input
    while True:
        status = status_exchange.get_status()
        if status == Status.NEED_PASSWORD:
            time.sleep(1)
        else:
            break
    if status_exchange.replace_status(Status.SUPPLIED_PASSWORD, Status.CHECKING_PASSWORD):
        password = status_exchange.get_payload()
        if not password:
            logger.error("Internal error: did not get password for SUPPLIED_PASSWORD status")
            status_exchange.replace_status(
                Status.CHECKING_PASSWORD, Status.NO_INPUT_NEEDED
            )  # TODO Error
            return None
        return password

    return None  # TODO


def update_password_status_in_webui(status_exchange: StatusExchange, _u: str, _p: str) -> None:
    status_exchange.replace_status(Status.CHECKING_PASSWORD, Status.NO_INPUT_NEEDED)


def update_auth_error_in_webui(status_exchange: StatusExchange, error: str) -> bool:
    return status_exchange.set_error(error)


# def get_click_param_by_name(_name: str, _params: List[Parameter]) -> Optional[Parameter]:
#     _with_password = [_p for _p in _params if _name in _p.name]
#     if len(_with_password) == 0:
#         return None
#     return _with_password[0]


def dummy_password_writter(_u: str, _p: str) -> None:
    pass


def keyring_password_writter(logger: Logger) -> Callable[[str, str], None]:
    def _intern(username: str, password: str) -> None:
        try:
            store_password_in_keyring(username, password)
        except Exception:
            logger.warning("Password was not saved to keyring")

    return _intern


def skip_created_generator(
    name: str, formatted: str | None
) -> datetime.datetime | datetime.timedelta | None:
    """Converts ISO dates to datetime and interval in days to timeinterval using supplied name as part of raised exception in case of the error"""
    if formatted is None:
        return None
    result = parse_timestamp_or_timedelta(formatted)
    if result is None:
        raise ValueError(f"{name} parameter did not parse ISO timestamp or interval successfully")
    if isinstance(result, datetime.datetime):
        return ensure_tzinfo(get_localzone(), result)
    return result


def ensure_tzinfo(tz: datetime.tzinfo, input: datetime.datetime) -> datetime.datetime:
    if input.tzinfo is None:
        return input.astimezone(tz)
    return input


# Must import the constants object so that we can mock values in tests.


def create_logger(config: GlobalConfig) -> logging.Logger:
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    logger = logging.getLogger("icloudpd")
    if config.only_print_filenames:
        logger.disabled = True
    else:
        # Need to make sure disabled is reset to the correct value,
        # because the logger instance is shared between tests.
        logger.disabled = False
        if config.log_level == LogLevel.DEBUG:
            logger.setLevel(logging.DEBUG)
        elif config.log_level == LogLevel.INFO:
            logger.setLevel(logging.INFO)
        elif config.log_level == LogLevel.ERROR:
            logger.setLevel(logging.ERROR)
        else:
            # Developer's error - not an exhaustive match
            raise ValueError(f"Unsupported logging level {config.log_level}")
    return logger


def run_with_configs(global_config: GlobalConfig, user_configs: Sequence[UserConfig]) -> int:
    """Run the application with the new configuration system"""

    # Create shared logger
    logger = create_logger(global_config)

    # Create shared status exchange for web server and progress tracking
    shared_status_exchange = StatusExchange()

    # Check if any user needs web server (webui for MFA or passwords)
    needs_web_server = global_config.mfa_provider == MFAProvider.WEBUI or any(
        provider == PasswordProvider.WEBUI for provider in global_config.password_providers
    )

    # Start Telegram bot if configured (before web server to pass it if needed)
    telegram_bot = None
    if global_config.telegram_polling and global_config.telegram_token and global_config.telegram_chat_id:
        from icloudpd.telegram_bot import TelegramBot
        telegram_bot = TelegramBot(
            logger,
            global_config.telegram_token,
            global_config.telegram_chat_id,
            shared_status_exchange,
            global_config.telegram_polling_interval,
            global_config.telegram_webhook_url,
        )
        telegram_bot.start_polling()
        # Store telegram bot reference in status_exchange for auth requests
        shared_status_exchange.set_telegram_bot(telegram_bot)

    # Start web server ONCE if needed, outside all loops
    # Pass telegram_bot if available for webhook support
    # Use webhook port if Telegram webhook is configured, otherwise default port 8080
    webhook_port = (
        global_config.telegram_webhook_port
        if telegram_bot and telegram_bot.webhook_url
        else 8080
    )
    if needs_web_server or telegram_bot:
        if needs_web_server:
            logger.info(f"Starting web server for WebUI authentication on port {webhook_port}...")
        if telegram_bot and telegram_bot.webhook_url:
            logger.info(f"Starting web server for Telegram webhooks on port {webhook_port}...")
        server_thread = Thread(
            target=serve_app,
            daemon=True,
            args=[logger, shared_status_exchange, telegram_bot, webhook_port],
        )
        server_thread.start()

    # Check if we're in watch mode
    watch_interval = global_config.watch_with_interval
    
    # Set watch_interval in progress for status messages (even before first sync)
    if watch_interval:
        shared_status_exchange.get_progress().watch_interval = watch_interval
        # Set initial sync time to now so we can calculate time until first sync
        import time
        shared_status_exchange.get_progress().last_sync_time = time.time()

    if not watch_interval:
        # No watch mode - process each user once and exit
        return _process_all_users_once(global_config, user_configs, logger, shared_status_exchange, telegram_bot)
    else:
        # Watch mode - infinite loop processing all users, then wait
        skip_bar = not os.environ.get("FORCE_TQDM") and (
            global_config.only_print_filenames
            or global_config.no_progress_bar
            or not sys.stdout.isatty()
        )

        while True:
            # Check if resume was requested before processing (might have been set while waiting)
            if shared_status_exchange.get_progress().resume:
                logger.info("Sync requested, starting immediately...")
                shared_status_exchange.get_progress().resume = False  # Clear resume flag
            
            # Process all user configs in this iteration
            result = _process_all_users_once(
                global_config, user_configs, logger, shared_status_exchange, telegram_bot
            )

            # If any critical operation (auth-only, list commands) succeeded, exit
            if result == 0:
                first_user = user_configs[0] if user_configs else None
                if first_user and (
                    first_user.auth_only or first_user.list_albums or first_user.list_libraries
                ):
                    return 0

            # Wait for the watch interval before next iteration
            # Clear current user during wait period to avoid misleading UI
            shared_status_exchange.clear_current_user()
            logger.info(f"Waiting for {watch_interval} sec...")
            interval: Sequence[int] = range(1, watch_interval)
            iterable: Sequence[int] = (
                interval
                if skip_bar
                else typing.cast(
                    Sequence[int],
                    tqdm(
                        iterable=interval,
                        desc="Waiting...",
                        ascii=True,
                        leave=False,
                        dynamic_ncols=True,
                    ),
                )
            )
            for counter in iterable:
                # Update shared status exchange with wait progress
                shared_status_exchange.get_progress().waiting = watch_interval - counter
                if shared_status_exchange.get_progress().resume:
                    logger.info("Sync requested, breaking wait loop...")
                    shared_status_exchange.get_progress().resume = False  # Clear resume flag
                    shared_status_exchange.get_progress().waiting = 0  # Clear waiting
                    break
                time.sleep(1)
            
            # Check if resume was requested (might have been set while processing)
            if shared_status_exchange.get_progress().resume:
                logger.info("Sync requested, starting immediately...")
                shared_status_exchange.get_progress().resume = False  # Clear resume flag


def _process_all_users_once(
    global_config: GlobalConfig,
    user_configs: Sequence[UserConfig],
    logger: logging.Logger,
    shared_status_exchange: StatusExchange,
    telegram_bot: Optional[Any] = None,
) -> int:
    """Process all user configs once (used by both single run and watch mode)"""

    # Set global config and all user configs to status exchange once, before processing
    shared_status_exchange.set_global_config(global_config)
    shared_status_exchange.set_user_configs(user_configs)

    for user_config in user_configs:
        with logging_redirect_tqdm():
            # Use shared status exchange instead of creating new ones per user
            status_exchange = shared_status_exchange

            # Set up password providers with proper function replacements
            password_providers_dict: Dict[
                PasswordProvider, Tuple[Callable[[str], str | None], Callable[[str, str], None]]
            ] = {}

            for provider in global_config.password_providers:
                if provider == PasswordProvider.WEBUI:
                    password_providers_dict[provider] = (
                        partial(get_password_from_webui, logger, status_exchange),
                        partial(update_password_status_in_webui, status_exchange),
                    )
                elif provider == PasswordProvider.CONSOLE:
                    password_providers_dict[provider] = (
                        ask_password_in_console,
                        dummy_password_writter,
                    )
                elif provider == PasswordProvider.KEYRING:
                    password_providers_dict[provider] = (
                        get_password_from_keyring,
                        keyring_password_writter(logger),
                    )
                elif provider == PasswordProvider.PARAMETER:

                    def create_constant_password_provider(
                        password: str | None,
                    ) -> Callable[[str], str | None]:
                        def password_provider(_username: str) -> str | None:
                            return password

                        return password_provider

                    password_providers_dict[provider] = (
                        create_constant_password_provider(user_config.password),
                        dummy_password_writter,
                    )

            # Only set current user - global config and user configs are already set
            status_exchange.set_current_user(user_config.username)

            # Web server is now started once outside the user loop - no need to start it here

            # Set up filename processors directly since we don't have click context
            # filename_cleaner was removed from services and should be passed explicitly to functions that need it

            # Set up live photo filename generator directly
            lp_filename_generator = (
                lp_filename_original
                if user_config.live_photo_mov_filename_policy == LivePhotoMovFilenamePolicy.ORIGINAL
                else lp_filename_concatinator
            )

            # Set up filename cleaner based on user preference
            filename_cleaner = build_filename_cleaner(user_config.keep_unicode_in_filenames)

            # Create filename builder with pre-configured policy and cleaner
            filename_builder = create_filename_builder(
                user_config.file_match_policy, filename_cleaner
            )

            # Set up function builders
            passer = partial(
                where_builder,
                logger,
                user_config.skip_videos,
                user_config.skip_created_before,
                user_config.skip_created_after,
                user_config.skip_photos,
                filename_builder,
            )

            # Initialize file cache only for sync date tracking (not for file caching)
            file_cache: FileCache | None = None
            if user_config.directory is not None:
                # Create cache database path in the cookie directory or config directory
                # We only use it for storing last sync date, not for file caching
                cache_dir = user_config.cookie_directory or os.path.dirname(user_config.directory)
                cache_db_path = os.path.join(cache_dir, "file_cache.db")
                file_cache = FileCache(cache_db_path, logger)
                
                # Reset force_full_sync flag after checking
                status_exchange.set_force_full_sync(False)

            # Create downloader partial - file_cache and use_cache will be passed later
            # We need to create a wrapper that captures file_cache and use_cache
            if user_config.directory is not None:
                download_builder_partial = partial(
                    download_builder,
                    logger,
                    user_config.folder_structure,
                    user_config.directory,
                    user_config.sizes,
                    user_config.force_size,
                    global_config.only_print_filenames,
                    user_config.set_exif_datetime,
                    user_config.skip_live_photos,
                    user_config.live_photo_size,
                    user_config.dry_run,
                    user_config.file_match_policy,
                    user_config.xmp_sidecar,
                    lp_filename_generator,
                    filename_builder,
                    user_config.align_raw,
                )
                # Create a wrapper (file_cache no longer used for file caching, only for sync date)
                # total_photos and start_time will be set later when we know the actual count
                def downloader_wrapper(icloud: PyiCloudService, counter: Counter, photo: PhotoAsset, total_photos: int | None = None, start_time: float | None = None) -> bool:
                    return download_builder_partial(icloud, counter, photo, file_cache=None, total_photos=total_photos, start_time=start_time)
                downloader = downloader_wrapper
            else:
                downloader = lambda _s, _c, _p: False

            notificator = partial(
                notificator_builder,
                logger,
                user_config.username,
                user_config.smtp_username,
                user_config.smtp_password,
                user_config.smtp_host,
                user_config.smtp_port,
                user_config.smtp_no_tls,
                user_config.notification_email,
                user_config.notification_email_from,
                str(user_config.notification_script) if user_config.notification_script else None,
            )

            # Use core_single_run since we've disabled watch at this level
            logger.info(f"Processing user: {user_config.username}")
            result = core_single_run(
                logger,
                status_exchange,
                global_config,
                user_config,
                password_providers_dict,
                passer,
                downloader,
                notificator,
                lp_filename_generator,
                file_cache,  # Only used for sync date tracking, not for file caching
                filename_builder,
                telegram_bot,
            )

            # If any user config fails and we're not in watch mode, return the error code
            if result != 0:
                if not global_config.watch_with_interval:
                    return result
                else:
                    # In watch mode, log error and continue with next user
                    logger.error(
                        f"Error processing user {user_config.username}, continuing with next user..."
                    )

    return 0


def notificator_builder(
    logger: logging.Logger,
    username: str,
    smtp_username: str | None,
    smtp_password: str | None,
    smtp_host: str,
    smtp_port: int,
    smtp_no_tls: bool,
    notification_email: str | None,
    notification_email_from: str | None,
    notification_script: str | None,
) -> None:
    try:
        if notification_script is not None:
            logger.debug("Executing notification script...")
            subprocess.call([notification_script])
        else:
            pass
        if smtp_username is not None or notification_email is not None:
            send_2sa_notification(
                logger,
                username,
                smtp_username,
                smtp_password,
                smtp_host,
                smtp_port,
                smtp_no_tls,
                notification_email,
                notification_email_from,
            )
        else:
            pass
    except Exception as error:
        logger.error("Notification of the required MFA failed")
        logger.debug(error)


@singledispatch
def offset_to_datetime(offset: Any) -> datetime.datetime:
    raise NotImplementedError()


@offset_to_datetime.register(datetime.datetime)
def _(offset: datetime.datetime) -> datetime.datetime:
    return offset


@offset_to_datetime.register(datetime.timedelta)
def _(offset: datetime.timedelta) -> datetime.datetime:
    return datetime.datetime.now(get_localzone()) - offset


def where_builder(
    logger: logging.Logger,
    skip_videos: bool,
    skip_created_before: datetime.datetime | datetime.timedelta | None,
    skip_created_after: datetime.datetime | datetime.timedelta | None,
    skip_photos: bool,
    filename_builder: Callable[[PhotoAsset], str],
    photo: PhotoAsset,
) -> bool:
    if skip_videos and photo.item_type == AssetItemType.MOVIE:
        logger.debug(asset_type_skip_message(AssetItemType.IMAGE, filename_builder, photo))
        return False
    if skip_photos and photo.item_type == AssetItemType.IMAGE:
        logger.debug(asset_type_skip_message(AssetItemType.MOVIE, filename_builder, photo))
        return False

    if skip_created_before is not None:
        temp_created_before = offset_to_datetime(skip_created_before)
        if photo.created < temp_created_before:
            logger.debug(skip_created_before_message(temp_created_before, photo, filename_builder))
            return False

    if skip_created_after is not None:
        temp_created_after = offset_to_datetime(skip_created_after)
        if photo.created > temp_created_after:
            logger.debug(skip_created_after_message(temp_created_after, photo, filename_builder))
            return False

    return True


def skip_created_before_message(
    target_created_date: datetime.datetime,
    photo: PhotoAsset,
    filename_builder: Callable[[PhotoAsset], str],
) -> str:
    filename = filename_builder(photo)
    return f"Skipping {filename}, as it was created {photo.created}, before {target_created_date}."


def skip_created_after_message(
    target_created_date: datetime.datetime,
    photo: PhotoAsset,
    filename_builder: Callable[[PhotoAsset], str],
) -> str:
    filename = filename_builder(photo)
    return f"Skipping {filename}, as it was created {photo.created}, after {target_created_date}."


def download_builder(
    logger: logging.Logger,
    folder_structure: str,
    directory: str,
    primary_sizes: Sequence[AssetVersionSize],
    force_size: bool,
    only_print_filenames: bool,
    set_exif_datetime: bool,
    skip_live_photos: bool,
    live_photo_size: LivePhotoVersionSize,
    dry_run: bool,
    file_match_policy: FileMatchPolicy,
    xmp_sidecar: bool,
    lp_filename_generator: Callable[[str], str],
    filename_builder: Callable[[PhotoAsset], str],
    raw_policy: RawTreatmentPolicy,
    icloud: PyiCloudService,
    counter: Counter,
    photo: PhotoAsset,
    file_cache: FileCache | None = None,  # Not used anymore, kept for compatibility
    total_photos: int | None = None,  # Total photos to process (for counter display)
    start_time: float | None = None,  # Start time for rate calculation
) -> bool:
    """function for actually downloading the photos"""

    try:
        created_date = photo.created.astimezone(get_localzone())
    except (ValueError, OSError):
        logger.error("Could not convert photo created date to local timezone (%s)", photo.created)
        created_date = photo.created

    from foundation.core import compose
    from foundation.string_utils import eq, lower

    is_none_folder = compose(eq("none"), lower)

    if is_none_folder(folder_structure):
        date_path = ""
    else:
        try:
            date_path = folder_structure.format(created_date)
        except ValueError:  # pragma: no cover
            # This error only seems to happen in Python 2
            logger.error("Photo created date was not valid (%s)", photo.created)
            # e.g. ValueError: year=5 is before 1900
            # (https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues/122)
            # Just use the Unix epoch
            created_date = datetime.datetime.fromtimestamp(0)
            date_path = folder_structure.format(created_date)

    try:
        versions, filename_overrides = disambiguate_filenames(
            photo.versions_with_raw_policy(raw_policy), primary_sizes, photo, lp_filename_generator
        )
    except KeyError as ex:
        print(f"KeyError: {ex} attribute was not found in the photo fields.")
        with open(file="icloudpd-photo-error.json", mode="w", encoding="utf8") as outfile:
            json.dump(
                {
                    "master_record": photo._master_record,
                    "asset_record": photo._asset_record,
                },
                outfile,
            )
        print("icloudpd has saved the photo record to: ./icloudpd-photo-error.json")
        print("Please create a Gist with the contents of this file: https://gist.github.com")
        print(
            "Then create an issue on GitHub: "
            "https://github.com/icloud-photos-downloader/icloud_photos_downloader/issues"
        )
        print("Include a link to the Gist in your issue, so that we can see what went wrong.\n")
        return False

    download_dir = os.path.normpath(os.path.join(directory, date_path))
    success = False

    for download_size in primary_sizes:
        if download_size not in versions and download_size != AssetVersionSize.ORIGINAL:
            if force_size:
                error_filename = filename_builder(photo)
                logger.error(
                    "%s size does not exist for %s. Skipping...",
                    download_size.value,
                    error_filename,
                )
                continue
            if AssetVersionSize.ORIGINAL in primary_sizes:
                continue  # that should avoid double download for original
            download_size = AssetVersionSize.ORIGINAL

        version = versions[download_size]
        photo_filename = filename_builder(photo)
        filename = calculate_version_filename(
            photo_filename,
            version,
            download_size,
            lp_filename_generator,
            photo.item_type,
            filename_overrides.get(download_size),
        )

        download_path = local_download_path(filename, download_dir)

        original_download_path = None
        # Check if file exists using os.path.isfile() (no cache)
        file_exists = os.path.isfile(download_path)
        if not file_exists and download_size == AssetVersionSize.ORIGINAL:
            # Deprecation - We used to download files like IMG_1234-original.jpg,
            # so we need to check for these.
            # Now we match the behavior of iCloud for Windows: IMG_1234.jpg
            original_download_path = add_suffix_to_filename("-original", download_path)
            file_exists = os.path.isfile(original_download_path)

        if file_exists:
            # Only do additional checks for deduplication
            if file_match_policy == FileMatchPolicy.NAME_SIZE_DEDUP_WITH_SUFFIX:
                # for later: this crashes if download-size medium is specified
                file_size = os.stat(original_download_path or download_path).st_size
                photo_size = version.size
                if file_size != photo_size:
                    download_path = (f"-{photo_size}.").join(download_path.rsplit(".", 1))
                    logger.debug("%s deduplicated", truncate_middle(download_path, 96))
                    # Check again with os.path.isfile() (not using cache here)
                    file_exists = os.path.isfile(download_path)
            if file_exists:
                counter.increment()
                # Only show "already exists" when using is_file (not cache)
                current_count = counter.value()
                counter_text = ""
                if total_photos is not None and start_time is not None:
                    elapsed = time.time() - start_time
                    rate = current_count / elapsed if elapsed > 0 else 0.0
                    counter_text = f" ({current_count}/{total_photos}) (Rate: {rate:.2f} items/s)"
                logger.debug("%s already exists%s", truncate_middle(download_path, 96), counter_text)

        if not file_exists:
            counter.reset()
            if only_print_filenames:
                print(download_path)
            else:
                truncated_path = truncate_middle(download_path, 96)
                logger.debug("Downloading %s...", truncated_path)

                download_result = download.download_media(
                    logger,
                    dry_run,
                    icloud,
                    photo,
                    download_path,
                    version,
                    download_size,
                    filename_builder,
                )
                success = download_result

                if download_result:
                    from foundation.core import compose
                    from foundation.string_utils import endswith, lower

                    is_jpeg = compose(endswith((".jpg", ".jpeg")), lower)

                    if (
                        not dry_run
                        and set_exif_datetime
                        and is_jpeg(filename)
                        and not exif_datetime.get_photo_exif(logger, download_path)
                    ):
                        # %Y:%m:%d looks wrong, but it's the correct format
                        date_str = created_date.strftime("%Y-%m-%d %H:%M:%S%z")
                        logger.debug("Setting EXIF timestamp for %s: %s", download_path, date_str)
                        exif_datetime.set_photo_exif(
                            logger,
                            download_path,
                            created_date.strftime("%Y:%m:%d %H:%M:%S"),
                        )
                    if not dry_run:
                        download.set_utime(download_path, created_date)
                    logger.info("Downloaded %s", truncated_path)

        if xmp_sidecar:
            generate_xmp_file(logger, download_path, photo._asset_record, dry_run)

    # Also download the live photo if present
    if not skip_live_photos:
        lp_size = live_photo_size
        photo_versions_with_policy = photo.versions_with_raw_policy(raw_policy)
        if lp_size in photo_versions_with_policy:
            version = photo_versions_with_policy[lp_size]
            lp_photo_filename = filename_builder(photo)
            lp_filename = calculate_version_filename(
                lp_photo_filename,
                version,
                lp_size,
                lp_filename_generator,
                photo.item_type,
            )
            if live_photo_size != LivePhotoVersionSize.ORIGINAL:
                # Add size to filename if not original
                lp_filename = add_suffix_to_filename(
                    size_to_suffix(live_photo_size),
                    lp_filename,
                )
            else:
                pass
            lp_download_path = os.path.join(download_dir, lp_filename)

            # Use cache if available and enabled, otherwise use os.path.isfile()
            # verify_disk=True only when use_cache=False (e.g., /syncall command)
            if file_cache is not None and use_cache:
                lp_file_exists = file_cache.file_exists(lp_download_path, verify_disk=False)
                # If file not in cache but exists on disk, add it to cache silently
                if not lp_file_exists and os.path.isfile(lp_download_path):
                    file_cache.add_file(lp_download_path)
                    lp_file_exists = True
            else:
                lp_file_exists = os.path.isfile(lp_download_path)

            if only_print_filenames:
                if not lp_file_exists:
                    print(lp_download_path)
                # Handle deduplication case for only_print_filenames
                if (
                    lp_file_exists
                    and file_match_policy == FileMatchPolicy.NAME_SIZE_DEDUP_WITH_SUFFIX
                ):
                    lp_file_size = os.stat(lp_download_path).st_size
                    lp_photo_size = version.size
                    if lp_file_size != lp_photo_size:
                        lp_download_path = (f"-{lp_photo_size}.").join(
                            lp_download_path.rsplit(".", 1)
                        )
                        logger.debug("%s deduplicated", truncate_middle(lp_download_path, 96))
                        # Print the deduplicated filename but don't download
                        print(lp_download_path)
            else:
                if lp_file_exists:
                    # Only do additional checks for deduplication
                    if file_match_policy == FileMatchPolicy.NAME_SIZE_DEDUP_WITH_SUFFIX:
                        lp_file_size = os.stat(lp_download_path).st_size
                        lp_photo_size = version.size
                        if lp_file_size != lp_photo_size:
                            lp_download_path = (f"-{lp_photo_size}.").join(
                                lp_download_path.rsplit(".", 1)
                            )
                            logger.debug("%s deduplicated", truncate_middle(lp_download_path, 96))
                            # Check again with os.path.isfile()
                            lp_file_exists = os.path.isfile(lp_download_path)
                    if lp_file_exists:
                        # For live photos, use the same counter and rate info
                        current_count = counter.value()
                        counter_text = ""
                        if total_photos is not None and start_time is not None:
                            elapsed = time.time() - start_time
                            rate = current_count / elapsed if elapsed > 0 else 0.0
                            counter_text = f" ({current_count}/{total_photos}) (Rate: {rate:.2f} items/s)"
                        logger.debug("%s already exists%s", truncate_middle(lp_download_path, 96), counter_text)
                if not lp_file_exists:
                    truncated_path = truncate_middle(lp_download_path, 96)
                    logger.debug("Downloading %s...", truncated_path)
                    download_result = download.download_media(
                        logger,
                        dry_run,
                        icloud,
                        photo,
                        lp_download_path,
                        version,
                        lp_size,
                        filename_builder,
                    )
                    success = download_result and success
                    if download_result:
                        logger.info("Downloaded %s", truncated_path)
    return success


def delete_photo(
    logger: logging.Logger,
    library_object: PhotoLibrary,
    photo: PhotoAsset,
    filename_builder: Callable[[PhotoAsset], str],
) -> None:
    """Delete a photo from the iCloud account."""
    clean_filename_local = filename_builder(photo)
    logger.debug("Deleting %s in iCloud...", clean_filename_local)
    url = (
        f"{library_object.service_endpoint}/records/modify?"
        f"{urllib.parse.urlencode(library_object.params)}"
    )
    post_data = json.dumps(
        {
            "atomic": True,
            "desiredKeys": ["isDeleted"],
            "operations": [
                {
                    "operationType": "update",
                    "record": {
                        "fields": {"isDeleted": {"value": 1}},
                        "recordChangeTag": photo._asset_record["recordChangeTag"],
                        "recordName": photo._asset_record["recordName"],
                        "recordType": "CPLAsset",
                    },
                }
            ],
            "zoneID": library_object.zone_id,
        }
    )
    library_object.session.post(url, data=post_data, headers={"Content-type": "application/json"})
    logger.info("Deleted %s in iCloud", clean_filename_local)


def delete_photo_dry_run(
    logger: logging.Logger,
    library_object: PhotoLibrary,
    photo: PhotoAsset,
    filename_builder: Callable[[PhotoAsset], str],
) -> None:
    """Dry run for deleting a photo from the iCloud"""
    filename = filename_builder(photo)
    logger.info(
        "[DRY RUN] Would delete %s in iCloud library %s",
        filename,
        library_object.zone_id["zoneName"],
    )


def dump_responses(dumper: Callable[[Any], None], responses: List[Mapping[str, Any]]) -> None:
    # dump captured responses
    for entry in responses:
        # compose(logger.debug, compose(json.dumps, response_to_har))(response)
        dumper(json.dumps(entry, indent=2))


def asset_type_skip_message(
    desired_item_type: AssetItemType,
    filename_builder: Callable[[PhotoAsset], str],
    photo: PhotoAsset,
) -> str:
    photo_video_phrase = "photos" if desired_item_type == AssetItemType.IMAGE else "videos"
    filename = filename_builder(photo)
    return f"Skipping {filename}, only downloading {photo_video_phrase}. (Item type was: {photo.item_type})"


def core_single_run(
    logger: logging.Logger,
    status_exchange: StatusExchange,
    global_config: GlobalConfig,
    user_config: UserConfig,
    password_providers_dict: Dict[
        PasswordProvider, Tuple[Callable[[str], str | None], Callable[[str, str], None]]
    ],
    passer: Callable[[PhotoAsset], bool],
    downloader: Callable[[PyiCloudService, Counter, PhotoAsset], bool],
    notificator: Callable[[], None],
    lp_filename_generator: Callable[[str], str],
    file_cache: FileCache | None = None,
    use_cache: bool = True,
    filename_builder: Callable[[PhotoAsset], str] | None = None,
    telegram_bot: Optional[Any] = None,
) -> int:
    """Download all iCloud photos to a local directory for a single execution (no watch loop)"""

    skip_bar = not os.environ.get("FORCE_TQDM") and (
        global_config.only_print_filenames
        or global_config.no_progress_bar
        or not sys.stdout.isatty()
    )
    while True:  # retry loop (not watch - only for immediate retries)
        captured_responses: List[Mapping[str, Any]] = []

        def append_response(captured: List[Mapping[str, Any]], response: Mapping[str, Any]) -> None:
            captured.append(response)

        try:
            # Check if authentication was requested via Telegram /auth command
            # If so, delete cookies to force re-authentication
            if telegram_bot and hasattr(telegram_bot, '_auth_requested') and telegram_bot._auth_requested:
                telegram_bot._auth_requested = False  # Reset flag
                cookie_dir = user_config.cookie_directory or os.path.expanduser("~/.pyicloud")
                # Delete cookie and session files to force re-authentication
                # Cookie file name is based on username (alphanumeric characters only)
                import re
                cookie_filename = "".join([c for c in user_config.username if re.match(r'\w', c)])
                cookie_path = os.path.join(cookie_dir, cookie_filename)
                session_path = cookie_path + ".session"
                for file_path in [cookie_path, session_path]:
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            logger.info(f"Deleted {file_path} to force re-authentication")
                        except OSError as e:
                            logger.warning(f"Could not delete {file_path}: {e}")
            
            icloud = authenticator(
                logger,
                global_config.domain,
                {
                    provider.value: functions
                    for provider, functions in password_providers_dict.items()
                },
                global_config.mfa_provider,
                status_exchange,
                user_config.username,
                notificator,
                partial(append_response, captured_responses),
                user_config.cookie_directory,
                os.environ.get("CLIENT_ID"),
            )

            # dump captured responses for debugging
            # dump_responses(logger.debug, captured_responses)

            # turn off response capture
            icloud.response_observer = None

            if user_config.auth_only:
                logger.info("Authentication completed successfully")
                return 0

            elif user_config.list_libraries:
                library_names = (
                    icloud.photos.private_libraries.keys() | icloud.photos.shared_libraries.keys()
                )
                print(*library_names, sep="\n")
                return 0

            else:
                # Access to the selected library. Defaults to the primary photos object.
                if user_config.library:
                    if user_config.library in icloud.photos.private_libraries:
                        library_object: PhotoLibrary = icloud.photos.private_libraries[
                            user_config.library
                        ]
                    elif user_config.library in icloud.photos.shared_libraries:
                        library_object = icloud.photos.shared_libraries[user_config.library]
                    else:
                        logger.error("Unknown library: %s", user_config.library)
                        return 1
                else:
                    library_object = icloud.photos

                if user_config.list_albums:
                    print("Albums:")
                    album_titles = [str(a) for a in library_object.albums.values()]
                    print(*album_titles, sep="\n")
                    return 0
                else:
                    if not user_config.directory:
                        # should be checked upstream
                        raise NotImplementedError()
                    else:
                        pass

                    directory = os.path.normpath(user_config.directory)
                    
                    # Create filename_builder if not provided (for backward compatibility)
                    if filename_builder is None:
                        from icloudpd.filename_policies import build_filename_cleaner, create_filename_builder
                        filename_cleaner = build_filename_cleaner(user_config.keep_unicode_in_filenames)
                        filename_builder = create_filename_builder(
                            user_config.file_match_policy, filename_cleaner
                        )

                    if user_config.skip_photos or user_config.skip_videos:
                        photo_video_phrase = "photos" if user_config.skip_videos else "videos"
                    else:
                        photo_video_phrase = "photos and videos"
                    if len(user_config.albums) == 0:
                        album_phrase = ""
                    elif len(user_config.albums) == 1:
                        album_phrase = f" from album {','.join(user_config.albums)}"
                    else:
                        album_phrase = f" from albums {','.join(user_config.albums)}"

                    logger.debug(f"Looking up all {photo_video_phrase}{album_phrase}...")

                    albums: Iterable[PhotoAlbum] = (
                        list(map_(library_object.albums.__getitem__, user_config.albums))
                        if len(user_config.albums) > 0
                        else [library_object.all]
                    )
                    album_lengths: Callable[[Iterable[PhotoAlbum]], Iterable[int]] = partial_1_1(
                        map_, len
                    )

                    def sum_(inp: Iterable[int]) -> int:
                        return sum(inp)

                    photos_count: int | None = compose(sum_, album_lengths)(albums)
                    total_photos_in_icloud = photos_count if photos_count is not None else 0
                    logger.info(f"Found {total_photos_in_icloud} total photos in iCloud")
                    
                    for photo_album in albums:
                        # OPTIMIZATION: Increase page_size to reduce number of HTTP requests
                        # Default is 100, which means 200 records per request (page_size * 2)
                        # Increasing to 500 means 1000 records per request, reducing HTTP calls by 5x
                        if hasattr(photo_album, 'page_size'):
                            original_page_size = photo_album.page_size
                            photo_album.page_size = 500  # Increase from 100 to 500 (1000 records per request)
                            logger.debug(f"Increased page_size from {original_page_size} to {photo_album.page_size} for faster loading")
                        
                        # OPTIMIZATION: Filter by addedDate if not doing full sync and we have a last sync date
                        # This dramatically reduces the number of photos to process
                        # Use 1 day margin to account for timing differences (photo added to device vs uploaded to iCloud)
                        if file_cache is not None and not status_exchange.get_force_full_sync():
                            last_sync_timestamp = file_cache.get_last_sync_date()
                            if last_sync_timestamp:
                                # Subtract 1 day (86400 seconds) as margin for timing differences
                                margin_seconds = 86400  # 1 day
                                last_sync_with_margin = last_sync_timestamp - margin_seconds
                                
                                # Add filter for addedDate >= (last_sync_date - 1 day)
                                # Convert timestamp (seconds) to milliseconds (what iCloud uses)
                                added_date_ms = int(last_sync_with_margin * 1000)
                                
                                # Create or extend query_filter
                                added_date_filter = {
                                    "fieldName": "addedDate",
                                    "fieldValue": {"type": "INT64", "value": added_date_ms},
                                    "comparator": "GREATER_THAN_OR_EQUALS",
                                }
                                
                                if photo_album.query_filter is None:
                                    photo_album.query_filter = [added_date_filter]
                                else:
                                    # Add to existing filters
                                    photo_album.query_filter = list(photo_album.query_filter) + [added_date_filter]
                                
                                last_sync_readable = datetime.datetime.fromtimestamp(last_sync_timestamp).strftime("%Y-%m-%d %H:%M:%S")
                                margin_readable = datetime.datetime.fromtimestamp(last_sync_with_margin).strftime("%Y-%m-%d %H:%M:%S")
                                logger.info(f"🔄 INCREMENTAL SYNC: Filtering photos added since {margin_readable} (last sync: {last_sync_readable}, 1 day margin)")
                                logger.info(f"   This will only process NEW photos, not all {total_photos_in_icloud} photos")
                            else:
                                logger.info("🔄 FULL SYNC: No previous sync date found, processing all photos (first sync)")
                        
                        photos_enumerator: Iterable[PhotoAsset] = photo_album
                        
                        # Note: photos_count is calculated before filter, so it shows total
                        # The actual number of photos returned by Apple after filter will be less
                        # We'll update photos_to_download as we process them
                        photos_to_download = photos_count if photos_count is not None else 0
                        
                        progress = status_exchange.get_progress()
                        progress.total_photos_in_icloud = total_photos_in_icloud
                        progress.photos_to_download = photos_to_download
                        
                        # Send initial message if manual sync
                        if telegram_bot and status_exchange.get_manual_sync():
                            telegram_bot.send_sync_start_message(photos_to_download, total_photos_in_icloud)
                            # Mark that we should send progress updates
                            progress.last_progress_message_time = time.time()
                            # Reset manual sync flag after sending initial message
                            status_exchange.set_manual_sync(False)

                        # Optional: Only download the x most recent photos.
                        if user_config.recent is not None:
                            # Adjust photos_to_download if using recent limit
                            photos_to_download = min(photos_to_download, user_config.recent)
                            progress = status_exchange.get_progress()
                            progress.photos_to_download = photos_to_download
                            photos_count = user_config.recent
                            photos_top: Iterable[PhotoAsset] = itertools.islice(
                                photos_enumerator, user_config.recent
                            )
                        else:
                            photos_top = photos_enumerator

                        if user_config.until_found is not None:
                            photos_count = None
                            # Can't know photos_to_download in advance with until_found
                            progress = status_exchange.get_progress()
                            progress.photos_to_download = 0  # Will be updated dynamically
                            # ensure photos iterator doesn't have a known length
                            # photos_enumerator = (p for p in photos_enumerator)

                        # Skip the one-line progress bar if we're only printing the filenames,
                        # or if the progress bar is explicitly disabled,
                        # or if this is not a terminal (e.g. cron or piping output to file)
                        if skip_bar:
                            photos_bar: Iterable[PhotoAsset] = photos_top
                            # logger.set_tqdm(None)
                        else:
                            photos_bar = tqdm(
                                iterable=photos_top,
                                total=photos_count,
                                leave=False,
                                dynamic_ncols=True,
                                ascii=True,
                            )
                            # logger.set_tqdm(photos_enumerator)

                        if photos_count is not None:
                            plural_suffix = "" if photos_count == 1 else "s"
                            photos_count_str = (
                                "the first" if photos_count == 1 else str(photos_count)
                            )

                            if user_config.skip_photos or user_config.skip_videos:
                                photo_video_phrase = (
                                    "photo" if user_config.skip_videos else "video"
                                ) + plural_suffix
                            else:
                                photo_video_phrase = (
                                    "photo or video" if photos_count == 1 else "photos and videos"
                                )
                        else:
                            photos_count_str = "???"
                            if user_config.skip_photos or user_config.skip_videos:
                                photo_video_phrase = (
                                    "photos" if user_config.skip_videos else "videos"
                                )
                            else:
                                photo_video_phrase = "photos and videos"
                        logger.info(
                            ("Downloading %s %s %s to %s ..."),
                            photos_count_str,
                            ",".join([_s.value for _s in user_config.sizes]),
                            photo_video_phrase,
                            directory,
                        )

                        consecutive_files_found = Counter(0)

                        def should_break(counter: Counter) -> bool:
                            """Exit if until_found condition is reached"""
                            return (
                                user_config.until_found is not None
                                and counter.value() >= user_config.until_found
                            )

                        # For cache mode, we don't know exact count upfront, so start with 0
                        # It will be updated as we process photos
                        progress = status_exchange.get_progress()
                        if file_cache is not None and use_cache:
                            # Start with 0, will be updated dynamically
                            progress.photos_count = 0
                        else:
                            progress.photos_count = photos_to_download
                        photos_counter = 0
                        photos_downloaded = 0  # Track photos actually downloaded in this iteration
                        # Initialize photos_checked for status tracking
                        progress.photos_checked = 0

                        now = datetime.datetime.now(get_localzone())
                        last_progress_message_time = time.time()  # Track last progress message time
                        loop_start_time = time.time()  # Track start time for rate calculation
                        # Store processing start time in progress for status messages
                        progress.processing_start_time = loop_start_time
                        # Create download_photo with total_photos and start_time for counter display
                        # Use lambda to pass keyword arguments correctly
                        download_photo = lambda counter, photo: downloader(icloud, counter, photo, total_photos=photos_to_download, start_time=loop_start_time)

                        for item in photos_bar:
                            try:
                                if should_break(consecutive_files_found):
                                    logger.info(
                                        "Found %s consecutive previously downloaded photos. Exiting",
                                        user_config.until_found,
                                    )
                                    break
                                # item = next(photos_iterator)
                                should_delete = False

                                # Update photos_checked for status tracking (every photo we process)
                                progress = status_exchange.get_progress()
                                progress.photos_checked += 1

                                passer_result = passer(item)
                                download_result = passer_result and download_photo(
                                    consecutive_files_found, item
                                )
                                
                                # Count photos that were actually downloaded
                                if download_result:
                                    photos_downloaded += 1
                                    photos_counter += 1
                                    status_exchange.get_progress().photos_counter = photos_counter
                                    
                                    # Send progress update every minute if manual sync was triggered
                                    current_time = time.time()
                                    if telegram_bot and progress.last_progress_message_time > 0:
                                        # Manual sync was triggered, send updates every minute
                                        if (current_time - last_progress_message_time) >= 60:
                                            telegram_bot.send_progress_update()
                                            last_progress_message_time = current_time
                                            progress.last_progress_message_time = current_time
                                elif passer_result:
                                    # Photo passed filters but was already downloaded
                                    photos_counter += 1
                                    status_exchange.get_progress().photos_counter = photos_counter
                                if download_result and user_config.delete_after_download:
                                    should_delete = True

                                if (
                                    passer_result
                                    and user_config.keep_icloud_recent_days is not None
                                ):
                                    created_date = item.created.astimezone(get_localzone())
                                    age_days = (now - created_date).days
                                    logger.debug(f"Created date: {created_date}")
                                    logger.debug(
                                        f"Keep iCloud recent days: {user_config.keep_icloud_recent_days}"
                                    )
                                    logger.debug(f"Age days: {age_days}")
                                    if age_days < user_config.keep_icloud_recent_days:
                                        # Create filename cleaner for debug message
                                        filename_cleaner_for_debug = build_filename_cleaner(
                                            user_config.keep_unicode_in_filenames
                                        )
                                        debug_filename = build_filename_with_policies(
                                            user_config.file_match_policy,
                                            filename_cleaner_for_debug,
                                            item,
                                        )
                                        logger.debug(
                                            "Skipping deletion of %s as it is within the keep_icloud_recent_days period (%d days old)",
                                            debug_filename,
                                            age_days,
                                        )
                                    else:
                                        should_delete = True

                                if should_delete:
                                    # Create filename cleaner and builder for delete operations
                                    filename_cleaner_for_delete = build_filename_cleaner(
                                        user_config.keep_unicode_in_filenames
                                    )
                                    filename_builder_for_delete = create_filename_builder(
                                        user_config.file_match_policy, filename_cleaner_for_delete
                                    )
                                    if user_config.dry_run:
                                        delete_photo_dry_run(
                                            logger,
                                            library_object,
                                            item,
                                            filename_builder_for_delete,
                                        )
                                    else:
                                        delete_photo(
                                            logger,
                                            library_object,
                                            item,
                                            filename_builder_for_delete,
                                        )

                                    # retrier(delete_local, error_handler)
                                    photo_album.increment_offset(-1)


                                if status_exchange.get_progress().cancel:
                                    break

                            except StopIteration:
                                break

                        if global_config.only_print_filenames:
                            return 0
                        else:
                            pass

                        if status_exchange.get_progress().cancel:
                            logger.info("Iteration was cancelled")
                            status_exchange.get_progress().photos_last_message = (
                                "Iteration was cancelled"
                            )
                        else:
                            if user_config.skip_photos or user_config.skip_videos:
                                photo_video_phrase = (
                                    "photos" if user_config.skip_videos else "videos"
                                )
                            else:
                                photo_video_phrase = "photos and videos"
                            message = f"All {photo_video_phrase} have been downloaded"
                            logger.info(message)
                            status_exchange.get_progress().photos_last_message = message
                            
                            # Send final message via Telegram
                            # Only send if manual sync was triggered (last_progress_message_time > 0)
                            # OR if it's a periodic sync (always send final message for periodic)
                            progress = status_exchange.get_progress()
                            if telegram_bot:
                                watch_interval = global_config.watch_with_interval or 0
                                # Send final message if manual sync OR if periodic (last_progress_message_time == 0 means periodic)
                                if progress.last_progress_message_time > 0:
                                    # Manual sync - send final message
                                    telegram_bot.send_sync_complete_message(photos_downloaded, watch_interval)
                                elif watch_interval > 0:
                                    # Periodic sync - send final message (but no initial or progress messages)
                                    telegram_bot.send_sync_complete_message(photos_downloaded, watch_interval)
                        
                        # Update last sync time and watch interval before reset
                        progress = status_exchange.get_progress()
                        current_time = time.time()
                        if global_config.watch_with_interval:
                            progress.watch_interval = global_config.watch_with_interval
                            progress.last_sync_time = current_time
                        # Always save last sync date to cache for incremental syncs (even without watch mode)
                        # This allows subsequent runs to only process new photos
                        if file_cache is not None:
                            file_cache.set_last_sync_date(current_time)
                            logger.info(f"Saved last sync date: {datetime.datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')} (next sync will only process new photos)")
                        progress.reset()

                    if user_config.auto_delete:
                        autodelete_photos(
                            logger,
                            user_config.dry_run,
                            library_object,
                            user_config.folder_structure,
                            directory,
                            user_config.sizes,
                            lp_filename_generator,
                            user_config.align_raw,
                        )
                    else:
                        pass
        except PyiCloudFailedLoginException as error:
            logger.info(error)
            dump_responses(logger.debug, captured_responses)
            if PasswordProvider.WEBUI in global_config.password_providers:
                update_auth_error_in_webui(status_exchange, str(error))
                continue
            else:
                return 1
        except PyiCloudFailedMFAException as error:
            logger.info(str(error))
            dump_responses(logger.debug, captured_responses)
            if global_config.mfa_provider == MFAProvider.WEBUI:
                update_auth_error_in_webui(status_exchange, str(error))
                continue
            elif global_config.mfa_provider == MFAProvider.TELEGRAM and telegram_bot:
                # Error already handled in request_2fa_telegram, just continue
                continue
            else:
                return 1
        except PyiCloud2SARequiredException as error:
            logger.info(str(error))
            dump_responses(logger.debug, captured_responses)
            # Notify via Telegram if available
            if telegram_bot:
                username = user_config.username
                telegram_bot.notify_auth_required(username)
            # Continue to retry authentication (will detect requires_2fa and use Telegram if configured)
            continue
        except (
            PyiCloudServiceNotActivatedException,
            PyiCloudServiceUnavailableException,
            PyiCloudAPIResponseException,
            PyiCloudConnectionErrorException,
        ) as error:
            logger.info(error)
            dump_responses(logger.debug, captured_responses)
            # Check if it's an authentication error (421, 450, 500)
            if isinstance(error, PyiCloudAPIResponseException) and str(error.code) in ["421", "450", "500"]:
                # Authentication required - notify via Telegram if available
                if telegram_bot:
                    username = user_config.username
                    telegram_bot.notify_auth_required(username)
                # Continue to retry authentication (will detect requires_2fa and use Telegram if configured)
                if global_config.mfa_provider == MFAProvider.TELEGRAM and telegram_bot:
                    continue
            # webui will display error and wait for password again
            if (
                PasswordProvider.WEBUI in global_config.password_providers
                or global_config.mfa_provider == MFAProvider.WEBUI
            ):
                if update_auth_error_in_webui(status_exchange, str(error)):
                    # retry if it was during auth
                    continue
                else:
                    pass
            else:
                pass
            # In single run mode, return error after webui retry attempts
            return 1
        except (
            ChunkedEncodingError,
            ContentDecodingError,
            StreamConsumedError,
            UnrewindableBodyError,
        ) as error:
            logger.debug(error)
            logger.debug("Retrying...")
            # these errors we can safely retry
            continue
        except Exception:
            dump_responses(logger.debug, captured_responses)
            raise

        # In single run mode, we don't handle watch intervals - that's done at higher level
        break

    return 0
