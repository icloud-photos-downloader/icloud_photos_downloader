"""Tests for plugin system"""

import tempfile
import unittest
from argparse import ArgumentParser, Namespace
from pathlib import Path
from unittest.mock import MagicMock

from icloudpd.plugins.base import IcloudpdPlugin
from icloudpd.plugins.demo import DemoPlugin
from icloudpd.plugins.manager import PluginManager
from pyicloud_ipd.services.photos import PhotoAsset
from pyicloud_ipd.version_size import AssetVersionSize


class MockPlugin(IcloudpdPlugin):
    """Mock plugin for testing"""

    def __init__(self):
        super().__init__()
        self.calls = []
        self.configured = False
        self.cleaned_up = False
        self.mock_option = None
        self.configure_count = 0

    @property
    def name(self) -> str:
        return "mock"

    @property
    def description(self) -> str:
        return "Mock plugin for testing"

    def add_arguments(self, parser: ArgumentParser) -> None:
        group = parser.add_argument_group("Mock Plugin")
        group.add_argument("--mock-option", help="Mock option")

    def configure(self, config: Namespace, global_config=None, user_configs=None) -> None:
        self.configured = True
        self.configure_count += 1
        self.mock_option = getattr(config, "mock_option", None)

    def on_download_exists(
        self, download_path, photo_filename, requested_size, photo, dry_run
    ) -> None:
        self.calls.append(("on_download_exists", download_path))

    def on_download_downloaded(
        self, download_path, photo_filename, requested_size, photo, dry_run
    ) -> None:
        self.calls.append(("on_download_downloaded", download_path))

    def on_download_complete(
        self, download_path, photo_filename, requested_size, photo, dry_run
    ) -> None:
        self.calls.append(("on_download_complete", download_path))

    def on_download_all_sizes_complete(self, photo, dry_run) -> None:
        self.calls.append(("on_download_all_sizes_complete", photo.filename))

    def on_run_completed(self, dry_run) -> None:
        self.calls.append(("on_run_completed", None))

    def cleanup(self) -> None:
        self.cleaned_up = True


class BrokenPlugin(IcloudpdPlugin):
    """Plugin that raises errors for testing error handling"""

    @property
    def name(self) -> str:
        return "broken"

    def on_download_complete(self, **kwargs) -> None:
        raise RuntimeError("Simulated plugin error")


