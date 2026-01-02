"""Immich plugin for stacking, favoriting, and adding photos to albums

This plugin integrates with Immich to:
1. Register photos in Immich external library via scan-and-wait
2. Stack multiple size variants together (original, medium, adjusted)
3. Associate live photo videos with multiple size variants
4. Mark specific sizes as favorites based on iCloud favorite status
5. Add specific sizes to albums with flexible size-based rules

NOTES on Immich API Behavior
-----------------------------
Stacking:
- Stacks are visual groupings only, not returnable asset IDs
- Stacked images appear grouped in timeline/favorites but NOT in albums
- Individual assets from a stack can be favorited/added to albums independently

Favoriting:
- Can favorite individual assets OR multiple assets in a stack
- Favorited assets in a stack appear stacked in favorites view
- Deleting a stack leaves favorited assets in favorites

Albums:
- Stacks cannot be added to albums (no API support)
- Individual assets must be added to albums
- Adding all assets from a stack to an album doesn't show them as stacked

Live Photos:
- Immich auto-associates the MOV with original HEIC (MOV becomes hidden)
- We can associate the same livePhotoVideoId with other sizes (adjusted, medium, etc.)
- This allows live photo playback for all size variants
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

import requests

from icloudpd.plugins.base import IcloudpdPlugin
from pyicloud_ipd.services.photos import PhotoAsset
from pyicloud_ipd.version_size import VersionSize

if TYPE_CHECKING:
    from typing import Sequence

    from icloudpd.config import GlobalConfig, UserConfig

# Use icloudpd namespace for logging so it inherits the configured log level
logger = logging.getLogger("icloudpd.plugins.immich")


# ============================================================================
# Helper Functions
# ============================================================================


def _parse_sizes(value: str | None) -> List[str]:
    """Parse comma-separated size list and validate against available sizes.

    Args:
        value: Comma-separated size list or None (means all sizes)

    Returns:
        List of valid size names

    Raises:
        argparse.ArgumentTypeError: If invalid sizes specified
    """
    available = ["original", "adjusted", "alternative", "medium", "thumb"]

    # No value given (--flag with no argument) → return all
    if value is None:
        return available

    # Parse comma-separated values
    items = [s.strip() for s in value.split(",")]

    # Validate against available
    invalid = [s for s in items if s not in available]
    if invalid:
        raise argparse.ArgumentTypeError(f"Invalid sizes: {invalid}. Available: {available}")

    return items


def _parse_batch_size(value: str | None) -> int:
    """Parse batch size argument.

    Args:
        value: Batch size value - None, 'all', or an integer string

    Returns:
        Integer batch size where 0='all', 1=immediate (default), N=batch every N

    Raises:
        argparse.ArgumentTypeError: If invalid value
    """
    # No argument (--immich-batch-process with no value) → process all at end (0)
    if value is None:
        return 0

    # Explicit 'all' → 0
    if value.lower() == "all":
        return 0

    # Try to parse as integer
    try:
        batch_size = int(value)
        if batch_size < 1:
            raise argparse.ArgumentTypeError(f"Batch size must be >= 1, got {batch_size}")
        return batch_size
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"Invalid batch size: {value}. Use 'all' or a positive integer"
        ) from e


# ============================================================================
# Pure Helper Functions
# ============================================================================


def _has_new_files(files: List[Dict]) -> bool:
    """Check if any files were newly downloaded (vs existed).

    Args:
        files: List of file info dicts with 'status' key

    Returns:
        True if any file has status 'downloaded'
    """
    return any(f["status"] == "downloaded" for f in files)


def _get_asset_ids_for_sizes(assets: List[Dict[str, Any]], target_sizes: List[str]) -> List[str]:
    """Extract asset IDs for specific sizes from asset list.

    Args:
        assets: List of asset dicts with 'size' and 'asset_id' keys
        target_sizes: List of size names to extract

    Returns:
        List of asset IDs matching target sizes
    """
    return [a["asset_id"] for a in assets if a["size"] in target_sizes]


# ============================================================================
# Album Rule Class
# ============================================================================


class AlbumRule:
    """Represents a single album assignment rule.

    Format: [size1,size2]:album_template or just album_template

    Examples:
        [adjusted]:iCloud Photos/{:%Y/%m}  - Only adjusted size
        [original]:iCloud Raw              - Only original size
        [adjusted,medium]:Processed        - Adjusted and medium sizes
        All Photos                         - All sizes (no filter)

    Note: [stacked] is no longer supported since stacks cannot be added to albums
    """

    def __init__(self, rule_string: str):
        """Parse album rule string.

        Args:
            rule_string: Format "[sizes]:template" or just "template" (no filter)

        Raises:
            ValueError: If rule format is invalid or contains [stacked]
        """
        # Try to match [sizes]:template format
        match = re.match(r"^\[([^\]]+)\]:(.+)$", rule_string.strip())

        if match:
            # Has size filter
            sizes_str, self.template = match.groups()

            # Parse size targets
            self.size_targets = [s.strip() for s in sizes_str.split(",")]

            # Validate: [stacked] is no longer allowed
            if "stacked" in self.size_targets:
                raise ValueError(
                    "Album rule '[stacked]:...' is not supported. "
                    "Stacks cannot be added to albums in Immich. "
                    "Use specific sizes like [adjusted]:... or [original]:... instead."
                )

            # Validate all sizes are known
            valid_sizes = ["original", "adjusted", "alternative", "medium", "thumb"]
            invalid = [s for s in self.size_targets if s not in valid_sizes]
            if invalid:
                raise ValueError(
                    f"Invalid sizes in album rule: {invalid}. Valid sizes: {valid_sizes}"
                )

            self.match_all = False
        else:
            # No filter - match everything
            self.template = rule_string.strip()
            if not self.template:
                raise ValueError(f"Empty album template: {rule_string}")

            self.size_targets = []
            self.match_all = True

    def matches(self, size: str) -> bool:
        """Check if this rule matches the given size.

        Args:
            size: The size name (e.g., 'original', 'adjusted')

        Returns:
            True if this rule should be applied to this size
        """
        # Match-all rule: matches everything
        if self.match_all:
            return True

        # Check if size is in target list
        return size in self.size_targets

    def __repr__(self) -> str:
        if self.match_all:
            return f"AlbumRule(all:{self.template})"
        return f"AlbumRule([{','.join(self.size_targets)}]:{self.template})"


# ============================================================================
# Immich Plugin
# ============================================================================


class ImmichPlugin(IcloudpdPlugin):
    """Immich integration plugin for photo management.

    Registers photos in Immich external library with optional stacking,
    favoriting, and flexible album management based on size variants.

    Example:
        $ icloudpd --plugin immich --immich-server-url https://immich.example.com \\
                   --immich-api-key YOUR_API_KEY --immich-library-id abc123 \\
                   --immich-album "[adjusted]:iCloud/{:%Y/%B}" \\
                   --immich-album "[original]:Raw"

        $ icloudpd --plugin immich --immich-server-url https://immich.example.com \\
                   --immich-api-key YOUR_API_KEY --immich-library-id abc123 \\
                   --immich-stack-media adjusted,original \\
                   --immich-favorite adjusted \\
                   --immich-album "[adjusted]:Favorites"
    """

    def __init__(self):
        """Initialize Immich plugin with configuration and accumulators"""
        # Configuration options
        self.server_url: str | None = None
        self.api_key: str | None = None
        self.library_id: str | None = None
        self.process_existing: bool = False
        self.process_existing_favorites: bool = (
            False  # Set from global --process-existing-favorites
        )
        self.scan_timeout: float = 5.0
        self.poll_interval: float = 1.0

        # Batch processing configuration
        # batch_size: 0='all' (process at end), 1=immediate (default), N=batch every N photos
        self.batch_size: int = 1
        self.batch_log_file: str = os.path.expanduser("~/.pyicloud/immich_pending_files.json")

        # Stacking configuration
        self.stack_media: bool = False
        self.stack_priority: List[str] = ["adjusted", "medium", "original"]

        # Favoriting configuration - now a list of sizes to favorite
        self.favorite_sizes: List[str] = []

        # Live photo association configuration
        self.associate_live_sizes: List[str] = []

        # Album rules
        self.album_rules: List[AlbumRule] = []

        # Accumulators for current photo being processed
        # Each entry: {'status': 'downloaded'|'existed', 'path': str, 'size': str, 'is_live': bool, 'photo_filename': str}
        self.current_photo_files: List[Dict[str, Any]] = []

        # Batch queue for accumulating photos before processing
        # Each entry: {'photo_id': str, 'files': List[Dict], 'is_favorite': bool, 'created': datetime, ...}
        self.batch_queue: List[Dict[str, Any]] = []

        # Global counters for the run
        self.total_photos = 0
        self.total_registered = 0
        self.total_stacked = 0
        self.total_favorited = 0
        self.total_added_to_albums = 0
        self.total_live_associated = 0

    @property
    def name(self) -> str:
        """Plugin name"""
        return "immich"

    @property
    def version(self) -> str:
        """Plugin version"""
        return "2.0.0"

    @property
    def description(self) -> str:
        """Plugin description"""
        return "Register and organize photos in Immich with stacking, favorites, and album support"

    # ========================================================================
    # CLI Argument Configuration
    # ========================================================================

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add Immich plugin CLI arguments"""
        group = parser.add_argument_group("Immich Plugin Options")

        group.add_argument(
            "--immich-server-url",
            metavar="URL",
            help="Immich server URL (e.g., https://immich.example.com)",
        )

        group.add_argument(
            "--immich-api-key", metavar="KEY", help="Immich API key for authentication"
        )

        group.add_argument(
            "--immich-library-id",
            metavar="ID",
            help="Immich external library ID (required for scanning)",
        )

        group.add_argument(
            "--immich-process-existing",
            action="store_true",
            help="Process files that already existed (in addition to newly downloaded files)",
        )

        group.add_argument(
            "--immich-stack-media",
            nargs="?",
            const=None,
            default=False,
            type=_parse_sizes,
            metavar="SIZE(Primary),SIZE,...",
            help="Stack size variants. No argument stacks all sizes. "
            "With argument: comma-separated priority list (first=primary)",
        )

        group.add_argument(
            "--immich-favorite",
            nargs="?",
            const=None,
            default=False,
            type=_parse_sizes,
            metavar="SIZE,SIZE,...",
            help="Mark sizes as favorite in Immich based on iCloud favorite status. "
            "No argument favorites all sizes. With argument: comma-separated list of sizes",
        )

        group.add_argument(
            "--associate-live-with-extra-sizes",
            nargs="?",
            const=None,
            default=False,
            type=_parse_sizes,
            metavar="SIZE,SIZE,...",
            help="Associate live photo MOV with other sizes. "
            "No argument associates with all sizes. With argument: comma-separated list of sizes",
        )

        group.add_argument(
            "--immich-album",
            action="append",
            dest="immich_albums",
            metavar="RULE",
            help="Album rule in format [sizes]:template or just template (all sizes). "
            "Can be used multiple times. "
            'Examples: --immich-album "[adjusted]:iCloud/{:%%Y/%%m}" '
            '--immich-album "[original]:Raw" --immich-album "All Photos"',
        )

        group.add_argument(
            "--immich-scan-timeout",
            type=float,
            default=5.0,
            metavar="SECONDS",
            help="Time to wait for Immich library scan to complete after adding photos "
            "(default: %(default)s, 0 for infinite)",
        )

        group.add_argument(
            "--immich-poll-interval",
            type=float,
            default=1.0,
            metavar="SECONDS",
            help="Time to wait for between polls post scan. (default: %(default)s)",
        )

        group.add_argument(
            "--immich-batch-process",
            nargs="?",
            const=None,
            default=False,
            type=_parse_batch_size,
            metavar="N|all",
            help="Batch process photos to reduce Immich server load. "
            'No argument or "all": process all at end. '
            "Integer N: process every N photos. "
            "Reduces library scan frequency by accumulating photos before processing. "
            "Default: disabled (process each photo immediately)",
        )

        group.add_argument(
            "--immich-batch-log-file",
            metavar="PATH",
            help="Path to batch processing log file for crash recovery "
            "(default: ~/.pyicloud/immich_pending_files.json)",
        )

    # ========================================================================
    # Plugin Configuration
    # ========================================================================

    def configure(
        self,
        config: Namespace,
        global_config: "GlobalConfig | None" = None,
        user_configs: "Sequence[UserConfig] | None" = None,
    ) -> None:
        """Configure Immich plugin from CLI arguments and runtime configs.

        This is called twice:
        1. Early (from cli.py): Only config is available
        2. Late (from base.py): All parameters are available

        Args:
            config: Parsed CLI arguments namespace
            global_config: Global configuration (None on first call)
            user_configs: List of user configurations (None on first call)
        """
        # Basic configuration
        self.server_url = getattr(config, "immich_server_url", None)
        self.api_key = getattr(config, "immich_api_key", None)
        self.library_id = getattr(config, "immich_library_id", None)
        self.process_existing = getattr(config, "immich_process_existing", False)
        self.scan_timeout = getattr(config, "immich_scan_timeout", 5.0)
        self.poll_interval = getattr(config, "immich_poll_interval", 1.0)

        # Batch processing configuration
        batch_arg = getattr(config, "immich_batch_process", False)
        if batch_arg is not False:
            self.batch_size = batch_arg  # Will be int: 0='all', 1=immediate, N=batch every N

        # Batch log file
        batch_log_file_arg = getattr(config, "immich_batch_log_file", None)
        if batch_log_file_arg:
            self.batch_log_file = batch_log_file_arg

        # Parse stack_media argument (False, None=all, or list of sizes)
        stack_arg = getattr(config, "immich_stack_media", False)
        if stack_arg is not False:
            self.stack_media = True
            if stack_arg is not None and isinstance(stack_arg, list):
                # User provided custom priority list (first=primary)
                self.stack_priority = stack_arg

        # Parse favorite argument (False, None=all, or list of sizes)
        favorite_arg = getattr(config, "immich_favorite", False)
        if favorite_arg is not False:
            if favorite_arg is None:
                # Favorite all sizes
                self.favorite_sizes = ["original", "adjusted", "alternative", "medium", "thumb"]
            elif isinstance(favorite_arg, list):
                # Favorite specific sizes
                self.favorite_sizes = favorite_arg

        # Parse associate-live argument (False, None=all, or list of sizes)
        associate_arg = getattr(config, "associate_live_with_extra_sizes", False)
        if associate_arg is not False:
            if associate_arg is None:
                # Associate with all sizes
                self.associate_live_sizes = [
                    "original",
                    "adjusted",
                    "alternative",
                    "medium",
                    "thumb",
                ]
            elif isinstance(associate_arg, list):
                # Associate with specific sizes
                self.associate_live_sizes = associate_arg

        # Parse album rules
        album_rules_raw = getattr(config, "immich_albums", None) or []
        for rule_str in album_rules_raw:
            try:
                rule = AlbumRule(rule_str)
                self.album_rules.append(rule)
            except ValueError as e:
                print(f"Error: Invalid album rule '{rule_str}': {e}", file=sys.stderr)
                sys.exit(1)

        # Get process_existing_favorites from user_configs (only available on second call)
        # This is a global icloudpd setting, not a plugin-specific one
        self.process_existing_favorites = False
        if user_configs is not None and len(user_configs) > 0:
            # Use first user config's setting (all should be the same)
            self.process_existing_favorites = user_configs[0].process_existing_favorites

        # Validation
        if self.server_url and not self.api_key:
            print("Error: Immich server URL provided but no API key", file=sys.stderr)
            sys.exit(1)
        if self.api_key and not self.server_url:
            print("Error: Immich API key provided but no server URL", file=sys.stderr)
            sys.exit(1)
        if not self.library_id:
            print("Error: Immich library ID is required (--immich-library-id)", file=sys.stderr)
            sys.exit(1)
        if self.process_existing and self.process_existing_favorites:
            print(
                "Error: Cannot use both --immich-process-existing and --process-existing-favorites",
                file=sys.stderr,
            )
            print(
                "Choose one: process all existing files OR only existing favorites", file=sys.stderr
            )
            sys.exit(1)
        if self.process_existing_favorites and not self.favorite_sizes:
            print(
                "Warning: --process-existing-favorites is enabled but no favorite sizes configured",
                file=sys.stderr,
            )
            print(
                "Add --immich-favorite to specify which sizes to mark as favorites in Immich",
                file=sys.stderr,
            )

        # Print configuration (using print since logger isn't configured yet)
        print("\n" + "=" * 70)
        print("Immich Plugin: Initialized")
        print("=" * 70)
        print(f"  Version:                  {self.version}")
        print(f"  Server URL:               {self.server_url}")
        print(f"  Library ID:               {self.library_id}")
        print(f"  Process Existing:         {self.process_existing}")
        print(f"  Process Existing Favs:    {self.process_existing_favorites}")
        batch_desc = (
            "all (at end)"
            if self.batch_size == 0
            else ("immediate" if self.batch_size == 1 else f"every {self.batch_size} photos")
        )
        print(f"  Batch Processing:         {batch_desc}")
        if self.batch_size != 1:
            print(f"  Batch Log File:           {self.batch_log_file}")
        print(f"  Scan Timeout:             {self.scan_timeout}s")
        print(f"  Poll interval:            {self.poll_interval}s")
        print(f"  Stack Media:              {self.stack_media}")
        if self.stack_media:
            print(f"  Stack Priority:           {', '.join(self.stack_priority)}")
        print(
            f"  Favorite Sizes:           {', '.join(self.favorite_sizes) if self.favorite_sizes else 'None'}"
        )
        print(
            f"  Live Association:         {', '.join(self.associate_live_sizes) if self.associate_live_sizes else 'None'}"
        )
        print(f"  Album Rules:              {len(self.album_rules)}")
        for rule in self.album_rules:
            print(f"    - {rule}")
        print("=" * 70 + "\n")

        # Test Immich connection (after showing config so user knows what's being tested)
        if self.server_url and self.api_key:
            self._test_immich_connection()

            # Validate directories when user_configs are available (second call from base.py)
            if user_configs is not None:
                self._validate_directories(user_configs)

        # Load pending files from previous run if batch processing is enabled (batch_size != 1)
        if self.batch_size != 1:
            self._load_pending_files()

    @staticmethod
    def _strip_date_templates(path: str) -> str:
        """Strip date templates from a directory path.

        Converts paths like '/a/b/c/%Y/%m' to '/a/b/c'

        Args:
            path: Directory path potentially containing date templates

        Returns:
            Base path with date templates removed
        """
        # Remove path components that contain % (date templates)
        parts = path.split("/")
        # Keep only parts that don't contain %
        base_parts = [p for p in parts if "%" not in p]
        # Rejoin, ensuring we preserve leading /
        result = "/".join(base_parts)
        # Normalize path (remove duplicate slashes, etc.)
        return str(Path(result))

    @staticmethod
    def _is_subdirectory(child: str, parent: str) -> bool:
        """Check if child path is within parent directory.

        Args:
            child: Potential subdirectory path
            parent: Parent directory path

        Returns:
            True if child is within parent directory
        """
        try:
            child_path = Path(child).resolve()
            parent_path = Path(parent).resolve()
            # Check if child is relative to parent (will raise ValueError if not)
            child_path.relative_to(parent_path)
            return True
        except (ValueError, RuntimeError):
            return False

    def _validate_directories(self, user_configs: "Sequence[UserConfig]") -> None:
        """Validate that all icloudpd directories are within Immich library importPaths.

        Args:
            user_configs: List of user configurations containing directory settings

        Raises:
            SystemExit: If any directory is not within library importPaths
        """
        assert self.server_url is not None
        assert self.api_key is not None
        assert self.library_id is not None

        try:
            # Fetch library data to get importPaths
            url = f"{self.server_url}/api/libraries/{self.library_id}"
            headers = {"x-api-key": self.api_key}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            library_data = response.json()
            import_paths = library_data.get("importPaths", [])

            if not import_paths:
                print("Warning: Immich library has no importPaths configured", file=sys.stderr)
                print(
                    "Please configure importPaths in your Immich library settings", file=sys.stderr
                )
                sys.exit(1)

            # Collect all directories from user configs
            user_directories = []
            for user_config in user_configs:
                directory = user_config.directory
                # Strip date templates from the directory path
                base_directory = self._strip_date_templates(directory)
                user_directories.append((directory, base_directory))

            # Validate each directory is within at least one importPath
            invalid_dirs = []
            for original_dir, base_dir in user_directories:
                is_valid = False
                for import_path in import_paths:
                    if self._is_subdirectory(base_dir, import_path):
                        is_valid = True
                        break

                if not is_valid:
                    invalid_dirs.append(original_dir)

            # If any directories are invalid, exit with error
            if invalid_dirs:
                print(
                    "Error: The following icloudpd directories are not within Immich library importPaths:",
                    file=sys.stderr,
                )
                for invalid_dir in invalid_dirs:
                    print(f"  - {invalid_dir}", file=sys.stderr)
                print("\nImmich library importPaths:", file=sys.stderr)
                for import_path in import_paths:
                    print(f"  - {import_path}", file=sys.stderr)
                print(
                    "\nAll icloudpd directories must be subdirectories of at least one Immich importPath.",
                    file=sys.stderr,
                )
                sys.exit(1)

            # Success - print confirmation
            print(f"  Directory validation: OK ({len(user_directories)} directories validated)")

        except requests.RequestException as e:
            print(
                f"Error: Failed to fetch library data for directory validation: {e}",
                file=sys.stderr,
            )
            sys.exit(1)

    def _test_immich_connection(self) -> None:
        """Test connection to Immich server and validate library ID.

        Raises:
            SystemExit: If connection fails or library ID is invalid
        """
        # Validate required values (should be guaranteed by configure() validation)
        assert self.server_url is not None
        assert self.api_key is not None
        assert self.library_id is not None

        try:
            # Test general connection with /api/server/about
            url = f"{self.server_url}/api/server/about"
            headers = {"x-api-key": self.api_key}

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # Validate library ID exists
            url = f"{self.server_url}/api/libraries/{self.library_id}"
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            library_data = response.json()
            library_name = library_data.get("name", "Unknown")
            print(f"  Connected to Immich library: {library_name}")

        except requests.RequestException as e:
            print(f"Error: Failed to connect to Immich: {e}", file=sys.stderr)
            print(
                "Please check --immich-server-url, --immich-api-key, and --immich-library-id",
                file=sys.stderr,
            )
            sys.exit(1)

    # ========================================================================
    # Per-Size Hooks - Accumulate Data
    # ========================================================================

    def on_download_exists(
        self,
        download_path: str,
        photo_filename: str,
        download_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """File already exists - add to accumulator if process_existing is enabled"""
        # Check if we should process this existing file
        should_process = False

        if self.process_existing:
            # Process all existing files
            should_process = True
        elif self.process_existing_favorites:
            # Only process if photo is marked as favorite in iCloud
            is_favorite = (
                photo._asset_record.get("fields", {}).get("isFavorite", {}).get("value") == 1
            )
            if is_favorite:
                should_process = True
                logger.debug("Immich: Photo is favorite, will process existing file")
            else:
                logger.debug("Immich: Photo is not favorite, skipping existing file")

        if should_process:
            logger.debug(
                f"Immich: Accumulating existing file {download_size.value} - {download_path}"
            )
            self.current_photo_files.append(
                {
                    "status": "existed",
                    "path": download_path,
                    "size": download_size.value,
                    "is_live": False,
                    "photo_filename": photo_filename,
                }
            )
        else:
            logger.debug("Immich: Skipping existing file (not configured to process)")

    def on_download_downloaded(
        self,
        download_path: str,
        photo_filename: str,
        download_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """File was downloaded - always add to accumulator"""
        logger.debug(
            f"Immich: Accumulating downloaded file {download_size.value} - {download_path}"
        )
        self.current_photo_files.append(
            {
                "status": "downloaded",
                "path": download_path,
                "size": download_size.value,
                "is_live": False,
                "photo_filename": photo_filename,
            }
        )

    def on_download_complete(
        self,
        download_path: str,
        photo_filename: str,
        download_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """Size processing complete - hook available but not needed"""
        pass

    # ========================================================================
    # Live Photo Hooks - COMMENTED OUT (not needed - Immich handles automatically)
    # ========================================================================
    #
    # Live photo videos are NOT processed separately. They are automatically
    # associated with the main photo asset by Immich when we use the
    # livePhotoVideoId association in Step 5 of on_download_all_sizes_complete.
    #
    # We do NOT want to:
    # - Track live photo videos as separate files
    # - Search for them in Immich
    # - Stack them
    # - Add them to albums
    #
    # The live photo video is handled entirely through the association API.
    #
    # def on_download_exists_live(
    #     self,
    #     download_path: str,
    #     photo_filename: str,
    #     download_size: VersionSize,
    #     photo: PhotoAsset,
    #     dry_run: bool,
    # ) -> None:
    #     """Live photo exists - track filename for later association"""
    #     if self.process_existing:
    #         logger.debug(f"Immich: Accumulating existing live photo {download_size.value} - {download_path}")
    #         self.current_photo_files.append({
    #             'status': 'existed',
    #             'path': download_path,
    #             'size': download_size.value,
    #             'is_live': True,
    #             'photo_filename': photo_filename,
    #         })
    #         # Track that this photo has a live component
    #         self.live_photo_filename = photo_filename
    #
    # def on_download_downloaded_live(
    #     self,
    #     download_path: str,
    #     photo_filename: str,
    #     download_size: VersionSize,
    #     photo: PhotoAsset,
    #     dry_run: bool,
    # ) -> None:
    #     """Live photo downloaded - track filename for later association"""
    #     logger.debug(f"Immich: Accumulating downloaded live photo {download_size.value} - {download_path}")
    #     self.current_photo_files.append({
    #         'status': 'downloaded',
    #         'path': download_path,
    #         'size': download_size.value,
    #         'is_live': True,
    #         'photo_filename': photo_filename,
    #     })
    #     # Track that this photo has a live component
    #     self.live_photo_filename = photo_filename
    #
    # def on_download_complete_live(
    #     self,
    #     download_path: str,
    #     photo_filename: str,
    #     download_size: VersionSize,
    #     photo: PhotoAsset,
    #     dry_run: bool,
    # ) -> None:
    #     """Live photo processing complete - hook available but not needed"""
    #     pass

    # ========================================================================
    # Immich API Functions
    # ========================================================================

    def _trigger_library_scan(self, library_id: str) -> None:
        """Trigger a library scan in Immich.

        Args:
            library_id: The Immich library ID to scan

        Raises:
            requests.RequestException: If API call fails
        """
        assert self.server_url is not None
        assert self.api_key is not None
        url = f"{self.server_url}/api/libraries/{library_id}/scan"
        headers = {"x-api-key": self.api_key}
        body = {"refreshAllFiles": False}

        logger.debug(f"POST {url}")
        response = requests.post(url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        logger.debug(f"Library scan triggered: {response.status_code}")

    def _search_asset_by_path(self, file_path: str) -> Dict[str, Any] | None:
        """Search for a single asset by exact originalPath.

        Args:
            file_path: The exact file path to search for

        Returns:
            Asset dictionary from Immich API, or None if not found

        Raises:
            requests.RequestException: If API call fails
        """
        assert self.server_url is not None
        assert self.api_key is not None
        url = f"{self.server_url}/api/search/metadata"
        headers = {"x-api-key": self.api_key}
        body = {"originalPath": file_path}

        logger.debug(f"POST {url} (searching for: {file_path})")
        response = requests.post(url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Extract assets from response: {"assets": {"items": [...]}}
        assets = data.get("assets", {}).get("items", [])

        if assets:
            # Should only be one exact match
            asset = assets[0]
            logger.debug(f"Found asset: {asset.get('id')}")
            return asset

        logger.debug("Asset not found")
        return None

    def _create_stack(self, asset_ids: List[str]) -> None:
        """Create a stack in Immich with specified assets.

        Args:
            asset_ids: List of asset IDs to stack together (first = primary)

        Raises:
            requests.RequestException: If API call fails
        """
        assert self.server_url is not None
        assert self.api_key is not None
        url = f"{self.server_url}/api/stacks"
        headers = {"x-api-key": self.api_key}
        body = {"assetIds": asset_ids}

        logger.debug(f"POST {url}")
        logger.debug(f"  Stacking {len(asset_ids)} assets, primary: {asset_ids[0]}")
        response = requests.post(url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        logger.debug("Stack created successfully")

    def _set_favorite(self, asset_ids: List[str], is_favorite: bool) -> None:
        """Set favorite status for multiple assets.

        Args:
            asset_ids: List of asset IDs
            is_favorite: Whether to mark as favorite

        Raises:
            requests.RequestException: If API call fails
        """
        assert self.server_url is not None
        assert self.api_key is not None
        url = f"{self.server_url}/api/assets"
        headers = {"x-api-key": self.api_key}
        body = {"ids": asset_ids, "isFavorite": is_favorite}

        logger.debug(f"PUT {url}")
        logger.debug(f"  Setting favorite={is_favorite} for {len(asset_ids)} assets")
        response = requests.put(url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        logger.debug("Favorites updated successfully")

    def _get_or_create_album(self, album_name: str) -> str:
        """Get existing album or create new one.

        Args:
            album_name: Name of the album

        Returns:
            Album ID

        Raises:
            requests.RequestException: If API call fails
        """
        assert self.server_url is not None
        assert self.api_key is not None
        url = f"{self.server_url}/api/albums"
        headers = {"x-api-key": self.api_key}

        # Get all albums
        logger.debug(f"GET {url} (searching for album: {album_name})")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        albums = response.json()

        # Search for existing album
        for album in albums:
            if album.get("albumName") == album_name:
                album_id = album.get("id")
                logger.debug(f"Found existing album: {album_name} (id: {album_id})")
                return album_id

        # Create new album
        body = {"albumName": album_name}
        logger.debug(f"POST {url} (creating album: {album_name})")
        response = requests.post(url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        album_data = response.json()
        album_id = album_data.get("id")
        logger.debug(f"Created new album: {album_name} (id: {album_id})")
        return album_id

    def _add_assets_to_album(self, album_id: str, asset_ids: List[str]) -> None:
        """Add assets to an album.

        Args:
            album_id: The album ID
            asset_ids: List of asset IDs to add

        Raises:
            requests.RequestException: If API call fails
        """
        assert self.server_url is not None
        assert self.api_key is not None
        url = f"{self.server_url}/api/albums/{album_id}/assets"
        headers = {"x-api-key": self.api_key}
        body = {"ids": asset_ids}

        logger.debug(f"PUT {url}")
        logger.debug(f"  Adding {len(asset_ids)} assets to album")
        response = requests.put(url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        logger.debug("Assets added to album successfully")

    def _associate_live_photo(self, asset_id: str, live_photo_video_id: str) -> None:
        """Associate a live photo video with an asset.

        Args:
            asset_id: The image asset ID to associate with
            live_photo_video_id: The live photo video ID

        Raises:
            requests.RequestException: If API call fails
        """
        assert self.server_url is not None
        assert self.api_key is not None
        url = f"{self.server_url}/api/assets/{asset_id}"
        headers = {"x-api-key": self.api_key}
        body = {"livePhotoVideoId": live_photo_video_id}

        logger.debug(f"PATCH {url}")
        logger.debug(f"  Associating live video: {live_photo_video_id}")
        response = requests.patch(url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        logger.debug("Live photo associated successfully")

    # ========================================================================
    # Processing Logic
    # ========================================================================

    def _wait_for_assets(
        self, expected_files: List[Dict[str, Any]], timeout: float
    ) -> Dict[str, Dict[str, Any]]:
        """Wait for all expected files to appear in Immich after scan.

        Polls Immich every 50ms until all files are found or timeout occurs.
        Searches for each file individually by exact path.

        Args:
            expected_files: List of file info dicts from current_photo_files
            timeout: Maximum time to wait in seconds (0 = infinite)

        Returns:
            Mapping of path -> asset info (includes 'id', 'originalPath', 'livePhotoVideoId', etc.)

        Raises:
            SystemExit: If timeout exceeded before all assets found
        """
        if not expected_files:
            return {}

        # Build set of expected paths for quick lookup
        expected_paths = {f["path"] for f in expected_files}

        logger.info(f"  Waiting for {len(expected_paths)} assets to appear in Immich...")

        start_time = time.time()
        found_assets: Dict[str, Dict[str, Any]] = {}
        paths_to_search = list(expected_paths)  # Paths we haven't found yet

        while True:
            # Search for each file we haven't found yet
            for file_path in list(
                paths_to_search
            ):  # Use list() to avoid modification during iteration
                asset = self._search_asset_by_path(file_path)
                if asset:
                    found_assets[file_path] = asset
                    paths_to_search.remove(file_path)
                    logger.debug(f"    Found: {file_path} -> {asset.get('id', 'unknown')}")

            # Check if all found
            if len(found_assets) == len(expected_paths):
                elapsed = time.time() - start_time
                logger.info(f"  All {len(found_assets)} assets found in {elapsed:.2f}s")
                return found_assets

            # Check timeout
            elapsed = time.time() - start_time
            if timeout > 0 and elapsed >= timeout:
                missing = expected_paths - set(found_assets.keys())
                logger.error(f"Timeout waiting for Immich assets after {timeout}s")
                logger.error(f"Found {len(found_assets)}/{len(expected_paths)} assets")
                logger.error(f"Missing: {missing}")
                sys.exit(1)

            # Sleep before next poll
            time.sleep(self.poll_interval)

    def _find_assets_for_files(
        self, files: List[Dict[str, str]], trigger_scan: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """Find assets in Immich, optionally triggering scan and waiting.

        Args:
            files: List of file info dicts with 'path' key
            trigger_scan: If True, trigger library scan and wait for assets

        Returns:
            Mapping of path -> asset info (includes 'id', 'originalPath', 'livePhotoVideoId', etc.)

        Raises:
            SystemExit: If scan triggered and timeout exceeded before all assets found
        """
        if trigger_scan:
            # Trigger scan and wait for all assets
            logger.info(f"  Triggering library scan for {len(files)} files")
            try:
                assert self.library_id is not None
                self._trigger_library_scan(self.library_id)
            except requests.RequestException as e:
                logger.error(f"FATAL: Failed to trigger library scan: {e}")
                sys.exit(1)

            # Wait for all files to appear
            return self._wait_for_assets(expected_files=files, timeout=self.scan_timeout)
        else:
            # Just search without scanning
            found_assets: Dict[str, Dict[str, Any]] = {}
            for file_info in files:
                asset = self._search_asset_by_path(file_info["path"])
                if asset:
                    found_assets[file_info["path"]] = asset
            return found_assets

    def _ensure_assets_registered(self, files: List[Dict[str, str]]) -> Dict[str, Dict[str, Any]]:
        """Ensure all files are registered in Immich, scanning only if needed.

        This implements smart scan logic:
        - If any files are newly downloaded, always scan (they won't exist yet)
        - If all files existed, search first without scanning
        - If all found, skip scan (optimization)
        - If some missing, then trigger scan

        Args:
            files: List of file info dicts with 'status' and 'path' keys

        Returns:
            Mapping of path -> asset info for all files

        Raises:
            SystemExit: If scan needed and timeout exceeded
        """
        has_new = _has_new_files(files)

        if has_new:
            # New files require scan
            logger.info("  New files detected, triggering scan")
            return self._find_assets_for_files(files, trigger_scan=True)

        # All files existed - check first without scanning
        logger.info("  All files already existed, checking if assets already registered...")
        found = self._find_assets_for_files(files, trigger_scan=False)

        if len(found) == len(files):
            logger.info(f"  All {len(found)} assets already registered, skipping scan")
            return found

        # Some assets missing - need to scan
        logger.info(f"  Found {len(found)}/{len(files)} assets, triggering scan for missing files")
        return self._find_assets_for_files(files, trigger_scan=True)

    # ========================================================================
    # Post-Processing Functions
    # ========================================================================

    def _process_stacking(self, assets: List[Dict[str, Any]]) -> None:
        """Create stacks for size variants.

        Args:
            assets: List of asset dicts with 'size' and 'asset_id' keys
        """
        if not self.stack_media or len(assets) <= 1:
            return

        # Build priority-ordered list of asset IDs
        ordered_ids = []

        # Add assets in priority order
        for priority_size in self.stack_priority:
            for asset in assets:
                if asset["size"] == priority_size and asset["asset_id"] not in ordered_ids:
                    ordered_ids.append(asset["asset_id"])

        # Add remaining assets not in priority list
        for asset in assets:
            if asset["asset_id"] not in ordered_ids:
                ordered_ids.append(asset["asset_id"])

        if len(ordered_ids) <= 1:
            return

        # Create stack
        try:
            self._create_stack(ordered_ids)
            logger.info(f"  Stacked {len(ordered_ids)} size variants")
            self.total_stacked += 1
        except requests.RequestException as e:
            logger.error(f"FATAL: Failed to create stack: {e}")
            sys.exit(1)

    def _process_favoriting(self, assets: List[Dict[str, Any]], is_favorite: bool) -> None:
        """Mark configured sizes as favorite.

        Args:
            assets: List of asset dicts with 'size' and 'asset_id' keys
            is_favorite: Whether photo is marked favorite in iCloud
        """
        if not self.favorite_sizes or not is_favorite:
            return

        asset_ids = _get_asset_ids_for_sizes(assets, self.favorite_sizes)

        if not asset_ids:
            return

        try:
            self._set_favorite(asset_ids, True)
            logger.info(f"  Marked {len(asset_ids)} assets as favorite")
            self.total_favorited += len(asset_ids)
        except requests.RequestException as e:
            logger.error(f"FATAL: Failed to mark favorites: {e}")
            sys.exit(1)

    def _process_live_association(self, assets: List[Dict[str, Any]]) -> None:
        """Associate live photo video with size variants.

        Args:
            assets: List of asset dicts with 'size', 'asset_id', and 'live_photo_video_id' keys
        """
        if not self.associate_live_sizes:
            return

        # Find the original live photo video ID
        original_video_id = None
        for asset in assets:
            if asset.get("live_photo_video_id"):
                original_video_id = asset["live_photo_video_id"]
                break

        if not original_video_id:
            return

        # Associate with configured sizes
        associated_count = 0
        for asset in assets:
            if asset["size"] not in self.associate_live_sizes:
                continue

            # Skip if already has this live video ID
            if asset.get("live_photo_video_id") == original_video_id:
                continue

            try:
                self._associate_live_photo(asset["asset_id"], original_video_id)
                logger.info(f"  Associated live video with {asset['size']}")
                associated_count += 1
            except requests.RequestException as e:
                logger.error(f"FATAL: Failed to associate live photo with {asset['size']}: {e}")
                sys.exit(1)

        if associated_count > 0:
            self.total_live_associated += associated_count

    def _process_albums(
        self, assets: List[Dict[str, Any]], photo_created: Any, photo_filename: str
    ) -> None:
        """Add assets to albums based on rules.

        Args:
            assets: List of asset dicts with 'size' and 'asset_id' keys
            photo_created: Photo creation date for template substitution
            photo_filename: Photo filename for logging
        """
        if not self.album_rules:
            return

        # Build a map of album_name -> [asset_ids]
        album_assignments: Dict[str, List[str]] = {}

        for rule in self.album_rules:
            # Parse the template with photo's created date
            try:
                if "{:" in rule.template:
                    album_name = rule.template.format(photo_created)
                else:
                    album_name = rule.template
            except (AttributeError, ValueError, KeyError) as e:
                logger.error(f"Error parsing album template '{rule.template}': {e}")
                continue

            # Find matching assets
            for asset in assets:
                if rule.matches(asset["size"]):
                    if album_name not in album_assignments:
                        album_assignments[album_name] = []
                    album_assignments[album_name].append(asset["asset_id"])

        # Add assets to their assigned albums
        for album_name, asset_ids in album_assignments.items():
            # Remove duplicates
            asset_ids = list(set(asset_ids))

            try:
                album_id = self._get_or_create_album(album_name)
                self._add_assets_to_album(album_id, asset_ids)
                logger.info(f"  Added {len(asset_ids)} assets to album '{album_name}'")
                self.total_added_to_albums += 1
            except requests.RequestException as e:
                logger.error(f"FATAL: Failed to add assets to album '{album_name}': {e}")
                sys.exit(1)

    # ========================================================================
    # Main Processing Pipeline
    # ========================================================================

    def _process_photo_group(
        self,
        files: List[Dict[str, str]],
        photo_id: str,
        is_favorite: bool,
        photo_created: Any,
        photo_filename: str,
        favorites_only: bool = False,
    ) -> None:
        """Process a single photo group (all sizes of one photo).

        This is the unified pipeline used by both immediate and batch processing modes.

        Args:
            files: List of file info dicts with 'status', 'path', 'size' keys
            photo_id: Photo ID for logging
            is_favorite: Whether photo is marked favorite in iCloud
            photo_created: Photo creation date for album template substitution
            photo_filename: Photo filename for logging
            favorites_only: If True, only process favoriting (skip stacking/albums/live)
        """
        logger.info(f"  Processing photo group: {photo_filename}")

        # Step 1: Ensure all files are registered in Immich
        found_assets = self._ensure_assets_registered(files)

        # Step 2: Build asset list with metadata
        assets: List[Dict[str, Any]] = []
        for file_info in files:
            path = file_info["path"]
            asset = found_assets.get(path)

            if not asset:
                logger.error(f"FATAL: Asset not found for {path} (should never happen)")
                sys.exit(1)

            assets.append(
                {
                    "size": file_info["size"],
                    "asset_id": asset.get("id"),
                    "path": path,
                    "live_photo_video_id": asset.get("livePhotoVideoId"),
                }
            )

            logger.info(f"  Registered {file_info['size']}: {path} -> {asset.get('id')}")
            self.total_registered += 1

        # Step 3: Post-processing
        if favorites_only:
            # Only favorite (for existing favorites mode)
            self._process_favoriting(assets, is_favorite)
        else:
            # Full processing pipeline
            self._process_stacking(assets)
            self._process_live_association(assets)
            self._process_favoriting(assets, is_favorite)
            self._process_albums(assets, photo_created, photo_filename)

        self.total_photos += 1

    # ========================================================================
    # Main Processing Hook
    # ========================================================================

    def on_download_all_sizes_complete(
        self,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """Process all accumulated files after all sizes are downloaded.

        Args:
            photo: PhotoAsset with metadata (for favorite status, date, etc.)
            dry_run: If True, only log what would happen
        """
        # Validate required configuration (should be guaranteed by configure())
        assert self.server_url is not None
        assert self.api_key is not None
        assert self.library_id is not None

        # Skip if no files to process
        if not self.current_photo_files:
            logger.debug(f"Immich: No files to process for {photo.filename}")
            return

        # Dry run mode - just log and clear
        if dry_run:
            for file_info in self.current_photo_files:
                logger.info(f"  [DRY RUN] Would process {file_info['size']}: {file_info['path']}")
            self.current_photo_files.clear()
            return

        # Batch processing logic:
        # - batch_size == 0 ('all'): Accumulate all photos, process at end (on_run_completed)
        # - batch_size == 1 (default): Process immediately (accumulate + process batch of 1)
        # - batch_size > 1: Accumulate until batch size reached, then process batch
        #
        # Note: We ALWAYS accumulate first, then decide whether to process the batch.
        # This keeps the code simple - processing a batch of 1 works fine!

        logger.info(
            f"Immich: Accumulating {photo.filename} to batch ({len(self.current_photo_files)} files)"
        )
        self._accumulate_to_batch(photo)

        # Decide whether to process the batch now
        # batch_size == 0: Never process (wait for on_run_completed)
        # batch_size >= 1: Process when batch queue reaches batch_size
        if self.batch_size > 0 and len(self.batch_queue) >= self.batch_size:
            logger.info(f"Batch size ({self.batch_size}) reached, processing batch now")
            self._process_batch()

    # ========================================================================
    # Batch Processing Methods
    # ========================================================================

    def _load_pending_files(self) -> None:
        """Load pending files from batch log file (for crash recovery).

        Called during plugin initialization if batch processing is enabled.
        Loads any unprocessed photos from a previous run that was interrupted.
        """
        if not os.path.exists(self.batch_log_file):
            logger.debug(f"No pending batch file found at {self.batch_log_file}")
            return

        try:
            with open(self.batch_log_file) as f:
                pending_data = json.load(f)

            if pending_data:
                self.batch_queue = pending_data
                logger.info(f"Loaded {len(self.batch_queue)} pending photos from previous run")
                logger.info("These will be processed first before new photos")
            else:
                logger.debug("Pending batch file is empty")

        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load pending batch file: {e}")
            logger.warning("Starting with empty batch queue")
            self.batch_queue = []

    def _save_pending_files(self) -> None:
        """Save current batch queue to disk for crash recovery.

        Writes the batch queue to a JSON file so that if the process crashes,
        we can resume from where we left off on the next run.
        """
        try:
            # Create directory if it doesn't exist
            log_dir = os.path.dirname(self.batch_log_file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)

            with open(self.batch_log_file, "w") as f:
                json.dump(self.batch_queue, f, indent=2, default=str)

            logger.debug(f"Saved {len(self.batch_queue)} pending photos to {self.batch_log_file}")

        except OSError as e:
            logger.error(f"Failed to save pending batch file: {e}")
            logger.error("Progress may be lost if process is interrupted")

    def _clear_processed_from_log(self, photo_ids: List[str]) -> None:
        """Remove successfully processed photos from batch queue and update log file.

        Args:
            photo_ids: List of photo IDs that were successfully processed
        """
        # Remove processed photos from batch queue
        self.batch_queue = [item for item in self.batch_queue if item["photo_id"] not in photo_ids]

        # Update log file
        self._save_pending_files()

        logger.debug(f"Cleared {len(photo_ids)} processed photos from batch log")

    def _accumulate_to_batch(self, photo: PhotoAsset) -> None:
        """Add current photo and its files to the batch queue.

        Args:
            photo: PhotoAsset with metadata needed for processing later
        """
        if not self.current_photo_files:
            logger.debug(f"No files to accumulate for {photo.id}")
            return

        # Extract necessary metadata from photo for later processing
        is_favorite = photo._asset_record.get("fields", {}).get("isFavorite", {}).get("value") == 1

        # Build batch item
        batch_item = {
            "photo_id": photo.id,
            "files": self.current_photo_files.copy(),  # Copy the file list
            "is_favorite": is_favorite,
            "created": photo.created.isoformat()
            if hasattr(photo.created, "isoformat")
            else str(photo.created),
            "filename": photo.filename,
        }

        self.batch_queue.append(batch_item)
        logger.debug(f"Added photo {photo.id} to batch queue ({len(self.batch_queue)} total)")

        # Save to disk for crash recovery
        self._save_pending_files()

        # Clear current photo files for next photo
        self.current_photo_files.clear()

    def _process_batch(self) -> None:
        """Process all photos in the current batch queue.

        Uses the unified _process_photo_group pipeline for each photo.
        """
        # Validate required configuration (should be guaranteed by configure())
        assert self.server_url is not None
        assert self.api_key is not None
        assert self.library_id is not None

        if not self.batch_queue:
            logger.debug("Batch queue is empty, nothing to process")
            return

        logger.info(f"Processing batch of {len(self.batch_queue)} photos")
        successfully_processed = []

        # Process each photo in the batch using unified pipeline
        for batch_item in self.batch_queue:
            try:
                # Reconstruct photo_created from ISO string if needed
                from datetime import datetime

                photo_created = batch_item.get("created")
                if isinstance(photo_created, str):
                    photo_created = datetime.fromisoformat(photo_created)

                # Calculate favorites_only flag for this batch item
                # Same logic as immediate mode:
                # 1. All files existed (not downloaded)
                # 2. process_existing_favorites is enabled
                # 3. Photo is actually marked as favorite
                all_existed = all(f["status"] == "existed" for f in batch_item["files"])
                is_favorite = batch_item["is_favorite"]
                favorites_only = all_existed and self.process_existing_favorites and is_favorite

                # Process using unified pipeline
                self._process_photo_group(
                    files=batch_item["files"],
                    photo_id=batch_item["photo_id"],
                    is_favorite=is_favorite,
                    photo_created=photo_created,
                    photo_filename=batch_item.get("filename", ""),
                    favorites_only=favorites_only,
                )

                successfully_processed.append(batch_item["photo_id"])

            except Exception as e:
                logger.error(f"Failed to process photo {batch_item['photo_id']}: {e}")
                # Continue with next photo

        # Clear processed photos from log
        self._clear_processed_from_log(successfully_processed)

        logger.info(f"Batch processing complete: {len(successfully_processed)} photos processed")

    # ========================================================================
    # Run Complete Hook
    # ========================================================================

    def on_run_completed(self, dry_run: bool) -> None:
        """Run complete - process any remaining batch and show final summary"""
        # Process any remaining photos in batch queue (if batch mode enabled)
        if self.batch_size != 1 and self.batch_queue:
            logger.info(f"Processing remaining batch of {len(self.batch_queue)} photos")
            self._process_batch()

        logger.info("=" * 70)
        logger.info("Immich Plugin: Run Completed")
        logger.info("=" * 70)
        logger.info(f"  Total Photos Processed:    {self.total_photos}")
        logger.info(f"  Files Registered:          {self.total_registered}")
        logger.info(f"  Stacks Created:            {self.total_stacked}")
        logger.info(f"  Assets Favorited:          {self.total_favorited}")
        logger.info(f"  Live Photos Associated:    {self.total_live_associated}")
        logger.info(f"  Albums Updated:            {self.total_added_to_albums}")
        logger.info("=" * 70)

    def cleanup(self) -> None:
        """Cleanup called on shutdown"""
        logger.debug("Immich Plugin: Cleanup called")
