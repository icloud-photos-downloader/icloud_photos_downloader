"""Immich plugin for icloudpd

Automatically uploads downloaded photos to Immich with support for:
- Size variant stacking
- Favorites synchronization
- Album organization
- Live photo association

For usage information, see the plugin's README.md or run:
    icloudpd --help

Example:
    icloudpd --plugin immich \\
             --immich-server-url http://localhost:2283 \\
             --immich-api-key YOUR_API_KEY \\
             --immich-library-id YOUR_LIBRARY_ID \\
             --immich-stack-media adjusted,original \\
             --immich-favorite adjusted
"""

from plugins.immich.immich import ImmichPlugin

__all__ = ["ImmichPlugin"]
__version__ = "1.0.0"