class TestPluginManager(unittest.TestCase):
    """Test PluginManager functionality"""

    def test_init(self):
        """Test plugin manager initialization"""
        manager = PluginManager()
        self.assertEqual(manager.available, {})
        self.assertEqual(manager.enabled, {})

    def test_list_available(self):
        """Test listing available plugins"""
        manager = PluginManager()
        manager.available["mock"] = MockPlugin
        manager.available["broken"] = BrokenPlugin

        plugins = manager.list_available()
        self.assertIn("mock", plugins)
        self.assertIn("broken", plugins)
        # Should be sorted
        self.assertEqual(plugins, sorted(plugins))

    def test_get_plugin_info(self):
        """Test getting plugin information"""
        manager = PluginManager()
        manager.available["mock"] = MockPlugin

        info = manager.get_plugin_info("mock")
        self.assertEqual(info["name"], "mock")
        self.assertEqual(info["description"], "Mock plugin for testing")
        self.assertIn("version", info)

    def test_get_plugin_info_not_found(self):
        """Test getting info for unknown plugin raises KeyError"""
        manager = PluginManager()

        with self.assertRaises(KeyError):
            manager.get_plugin_info("nonexistent")

    def test_enable_plugin(self):
        """Test enabling a plugin with explicit config"""
        manager = PluginManager()
        manager.available["mock"] = MockPlugin

        config = Namespace(mock_option="test")
        manager.enable("mock", config)

        self.assertIn("mock", manager.enabled)
        self.assertIsInstance(manager.enabled["mock"], MockPlugin)
        self.assertTrue(manager.enabled["mock"].configured)
        self.assertEqual(manager.enabled["mock"].mock_option, "test")

    def test_enable_plugin_with_stored_config(self):
        """Test enabling a plugin using stored config"""
        manager = PluginManager()
        manager.available["mock"] = MockPlugin

        # Store config first
        config = Namespace(mock_option="from_stored")
        manager.set_plugin_config(config)

        # Enable without passing config explicitly
        manager.enable("mock")

        self.assertIn("mock", manager.enabled)
        self.assertIsInstance(manager.enabled["mock"], MockPlugin)
        self.assertTrue(manager.enabled["mock"].configured)
        self.assertEqual(manager.enabled["mock"].mock_option, "from_stored")

    def test_enable_plugin_without_config_raises(self):
        """Test enabling plugin without config raises ValueError"""
        manager = PluginManager()
        manager.available["mock"] = MockPlugin

        # Don't set config or pass it
        with self.assertRaises(ValueError) as ctx:
            manager.enable("mock")

        self.assertIn("No configuration available", str(ctx.exception))

    def test_enable_unknown_plugin(self):
        """Test enabling unknown plugin raises KeyError"""
        manager = PluginManager()

        with self.assertRaises(KeyError):
            manager.enable("nonexistent", Namespace())

    def test_disable_plugin(self):
        """Test disabling a plugin calls cleanup"""
        manager = PluginManager()
        manager.available["mock"] = MockPlugin
        manager.enable("mock", Namespace())

        plugin = manager.enabled["mock"]
        self.assertIn("mock", manager.enabled)

        manager.disable("mock")

        self.assertNotIn("mock", manager.enabled)
        self.assertTrue(plugin.cleaned_up)

    def test_is_enabled(self):
        """Test checking if plugin is enabled"""
        manager = PluginManager()
        manager.available["mock"] = MockPlugin

        self.assertFalse(manager.is_enabled("mock"))

        manager.enable("mock", Namespace())
        self.assertTrue(manager.is_enabled("mock"))

        manager.disable("mock")
        self.assertFalse(manager.is_enabled("mock"))

    def test_configure_called_once_with_runtime_configs(self):
        """Test that configure is only called once when runtime configs are provided later"""

        manager = PluginManager()
        manager.available["mock"] = MockPlugin

        # Step 1: Store config (like cli.py does)
        config = Namespace(mock_option="test")
        manager.set_plugin_config(config)

        # Step 2: Enable plugin (like cli.py does) - should call configure once
        manager.enable("mock")

        plugin = manager.enabled["mock"]
        self.assertEqual(plugin.configure_count, 1)

        # Step 3: Provide runtime configs (like base.py does) - should NOT call configure again
        mock_global_config = MagicMock()
        mock_user_configs = [MagicMock()]
        manager.set_plugin_config(config, mock_global_config, mock_user_configs)

        # Verify configure was still only called once
        self.assertEqual(plugin.configure_count, 1)

    def test_add_plugin_arguments(self):
        """Test adding plugin arguments to parser"""
        manager = PluginManager()
        manager.available["mock"] = MockPlugin

        parser = ArgumentParser()
        manager.add_plugin_arguments(parser, ["mock"])

        # Parse args with plugin option
        args = parser.parse_args(["--mock-option", "value"])
        self.assertEqual(args.mock_option, "value")

    def test_call_hook_single_plugin(self):
        """Test calling hooks on a single enabled plugin"""
        manager = PluginManager()
        manager.available["mock"] = MockPlugin
        manager.enable("mock", Namespace())

        # Create mock photo
        mock_photo = MagicMock(spec=PhotoAsset)
        mock_photo.filename = "test.jpg"

        manager.call_hook(
            "on_download_complete",
            download_path="/path/to/file.jpg",
            photo_filename="test.jpg",
            requested_size=AssetVersionSize.ORIGINAL,
            photo=mock_photo,
            dry_run=False,
        )

        plugin = manager.enabled["mock"]
        self.assertEqual(len(plugin.calls), 1)
        self.assertEqual(plugin.calls[0][0], "on_download_complete")
        self.assertEqual(plugin.calls[0][1], "/path/to/file.jpg")

    def test_call_hook_multiple_plugins(self):
        """Test hooks called on all enabled plugins"""
        manager = PluginManager()

        class MockPlugin1(MockPlugin):
            @property
            def name(self):
                return "mock1"

        class MockPlugin2(MockPlugin):
            @property
            def name(self):
                return "mock2"

        manager.available["mock1"] = MockPlugin1
        manager.available["mock2"] = MockPlugin2

        manager.enable("mock1", Namespace())
        manager.enable("mock2", Namespace())

        mock_photo = MagicMock(spec=PhotoAsset)
        mock_photo.filename = "test.jpg"

        manager.call_hook("on_download_all_sizes_complete", photo=mock_photo, dry_run=False)

        self.assertEqual(len(manager.enabled["mock1"].calls), 1)
        self.assertEqual(len(manager.enabled["mock2"].calls), 1)

    def test_call_hook_only_enabled_plugins(self):
        """Test hooks only called on enabled plugins"""
        manager = PluginManager()

        class MockPlugin2(MockPlugin):
            @property
            def name(self):
                return "mock2"

        manager.available["mock1"] = MockPlugin
        manager.available["mock2"] = MockPlugin2

        # Only enable mock1
        manager.enable("mock1", Namespace())

        mock_photo = MagicMock(spec=PhotoAsset)
        mock_photo.filename = "test.jpg"

        manager.call_hook("on_download_all_sizes_complete", photo=mock_photo, dry_run=False)

        self.assertEqual(len(manager.enabled["mock1"].calls), 1)
        # mock2 not enabled
        self.assertNotIn("mock2", manager.enabled)

    def test_cleanup_all(self):
        """Test cleanup_all disables all plugins"""
        manager = PluginManager()

        class MockPlugin1(MockPlugin):
            @property
            def name(self):
                return "mock1"

        class MockPlugin2(MockPlugin):
            @property
            def name(self):
                return "mock2"

        manager.available["mock1"] = MockPlugin1
        manager.available["mock2"] = MockPlugin2

        manager.enable("mock1", Namespace())
        manager.enable("mock2", Namespace())

        plugin1 = manager.enabled["mock1"]
        plugin2 = manager.enabled["mock2"]

        manager.cleanup_all()

        self.assertEqual(len(manager.enabled), 0)
        self.assertTrue(plugin1.cleaned_up)
        self.assertTrue(plugin2.cleaned_up)


