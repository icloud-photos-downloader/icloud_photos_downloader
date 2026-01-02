"""Tests for Immich plugin"""

import argparse
import unittest
from argparse import ArgumentParser, Namespace
from unittest.mock import Mock, patch

from plugins.immich.immich import AlbumRule, ImmichPlugin, _parse_batch_size, _parse_sizes
from pyicloud_ipd.services.photos import PhotoAsset


class TestParseSizes(unittest.TestCase):
    """Test _parse_sizes helper function"""

    def test_parse_sizes_none(self):
        """Test parsing None returns all sizes"""
        result = _parse_sizes(None)
        self.assertEqual(result, ["original", "adjusted", "alternative", "medium", "thumb"])

    def test_parse_sizes_comma_separated(self):
        """Test parsing comma-separated size list"""
        result = _parse_sizes("original,medium")
        self.assertEqual(result, ["original", "medium"])

    def test_parse_sizes_single(self):
        """Test parsing single size"""
        result = _parse_sizes("adjusted")
        self.assertEqual(result, ["adjusted"])

    def test_parse_sizes_with_spaces(self):
        """Test parsing with spaces around commas"""
        result = _parse_sizes("original, medium, adjusted")
        self.assertEqual(result, ["original", "medium", "adjusted"])

    def test_parse_sizes_invalid_raises(self):
        """Test parsing invalid size raises ArgumentTypeError"""
        with self.assertRaises(argparse.ArgumentTypeError):
            _parse_sizes("invalid")


class TestAlbumRule(unittest.TestCase):
    """Test AlbumRule class"""

    def test_parse_single_size(self):
        """Test parsing rule with single size"""
        rule = AlbumRule("[original]:Originals")
        self.assertEqual(rule.size_targets, ["original"])
        self.assertEqual(rule.template, "Originals")
        self.assertFalse(rule.match_all)

    def test_parse_multiple_sizes(self):
        """Test parsing rule with multiple sizes"""
        rule = AlbumRule("[original,adjusted]:High Quality")
        self.assertEqual(rule.size_targets, ["original", "adjusted"])
        self.assertEqual(rule.template, "High Quality")
        self.assertFalse(rule.match_all)

    def test_parse_all_sizes(self):
        """Test parsing rule without size filter (matches all)"""
        rule = AlbumRule("All Photos")
        self.assertTrue(rule.match_all)
        self.assertEqual(rule.template, "All Photos")
        self.assertEqual(rule.size_targets, [])

    def test_parse_date_template(self):
        """Test parsing rule with date template"""
        rule = AlbumRule("[adjusted]:{:%Y/%m}")
        self.assertEqual(rule.size_targets, ["adjusted"])
        self.assertEqual(rule.template, "{:%Y/%m}")

    def test_parse_invalid_format_raises(self):
        """Test parsing empty template raises ValueError"""
        with self.assertRaises(ValueError):
            AlbumRule("")

    def test_parse_missing_bracket_raises(self):
        """Test parsing invalid sizes raises ValueError"""
        with self.assertRaises(ValueError):
            AlbumRule("[invalidsize]:Photos")

    def test_matches_wildcard(self):
        """Test match_all matches all sizes"""
        rule = AlbumRule("All Photos")
        self.assertTrue(rule.matches("original"))
        self.assertTrue(rule.matches("adjusted"))
        self.assertTrue(rule.matches("medium"))

    def test_matches_specific_size(self):
        """Test specific size matching"""
        rule = AlbumRule("[original]:Originals")
        self.assertTrue(rule.matches("original"))
        self.assertFalse(rule.matches("adjusted"))

    def test_matches_multiple_sizes(self):
        """Test multiple size matching"""
        rule = AlbumRule("[original,adjusted]:High Quality")
        self.assertTrue(rule.matches("original"))
        self.assertTrue(rule.matches("adjusted"))
        self.assertFalse(rule.matches("medium"))

    def test_str_representation(self):
        """Test string representation"""
        rule_specific = AlbumRule("[original]:Originals")
        self.assertEqual(repr(rule_specific), "AlbumRule([original]:Originals)")

        rule_all = AlbumRule("All Photos")
        self.assertEqual(repr(rule_all), "AlbumRule(all:All Photos)")


class TestImmichPluginInit(unittest.TestCase):
    """Test ImmichPlugin initialization and properties"""

    def test_plugin_initialization(self):
        """Test plugin can be initialized"""
        plugin = ImmichPlugin()
        self.assertIsNotNone(plugin)

    def test_plugin_name(self):
        """Test plugin name property"""
        plugin = ImmichPlugin()
        self.assertEqual(plugin.name, "immich")

    def test_plugin_version(self):
        """Test plugin version property"""
        plugin = ImmichPlugin()
        # Version should be a string with format like "1.0.0"
        self.assertIsInstance(plugin.version, str)
        self.assertRegex(plugin.version, r"^\d+\.\d+\.\d+$")

    def test_plugin_description(self):
        """Test plugin description property"""
        plugin = ImmichPlugin()
        self.assertIsInstance(plugin.description, str)
        self.assertIn("immich", plugin.description.lower())

    def test_initial_state(self):
        """Test initial plugin state"""
        plugin = ImmichPlugin()
        # Configuration should be None/default
        self.assertIsNone(plugin.server_url)
        self.assertIsNone(plugin.api_key)
        self.assertIsNone(plugin.library_id)
        self.assertFalse(plugin.process_existing)
        self.assertEqual(plugin.scan_timeout, 5.0)
        self.assertEqual(plugin.poll_interval, 1.0)
        self.assertFalse(plugin.stack_media)
        self.assertEqual(plugin.favorite_sizes, [])
        self.assertEqual(plugin.album_rules, [])
        # Accumulators should be empty
        self.assertEqual(plugin.current_photo_files, [])
        # Batch processing defaults
        self.assertEqual(plugin.batch_size, 1)  # 1 = immediate processing (default)
        self.assertEqual(plugin.batch_queue, [])


