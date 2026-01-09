"""Base plugin class for icloudpd

All plugins should inherit from IcloudpdPlugin and implement the hooks they need.
"""

from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace
from typing import TYPE_CHECKING

from pyicloud_ipd.services.photos import PhotoAsset
from pyicloud_ipd.version_size import VersionSize

if TYPE_CHECKING:
    from typing import Sequence

    from icloudpd.config import GlobalConfig, UserConfig


class IcloudpdPlugin(ABC):
    """Base class for icloudpd plugins.

    To create a plugin:
    1. Subclass IcloudpdPlugin
    2. Implement the name property (required)
    3. Implement hook methods you need (optional)
    4. Add CLI arguments if needed (optional)
    5. Register via entry point in pyproject.toml

    Example:
        >>> class MyPlugin(IcloudpdPlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "myplugin"
        ...
        ...     def on_download_all_sizes_complete(self, photo, **kwargs):
        ...         print(f"Photo complete: {photo.filename}")

        Then in pyproject.toml:
        [project.entry-points."icloudpd.plugins"]
        myplugin = "my_package.plugin:MyPlugin"
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name (e.g., 'immich', 'backup')

        This must match the entry point name in pyproject.toml.
        Used for --plugin NAME on the command line.

        Returns:
            Plugin name in lowercase, no spaces
        """
        ...

    @property
    def version(self) -> str:
        """Plugin version

        Returns:
            Version string (e.g., '1.0.0')
        """
        return "0.1.0"

    @property
    def description(self) -> str:
        """Short description shown in help text

        Returns:
            One-line description of what the plugin does
        """
        return ""

    def add_arguments(self, parser: ArgumentParser) -> None:  # noqa: B027
        """Add plugin-specific CLI arguments.

        Create an argument group for your plugin and add arguments to it.
        Arguments will be shown in --help when the plugin is enabled.

        Args:
            parser: ArgumentParser to add arguments to

        Example:
            >>> def add_arguments(self, parser):
            ...     group = parser.add_argument_group("My Plugin Options")
            ...     group.add_argument("--my-option", help="My option")
            ...     group.add_argument("--my-flag", action="store_true")
        """
        ...

    def configure(  # noqa: B027
        self,
        config: Namespace,
        global_config: "GlobalConfig | None" = None,
        user_configs: "Sequence[UserConfig] | None" = None,
    ) -> None:
        """Configure plugin from parsed CLI arguments.

        Called once during initialization when all configs are available.

        Use this to initialize your plugin with the provided configuration.
        Avoid printing messages here - use on_configure_complete() instead.

        Args:
            config: Parsed arguments namespace containing all CLI arguments
            global_config: Global configuration object
            user_configs: List of user configurations

        Example:
            >>> def configure(self, config, global_config=None, user_configs=None):
            ...     self.api_key = config.my_api_key
            ...     self.client = MyClient(self.api_key)
            ...     # Use configs if available for validation
            ...     if user_configs:
            ...         directories = [uc.directory for uc in user_configs]
            ...         self.validate_directories(directories)
        """
        ...

    def on_configure_complete(self) -> None:  # noqa: B027
        """Called after configuration is complete.

        Use this hook to print configuration messages or perform post-configuration
        actions that should only happen once. This is called after configure()
        when the plugin manager has all runtime configs available.

        Example:
            >>> def on_configure_complete(self):
            ...     print(f"Immich plugin configured:")
            ...     print(f"  Server: {self.server_url}")
            ...     print(f"  Process existing: {self.process_existing}")
        """
        ...

    # ========================================================================
    # HOOK METHODS - All optional, implement what you need
    # ========================================================================

    # Per-size hooks (called for each size variant)

    def on_download_exists(  # noqa: B027
        self,
        download_path: str,
        photo_filename: str,
        requested_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """Called when a file already exists (per size variant)"""
        ...

    def on_download_downloaded(  # noqa: B027
        self,
        download_path: str,
        photo_filename: str,
        requested_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """Called after a file is downloaded (per size variant)"""
        ...

    def on_download_complete(  # noqa: B027
        self,
        download_path: str,
        photo_filename: str,
        requested_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """Called after a size is processed - ALWAYS runs (per size variant)"""
        ...

    # Live photo hooks

    def on_download_exists_live(  # noqa: B027
        self,
        download_path: str,
        photo_filename: str,
        requested_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """Called when live photo video already exists"""
        ...

    def on_download_downloaded_live(  # noqa: B027
        self,
        download_path: str,
        photo_filename: str,
        requested_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """Called after live photo video is downloaded"""
        ...

    def on_download_complete_live(  # noqa: B027
        self,
        download_path: str,
        photo_filename: str,
        requested_size: VersionSize,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """Called after live photo is processed - ALWAYS runs"""
        ...

    # Per-photo hook (KEY HOOK - called once per photo)

    def on_download_all_sizes_complete(  # noqa: B027
        self,
        photo: PhotoAsset,
        dry_run: bool,
    ) -> None:
        """Called after ALL sizes of a photo are complete.

        This is the most important hook for most plugins.
        Use this to process the complete photo with all its size variants.
        """
        ...

    # Per-run hook (called once at end)

    def on_run_completed(  # noqa: B027
        self,
        dry_run: bool,
    ) -> None:
        """Called after entire download run is complete"""
        ...

    def cleanup(self) -> None:  # noqa: B027
        """Called on shutdown, even if there was an error.

        Override this to clean up resources, close connections, etc.
        Will be called even if downloads failed or were interrupted.
        """
        ...