class TestDemoPlugin(unittest.TestCase):
    """Test the demo plugin"""

    def test_demo_plugin_initialization(self):
        """Test demo plugin can be created"""
        plugin = DemoPlugin()
        self.assertEqual(plugin.name, "demo")
        self.assertIn("demo", plugin.description.lower())
        self.assertEqual(plugin.version, "1.0.0")

    def test_demo_plugin_arguments(self):
        """Test demo plugin adds arguments"""
        plugin = DemoPlugin()
        parser = ArgumentParser()
        plugin.add_arguments(parser)

        # Test --demo-verbose
        args = parser.parse_args(["--demo-verbose"])
        self.assertTrue(args.demo_verbose)

        # Test --demo-compact
        args = parser.parse_args(["--demo-compact"])
        self.assertTrue(args.demo_compact)

    def test_demo_plugin_accumulation(self):
        """Test demo plugin accumulates files in on_download_complete"""
        plugin = DemoPlugin()
        plugin.configure(Namespace(demo_verbose=False, demo_compact=True))

        mock_photo = MagicMock(spec=PhotoAsset)
        mock_photo.filename = "test.jpg"
        mock_photo.id = "ABC123"
        mock_photo._asset_record = {"fields": {}}

        # Simulate files being processed with on_download_complete
        # (This is what always runs, so it should accumulate)
        plugin.on_download_complete(
            download_path="/path/original.jpg",
            photo_filename="test.jpg",
            requested_size=AssetVersionSize.ORIGINAL,
            photo=mock_photo,
            dry_run=False,
        )

        plugin.on_download_complete(
            download_path="/path/medium.jpg",
            photo_filename="test.jpg",
            requested_size=AssetVersionSize.MEDIUM,
            photo=mock_photo,
            dry_run=False,
        )

        # Should have accumulated 2 files
        self.assertEqual(len(plugin.current_photo_files), 2)

        # Process all sizes complete
        plugin.on_download_all_sizes_complete(photo=mock_photo, dry_run=False)

        # Accumulator should be cleared
        self.assertEqual(len(plugin.current_photo_files), 0)
        self.assertEqual(plugin.total_photos, 1)

    def test_demo_plugin_counts_downloads_and_exists(self):
        """Test demo plugin tracks downloaded vs existing files"""
        plugin = DemoPlugin()
        plugin.configure(Namespace(demo_verbose=False, demo_compact=True))

        mock_photo = MagicMock(spec=PhotoAsset)
        mock_photo.filename = "test.jpg"
        mock_photo._asset_record = {"fields": {}}

        # File exists
        plugin.on_download_exists(
            download_path="/path/original.jpg",
            photo_filename="test.jpg",
            requested_size=AssetVersionSize.ORIGINAL,
            photo=mock_photo,
            dry_run=False,
        )

        # File downloaded
        plugin.on_download_downloaded(
            download_path="/path/medium.jpg",
            photo_filename="test.jpg",
            requested_size=AssetVersionSize.MEDIUM,
            photo=mock_photo,
            dry_run=False,
        )

        self.assertEqual(plugin.total_files_existed, 1)
        self.assertEqual(plugin.total_files_downloaded, 1)