class TestImmichPluginArguments(unittest.TestCase):
    """Test ImmichPlugin CLI argument registration"""

    def test_add_arguments(self):
        """Test that plugin adds all expected CLI arguments"""
        parser = ArgumentParser()
        plugin = ImmichPlugin()
        plugin.add_arguments(parser)

        # Parse empty args to get defaults
        args = parser.parse_args([])

        # Check that all expected arguments exist
        self.assertTrue(hasattr(args, "immich_server_url"))
        self.assertTrue(hasattr(args, "immich_api_key"))
        self.assertTrue(hasattr(args, "immich_library_id"))
        self.assertTrue(hasattr(args, "immich_process_existing"))
        self.assertTrue(hasattr(args, "immich_scan_timeout"))
        self.assertTrue(hasattr(args, "immich_poll_interval"))
        self.assertTrue(hasattr(args, "immich_stack_media"))
        self.assertTrue(hasattr(args, "immich_favorite"))
        self.assertTrue(hasattr(args, "associate_live_with_extra_sizes"))
        self.assertTrue(hasattr(args, "immich_albums"))

    def test_default_arguments(self):
        """Test default values for CLI arguments"""
        parser = ArgumentParser()
        plugin = ImmichPlugin()
        plugin.add_arguments(parser)

        args = parser.parse_args([])

        self.assertIsNone(args.immich_server_url)
        self.assertIsNone(args.immich_api_key)
        self.assertIsNone(args.immich_library_id)
        self.assertFalse(args.immich_process_existing)
        self.assertEqual(args.immich_scan_timeout, 5.0)
        self.assertEqual(args.immich_poll_interval, 1.0)
        self.assertFalse(args.immich_stack_media)  # Default is False, not None
        self.assertFalse(args.immich_favorite)  # Default is False, not None
        self.assertFalse(args.associate_live_with_extra_sizes)  # Default is False
        self.assertIsNone(args.immich_albums)  # append action with no default


class TestImmichPluginConfiguration(unittest.TestCase):
    """Test ImmichPlugin configuration"""

    @patch("plugins.immich.immich.ImmichPlugin._test_immich_connection")
    def test_configure_basic(self, mock_test_conn):
        """Test basic plugin configuration"""
        plugin = ImmichPlugin()
        config = Namespace(
            immich_server_url="http://localhost:2283",
            immich_api_key="test-key",
            immich_library_id="lib-123",
            immich_process_existing=False,
            immich_scan_timeout=5.0,
            immich_poll_interval=1.0,
            immich_stack_media=False,
            immich_favorite=False,
            associate_live_with_extra_sizes=False,
            immich_albums=None,
        )

        plugin.configure(config, None, None)

        self.assertEqual(plugin.server_url, "http://localhost:2283")
        self.assertEqual(plugin.api_key, "test-key")
        self.assertEqual(plugin.library_id, "lib-123")
        self.assertFalse(plugin.process_existing)
        self.assertEqual(plugin.scan_timeout, 5.0)
        self.assertEqual(plugin.poll_interval, 1.0)

    @patch("plugins.immich.immich.ImmichPlugin._test_immich_connection")
    def test_configure_stacking_with_priority(self, mock_test_conn):
        """Test configuration with stacking and priority"""
        plugin = ImmichPlugin()
        config = Namespace(
            immich_server_url="http://localhost:2283",
            immich_api_key="test-key",
            immich_library_id="lib-123",
            immich_process_existing=False,
            immich_scan_timeout=5.0,
            immich_poll_interval=1.0,
            immich_stack_media=["adjusted", "original"],
            immich_favorite=False,
            associate_live_with_extra_sizes=False,
            immich_albums=None,
        )

        plugin.configure(config, None, None)

        self.assertTrue(plugin.stack_media)
        self.assertEqual(plugin.stack_priority, ["adjusted", "original"])

    @patch("plugins.immich.immich.ImmichPlugin._test_immich_connection")
    def test_configure_favorite_specific_sizes(self, mock_test_conn):
        """Test configuration with specific favorite sizes"""
        plugin = ImmichPlugin()
        config = Namespace(
            immich_server_url="http://localhost:2283",
            immich_api_key="test-key",
            immich_library_id="lib-123",
            immich_process_existing=False,
            immich_scan_timeout=5.0,
            immich_poll_interval=1.0,
            immich_stack_media=False,
            immich_favorite=["adjusted"],
            associate_live_with_extra_sizes=False,
            immich_albums=None,
        )

        plugin.configure(config, None, None)

        self.assertEqual(plugin.favorite_sizes, ["adjusted"])

    @patch("plugins.immich.immich.ImmichPlugin._test_immich_connection")
    def test_configure_favorite_all_sizes(self, mock_test_conn):
        """Test configuration with all favorite sizes"""
        plugin = ImmichPlugin()
        config = Namespace(
            immich_server_url="http://localhost:2283",
            immich_api_key="test-key",
            immich_library_id="lib-123",
            immich_process_existing=False,
            immich_scan_timeout=5.0,
            immich_poll_interval=1.0,
            immich_stack_media=False,
            immich_favorite=["original", "adjusted", "alternative", "medium", "thumb"],
            associate_live_with_extra_sizes=False,
            immich_albums=None,
        )

        plugin.configure(config, None, None)

        self.assertEqual(
            plugin.favorite_sizes, ["original", "adjusted", "alternative", "medium", "thumb"]
        )

    @patch("plugins.immich.immich.ImmichPlugin._test_immich_connection")
    def test_configure_album_rules(self, mock_test_conn):
        """Test configuration with album rules"""
        plugin = ImmichPlugin()
        config = Namespace(
            immich_server_url="http://localhost:2283",
            immich_api_key="test-key",
            immich_library_id="lib-123",
            immich_process_existing=False,
            immich_scan_timeout=5.0,
            immich_poll_interval=1.0,
            immich_stack_media=False,
            immich_favorite=False,
            associate_live_with_extra_sizes=False,
            immich_albums=["[adjusted]:Favorites", "[original]:Originals"],
        )

        plugin.configure(config, None, None)

        self.assertEqual(len(plugin.album_rules), 2)
        self.assertEqual(plugin.album_rules[0].template, "Favorites")
        self.assertEqual(plugin.album_rules[1].template, "Originals")

    def test_configure_validation_missing_api_key(self):
        """Test configuration fails with missing API key"""
        plugin = ImmichPlugin()
        config = Namespace(
            immich_server_url="http://localhost:2283",
            immich_api_key=None,
            immich_library_id="lib-123",
            immich_process_existing=False,
            immich_scan_timeout=5.0,
            immich_poll_interval=1.0,
            immich_stack_media=False,
            immich_favorite=False,
            associate_live_with_extra_sizes=False,
            immich_albums=None,
        )

        with self.assertRaises(SystemExit):
            plugin.configure(config, None, None)

    def test_configure_validation_missing_library_id(self):
        """Test configuration fails with missing library ID"""
        plugin = ImmichPlugin()
        config = Namespace(
            immich_server_url="http://localhost:2283",
            immich_api_key="test-key",
            immich_library_id=None,
            immich_process_existing=False,
            immich_scan_timeout=5.0,
            immich_poll_interval=1.0,
            immich_stack_media=False,
            immich_favorite=False,
            associate_live_with_extra_sizes=False,
            immich_albums=None,
        )

        with self.assertRaises(SystemExit):
            plugin.configure(config, None, None)


