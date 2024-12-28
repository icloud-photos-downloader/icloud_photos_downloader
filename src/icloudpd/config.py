from typing import Callable, Dict, Optional, Sequence, Tuple

from icloudpd.mfa_provider import MFAProvider
from pyicloud_ipd.file_match import FileMatchPolicy
from pyicloud_ipd.raw_policy import RawTreatmentPolicy
from pyicloud_ipd.version_size import AssetVersionSize, LivePhotoVersionSize


class Config:
    def __init__(
        self,
        directory: Optional[str],
        username: str,
        auth_only: bool,
        cookie_directory: str,
        primary_sizes: Sequence[AssetVersionSize],
        live_photo_size: LivePhotoVersionSize,
        recent: Optional[int],
        until_found: Optional[int],
        album: str,
        list_albums: bool,
        library: str,
        list_libraries: bool,
        skip_videos: bool,
        skip_live_photos: bool,
        xmp_sidecar: bool,
        force_size: bool,
        auto_delete: bool,
        only_print_filenames: bool,
        folder_structure: str,
        set_exif_datetime: bool,
        smtp_username: Optional[str],
        smtp_host: str,
        smtp_port: int,
        smtp_no_tls: bool,
        notification_email: Optional[str],
        notification_email_from: Optional[str],
        log_level: str,
        no_progress_bar: bool,
        notification_script: Optional[str],
        threads_num: int,
        delete_after_download: bool,
        domain: str,
        watch_with_interval: Optional[int],
        dry_run: bool,
        raw_policy: RawTreatmentPolicy,
        password_providers: Dict[
            str, Tuple[Callable[[str], Optional[str]], Callable[[str, str], None]]
        ],
        file_match_policy: FileMatchPolicy,
        mfa_provider: MFAProvider,
        use_os_locale: bool,
    ):
        self.directory = directory
        self.username = username
        self.auth_only = auth_only
        self.cookie_directory = cookie_directory
        self.size = " ".join(str(e) for e in primary_sizes)
        self.live_photo_size = live_photo_size
        self.recent = recent
        self.until_found = until_found
        self.album = album
        self.list_albums = list_albums
        self.library = library
        self.list_libraries = list_libraries
        self.skip_videos = skip_videos
        self.skip_live_photos = skip_live_photos
        self.force_size = force_size
        self.auto_delete = auto_delete
        self.only_print_filenames = only_print_filenames
        self.folder_structure = folder_structure
        self.set_exif_datetime = set_exif_datetime
        self.smtp_username = smtp_username
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_no_tls = smtp_no_tls
        self.notification_email = notification_email
        self.notification_email_from = notification_email_from
        self.log_level = log_level
        self.no_progress_bar = no_progress_bar
        self.notification_script = notification_script
        self.threads_num = threads_num
        self.delete_after_download = delete_after_download
        self.domain = domain
        self.watch_with_interval = watch_with_interval
        self.dry_run = dry_run
        self.raw_policy = raw_policy
        self.password_providers = " ".join(str(e) for e in password_providers)
        self.file_match_policy = file_match_policy
        self.mfa_provider = mfa_provider
        self.use_os_locale = use_os_locale