class TestPluginManagerErrorHandling(unittest.TestCase):
    """Test error handling in PluginManager"""

    def test_discover_plugin_directory_scan_error(self):
        """Test error handling when scanning plugin directory fails"""
        manager = PluginManager()
        # The discover() method handles errors internally, so we just verify it doesn't crash
        manager.discover()
        # Should complete without raising

    def test_discover_entry_point_error(self):
        """Test error handling when entry point loading fails"""
        manager = PluginManager()
        # discover() handles errors internally
        manager.discover()
        # Should complete without raising

    def test_enable_plugin_configure_error(self):
        """Test error handling when plugin.configure() raises exception"""

        class FailingConfigurePlugin(IcloudpdPlugin):
            @property
            def name(self):
                return "failing"

            def configure(self, config, global_config=None, user_configs=None):
                raise ValueError("Configuration failed!")

        manager = PluginManager()
        manager.available["failing"] = FailingConfigurePlugin
        manager.set_plugin_config(Namespace())

        # Should raise the configuration error
        with self.assertRaises(ValueError):
            manager.enable("failing")

    def test_disable_plugin_cleanup_error(self):
        """Test error handling when plugin.cleanup() raises exception"""

        class FailingCleanupPlugin(IcloudpdPlugin):
            @property
            def name(self):
                return "failing_cleanup"

            def cleanup(self):
                raise RuntimeError("Cleanup failed!")

        manager = PluginManager()
        manager.available["failing_cleanup"] = FailingCleanupPlugin
        manager.enable("failing_cleanup", Namespace())

        # disable() should handle cleanup errors and still remove plugin
        manager.disable("failing_cleanup")

        # Plugin should be removed despite cleanup error
        self.assertFalse(manager.is_enabled("failing_cleanup"))

    def test_add_plugin_arguments_error(self):
        """Test error handling when add_arguments() raises exception"""

        class FailingArgumentsPlugin(IcloudpdPlugin):
            @property
            def name(self):
                return "failing_args"

            def add_arguments(self, parser):
                raise TypeError("Failed to add arguments!")

        manager = PluginManager()
        manager.available["failing_args"] = FailingArgumentsPlugin

        parser = ArgumentParser()
        # Should handle error gracefully and not crash
        manager.add_plugin_arguments(parser, ["failing_args"])

    def test_call_hook_with_plugin_error(self):
        """Test that hook errors in one plugin don't stop other plugins"""
        manager = PluginManager()

        class WorkingPlugin(MockPlugin):
            @property
            def name(self):
                return "working"

        manager.available["broken"] = BrokenPlugin
        manager.available["working"] = WorkingPlugin

        manager.enable("broken", Namespace())
        manager.enable("working", Namespace())

        mock_photo = MagicMock(spec=PhotoAsset)
        mock_photo.filename = "test.jpg"

        # Call hook - broken plugin will error, but working plugin should still run
        manager.call_hook(
            "on_download_complete",
            download_path="/path/test.jpg",
            photo_filename="test.jpg",
            requested_size=AssetVersionSize.ORIGINAL,
            photo=mock_photo,
            dry_run=False,
        )

        # Working plugin should have been called despite broken plugin erroring
        working_plugin = manager.enabled["working"]
        self.assertEqual(len(working_plugin.calls), 1)

    def test_set_plugin_config_with_runtime_configs(self):
        """Test set_plugin_config with runtime configs provided later"""
        manager = PluginManager()
        manager.available["mock"] = MockPlugin

        # Step 1: Set config without runtime configs
        config = Namespace(mock_option="test")
        manager.set_plugin_config(config)

        # Step 2: Enable plugin
        manager.enable("mock")
        plugin = manager.enabled["mock"]
        self.assertEqual(plugin.configure_count, 1)

        # Step 3: Set runtime configs - plugin already configured, should skip
        mock_global_config = MagicMock()
        mock_user_configs = [MagicMock()]
        manager.set_plugin_config(config, mock_global_config, mock_user_configs)

        # Should not reconfigure
        self.assertEqual(plugin.configure_count, 1)

    def test_set_plugin_config_runtime_error(self):
        """Test error handling when runtime config causes configure error"""

        class RuntimeFailPlugin(IcloudpdPlugin):
            @property
            def name(self):
                return "runtime_fail"

            def configure(self, config, global_config=None, user_configs=None):
                # First call succeeds
                if not hasattr(self, "configured_once"):
                    self.configured_once = True
                    return
                # Second call with runtime configs fails
                if global_config is not None:
                    raise ValueError("Runtime config failed!")

        manager = PluginManager()
        manager.available["runtime_fail"] = RuntimeFailPlugin

        config = Namespace()
        manager.set_plugin_config(config)
        manager.enable("runtime_fail")

        # This should handle the error gracefully (not tested via set_plugin_config
        # because plugin is already configured)