class TestImmichPluginDirectoryValidation(unittest.TestCase):
    """Test ImmichPlugin directory validation methods"""

    def test_strip_date_templates(self):
        """Test stripping date templates from paths"""
        plugin = ImmichPlugin()

        # Test various date template patterns
        self.assertEqual(plugin._strip_date_templates("/photos/%Y/%m"), "/photos")
        self.assertEqual(plugin._strip_date_templates("/photos/{:%Y/%m}"), "/photos")
        self.assertEqual(plugin._strip_date_templates("/photos/no-template"), "/photos/no-template")

    def test_is_subdirectory_valid(self):
        """Test subdirectory check with valid paths"""
        plugin = ImmichPlugin()

        self.assertTrue(plugin._is_subdirectory("/photos/icloud", "/photos"))
        self.assertTrue(plugin._is_subdirectory("/photos/subdir/deep", "/photos"))

    def test_is_subdirectory_invalid(self):
        """Test subdirectory check with invalid paths"""
        plugin = ImmichPlugin()

        self.assertFalse(plugin._is_subdirectory("/other/path", "/photos"))
        self.assertFalse(
            plugin._is_subdirectory("/photo", "/photos")  # Not a subdirectory
        )


class TestImmichPluginHooks(unittest.TestCase):
    """Test ImmichPlugin hook methods"""

    def setUp(self):
        """Set up test plugin with basic config"""
        self.plugin = ImmichPlugin()
        # Set attributes directly without calling configure
        self.plugin.server_url = "http://localhost:2283"
        self.plugin.api_key = "test-key"
        self.plugin.library_id = "lib-123"
        self.plugin.process_existing = False
        self.plugin.scan_timeout = 5.0
        self.plugin.poll_interval = 1.0

    def test_on_download_exists_without_process_existing(self):
        """Test on_download_exists hook without process_existing flag"""
        photo = Mock(spec=PhotoAsset)
        download_size = Mock()
        download_size.name = "adjusted"

        self.plugin.on_download_exists(
            download_path="/photos/IMG_001.jpg",
            photo_filename="IMG_001.jpg",
            download_size=download_size,
            photo=photo,
            dry_run=False,
        )

        # Should not add to current_photo_files
        self.assertEqual(len(self.plugin.current_photo_files), 0)

    def test_on_download_exists_with_process_existing(self):
        """Test on_download_exists hook with process_existing flag"""
        self.plugin.process_existing = True
        photo = Mock(spec=PhotoAsset)
        download_size = Mock()
        download_size.name = "adjusted"

        self.plugin.on_download_exists(
            download_path="/photos/IMG_001.jpg",
            photo_filename="IMG_001.jpg",
            download_size=download_size,
            photo=photo,
            dry_run=False,
        )

        # Should add to current_photo_files
        self.assertEqual(len(self.plugin.current_photo_files), 1)
        self.assertEqual(self.plugin.current_photo_files[0]["status"], "existed")

    def test_on_download_exists_with_process_existing_favorites_favorite_photo(self):
        """Test on_download_exists with process_existing_favorites for favorite photo"""
        self.plugin.process_existing_favorites = True

        # Create mock photo that IS a favorite
        photo = Mock(spec=PhotoAsset)
        photo._asset_record = {"fields": {"isFavorite": {"value": 1}}}

        download_size = Mock()
        download_size.value = "adjusted"

        self.plugin.on_download_exists(
            download_path="/photos/IMG_001.jpg",
            photo_filename="IMG_001.jpg",
            download_size=download_size,
            photo=photo,
            dry_run=False,
        )

        # Should add to current_photo_files because photo is favorite
        self.assertEqual(len(self.plugin.current_photo_files), 1)
        self.assertEqual(self.plugin.current_photo_files[0]["status"], "existed")

    def test_on_download_exists_with_process_existing_favorites_non_favorite_photo(self):
        """Test on_download_exists with process_existing_favorites for non-favorite photo"""
        self.plugin.process_existing_favorites = True

        # Create mock photo that is NOT a favorite
        photo = Mock(spec=PhotoAsset)
        photo._asset_record = {"fields": {"isFavorite": {"value": 0}}}

        download_size = Mock()
        download_size.value = "adjusted"

        self.plugin.on_download_exists(
            download_path="/photos/IMG_001.jpg",
            photo_filename="IMG_001.jpg",
            download_size=download_size,
            photo=photo,
            dry_run=False,
        )

        # Should NOT add to current_photo_files because photo is not favorite
        self.assertEqual(len(self.plugin.current_photo_files), 0)

    def test_on_download_downloaded(self):
        """Test on_download_downloaded hook"""
        photo = Mock(spec=PhotoAsset)
        download_size = Mock()
        download_size.name = "adjusted"

        self.plugin.on_download_downloaded(
            download_path="/photos/IMG_001.jpg",
            photo_filename="IMG_001.jpg",
            download_size=download_size,
            photo=photo,
            dry_run=False,
        )

        # Should add to current_photo_files
        self.assertEqual(len(self.plugin.current_photo_files), 1)
        self.assertEqual(self.plugin.current_photo_files[0]["status"], "downloaded")

    def test_on_download_complete(self):
        """Test on_download_complete hook (doesn't reset state per-file)"""
        # Add some data
        self.plugin.current_photo_files.append({"test": "data"})

        photo = Mock(spec=PhotoAsset)
        download_size = Mock()
        download_size.name = "adjusted"

        self.plugin.on_download_complete(
            download_path="/photos/IMG_001.jpg",
            photo_filename="IMG_001.jpg",
            download_size=download_size,
            photo=photo,
            dry_run=False,
        )

        # State persists (on_download_complete is called per-file, state resets in on_download_all_sizes_complete)
        self.assertEqual(len(self.plugin.current_photo_files), 1)

    def test_cleanup(self):
        """Test cleanup method (no-op)"""
        # Should not raise any exceptions and doesn't reset state
        self.plugin.current_photo_files.append({"test": "data"})
        self.plugin.cleanup()
        # State should remain (cleanup is a no-op)
        self.assertEqual(len(self.plugin.current_photo_files), 1)


