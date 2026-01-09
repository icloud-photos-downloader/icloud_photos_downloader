# Plugin System

icloudpd includes a plugin system that allows you to extend functionality by hooking into the download process. Plugins can respond to events like file downloads, processing completions, and more.

## Overview

The plugin system uses a **hook-based architecture** where plugins can register callbacks for specific events during the download process. This allows you to:

- Process photos after they're downloaded (e.g., upload to cloud storage)
- Organize files based on metadata (e.g., create albums, stacks)
- Track download statistics and generate reports
- Integrate with external services (e.g., Immich, PhotoPrism)

## Built-in Plugins

### Immich Plugin

The Immich plugin integrates with [Immich](https://immich.app), an open-source photo management solution. It automatically registers downloaded photos, creates stacks for size variants, syncs favorites, and organizes photos into albums.

#### Features

- **Automatic Registration**: Photos are automatically registered in Immich after download via external library scanning
- **Size Variant Stacking**: Stack different size variants (original, adjusted, medium, etc.) together
- **Favorites Sync**: Synchronize iCloud favorites to Immich
- **Album Organization**: Organize photos into albums with flexible date-based rules
- **Live Photo Support**: Associate live photo videos with size variants
- **Batch Processing**: Process photos in batches to reduce server load
- **Favorites-Only Mode**: Lightweight mode to update favorites on existing downloaded images
- **Directory Validation**: Ensures icloudpd directories are within Immich library import paths

#### Requirements

- Immich server (tested with v1.100+)
- Immich API key (generate in Immich: Account Settings → API Keys)
- Immich external library with configured import paths
- icloudpd download directory must be within the Immich library's import paths

> **Note**: This plugin does NOT upload files - it uses Immich's external library feature to discover files already on disk.

#### Quick Start

```bash
icloudpd \
  --directory /path/to/photos \
  --username me@you.com \
  --plugin immich \
  --immich-server-url http://localhost:2283 \
  --immich-api-key YOUR_API_KEY \
  --immich-library-id YOUR_LIBRARY_ID \
  --immich-stack-media \
  --immich-favorite adjusted
```

**Finding your Library ID:**

```bash
curl -H "x-api-key: YOUR_API_KEY" http://localhost:2283/api/libraries
```

Look for the `id` field of your external library in the JSON response.

#### Configuration Options

**Required Parameters:**

- `--plugin immich` - Enable the Immich plugin
- `--immich-server-url URL` - Immich server URL (e.g., `http://localhost:2283`)
- `--immich-api-key KEY` - Immich API key
- `--immich-library-id ID` - Immich external library ID

**Stacking Size Variants:**

Stack multiple size variants together in Immich:

```bash
--immich-stack-media                    # Stack all downloaded sizes
--immich-stack-media adjusted,original  # Stack only these sizes (adjusted on top)
```

The first specified size becomes the primary asset on top of the stack.

**Favoriting:**

Sync iCloud favorites to Immich:

```bash
--immich-favorite adjusted              # Mark adjusted size as favorite
--immich-favorite adjusted,medium       # Mark multiple sizes as favorite
--immich-favorite                       # Mark all sizes as favorite
```

**Albums:**

Organize photos into Immich albums with flexible rules:

```bash
--immich-album "iCloud Photos"                      # Add all sizes to one album
--immich-album "[adjusted]:iCloud"                  # Only adjusted size
--immich-album "[adjusted]:iCloud/{:%Y/%m}"         # Date-based albums
--immich-album "[medium]:iCloud JPG"                # Multiple rules
--immich-album "[original]:iCloud Raw"
```

Album template syntax:
- `[size1,size2]:template` - Only these sizes go to this album
- `template` - All sizes go to this album
- `{:%Y/%m}` - Date substitution using photo's creation date (supports strftime format codes)

Examples:
- `iCloud/{:%Y/%m}` → "iCloud/2024/01", "iCloud/2024/02", etc.
- `Photos/{:%Y}` → "Photos/2024", "Photos/2025", etc.

**Live Photo Association:**

Associate live photo videos with size variants:

```bash
--associate-live-with-extra-sizes                   # Associate with all sizes
--associate-live-with-extra-sizes adjusted,medium   # Associate with specific sizes
```

This ensures that when you have multiple size variants, the live photo video component is associated with all of them in Immich.

**Processing Modes:**

Process existing files (not just newly downloaded):

```bash
--immich-process-existing               # Full processing: stack, favorite, albums
--process-existing-favorites            # Only update favorites on existing files
```

`--immich-process-existing` is useful for initial setup or full re-processing. `--process-existing-favorites` is useful when running with `--watch-with-interval` and `--until-found` to sync favorites that were added after photos were taken.

**Batch Processing:**

Reduce server load by processing photos in batches:

```bash
--immich-batch-process 10               # Process every 10 photos
--immich-batch-process all              # Process all at end of run
--immich-batch-log-file /path/file.json # Custom log file (default: ~/.pyicloud/immich_pending_files.json)
```

Batching reduces library scan frequency, preventing OOM errors on large imports. The log file enables crash recovery by tracking unprocessed photos.

**Performance Tuning:**

```bash
--immich-scan-timeout 60.0              # Wait up to 60s for library scan (default: 5s)
--immich-poll-interval 1.0              # Check every 1s during scan wait (default: 1s)
```

Increase `--immich-scan-timeout` if your Immich server is slow or heavily loaded.

#### Example Configuration

Daily sync with favorite updates:

```bash
icloudpd \
  --directory /mnt/photos \
  --username user@icloud.com \
  --size original --size medium --size adjusted \
  --watch-with-interval 86400 \
  --until-found 1000 \
  --plugin immich \
  --immich-server-url https://immich.example.com \
  --immich-api-key YOUR_API_KEY \
  --immich-library-id abc123 \
  --immich-stack-media \
  --associate-live-with-extra-sizes \
  --immich-favorite adjusted \
  --process-existing-favorites \
  --immich-batch-process 10 \
  --immich-album "[adjusted]:iCloud"
```

This configuration:
- Downloads 3 sizes and stacks them
- Runs daily, processing up to 1000 existing photos
- Updates favorites for existing photos
- Batches every 10 photos to reduce server load
- Marks adjusted size as favorite in Immich
- Adds adjusted size to "iCloud" album

### Demo Plugin

The demo plugin demonstrates the plugin system's capabilities. Use it as a reference when building your own plugins:

```bash
icloudpd --plugin demo --demo-verbose --recent 5
```

## Using Plugins

### Enabling a Plugin

Enable a plugin with the `--plugin` flag:

```bash
icloudpd --directory /photos --username me@example.com --plugin immich
```

### Plugin-Specific Options

Each plugin adds its own CLI arguments. Use `--help` to see available options:

```bash
icloudpd --plugin immich --help
```

## Available Hooks

Plugins can implement the following hooks to respond to download events:

### Per-Size Hooks

These hooks are called for each size variant (original, adjusted, medium, etc.) of a photo:

#### `on_download_exists(download_path, photo_filename, requested_size, photo, dry_run)`

Called when a file already exists on disk (not downloaded).

**Parameters:**
- `download_path` (str): Full path to the file
- `photo_filename` (str): Original filename from iCloud
- `requested_size` (VersionSize): Size variant requested (ORIGINAL, ADJUSTED, MEDIUM, etc.)
- `photo` (PhotoAsset): Photo metadata object
- `dry_run` (bool): True if running in dry-run mode

**Use case:** Track which files already exist, skip processing for existing files

#### `on_download_downloaded(download_path, photo_filename, requested_size, photo, dry_run)`

Called when a file is newly downloaded.

**Parameters:** Same as `on_download_exists`

**Use case:** Process newly downloaded files, upload to external service

#### `on_download_complete(download_path, photo_filename, requested_size, photo, dry_run)`

Called after a size variant is fully processed (always runs, regardless of exists/downloaded).

**Parameters:** Same as `on_download_exists`

**Use case:** Ensure all files are tracked, even if they didn't go through exists or downloaded hooks

### Live Photo Hooks

These hooks are called for live photo video components (.mov files):

#### `on_download_exists_live(download_path, photo_filename, requested_size, photo, dry_run)`

Called when a live photo video already exists.

**Parameters:** Same as `on_download_exists`

#### `on_download_downloaded_live(download_path, photo_filename, requested_size, photo, dry_run)`

Called when a live photo video is newly downloaded.

**Parameters:** Same as `on_download_exists`

#### `on_download_complete_live(download_path, photo_filename, requested_size, photo, dry_run)`

Called after a live photo video is fully processed.

**Parameters:** Same as `on_download_exists`

### Completion Hooks

#### `on_download_all_sizes_complete(photo, dry_run)`

**MOST IMPORTANT HOOK** - Called after all size variants of a photo are downloaded/processed.

**Parameters:**
- `photo` (PhotoAsset): Complete photo metadata
- `dry_run` (bool): True if running in dry-run mode

**Use case:** Process all variants together (e.g., stack them, upload as a group, add to album)

**Why this hook is critical:**
- This is where you process the complete photo with all its size variants
- You have access to all accumulated file paths from previous hooks
- You can read photo metadata (favorite status, creation date, etc.)
- This is the right place to clear your accumulators for the next photo

#### `on_run_completed(dry_run)`

Called when the entire icloudpd run completes.

**Parameters:**
- `dry_run` (bool): True if running in dry-run mode

**Use case:** Generate final reports, upload statistics, cleanup tasks

## Building a Plugin

### 1. Plugin Structure

Create a new plugin by inheriting from `IcloudpdPlugin`:

```python
import logging
from argparse import ArgumentParser, Namespace

from icloudpd.plugins.base import IcloudpdPlugin
from pyicloud_ipd.services.photos import PhotoAsset
from pyicloud_ipd.version_size import VersionSize

# Initialize logger with explicit namespace
logger = logging.getLogger("icloudpd.plugins.myplugin")


class MyPlugin(IcloudpdPlugin):
    """My custom plugin"""

    def __init__(self):
        """Initialize plugin state"""
        # Accumulators for current photo
        self.current_files = []

        # Global counters
        self.total_photos = 0

    @property
    def name(self) -> str:
        """Plugin name (used with --plugin flag)"""
        return "myplugin"

    @property
    def version(self) -> str:
        """Plugin version"""
        return "1.0.0"

    @property
    def description(self) -> str:
        """Plugin description (shown in --help)"""
        return "My custom plugin for processing photos"
```

### 2. Add CLI Arguments

```python
def add_arguments(self, parser: ArgumentParser) -> None:
    """Add plugin-specific CLI arguments"""
    group = parser.add_argument_group('MyPlugin Options')
    group.add_argument(
        '--myplugin-option',
        help='Example plugin option'
    )
```

### 3. Configure from Arguments

```python
def configure(self, config: Namespace, global_config=None, user_configs=None) -> None:
    """Configure plugin from parsed arguments"""
    self.option = getattr(config, 'myplugin_option', 'default')

    # Use print() in configure() - logger not yet initialized
    print("=" * 70)
    print(f"MyPlugin: Initialized (version {self.version})")
    print(f"  Option: {self.option}")
    print("=" * 70)
```

### 4. Implement Hooks

**CRITICAL PATTERN - Use the Accumulator Pattern:**

```python
def on_download_downloaded(
    self,
    download_path: str,
    photo_filename: str,
    requested_size: VersionSize,
    photo: PhotoAsset,
    dry_run: bool,
) -> None:
    """Accumulate downloaded files"""
    logger.info(f"Downloaded: {requested_size.value} - {download_path}")

    # ACCUMULATE - don't process yet!
    self.current_files.append({
        'path': download_path,
        'size': requested_size.value,
        'status': 'downloaded'
    })

def on_download_all_sizes_complete(
    self,
    photo: PhotoAsset,
    dry_run: bool,
) -> None:
    """Process all accumulated files for this photo"""
    self.total_photos += 1

    logger.info(f"Processing photo: {photo.filename}")
    logger.info(f"  Files: {len(self.current_files)}")

    # Process all accumulated files together
    for file_info in self.current_files:
        # Upload to service, create stacks, etc.
        self._process_file(file_info)

    # CRITICAL: Clear accumulator for next photo
    self.current_files.clear()

def on_run_completed(self, dry_run: bool) -> None:
    """Final summary"""
    logger.info("=" * 70)
    logger.info("MyPlugin: Run Completed")
    logger.info(f"  Total Photos: {self.total_photos}")
    logger.info("=" * 70)
```

### 5. Install Your Plugin

Place your plugin in one of these locations:

1. **Built-in plugins:** `src/icloudpd/plugins/myplugin.py`
2. **External plugins:** `~/.icloudpd/plugins/myplugin.py` (if supported)

Then use it with:

```bash
icloudpd --plugin myplugin --myplugin-option value
```

## Key Concepts and Gotchas

### 1. The Accumulator Pattern

**DO THIS:**
```python
# Accumulate in per-size hooks
def on_download_downloaded(self, download_path, ...):
    self.current_files.append({'path': download_path})

# Process in all-sizes-complete hook
def on_download_all_sizes_complete(self, photo, dry_run):
    # Process all files together
    for file in self.current_files:
        self._process(file)

    # CRITICAL: Clear for next photo
    self.current_files.clear()
```

**DON'T DO THIS:**
```python
# WRONG: Processing in per-size hook
def on_download_downloaded(self, download_path, ...):
    self._process(download_path)  # ❌ Wrong! Process in all_sizes_complete
```

**Why:** You need all size variants together to create stacks, determine which file is primary, etc.

### 2. Logger Initialization

**DO THIS:**
```python
import logging

# Use explicit namespace
logger = logging.getLogger("icloudpd.plugins.myplugin")
```

**DON'T DO THIS:**
```python
# WRONG: Using __name__
logger = logging.getLogger(__name__)  # ❌ Can vary depending on import
```

**Why:** Explicit namespace ensures correct logger hierarchy and inheritance.

### 3. Print vs Logger

**In `configure()`:** Use `print()` - logging not yet initialized
```python
def configure(self, config, ...):
    print("Plugin: Initialized")  # ✓ Correct in configure()
```

**Everywhere else:** Use `logger`
```python
def on_download_downloaded(self, ...):
    logger.info("Downloaded file")  # ✓ Correct in hooks
```

### 4. Accessing Photo Metadata

```python
def on_download_all_sizes_complete(self, photo: PhotoAsset, dry_run):
    # Check if photo is favorite
    is_fav = photo._asset_record.get("fields", {}).get("isFavorite", {}).get("value") == 1

    # Get creation date
    created = photo.created

    # Get photo ID
    photo_id = photo.id

    # Get filename
    filename = photo.filename
```

### 5. Dry Run Mode

Always respect the `dry_run` flag:

```python
def on_download_all_sizes_complete(self, photo, dry_run):
    if dry_run:
        logger.info(f"[DRY RUN] Would process {photo.filename}")
        self.current_files.clear()
        return

    # Actual processing
    self._process_files()
    self.current_files.clear()
```

### 6. Error Handling

Don't crash icloudpd - handle errors gracefully:

```python
def on_download_all_sizes_complete(self, photo, dry_run):
    try:
        self._process_files()
    except Exception as e:
        logger.error(f"Failed to process {photo.filename}: {e}")
        # Continue - don't raise
    finally:
        # ALWAYS clear accumulator
        self.current_files.clear()
```

### 7. Cleanup

Implement cleanup for graceful shutdown:

```python
def cleanup(self) -> None:
    """Called on shutdown"""
    logger.debug("MyPlugin: Cleanup called")
    # Close connections, save state, etc.
```

## Common Patterns

### Pattern 1: File Accumulation with Metadata

```python
def on_download_downloaded(self, download_path, photo_filename, requested_size, photo, dry_run):
    self.current_files.append({
        'path': download_path,
        'size': requested_size.value,
        'status': 'downloaded',
        'is_live': False,
        'filename': photo_filename,
    })

def on_download_exists(self, download_path, photo_filename, requested_size, photo, dry_run):
    self.current_files.append({
        'path': download_path,
        'size': requested_size.value,
        'status': 'existed',
        'is_live': False,
        'filename': photo_filename,
    })
```

### Pattern 2: Conditional Processing

```python
def on_download_all_sizes_complete(self, photo, dry_run):
    # Only process favorites
    is_fav = photo._asset_record.get("fields", {}).get("isFavorite", {}).get("value") == 1

    if not is_fav:
        logger.debug(f"Skipping non-favorite: {photo.filename}")
        self.current_files.clear()
        return

    # Process favorite
    self._process_favorite(photo)
    self.current_files.clear()
```

### Pattern 3: Batch Processing

```python
def __init__(self):
    self.current_files = []
    self.batch_queue = []
    self.batch_size = 10

def on_download_all_sizes_complete(self, photo, dry_run):
    # Add to batch
    self.batch_queue.append({
        'photo': photo,
        'files': self.current_files.copy()
    })
    self.current_files.clear()

    # Process when batch full
    if len(self.batch_queue) >= self.batch_size:
        self._process_batch()

def on_run_completed(self, dry_run):
    # Process remaining batch
    if self.batch_queue:
        self._process_batch()
```

## Testing Your Plugin

### Test Organization

Tests should live alongside your plugin code for easy distribution and maintenance:

```
plugins/
└── myplugin/
    ├── __init__.py
    ├── myplugin.py
    └── tests/
        ├── __init__.py
        └── test_myplugin.py
```

This structure:
- Keeps tests with the plugin they test
- Makes the plugin self-contained and distributable
- Works automatically with pytest discovery

### Setting Up Tests

1. **Create test directory structure:**
   ```bash
   mkdir -p plugins/myplugin/tests
   touch plugins/myplugin/tests/__init__.py
   touch plugins/myplugin/tests/test_myplugin.py
   ```

2. **Configure pytest** (already configured in `pyproject.toml`):
   ```toml
   [tool.pytest.ini_options]
   testpaths = [
       "tests",      # Core icloudpd tests
       "src",        # Doctests
       "plugins"     # Plugin tests (auto-discovers plugins/*/tests/)
   ]
   pythonpath = [
       "src",
       "."           # Needed for plugins directory
   ]
   ```

3. **Run your plugin tests:**
   ```bash
   # Run all plugin tests
   pytest plugins/myplugin/tests/

   # Run specific test file
   pytest plugins/myplugin/tests/test_myplugin.py

   # Run with coverage
   pytest plugins/myplugin/tests/ --cov=plugins.myplugin.myplugin --cov-report=term-missing
   ```

### Unit Testing

Write comprehensive unit tests for your plugin logic:

```python
"""Tests for MyPlugin"""

import argparse
import unittest
from argparse import ArgumentParser, Namespace
from unittest.mock import Mock, patch

from plugins.myplugin.myplugin import MyPlugin
from pyicloud_ipd.services.photos import PhotoAsset
from pyicloud_ipd.version_size import AssetVersionSize


class TestMyPluginBasics(unittest.TestCase):
    """Test basic plugin functionality"""

    def test_plugin_initialization(self):
        """Test plugin initializes correctly"""
        plugin = MyPlugin()
        self.assertEqual(plugin.name, "myplugin")
        self.assertEqual(plugin.version, "1.0.0")

    def test_add_arguments(self):
        """Test arguments are added to parser"""
        plugin = MyPlugin()
        parser = ArgumentParser()
        plugin.add_arguments(parser)

        # Parse with plugin args
        args = parser.parse_args(['--myplugin-option', 'test'])
        self.assertEqual(args.myplugin_option, 'test')


class TestMyPluginHooks(unittest.TestCase):
    """Test plugin hook methods"""

    def setUp(self):
        """Set up test fixtures"""
        self.plugin = MyPlugin()
        config = Namespace(myplugin_option='test')
        self.plugin.configure(config)

    def test_file_accumulation(self):
        """Test files are accumulated correctly"""
        mock_photo = Mock(spec=PhotoAsset)
        mock_photo.filename = 'test.jpg'
        mock_photo.id = 'ABC123'

        # Simulate download
        self.plugin.on_download_downloaded(
            download_path='/path/test.jpg',
            photo_filename='test.jpg',
            requested_size=AssetVersionSize.ORIGINAL,
            photo=mock_photo,
            dry_run=False
        )

        # Verify accumulation
        self.assertEqual(len(self.plugin.current_files), 1)
        self.assertEqual(self.plugin.current_files[0]['path'], '/path/test.jpg')

    def test_all_sizes_complete_clears_files(self):
        """Test completion clears accumulated files"""
        mock_photo = Mock(spec=PhotoAsset)
        mock_photo.filename = 'test.jpg'

        # Add some files
        self.plugin.current_files.append({'path': '/test.jpg'})

        # Simulate completion
        self.plugin.on_download_all_sizes_complete(
            photo=mock_photo,
            dry_run=False
        )

        # Verify cleared
        self.assertEqual(len(self.plugin.current_files), 0)

    def test_dry_run_mode(self):
        """Test dry run doesn't perform actual operations"""
        mock_photo = Mock(spec=PhotoAsset)
        mock_photo.filename = 'test.jpg'

        self.plugin.current_files.append({'path': '/test.jpg'})

        # Process in dry run mode
        self.plugin.on_download_all_sizes_complete(
            photo=mock_photo,
            dry_run=True
        )

        # Should still clear files but not perform actions
        self.assertEqual(len(self.plugin.current_files), 0)


class TestMyPluginWithMocks(unittest.TestCase):
    """Test plugin with external API calls mocked"""

    def setUp(self):
        """Set up test fixtures"""
        self.plugin = MyPlugin()
        self.plugin.api_url = "http://localhost:8080"
        self.plugin.api_key = "test-key"

    @patch("plugins.myplugin.myplugin.requests.post")
    def test_api_call_success(self, mock_post):
        """Test successful API call"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_post.return_value = mock_response

        result = self.plugin._call_api({"data": "test"})
        self.assertTrue(result)

    @patch("plugins.myplugin.myplugin.requests.post")
    def test_api_call_failure(self, mock_post):
        """Test API call handles errors gracefully"""
        mock_post.side_effect = Exception("Connection error")

        # Should not raise, just log error
        result = self.plugin._call_api({"data": "test"})
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
```

### Integration Testing via Plugin Manager

Test that your plugin integrates correctly with icloudpd's plugin manager:

```python
class TestMyPluginIntegration(unittest.TestCase):
    """Test plugin works through PluginManager"""

    def test_plugin_discovered(self):
        """Test plugin is discovered by manager"""
        from icloudpd.plugins.manager import PluginManager

        manager = PluginManager()
        manager.discover()

        # Verify plugin is available
        self.assertIn("myplugin", manager.list_available())

    def test_hooks_called_via_manager(self):
        """Test manager calls plugin hooks correctly"""
        from icloudpd.plugins.manager import PluginManager

        manager = PluginManager()
        manager.available["myplugin"] = MyPlugin

        config = Namespace(myplugin_option='test')
        manager.enable("myplugin", config)

        # Verify plugin is enabled
        self.assertTrue(manager.is_enabled("myplugin"))

        # Create mock photo
        mock_photo = Mock(spec=PhotoAsset)
        mock_photo.filename = 'test.jpg'

        # Call hook via manager
        manager.call_hook(
            "on_download_downloaded",
            download_path="/path/test.jpg",
            photo_filename="test.jpg",
            requested_size=AssetVersionSize.ORIGINAL,
            photo=mock_photo,
            dry_run=False
        )

        # Verify plugin processed the hook
        plugin = manager.enabled["myplugin"]
        self.assertGreater(len(plugin.current_files), 0)
```

### Testing Best Practices

1. **Test all hook implementations** - Ensure each hook works correctly
2. **Test error handling** - Verify graceful degradation on failures
3. **Test configuration** - Verify arguments parse correctly
4. **Mock external dependencies** - Don't make real API calls in tests
5. **Test dry run mode** - Ensure no actual operations in dry run
6. **Use realistic test data** - Create PhotoAsset mocks that match real data

### Running Tests

```bash
# Run all tests
pytest

# Run only plugin tests
pytest plugins/

# Run specific plugin
pytest plugins/myplugin/tests/

# Run with coverage
pytest plugins/myplugin/tests/ \
  --cov=plugins.myplugin \
  --cov-report=html \
  --cov-report=term-missing

# View coverage report
open htmlcov/index.html
```

### Manual/Integration Testing

Test with real icloudpd to verify end-to-end functionality:

```bash
# Test with demo plugin first (verify setup works)
icloudpd --plugin demo --demo-verbose --recent 1

# Test your plugin in dry-run mode
icloudpd --plugin myplugin --myplugin-option test --recent 1 --dry-run

# Test with small dataset
icloudpd --plugin myplugin --myplugin-option test --recent 5

# Test full workflow
icloudpd --plugin myplugin --myplugin-option production --recent 100
```

## Examples

See these plugins for real-world examples:

- **Immich Plugin** - Complete production plugin with stacking, favorites, albums, batch processing
- **Demo Plugin** - Educational example showing all hooks and patterns

## Plugin Lifecycle

```
icloudpd starts
  ↓
Plugin.__init__()
  ↓
Plugin.add_arguments(parser)
  ↓
[Arguments parsed]
  ↓
Plugin.configure(config)
  ↓
[For each photo]
  ↓
  [For each size variant]
    ↓
    on_download_exists() OR on_download_downloaded()
    ↓
    on_download_complete()
  ↓
  [For each live photo]
    ↓
    on_download_exists_live() OR on_download_downloaded_live()
    ↓
    on_download_complete_live()
  ↓
  on_download_all_sizes_complete()  ← KEY HOOK
  ↓
[After all photos]
  ↓
on_run_completed()
  ↓
cleanup()
  ↓
icloudpd exits
```

## Best Practices

1. ✅ **Use the accumulator pattern** - collect data in per-size hooks, process in all-sizes-complete
2. ✅ **Always clear accumulators** - prevent data leaking between photos
3. ✅ **Use explicit logger names** - `logging.getLogger("icloudpd.plugins.myplugin")`
4. ✅ **Respect dry-run mode** - check the flag and skip actual operations
5. ✅ **Handle errors gracefully** - don't crash icloudpd
6. ✅ **Use print() only in configure()** - use logger everywhere else
7. ✅ **Document your options** - add clear help text to CLI arguments
8. ✅ **Test with --dry-run first** - verify behavior before processing real files

## Troubleshooting

### Plugin not found

Check that:
1. Plugin file is in `src/icloudpd/plugins/` directory
2. Plugin class name matches the pattern `{Name}Plugin`
3. Plugin implements required properties: `name`, `version`, `description`

### Hooks not being called

Check that:
1. Hook method signatures exactly match the base class
2. Hook methods accept all required parameters
3. You're not raising exceptions in hooks

### Data not accumulating

Check that:
1. You're appending to accumulators in per-size hooks
2. You're not clearing accumulators too early
3. You're clearing accumulators in `on_download_all_sizes_complete`

### Logger not working

Check that:
1. You initialized logger with explicit namespace: `logging.getLogger("icloudpd.plugins.myplugin")`
2. You're using `print()` in `configure()` (before logging is initialized)
3. You're using `logger` everywhere else

## Additional Resources

- **icloudpd GitHub Repository** - Source code and documentation: https://github.com/icloud-photos-downloader/icloud_photos_downloader
- **Immich Documentation** - Official Immich docs: https://immich.app/docs/
- **Plugin Examples** - See the `src/icloudpd/plugins/` and `plugins/` directories in the icloudpd repository