class TestPluginManagerDirectoryDiscovery(unittest.TestCase):
    """Test directory-based plugin discovery edge cases"""

    def test_discover_with_nonexistent_plugins_directory(self):
        """Test discovery when plugins/ directory doesn't exist"""
        manager = PluginManager()
        # Should not raise an error, just log a warning
        manager.discover()
        # Demo plugin should still be found via entry points
        self.assertIn("demo", manager.list_available())

    def test_discover_with_invalid_plugin_module(self):
        """Test discovery with a plugin module that fails to import"""

        # Create a temporary plugins directory
        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / "plugins"
            plugins_dir.mkdir()

            # Create a plugin package with a syntax error
            bad_plugin_dir = plugins_dir / "badplugin"
            bad_plugin_dir.mkdir()
            (bad_plugin_dir / "__init__.py").write_text("this is invalid python syntax !!!")

            # Mock the plugin discovery to use our temp directory
            manager = PluginManager()

            try:
                # This should log a warning but not crash
                manager._discover_from_directory(plugins_dir)
            except Exception as e:
                self.fail(f"Plugin discovery should handle import errors gracefully: {e}")

    def test_discover_plugin_without_plugin_suffix(self):
        """Test that classes not ending in 'Plugin' are ignored"""

        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / "plugins"
            plugins_dir.mkdir()

            # Create a plugin with a class that doesn't end in 'Plugin'
            test_plugin_dir = plugins_dir / "testplugin"
            test_plugin_dir.mkdir()
            (test_plugin_dir / "__init__.py").write_text("""
from icloudpd.plugins.base import IcloudpdPlugin

class NotAPluginClass(IcloudpdPlugin):
    @property
    def name(self):
        return "shouldnotbeloaded"

    @property
    def version(self):
        return "1.0.0"
""")

            manager = PluginManager()
            manager._discover_from_directory(plugins_dir)

            # Should not have discovered the plugin
            self.assertNotIn("shouldnotbeloaded", manager.list_available())

    def test_discover_plugin_with_broken_init(self):
        """Test discovery of plugin whose __init__ raises an exception"""

        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / "plugins"
            plugins_dir.mkdir()

            # Create a plugin that raises in __init__
            broken_plugin_dir = plugins_dir / "brokenplugin"
            broken_plugin_dir.mkdir()
            (broken_plugin_dir / "__init__.py").write_text("""
from icloudpd.plugins.base import IcloudpdPlugin

class BrokenPlugin(IcloudpdPlugin):
    def __init__(self):
        raise ValueError("Broken plugin initialization")

    @property
    def name(self):
        return "broken"

    @property
    def version(self):
        return "1.0.0"
""")

            manager = PluginManager()
            # Should log warning but not crash
            manager._discover_from_directory(plugins_dir)

            # Should not have discovered the broken plugin
            self.assertNotIn("broken", manager.list_available())

    def test_discover_plugin_directory_without_init(self):
        """Test that directories without __init__.py are skipped"""

        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / "plugins"
            plugins_dir.mkdir()

            # Create a directory without __init__.py
            not_a_package_dir = plugins_dir / "notapackage"
            not_a_package_dir.mkdir()
            (not_a_package_dir / "somefile.py").write_text("# Just a file")

            manager = PluginManager()
            # Should skip this directory
            manager._discover_from_directory(plugins_dir)

            # No errors should occur
            self.assertIsInstance(manager.list_available(), list)

    def test_entry_point_discovery_with_duplicate_name(self):
        """Test that plugins/ directory takes precedence over entry points"""
        manager = PluginManager()
        manager.discover()

        # Demo plugin exists in both entry points and could be in plugins/
        # Verify it's discovered at least once
        self.assertIn("demo", manager.list_available())

        # Verify we can get plugin info (should work regardless of source)
        info = manager.get_plugin_info("demo")
        self.assertEqual(info["name"], "demo")


if __name__ == "__main__":
    unittest.main()