class TestImmichPluginProcessing(unittest.TestCase):
    """Test ImmichPlugin processing workflow"""

    def setUp(self):
        """Set up test plugin with basic config"""
        self.plugin = ImmichPlugin()
        # Set attributes directly without calling configure
        self.plugin.server_url = "http://localhost:2283"
        self.plugin.api_key = "test-key"
        self.plugin.library_id = "lib-123"
        self.plugin.process_existing = True
        self.plugin.scan_timeout = 5.0
        self.plugin.poll_interval = 1.0
        self.plugin.stack_media = True
        self.plugin.stack_priority = ["adjusted", "original"]
        self.plugin.favorite_sizes = ["adjusted"]
        self.plugin.album_rules = [AlbumRule("[adjusted]:Favorites")]

    def test_on_download_all_sizes_complete_no_files(self):
        """Test processing with no files"""
        mock_photo = Mock(spec=PhotoAsset)

        # No files in current_photo_files
        self.plugin.on_download_all_sizes_complete(photo=mock_photo, dry_run=False)

        # Should do nothing gracefully
        self.assertEqual(len(self.plugin.current_photo_files), 0)

    def test_on_download_all_sizes_complete_dry_run(self):
        """Test processing in dry run mode"""
        mock_photo = Mock(spec=PhotoAsset)
        mock_photo.filename = "IMG_001.jpg"

        self.plugin.current_photo_files = [
            {
                "path": "/photos/IMG_001.jpg",
                "size": "adjusted",
                "status": "downloaded",
                "is_live": False,
                "photo_filename": "IMG_001.jpg",
            },
        ]

        self.plugin.on_download_all_sizes_complete(photo=mock_photo, dry_run=True)

        # In dry run mode, batch queue should still be empty (no processing)
        # Note: dry_run skips accumulation entirely
        self.assertEqual(len(self.plugin.batch_queue), 0)

    @patch("plugins.immich.immich.ImmichPlugin._process_photo_group")
    def test_on_download_all_sizes_complete_success(self, mock_process_photo_group):
        """Test successful processing workflow"""
        mock_photo = Mock(spec=PhotoAsset)
        mock_photo.created = Mock()
        mock_photo.filename = "IMG_001.jpg"
        mock_photo._asset_record = {"fields": {"isFavorite": {"value": 1}}}

        self.plugin.current_photo_files = [
            {
                "path": "/photos/IMG_001.jpg",
                "size": "adjusted",
                "status": "downloaded",
                "is_live": False,
                "photo_filename": "IMG_001.jpg",
            },
        ]

        self.plugin.on_download_all_sizes_complete(photo=mock_photo, dry_run=False)

        # Verify _process_photo_group was called with correct parameters
        # For downloaded files (status='downloaded'), favorites_only should be False
        mock_process_photo_group.assert_called_once()
        call_args = mock_process_photo_group.call_args
        self.assertFalse(call_args[1]["favorites_only"])  # Downloaded files get full processing

    @patch("plugins.immich.immich.ImmichPlugin._process_photo_group")
    def test_on_download_all_sizes_complete_existing_assets_found(self, mock_process_photo_group):
        """Test that process_existing=True processes existing files"""
        mock_photo = Mock(spec=PhotoAsset)
        mock_photo.created = Mock()
        mock_photo.filename = "IMG_001.jpg"
        mock_photo._asset_record = {"fields": {"isFavorite": {"value": 0}}}

        # All files have status 'existed'
        self.plugin.current_photo_files = [
            {
                "path": "/photos/IMG_001.jpg",
                "size": "adjusted",
                "status": "existed",
                "is_live": False,
                "photo_filename": "IMG_001.jpg",
            },
            {
                "path": "/photos/IMG_001-medium.jpg",
                "size": "medium",
                "status": "existed",
                "is_live": False,
                "photo_filename": "IMG_001.jpg",
            },
        ]

        self.plugin.on_download_all_sizes_complete(photo=mock_photo, dry_run=False)

        # Verify _process_photo_group was called
        mock_process_photo_group.assert_called_once()

        # Verify accumulators were cleared at end
        self.assertEqual(len(self.plugin.current_photo_files), 0)

    @patch("plugins.immich.immich.ImmichPlugin._process_photo_group")
    def test_on_download_all_sizes_complete_existing_assets_missing(self, mock_process_photo_group):
        """Test that existing files are processed via batch/immediate mode"""
        mock_photo = Mock(spec=PhotoAsset)
        mock_photo.created = Mock()
        mock_photo.filename = "IMG_001.jpg"
        mock_photo._asset_record = {"fields": {"isFavorite": {"value": 0}}}

        # All files have status 'existed'
        self.plugin.current_photo_files = [
            {
                "path": "/photos/IMG_001.jpg",
                "size": "adjusted",
                "status": "existed",
                "is_live": False,
                "photo_filename": "IMG_001.jpg",
            },
            {
                "path": "/photos/IMG_001-medium.jpg",
                "size": "medium",
                "status": "existed",
                "is_live": False,
                "photo_filename": "IMG_001.jpg",
            },
        ]

        self.plugin.on_download_all_sizes_complete(photo=mock_photo, dry_run=False)

        # Verify _process_photo_group was called
        # The actual scan/wait logic is tested inside _process_photo_group
        mock_process_photo_group.assert_called_once()


