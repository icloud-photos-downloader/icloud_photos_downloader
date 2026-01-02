"""Hook definitions for icloudpd plugin system

This module defines ONLY type hints and protocols.
Plugins implement these hooks in their classes.
"""

from typing import Protocol

from pyicloud_ipd.services.photos import PhotoAsset
from pyicloud_ipd.version_size import VersionSize


class DownloadHook(Protocol):
    """Protocol defining all available plugin hooks.

    Plugins should implement the hook methods they need.
    All methods are optional.

    Note: These are called at different points in the download process:
    - Per-size hooks: Called for each size variant (original, medium, thumb)
    - Per-photo hooks: Called once per photo after all sizes
    - Per-run hooks: Called once at the end of the entire run
    """

    # ========================================================================
    # PER-SIZE HOOKS (called for each size: original, medium, thumb, etc.)
    # ========================================================================

    def on_download_exists(
        self,
        download_path: str,
        photo_filename: str,
        requested_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """Called when a file already exists (not downloaded).

        This is called for each size variant that already exists on disk.

        Args:
            download_path: Full path to the file that exists
            photo_filename: Base filename of the photo
            requested_size: Size variant requested (may differ from actual if fallback occurred)
            photo: The PhotoAsset object from iCloud
            dry_run: True if this is a dry run

        Example:
            >>> def on_download_exists(self, download_path, **kwargs):
            ...     print(f"Skipped (exists): {download_path}")
        """
        ...

    def on_download_downloaded(
        self,
        download_path: str,
        photo_filename: str,
        requested_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """Called after a file is successfully downloaded.

        This is called for each size variant that was just downloaded.

        Args:
            download_path: Full path to the downloaded file
            photo_filename: Base filename of the photo
            requested_size: Size variant requested (may differ from actual if fallback occurred)
            photo: The PhotoAsset object from iCloud
            dry_run: True if this is a dry run

        Example:
            >>> def on_download_downloaded(self, download_path, **kwargs):
            ...     print(f"Downloaded: {download_path}")
        """
        ...

    def on_download_complete(
        self,
        download_path: str,
        photo_filename: str,
        requested_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """Called after a size variant is processed (downloaded or skipped).

        This ALWAYS runs for each size, whether the file was downloaded
        or already existed. Use this to track all files.

        Args:
            download_path: Full path to the file
            photo_filename: Base filename of the photo
            requested_size: Size variant requested (may differ from actual if fallback occurred)
            photo: The PhotoAsset object from iCloud
            dry_run: True if this is a dry run

        Example:
            >>> def on_download_complete(self, download_path, requested_size, **kwargs):
            ...     self.files.append({"path": download_path, "size": requested_size})
        """
        ...

    # ========================================================================
    # LIVE PHOTO HOOKS (called for live photo video component)
    # ========================================================================

    def on_download_exists_live(
        self,
        download_path: str,
        photo_filename: str,
        requested_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """Called when a live photo video already exists.

        Args:
            download_path: Full path to the .MOV file that exists
            photo_filename: Base filename of the photo
            requested_size: Size variant of live photo
            photo: The PhotoAsset object from iCloud
            dry_run: True if this is a dry run
        """
        ...

    def on_download_downloaded_live(
        self,
        download_path: str,
        photo_filename: str,
        requested_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """Called after a live photo video is downloaded.

        Args:
            download_path: Full path to the downloaded .MOV file
            photo_filename: Base filename of the photo
            requested_size: Size variant that was downloaded
            photo: The PhotoAsset object from iCloud
            dry_run: True if this is a dry run
        """
        ...

    def on_download_complete_live(
        self,
        download_path: str,
        photo_filename: str,
        requested_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """Called after live photo is processed (downloaded or skipped).

        This ALWAYS runs if the photo has a live photo component.

        Args:
            download_path: Full path to the .MOV file
            photo_filename: Base filename of the photo
            requested_size: Size variant processed
            photo: The PhotoAsset object from iCloud
            dry_run: True if this is a dry run
        """
        ...

    # ========================================================================
    # PER-PHOTO HOOK (called once per photo after all sizes)
    # ========================================================================

    def on_download_all_sizes_complete(
        self,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """Called after ALL sizes of a photo have been processed.

        This is the KEY hook for processing a complete photo.
        Use this to:
        - Upload to cloud services (all sizes together)
        - Stack size variants
        - Generate reports
        - Add to albums

        At this point, all size variants and live photo (if exists)
        have been downloaded or skipped.

        Args:
            photo: The PhotoAsset object from iCloud
            dry_run: True if this is a dry run

        Example:
            >>> def on_download_all_sizes_complete(self, photo, **kwargs):
            ...     # Upload all accumulated files
            ...     for file in self.accumulated_files:
            ...         self.client.upload(file["path"])
            ...     # Clear accumulator for next photo
            ...     self.accumulated_files.clear()
        """
        ...

    # ========================================================================
    # PER-RUN HOOK (called once at end of entire run)
    # ========================================================================

    def on_run_completed(
        self,
        dry_run: bool,
    ) -> None:
        """Called after entire download run is complete.

        Use this for final cleanup, summary reports, etc.

        Args:
            dry_run: True if this was a dry run

        Example:
            >>> def on_run_completed(self, **kwargs):
            ...     print(f"Total photos processed: {self.total_count}")
        """
        ...
