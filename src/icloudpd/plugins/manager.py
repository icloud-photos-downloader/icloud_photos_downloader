"""Plugin manager for discovery, loading, and hook dispatching

The PluginManager handles:
- Discovering plugins via Python entry points
- Loading and enabling plugins
- Dispatching hook calls to all enabled plugins
- Plugin lifecycle (configure, cleanup)
"""

import importlib.util
import inspect
import logging
import sys
from argparse import ArgumentParser, Namespace
from importlib.metadata import entry_points
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from icloudpd.plugins.base import IcloudpdPlugin

if TYPE_CHECKING:
    from typing import Sequence

    from icloudpd.config import GlobalConfig, UserConfig

logger = logging.getLogger(__name__)


class PluginManager:
    """Manages plugin discovery, loading, and hook dispatching.

    Usage:
        >>> manager = PluginManager()
        >>> manager.discover()  # Find all installed plugins  # doctest: +SKIP
        >>> manager.list_available()  # doctest: +SKIP
        ['demo', 'immich', ...]
        >>> from argparse import Namespace  # doctest: +SKIP
        >>> manager.enable("demo", Namespace())  # Enable a plugin  # doctest: +SKIP
        >>> manager.call_hook("on_photo_downloaded")  # Call hooks  # doctest: +SKIP
    """

    def __init__(self):
        """Initialize the plugin manager."""
        self.available: Dict[str, type] = {}  # name -> plugin class
        self.enabled: Dict[str, IcloudpdPlugin] = {}  # name -> plugin instance
        self.plugin_config: Namespace | None = None  # Stored config with plugin args
        self.global_config: GlobalConfig | None = None  # Global configuration
        self.user_configs: Sequence[UserConfig] | None = None  # User configurations
        self._configured_plugins: set[str] = set()  # Track which plugins have been configured

    def discover(self) -> None:
        """Discover plugins from bundled plugins/ directory and entry points.

        Discovery order (first wins):
        1. Bundled plugins in project-root/plugins/ directory
        2. Installed plugins via entry points

        Bundled plugins are package directories under plugins/ like:
            plugins/immich/__init__.py  (exports ImmichPlugin)

        Entry point plugins are registered in pyproject.toml like:
            [project.entry-points."icloudpd.plugins"]
            demo = "icloudpd.plugins.demo:DemoPlugin"
        """
        # 1. Discover from project-root/plugins/ directory
        try:
            # Navigate from src/icloudpd/plugins/ up to project root
            project_root = Path(__file__).parent.parent.parent.parent
            plugins_dir = project_root / "plugins"

            if plugins_dir.exists() and plugins_dir.is_dir():
                self._discover_from_directory(plugins_dir)
        except Exception as e:
            logger.warning(f"Failed to scan plugins directory: {e}")

        # 2. Discover from entry points
        try:
            discovered_eps = entry_points(group="icloudpd.plugins")
            for ep in discovered_eps:
                try:
                    # Skip if already discovered from plugins/ directory (precedence)
                    if ep.name in self.available:
                        logger.debug(
                            f"Skipping entry point '{ep.name}' (already loaded from plugins/)"
                        )
                        continue

                    plugin_class = ep.load()
                    self.available[ep.name] = plugin_class
                    logger.debug(f"Discovered plugin from entry point: {ep.name}")
                except Exception as e:
                    logger.warning(f"Failed to load entry point plugin '{ep.name}': {e}")
        except Exception as e:
            logger.warning(f"Failed to discover entry point plugins: {e}")

    def _discover_from_directory(self, directory: Path) -> None:
        """Discover plugins from a directory by scanning for plugin packages.

        Looks for package directories (containing __init__.py) and attempts to
        import them to find IcloudpdPlugin subclasses.

        Args:
            directory: Path to directory containing plugin packages
        """

        # Add parent directory to sys.path so we can import plugins.* modules
        plugins_parent = str(directory.parent)
        if plugins_parent not in sys.path:
            sys.path.insert(0, plugins_parent)

        # Scan for package directories
        for item in directory.iterdir():
            # Only process directories with __init__.py (packages)
            if not item.is_dir() or not (item / "__init__.py").exists():
                continue

            plugin_package_name = item.name
            module_name = f"plugins.{plugin_package_name}"

            try:
                # Import the plugin package
                module = importlib.import_module(module_name)

                # Extract plugin classes from the module
                self._extract_plugins_from_module(module, plugin_package_name)

            except Exception as e:
                logger.warning(f"Failed to load plugin package '{plugin_package_name}': {e}")

    def _extract_plugins_from_module(self, module, source_name: str) -> None:
        """Extract IcloudpdPlugin subclasses from a module.

        Args:
            module: Python module to inspect
            source_name: Name of the source (for logging)
        """
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # Check if it's a subclass of IcloudpdPlugin (but not the base class itself)
            if not issubclass(obj, IcloudpdPlugin) or obj is IcloudpdPlugin:
                continue

            # Must end with 'Plugin' by convention
            if not name.endswith("Plugin"):
                continue

            # Create temporary instance to get plugin name
            try:
                temp_instance = obj()
                plugin_name = temp_instance.name

                # Register the plugin class
                self.available[plugin_name] = obj
                logger.debug(
                    f"Discovered plugin: {plugin_name} (from {source_name}, v{temp_instance.version})"
                )

            except Exception as e:
                logger.warning(
                    f"Failed to instantiate plugin class '{name}' from {source_name}: {e}"
                )

    def list_available(self) -> List[str]:
        """Get list of available plugin names.

        Returns:
            List of plugin names that have been discovered
        """
        return sorted(self.available.keys())

    def get_plugin_info(self, name: str) -> Dict[str, str]:
        """Get information about a plugin.

        Args:
            name: Plugin name

        Returns:
            Dictionary with 'name', 'version', 'description'

        Raises:
            KeyError: If plugin not found
        """
        if name not in self.available:
            raise KeyError(f"Plugin '{name}' not found")

        plugin_class = self.available[name]
        temp_instance = plugin_class()

        return {
            "name": temp_instance.name,
            "version": temp_instance.version,
            "description": temp_instance.description,
        }

    def set_plugin_config(
        self,
        config: Namespace,
        global_config: Optional["GlobalConfig"] = None,
        user_configs: Optional["Sequence[UserConfig]"] = None,
    ) -> None:
        """Store the plugin configuration namespace and runtime configs.

        This should be called:
        1. Early (from cli.py) with just the namespace
        2. Late (from base.py) with the runtime configs

        When called with runtime configs, this will configure any enabled plugins
        that haven't been configured yet (or reconfigure with the new runtime configs).

        Args:
            config: Namespace with plugin arguments
            global_config: Global configuration object (optional)
            user_configs: List of user configurations (optional)
        """
        self.plugin_config = config

        # Track if we're receiving runtime configs for the first time
        had_runtime_configs = self.global_config is not None and self.user_configs is not None

        if global_config is not None:
            self.global_config = global_config
        if user_configs is not None:
            self.user_configs = user_configs

        # Configure enabled plugins now that we have runtime configs
        # Only do this if this is the first time we're receiving runtime configs
        if (
            not had_runtime_configs
            and self.global_config is not None
            and self.user_configs is not None
            and self.enabled
        ):
            for plugin_name, plugin in self.enabled.items():
                # Skip if already configured (this avoids double-configuration)
                if plugin_name in self._configured_plugins:
                    logger.debug(f"Plugin {plugin_name} already configured, skipping")
                    continue

                try:
                    logger.debug(f"Configuring plugin {plugin_name} with runtime configs")
                    plugin.configure(self.plugin_config, self.global_config, self.user_configs)
                    self._configured_plugins.add(plugin_name)
                    logger.info(f"Configured plugin: {plugin_name}")
                except Exception as e:
                    logger.error(
                        f"Failed to configure plugin {plugin_name} with runtime configs: {e}",
                        exc_info=True,
                    )

    def enable(self, name: str, config: Namespace | None = None) -> None:
        """Enable and configure a plugin.

        Creates an instance of the plugin and calls its configure() method with
        available configs. If runtime configs are available later via set_plugin_config(),
        the plugin will NOT be reconfigured (avoiding double-configuration).

        Args:
            name: Plugin name to enable
            config: Parsed CLI arguments (optional, uses stored plugin_config if not provided)

        Raises:
            KeyError: If plugin name not found in available plugins
            ValueError: If no configuration is available
        """
        if name not in self.available:
            available = ", ".join(self.list_available())
            raise KeyError(
                f"Plugin '{name}' not found. "
                f"Available plugins: {available if available else 'none'}"
            )

        # Use stored plugin config if not explicitly passed
        plugin_config = config if config is not None else self.plugin_config
        if plugin_config is None:
            raise ValueError(f"No configuration available for plugin {name}")

        try:
            plugin_class = self.available[name]
            plugin = plugin_class()

            # Configure the plugin with available configs
            plugin.configure(plugin_config, self.global_config, self.user_configs)

            # Mark as configured to prevent double-configuration in set_plugin_config()
            self._configured_plugins.add(name)

            self.enabled[name] = plugin
            logger.info(f"Enabled plugin: {name} (v{plugin.version})")

        except Exception as e:
            logger.error(f"Failed to enable plugin {name}: {e}", exc_info=True)
            raise

    def disable(self, name: str) -> None:
        """Disable a plugin and call its cleanup method.

        Args:
            name: Plugin name to disable
        """
        if name in self.enabled:
            try:
                self.enabled[name].cleanup()
                logger.debug(f"Called cleanup for plugin: {name}")
            except Exception as e:
                logger.warning(f"Error during {name} plugin cleanup: {e}")

            del self.enabled[name]
            self._configured_plugins.discard(name)
            logger.info(f"Disabled plugin: {name}")

    def is_enabled(self, name: str) -> bool:
        """Check if a plugin is currently enabled.

        Args:
            name: Plugin name

        Returns:
            True if plugin is enabled
        """
        return name in self.enabled

    def add_plugin_arguments(self, parser: ArgumentParser, plugin_names: List[str]) -> None:
        """Add CLI arguments for specified plugins.

        Calls add_arguments() on each plugin to let them register
        their CLI options.

        Args:
            parser: ArgumentParser to add arguments to
            plugin_names: List of plugin names to add arguments for
        """
        for name in plugin_names:
            if name in self.available:
                try:
                    plugin_class = self.available[name]
                    temp_instance = plugin_class()
                    temp_instance.add_arguments(parser)
                    logger.debug(f"Added arguments for plugin: {name}")
                except Exception as e:
                    logger.warning(f"Failed to add arguments for plugin {name}: {e}")

    def call_hook(self, hook_name: str, **kwargs) -> None:
        """Call a hook on all enabled plugins.

        Calls the specified hook method on each enabled plugin.
        If a plugin's hook raises an exception, it's logged but
        doesn't stop other plugins from running.

        Args:
            hook_name: Name of the hook method to call
            **kwargs: Arguments to pass to the hook

        Example:
            manager.call_hook(
                "on_photo_downloaded",
                photo_id="ABC123",
                photo_filename="IMG_1234.jpg",
                downloaded_files=[...],
                is_favorite=True,
                metadata={...},
            )
        """
        for plugin_name, plugin in self.enabled.items():
            method = getattr(plugin, hook_name, None)
            if method and callable(method):
                try:
                    method(**kwargs)
                except Exception as e:
                    logger.error(
                        f"Plugin '{plugin_name}' hook '{hook_name}' failed: {e}", exc_info=True
                    )

    def cleanup_all(self) -> None:
        """Cleanup all enabled plugins.

        Calls cleanup() on all enabled plugins and disables them.
        Safe to call multiple times.
        """
        # Create a list to avoid modifying dict during iteration
        plugin_names = list(self.enabled.keys())

        for name in plugin_names:
            self.disable(name)

        logger.debug("All plugins cleaned up")