class TestImmichPluginStacking(unittest.TestCase):
    """Test ImmichPlugin media stacking functionality"""

    def setUp(self):
        """Set up test plugin"""
        self.plugin = ImmichPlugin()
        self.plugin.server_url = "http://localhost:2283"
        self.plugin.api_key = "test-key"
        self.plugin.stack_media = True
        self.plugin.stack_priority = ["adjusted", "original"]

    def test_process_stacking_no_sizes(self):
        """Test stacking with no eligible sizes"""
        assets = []
        self.plugin._process_stacking(assets)
        # Should do nothing (just logs debug)

    def test_process_stacking_single_size(self):
        """Test stacking with single size (no stacking needed)"""
        assets = [{"asset_id": "asset-001", "size": "adjusted"}]
        self.plugin._process_stacking(assets)
        # Should do nothing (just logs debug)

    @patch("plugins.immich.immich.ImmichPlugin._create_stack")
    def test_process_stacking_multiple_sizes(self, mock_create_stack):
        """Test stacking with multiple sizes"""
        assets = [
            {"asset_id": "asset-001", "size": "adjusted"},
            {"asset_id": "asset-002", "size": "original"},
        ]

        self.plugin._process_stacking(assets)

        # Should call _create_stack with ordered IDs
        mock_create_stack.assert_called_once()
        called_ids = mock_create_stack.call_args[0][0]
        # First should be adjusted (higher priority)
        self.assertEqual(called_ids[0], "asset-001")


class TestImmichPluginFavorites(unittest.TestCase):
    """Test ImmichPlugin favorites functionality"""

    def setUp(self):
        """Set up test plugin"""
        self.plugin = ImmichPlugin()
        self.plugin.server_url = "http://localhost:2283"
        self.plugin.api_key = "test-key"
        self.plugin.favorite_sizes = ["adjusted"]

    @patch("plugins.immich.immich.ImmichPlugin._set_favorite")
    def test_process_favoriting(self, mock_set_favorite):
        """Test marking assets as favorites"""
        assets = [
            {"asset_id": "asset-001", "size": "adjusted", "is_favorite": False},
            {"asset_id": "asset-002", "size": "original", "is_favorite": False},
        ]
        is_favorite = True

        self.plugin._process_favoriting(assets, is_favorite)

        # Should call _set_favorite with only adjusted asset
        mock_set_favorite.assert_called_once_with(["asset-001"], True)

    def test_process_favoriting_no_matches(self):
        """Test marking favorites with no matching sizes"""
        assets = [{"asset_id": "asset-001", "size": "medium", "is_favorite": False}]
        is_favorite = True

        # Should return early without calling any API
        self.plugin._process_favoriting(assets, is_favorite)
        # No exception should be raised


class TestImmichPluginProcessExistingFavoritesOnly(unittest.TestCase):
    """Test ImmichPlugin process existing favorites only functionality (favorites_only=True)"""

    def setUp(self):
        """Set up test plugin"""
        self.plugin = ImmichPlugin()
        self.plugin.server_url = "http://localhost:2283"
        self.plugin.api_key = "test-key"
        self.plugin.library_id = "lib-123"
        self.plugin.favorite_sizes = ["adjusted"]
        self.plugin.scan_timeout = 5.0
        self.plugin.process_existing_favorites = True

    @patch("plugins.immich.immich.ImmichPlugin._process_photo_group")
    def test_process_existing_favorites_only_assets_already_registered(
        self, mock_process_photo_group
    ):
        """Test processing existing favorites when all files existed"""
        # Mock photo
        mock_photo = Mock(spec=PhotoAsset)
        mock_photo.filename = "IMG_001.HEIC"
        mock_photo.created = Mock()
        mock_photo._asset_record = {
            "fields": {
                "isFavorite": {"value": 1}  # IS favorite
            }
        }

        # Set up current_photo_files - all existed
        self.plugin.current_photo_files = [
            {
                "status": "existed",
                "path": "/photos/IMG_001.jpg",
                "size": "adjusted",
                "is_live": False,
                "photo_filename": "IMG_001.HEIC",
            },
            {
                "status": "existed",
                "path": "/photos/IMG_001_original.jpg",
                "size": "original",
                "is_live": False,
                "photo_filename": "IMG_001.HEIC",
            },
        ]

        # Call on_download_all_sizes_complete
        self.plugin.on_download_all_sizes_complete(photo=mock_photo, dry_run=False)

        # Should call _process_photo_group with favorites_only=True
        # (all existed + process_existing_favorites + is_favorite)
        mock_process_photo_group.assert_called_once()
        call_args = mock_process_photo_group.call_args
        self.assertTrue(call_args[1]["favorites_only"])

    @patch("plugins.immich.immich.ImmichPlugin._process_photo_group")
    def test_process_existing_favorites_only_assets_missing_triggers_scan(
        self, mock_process_photo_group
    ):
        """Test that favorites_only=True when all conditions met"""
        # Mock photo
        mock_photo = Mock(spec=PhotoAsset)
        mock_photo.filename = "IMG_002.HEIC"
        mock_photo.created = Mock()
        mock_photo._asset_record = {
            "fields": {
                "isFavorite": {"value": 1}  # IS favorite
            }
        }

        # Set up current_photo_files - all existed
        self.plugin.current_photo_files = [
            {
                "status": "existed",
                "path": "/photos/IMG_002.jpg",
                "size": "adjusted",
                "is_live": False,
                "photo_filename": "IMG_002.HEIC",
            }
        ]

        # Call on_download_all_sizes_complete
        self.plugin.on_download_all_sizes_complete(photo=mock_photo, dry_run=False)

        # Should call _process_photo_group with favorites_only=True
        mock_process_photo_group.assert_called_once()
        call_args = mock_process_photo_group.call_args
        self.assertTrue(call_args[1]["favorites_only"])

    @patch("plugins.immich.immich.ImmichPlugin._process_photo_group")
    def test_process_existing_favorites_only_no_favorite_sizes_configured(
        self, mock_process_photo_group
    ):
        """Test that favorites_only=False when photo is NOT favorite"""
        # Mock photo that is NOT a favorite
        mock_photo = Mock(spec=PhotoAsset)
        mock_photo.filename = "IMG_003.HEIC"
        mock_photo.created = Mock()
        mock_photo._asset_record = {
            "fields": {
                "isFavorite": {"value": 0}  # NOT favorite
            }
        }

        # Set up current_photo_files - all existed
        self.plugin.current_photo_files = [
            {
                "status": "existed",
                "path": "/photos/IMG_003.jpg",
                "size": "adjusted",
                "is_live": False,
                "photo_filename": "IMG_003.HEIC",
            }
        ]

        # Call on_download_all_sizes_complete
        self.plugin.on_download_all_sizes_complete(photo=mock_photo, dry_run=False)

        # Should call _process_photo_group with favorites_only=False
        # (all existed + process_existing_favorites BUT NOT is_favorite)
        mock_process_photo_group.assert_called_once()
        call_args = mock_process_photo_group.call_args
        self.assertFalse(call_args[1]["favorites_only"])


