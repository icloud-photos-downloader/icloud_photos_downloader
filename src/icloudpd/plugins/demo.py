"""Demo plugin showing hook usage with instance variable accumulation

This plugin demonstrates:
1. Using instance variables to accumulate data across hook calls
2. Reporting accumulated data in on_download_all_sizes_complete
3. Clearing accumulator after each photo
4. Showing what context is available at each hook point
5. Proper logger initialization and usage
"""

import logging
from argparse import ArgumentParser, Namespace
from typing import TYPE_CHECKING, Any, Dict, List

from icloudpd.plugins.base import IcloudpdPlugin
from pyicloud_ipd.services.photos import PhotoAsset
from pyicloud_ipd.version_size import VersionSize

if TYPE_CHECKING:
    from typing import Sequence

    from icloudpd.config import GlobalConfig, UserConfig

# Initialize logger for this module
# This is the standard way to initialize a logger in Python plugins
# Use explicit namespace to ensure correct logger hierarchy
logger = logging.getLogger("icloudpd.plugins.demo")


class DemoPlugin(IcloudpdPlugin):
    """Demo plugin showing hook context and accumulator pattern.

    This plugin doesn't do anything useful - it demonstrates:
    - What data is available at each hook point
    - How to use instance variables to accumulate data
    - When to process and clear accumulated data

    Example:
        $ icloudpd --plugin demo --recent 5
        $ icloudpd --plugin demo --demo-verbose --recent 5
        $ icloudpd --plugin demo --demo-compact --recent 100
    """

    def __init__(self):
        """Initialize demo plugin with accumulators"""
        self.verbose = False
        self.compact = False

        # Accumulators for current photo being processed
        self.current_photo_files: List[Dict[str, Any]] = []
        self.current_photo_id: str = ""

        # Global counters for the run
        self.total_photos = 0
        self.total_files_downloaded = 0
        self.total_files_existed = 0
        self.total_files_live = 0

    @property
    def name(self) -> str:
        """Plugin name"""
        return "demo"

    @property
    def version(self) -> str:
        """Plugin version"""
        return "1.0.0"

    @property
    def description(self) -> str:
        """Plugin description"""
        return "Demo plugin showing hook context (development tool)"

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add demo plugin CLI arguments"""
        group = parser.add_argument_group("Demo Plugin Options")
        group.add_argument(
            "--demo-verbose",
            action="store_true",
            help="Show full metadata in hook output (very detailed)",
        )
        group.add_argument(
            "--demo-compact", action="store_true", help="Show compact one-line output per photo"
        )

    def configure(
        self,
        config: Namespace,
        global_config: "GlobalConfig | None" = None,
        user_configs: "Sequence[UserConfig] | None" = None,
    ) -> None:
        """Configure demo plugin from CLI arguments and runtime configs.

        Args:
            config: Parsed CLI arguments namespace
            global_config: Global configuration (optional)
            user_configs: List of user configurations (optional)
        """
        self.verbose = getattr(config, "demo_verbose", False)
        self.compact = getattr(config, "demo_compact", False)

        if not self.compact:
            print("\n" + "=" * 70)
            print("🔌 Demo Plugin: Initialized")
            print("=" * 70)
            print(f"   Version:     {self.version}")
            print(f"   Verbose:     {self.verbose}")
            print(f"   Compact:     {self.compact}")
            print("=" * 70)
            print("\nThis plugin shows data available at each hook point.")
            print("It accumulates files in instance variables, then reports")
            print("when all sizes are complete.\n")

    # ========================================================================
    # PER-SIZE HOOKS - Accumulate data
    # ========================================================================

    def on_download_exists(
        self,
        download_path: str,
        photo_filename: str,
        download_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """File already exists - add to accumulator"""
        if not self.compact and not self.verbose:
            logger.info(f"   📂 Exists:     {download_size.value:>11} - {download_path}")

        # Accumulate
        self.current_photo_files.append(
            {
                "status": "existed",
                "path": download_path,
                "size": download_size.value,
                "is_live": False,
            }
        )
        self.total_files_existed += 1

    def on_download_downloaded(
        self,
        download_path: str,
        photo_filename: str,
        download_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """File was downloaded - add to accumulator"""
        if not self.compact and not self.verbose:
            logger.info(f"   ⬇️  Downloaded: {download_size.value:>11} - {download_path}")

        # Accumulate
        self.current_photo_files.append(
            {
                "status": "downloaded",
                "path": download_path,
                "size": download_size.value,
                "is_live": False,
            }
        )
        self.total_files_downloaded += 1

    def on_download_complete(
        self,
        download_path: str,
        photo_filename: str,
        download_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """Size processing complete - accumulate if not already accumulated.

        This hook ALWAYS runs, so we use it to ensure files are tracked
        even if they didn't go through exists or downloaded hooks.
        """
        # Check if this file was already accumulated
        already_accumulated = any(f["path"] == download_path for f in self.current_photo_files)

        # If not accumulated yet (edge case), add it now
        if not already_accumulated:
            logger.debug(f"File {download_path} not previously accumulated, adding now")
            self.current_photo_files.append(
                {
                    "status": "complete",
                    "path": download_path,
                    "size": download_size.value,
                    "is_live": False,
                }
            )

        if self.verbose:
            logger.info(f"   ✅ Complete:   {download_size.value:>11} - {download_path}")

    # ========================================================================
    # LIVE PHOTO HOOKS - Accumulate live photo data
    # ========================================================================

    def on_download_exists_live(
        self,
        download_path: str,
        photo_filename: str,
        download_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """Live photo exists - add to accumulator"""
        if not self.compact and not self.verbose:
            logger.info(f"   📂 Exists:     {download_size.value:>11} - {download_path} 🎥")

        # Accumulate
        self.current_photo_files.append(
            {
                "status": "existed",
                "path": download_path,
                "size": download_size.value,
                "is_live": True,
            }
        )
        self.total_files_existed += 1
        self.total_files_live += 1

    def on_download_downloaded_live(
        self,
        download_path: str,
        photo_filename: str,
        download_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """Live photo downloaded - add to accumulator"""
        if not self.compact and not self.verbose:
            logger.info(f"   ⬇️  Downloaded: {download_size.value:>11} - {download_path} 🎥")

        # Accumulate
        self.current_photo_files.append(
            {
                "status": "downloaded",
                "path": download_path,
                "size": download_size.value,
                "is_live": True,
            }
        )
        self.total_files_downloaded += 1
        self.total_files_live += 1

    def on_download_complete_live(
        self,
        download_path: str,
        photo_filename: str,
        download_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """Live photo processing complete"""
        # Check if already accumulated
        already_accumulated = any(f["path"] == download_path for f in self.current_photo_files)

        if not already_accumulated:
            logger.debug(f"Live photo {download_path} not previously accumulated, adding now")
            self.current_photo_files.append(
                {
                    "status": "complete",
                    "path": download_path,
                    "size": download_size.value,
                    "is_live": True,
                }
            )
            self.total_files_live += 1

        if self.verbose:
            logger.info(f"   ✅ Complete:   {download_size.value:>11} - {download_path} 🎥")

    # ========================================================================
    # KEY HOOK - Process accumulated data and clear
    # ========================================================================

    def on_download_all_sizes_complete(
        self,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """ALL sizes complete - process accumulated data and clear.

        This is where you would:
        - Upload all accumulated files to a service
        - Stack size variants together
        - Add to albums
        - Generate reports
        """
        self.total_photos += 1

        logger.debug(
            f"Processing complete for photo {photo.filename} ({len(self.current_photo_files)} files)"
        )

        if self.compact:
            # Compact mode: one line per photo
            downloaded = sum(1 for f in self.current_photo_files if f["status"] == "downloaded")
            existed = sum(1 for f in self.current_photo_files if f["status"] == "existed")
            sizes = ",".join(set(f["size"] for f in self.current_photo_files))

            # Check if favorite
            is_fav = photo._asset_record.get("fields", {}).get("isFavorite", {}).get("value") == 1
            fav_marker = "⭐" if is_fav else "  "

            logger.info(f"{fav_marker} {photo.filename} [{sizes}] (↓{downloaded} ✓{existed})")
        else:
            # Full mode: detailed output
            logger.info("\n" + "=" * 70)
            logger.info(f"📸 PHOTO COMPLETE: {photo.filename} (#{self.total_photos})")
            logger.info("=" * 70)

            # Photo info
            is_fav = photo._asset_record.get("fields", {}).get("isFavorite", {}).get("value") == 1
            logger.info("\n📋 Photo Information:")
            logger.info(f"   ID:         {photo.id}")
            logger.info(f"   Filename:   {photo.filename}")
            logger.info(f"   Favorite:   {'⭐ YES' if is_fav else 'No'}")

            if self.verbose:
                logger.info(f"   Created:    {photo.created}")
                logger.info(f"   Size:       {photo.size:,} bytes")
                if hasattr(photo, "dimensions"):
                    logger.info(f"   Dimensions: {photo.dimensions}")

            # Accumulated files
            logger.info(f"\n📁 Processed Files ({len(self.current_photo_files)}):")
            for i, file_info in enumerate(self.current_photo_files, 1):
                status_icon = "⬇️" if file_info["status"] == "downloaded" else "📂"
                live_icon = " 🎥" if file_info["is_live"] else ""
                logger.info(f"   {status_icon} {i}. [{file_info['size']:>11}]{live_icon}")
                if self.verbose:
                    logger.info(f"       {file_info['path']}")

            # What a real plugin would do
            logger.info("\n💡 What a Real Plugin Would Do Here:")
            logger.info(f"   • Upload {len(self.current_photo_files)} file(s) to cloud storage")
            if len(self.current_photo_files) > 1:
                logger.info(
                    f"   • Stack/group the {len(self.current_photo_files)} variants together"
                )
            if is_fav:
                logger.info("   • Mark as favorite in the service")
            logger.info("   • Add to album based on date or tags")
            logger.info("")

        # IMPORTANT: Clear accumulator for next photo
        self.current_photo_files.clear()

    # ========================================================================
    # RUN COMPLETE - Final summary
    # ========================================================================

    def on_run_completed(
        self,
        dry_run: bool,
    ) -> None:
        """Run complete - show final summary"""
        logger.debug(f"Run completed - processed {self.total_photos} photos")

        if self.compact:
            logger.info(
                f"\n✅ Complete: {self.total_photos} photos, {self.total_files_downloaded + self.total_files_existed} files"
            )
        else:
            logger.info("\n" + "=" * 70)
            logger.info("✅ RUN COMPLETED")
            logger.info("=" * 70)
            logger.info("\n📊 Final Statistics:")
            logger.info(f"   Total Photos:         {self.total_photos}")
            logger.info(f"   Files Downloaded:     {self.total_files_downloaded}")
            logger.info(f"   Files Already Existed: {self.total_files_existed}")
            logger.info(f"   Live Photos:          {self.total_files_live}")
            logger.info(
                f"   Total Files:          {self.total_files_downloaded + self.total_files_existed}"
            )

            logger.info("\n💡 What a Real Plugin Would Do:")
            logger.info("   • Upload summary to service dashboard")
            logger.info("   • Send completion notification")
            logger.info("   • Trigger backup or sync processes")
            logger.info("   • Clean up temporary files")
            logger.info("=" * 70)
            logger.info("")

    def cleanup(self) -> None:
        """Cleanup called on shutdown"""
        logger.debug("Demo Plugin: Cleanup called")
        if not self.compact and self.verbose:
            logger.info("\n🔌 Demo Plugin: Cleanup called")
