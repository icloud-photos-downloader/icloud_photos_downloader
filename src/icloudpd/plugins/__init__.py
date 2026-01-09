"""Plugin system for icloudpd extensibility

This package provides a plugin system that allows extending icloudpd
functionality without modifying the core codebase.

Key Components:
    - IcloudpdPlugin: Base class for all plugins
    - PluginManager: Discovers and manages plugins
    - Hook Protocol: Type definitions for hooks (optional)

Quick Start:
    To create a plugin, subclass IcloudpdPlugin and register it via
    entry points in your pyproject.toml:

    [project.entry-points."icloudpd.plugins"]
    myplugin = "my_package.plugin:MyPlugin"

Example Plugin:
    >>> from icloudpd.plugins.base import IcloudpdPlugin
    >>> class MyPlugin(IcloudpdPlugin):
    ...     def __init__(self):
    ...         self.files = []  # Instance variable accumulator
    ...
    ...     @property
    ...     def name(self) -> str:
    ...         return "myplugin"
    ...
    ...     def on_download_complete(self, download_path, **kwargs):
    ...         # Accumulate files
    ...         self.files.append(download_path)
    ...
    ...     def on_download_all_sizes_complete(self, photo, **kwargs):
    ...         # Process accumulated files
    ...         print(f"Photo {photo.filename}: {len(self.files)} files")
    ...         self.files.clear()  # Clear for next photo

Hook Pattern:
    Use instance variables to accumulate data across hook calls:
    1. Initialize accumulators in __init__()
    2. Accumulate in per-size hooks (on_download_complete, etc.)
    3. Process in on_download_all_sizes_complete
    4. Clear accumulator for next photo
    5. Show totals in on_run_completed

Available Hooks:
    Per-size hooks (called for each size variant):
    - on_download_exists
    - on_download_downloaded
    - on_download_complete

    Live photo hooks:
    - on_download_exists_live
    - on_download_downloaded_live
    - on_download_complete_live

    Per-photo hook (KEY):
    - on_download_all_sizes_complete

    Per-run hook:
    - on_run_completed

Usage:
    >>> from argparse import Namespace
    >>> from icloudpd.plugins.manager import PluginManager
    >>> manager = PluginManager()
    >>> manager.discover()  # doctest: +SKIP
    >>> config = Namespace()  # doctest: +SKIP
    >>> manager.enable("demo", config)  # doctest: +SKIP
    >>> manager.call_hook("on_download_complete", download_path="/path/to/file")  # doctest: +SKIP
"""

from icloudpd.plugins.base import IcloudpdPlugin
from icloudpd.plugins.manager import PluginManager

__all__ = [
    "IcloudpdPlugin",
    "PluginManager",
]

__version__ = "1.0.0"