class TestImmichPluginAlbums(unittest.TestCase):
    """Test ImmichPlugin album functionality"""

    def setUp(self):
        """Set up test plugin"""
        self.plugin = ImmichPlugin()
        self.plugin.server_url = "http://localhost:2283"
        self.plugin.api_key = "test-key"
        self.plugin.album_rules = [AlbumRule("[adjusted]:Favorites")]

    @patch("plugins.immich.immich.ImmichPlugin._add_assets_to_album")
    @patch("plugins.immich.immich.ImmichPlugin._get_or_create_album")
    def test_process_albums(self, mock_get_album, mock_add_assets):
        """Test applying album rules"""
        mock_get_album.return_value = "album-123"

        mock_photo_created = Mock()
        photo_filename = "IMG_001.jpg"

        assets = [
            {"asset_id": "asset-001", "size": "adjusted"},
            {"asset_id": "asset-002", "size": "original"},
        ]

        self.plugin._process_albums(assets, mock_photo_created, photo_filename)

        # Should get/create album and add only adjusted asset
        mock_get_album.assert_called_once_with("Favorites")
        mock_add_assets.assert_called_once_with("album-123", ["asset-001"])


class TestImmichPluginBatchProcessing(unittest.TestCase):
    """Test ImmichPlugin batch processing functionality"""

    def setUp(self):
        """Set up test plugin with batch processing enabled"""
        self.plugin = ImmichPlugin()
        self.plugin.server_url = "http://localhost:2283"
        self.plugin.api_key = "test-key"
        self.plugin.library_id = "lib-123"

    def test_batch_processing_disabled_by_default(self):
        """Test batch processing is immediate by default (batch_size=1)"""
        # batch_size=1 means immediate processing (process batch of 1 immediately)
        self.assertEqual(self.plugin.batch_size, 1)

    def test_batch_processing_enabled_with_size(self):
        """Test batch processing enabled with specific batch size"""
        self.plugin.batch_size = 10
        self.assertEqual(self.plugin.batch_size, 10)

    def test_batch_processing_enabled_process_all(self):
        """Test batch processing enabled with 'all' (process at end)"""
        # batch_size=0 means process all at end
        self.plugin.batch_size = 0
        self.assertEqual(self.plugin.batch_size, 0)

    def test_batch_log_file_default_path(self):
        """Test default batch log file path"""
        import os

        expected_path = os.path.expanduser("~/.pyicloud/immich_pending_files.json")
        self.plugin.batch_log_file = expected_path
        self.assertEqual(self.plugin.batch_log_file, expected_path)

    def test_batch_accumulation_immediate_mode(self):
        """Test that with batch_size=1, photos are still accumulated (processed as batch of 1)"""
        # batch_size=1 is default, processes immediately as a batch of 1
        self.plugin.batch_size = 1

        # Mock photo
        photo = Mock(spec=PhotoAsset)
        photo.id = "photo-001"
        photo._asset_record = {"fields": {"isFavorite": {"value": 0}}}

        # Add files to current_photo_files
        self.plugin.current_photo_files = [
            {"status": "downloaded", "path": "/photos/img1.jpg", "size": "original"}
        ]

        # Call the accumulation method
        self.plugin._accumulate_to_batch(photo)

        # Verify batch queue has the photo (will be processed immediately in on_download_all_sizes_complete)
        self.assertEqual(len(self.plugin.batch_queue), 1)
        self.assertEqual(self.plugin.batch_queue[0]["photo_id"], "photo-001")
        self.assertEqual(len(self.plugin.batch_queue[0]["files"]), 1)

    def test_batch_accumulation_with_batching(self):
        """Test that with batching enabled, photos are added to batch queue"""
        self.plugin.batch_size = 10

        # Mock photo
        photo = Mock(spec=PhotoAsset)
        photo.id = "photo-001"
        photo._asset_record = {"fields": {"isFavorite": {"value": 0}}}

        # Add files to current_photo_files
        self.plugin.current_photo_files = [
            {"status": "downloaded", "path": "/photos/img1.jpg", "size": "original"}
        ]

        # Call the accumulation method
        self.plugin._accumulate_to_batch(photo)

        # Verify batch queue has the photo
        self.assertEqual(len(self.plugin.batch_queue), 1)
        self.assertEqual(self.plugin.batch_queue[0]["photo_id"], "photo-001")
        self.assertEqual(len(self.plugin.batch_queue[0]["files"]), 1)

    def test_batch_trigger_after_n_photos(self):
        """Test batch processing triggers after N photos accumulated"""
        self.plugin.batch_size = 3

        # Add 3 photos to batch queue
        for i in range(3):
            photo = Mock(spec=PhotoAsset)
            photo.id = f"photo-{i:03d}"
            photo._asset_record = {"fields": {"isFavorite": {"value": 0}}}

            self.plugin.current_photo_files = [
                {"status": "downloaded", "path": f"/photos/img{i}.jpg", "size": "original"}
            ]
            self.plugin._accumulate_to_batch(photo)

        # After 3 photos, batch queue should have 3 items
        self.assertEqual(len(self.plugin.batch_queue), 3)

    def test_batch_not_triggered_before_n_photos(self):
        """Test batch processing doesn't trigger before N photos"""
        self.plugin.batch_size = 10

        # Add only 5 photos
        for i in range(5):
            photo = Mock(spec=PhotoAsset)
            photo.id = f"photo-{i:03d}"
            photo._asset_record = {"fields": {"isFavorite": {"value": 0}}}

            self.plugin.current_photo_files = [
                {"status": "downloaded", "path": f"/photos/img{i}.jpg", "size": "original"}
            ]
            self.plugin._accumulate_to_batch(photo)

        # Batch queue should have 5 items but not be processed yet
        self.assertEqual(len(self.plugin.batch_queue), 5)

    def test_batch_process_all_waits_until_end(self):
        """Test batch_size=0 ('all') accumulates all photos until on_run_completed"""
        self.plugin.batch_size = 0  # 0 means 'all'

        # Add many photos
        for i in range(100):
            photo = Mock(spec=PhotoAsset)
            photo.id = f"photo-{i:03d}"
            photo._asset_record = {"fields": {"isFavorite": {"value": 0}}}

            self.plugin.current_photo_files = [
                {"status": "downloaded", "path": f"/photos/img{i}.jpg", "size": "original"}
            ]
            self.plugin._accumulate_to_batch(photo)

        # Should have accumulated all 100 photos
        self.assertEqual(len(self.plugin.batch_queue), 100)

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data="[]")
    def test_load_pending_files_empty(self, mock_open_file, mock_exists):
        """Test loading pending files when file is empty"""
        mock_exists.return_value = True
        self.plugin.batch_log_file = "/tmp/pending.json"

        self.plugin._load_pending_files()

        # Should have empty batch queue
        self.assertEqual(len(self.plugin.batch_queue), 0)

    @patch("os.path.exists")
    @patch(
        "builtins.open",
        new_callable=unittest.mock.mock_open,
        read_data='[{"photo_id": "photo-001", "files": [{"path": "/photos/img1.jpg"}], "is_favorite": false}]',
    )
    def test_load_pending_files_with_data(self, mock_open_file, mock_exists):
        """Test loading pending files when file has data"""
        mock_exists.return_value = True
        self.plugin.batch_log_file = "/tmp/pending.json"

        self.plugin._load_pending_files()

        # Should have loaded the pending photo
        self.assertEqual(len(self.plugin.batch_queue), 1)
        self.assertEqual(self.plugin.batch_queue[0]["photo_id"], "photo-001")

    @patch("os.path.exists")
    def test_load_pending_files_no_file(self, mock_exists):
        """Test loading pending files when file doesn't exist"""
        mock_exists.return_value = False
        self.plugin.batch_log_file = "/tmp/pending.json"

        self.plugin._load_pending_files()

        # Should have empty batch queue
        self.assertEqual(len(self.plugin.batch_queue), 0)

    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_save_pending_files(self, mock_open_file):
        """Test saving pending files to disk"""
        self.plugin.batch_log_file = "/tmp/pending.json"
        self.plugin.batch_queue = [
            {
                "photo_id": "photo-001",
                "files": [{"path": "/photos/img1.jpg", "size": "original"}],
                "is_favorite": False,
            }
        ]

        self.plugin._save_pending_files()

        # Should have written to file
        mock_open_file.assert_called_once_with("/tmp/pending.json", "w")

    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_clear_pending_files_after_processing(self, mock_open_file):
        """Test pending files are cleared after successful processing"""
        self.plugin.batch_log_file = "/tmp/pending.json"
        self.plugin.batch_queue = [
            {
                "photo_id": "photo-001",
                "files": [{"path": "/photos/img1.jpg", "size": "original"}],
                "is_favorite": False,
            }
        ]

        # Simulate successful processing
        self.plugin._clear_processed_from_log(["photo-001"])

        # Batch queue should be empty
        self.assertEqual(len(self.plugin.batch_queue), 0)

    def test_on_download_all_sizes_complete_immediate_mode(self):
        """Test on_download_all_sizes_complete with batch_size=1 processes immediately"""
        # batch_size=1 is the default (immediate processing)
        self.plugin.batch_size = 1

        photo = Mock(spec=PhotoAsset)
        photo.id = "photo-001"
        photo.filename = "IMG_001.jpg"
        photo._asset_record = {"fields": {"isFavorite": {"value": 0}}}

        self.plugin.current_photo_files = [
            {"status": "downloaded", "path": "/photos/img1.jpg", "size": "original"}
        ]

        # With batch_size=1, accumulates to queue and processes immediately
        # (batch queue gets cleared after processing)

    @patch("plugins.immich.immich.ImmichPlugin._process_batch")
    def test_on_run_completed_processes_remaining_batch(self, mock_process_batch):
        """Test on_run_completed processes all remaining batched photos"""
        self.plugin.batch_size = 10

        # Add some photos to batch queue (less than batch size)
        for i in range(5):
            self.plugin.batch_queue.append(
                {
                    "photo_id": f"photo-{i:03d}",
                    "files": [{"path": f"/photos/img{i}.jpg", "size": "original"}],
                    "is_favorite": False,
                }
            )

        self.plugin.on_run_completed(dry_run=False)

        # Should have processed the remaining batch
        mock_process_batch.assert_called_once()

    def test_batch_preserves_photo_metadata(self):
        """Test batch queue preserves necessary photo metadata for processing"""
        self.plugin.batch_size = 10

        photo = Mock(spec=PhotoAsset)
        photo.id = "photo-001"
        photo._asset_record = {"fields": {"isFavorite": {"value": 1}}}
        photo.created = Mock()

        self.plugin.current_photo_files = [
            {"status": "downloaded", "path": "/photos/img1.jpg", "size": "original"},
            {"status": "downloaded", "path": "/photos/img1-adjusted.jpg", "size": "adjusted"},
        ]

        self.plugin._accumulate_to_batch(photo)

        # Verify metadata is preserved
        batch_item = self.plugin.batch_queue[0]
        self.assertEqual(batch_item["photo_id"], "photo-001")
        self.assertTrue(batch_item["is_favorite"])
        self.assertEqual(len(batch_item["files"]), 2)
        self.assertIn("created", batch_item)

    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    @patch("os.makedirs")
    def test_save_pending_creates_directory(self, mock_makedirs, mock_open_file):
        """Test saving pending files creates directory if needed"""
        import os

        self.plugin.batch_log_file = "/new/path/pending.json"
        self.plugin.batch_queue = [{"photo_id": "photo-001", "files": [], "is_favorite": False}]

        self.plugin._save_pending_files()

        # Should create directory
        expected_dir = os.path.dirname("/new/path/pending.json")
        mock_makedirs.assert_called_once_with(expected_dir, exist_ok=True)

    def test_batch_queue_includes_all_files(self):
        """Test batching includes both downloaded and existed files"""
        self.plugin.batch_size = 10
        self.plugin.process_existing = True

        # Mix of downloaded and existed files
        photo = Mock(spec=PhotoAsset)
        photo.id = "photo-001"
        photo._asset_record = {"fields": {"isFavorite": {"value": 0}}}

        self.plugin.current_photo_files = [
            {"status": "downloaded", "path": "/photos/img1.jpg", "size": "original"},
            {"status": "existed", "path": "/photos/img1-adjusted.jpg", "size": "adjusted"},
        ]

        self.plugin._accumulate_to_batch(photo)

        # Batch should contain all files - batching applies to entire photo processing
        batch_item = self.plugin.batch_queue[0]

        # Both should be in batch - batching applies to all processing
        self.assertEqual(len(batch_item["files"]), 2)


class TestImmichPluginDirectoryValidationFull(unittest.TestCase):
    """Full tests for directory validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.plugin = ImmichPlugin()
        self.plugin.server_url = "http://localhost:2283"
        self.plugin.api_key = "test-api-key"
        self.plugin.library_id = "test-library-id"

    @patch("plugins.immich.immich.requests.get")
    def test_validate_directories_success(self, mock_get):
        """Test successful directory validation"""
        mock_response = Mock()
        mock_response.json.return_value = {"importPaths": ["/mnt/photos", "/backup/photos"]}
        mock_get.return_value = mock_response

        # Create mock user configs
        user_config = Mock()
        user_config.directory = "/mnt/photos/icloud"
        user_configs = [user_config]

        # Should not raise
        self.plugin._validate_directories(user_configs)

    @patch("plugins.immich.immich.requests.get")
    def test_validate_directories_no_import_paths(self, mock_get):
        """Test validation with no importPaths"""
        mock_response = Mock()
        mock_response.json.return_value = {"importPaths": []}
        mock_get.return_value = mock_response

        user_config = Mock()
        user_config.directory = "/mnt/photos/icloud"
        user_configs = [user_config]

        with self.assertRaises(SystemExit):
            self.plugin._validate_directories(user_configs)

    @patch("plugins.immich.immich.requests.get")
    def test_validate_directories_invalid_path(self, mock_get):
        """Test validation with path outside importPaths"""
        mock_response = Mock()
        mock_response.json.return_value = {"importPaths": ["/mnt/photos"]}
        mock_get.return_value = mock_response

        user_config = Mock()
        user_config.directory = "/other/path/icloud"
        user_configs = [user_config]

        with self.assertRaises(SystemExit):
            self.plugin._validate_directories(user_configs)

    @patch("plugins.immich.immich.requests.get")
    def test_validate_directories_with_date_templates(self, mock_get):
        """Test validation strips date templates"""
        mock_response = Mock()
        mock_response.json.return_value = {"importPaths": ["/mnt/photos"]}
        mock_get.return_value = mock_response

        user_config = Mock()
        user_config.directory = "/mnt/photos/{:%Y}/{:%m}"
        user_configs = [user_config]

        # Should not raise - date templates are stripped
        self.plugin._validate_directories(user_configs)


class TestParseBatchSize(unittest.TestCase):
    """Test _parse_batch_size helper function"""

    def test_parse_batch_size_none(self):
        """Test None returns 0"""
        result = _parse_batch_size(None)
        self.assertEqual(result, 0)

    def test_parse_batch_size_all_lowercase(self):
        """Test 'all' returns 0"""
        result = _parse_batch_size("all")
        self.assertEqual(result, 0)

    def test_parse_batch_size_all_uppercase(self):
        """Test 'ALL' returns 0"""
        result = _parse_batch_size("ALL")
        self.assertEqual(result, 0)

    def test_parse_batch_size_valid_integer(self):
        """Test valid integer"""
        result = _parse_batch_size("10")
        self.assertEqual(result, 10)

    def test_parse_batch_size_one(self):
        """Test batch size of 1"""
        result = _parse_batch_size("1")
        self.assertEqual(result, 1)

    def test_parse_batch_size_zero_raises(self):
        """Test that 0 raises error"""
        with self.assertRaises(argparse.ArgumentTypeError) as context:
            _parse_batch_size("0")
        self.assertIn("must be >= 1", str(context.exception))

    def test_parse_batch_size_negative_raises(self):
        """Test that negative raises error"""
        with self.assertRaises(argparse.ArgumentTypeError) as context:
            _parse_batch_size("-5")
        self.assertIn("must be >= 1", str(context.exception))

    def test_parse_batch_size_invalid_string_raises(self):
        """Test that invalid string raises error"""
        with self.assertRaises(argparse.ArgumentTypeError) as context:
            _parse_batch_size("invalid")
        self.assertIn("Invalid batch size", str(context.exception))


if __name__ == "__main__":
    unittest.main()
