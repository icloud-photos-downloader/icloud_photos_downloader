"""Unit tests for icloudpd.dir_cache — directory listing cache."""

import os
import shutil
import tempfile
from unittest import TestCase

from icloudpd.dir_cache import DirCache


class TestDirCache(TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir)

    def _create_file(self, name: str, size: int) -> str:
        path = os.path.join(self._tmpdir, name)
        with open(path, "wb") as f:
            f.write(b"\x00" * size)
        return path

    def test_isfile_returns_true_for_existing_file(self) -> None:
        path = self._create_file("test.jpg", 1024)
        cache = DirCache()
        self.assertTrue(cache.isfile(path))

    def test_isfile_returns_false_for_missing_file(self) -> None:
        cache = DirCache()
        path = os.path.join(self._tmpdir, "nonexistent.jpg")
        self.assertFalse(cache.isfile(path))

    def test_isfile_returns_false_for_directory(self) -> None:
        subdir = os.path.join(self._tmpdir, "subdir")
        os.makedirs(subdir)
        cache = DirCache()
        self.assertFalse(cache.isfile(subdir))

    def test_stat_size_returns_correct_size(self) -> None:
        path = self._create_file("test.jpg", 42)
        cache = DirCache()
        self.assertEqual(cache.stat_size(path), 42)

    def test_stat_size_raises_for_missing_file(self) -> None:
        cache = DirCache()
        path = os.path.join(self._tmpdir, "nonexistent.jpg")
        with self.assertRaises(FileNotFoundError):
            cache.stat_size(path)

    def test_exists_returns_true_for_file(self) -> None:
        path = self._create_file("test.jpg", 0)
        cache = DirCache()
        self.assertTrue(cache.exists(path))

    def test_exists_returns_false_for_missing(self) -> None:
        cache = DirCache()
        path = os.path.join(self._tmpdir, "nonexistent.jpg")
        self.assertFalse(cache.exists(path))

    def test_notify_new_file_makes_file_visible(self) -> None:
        cache = DirCache()
        path = os.path.join(self._tmpdir, "new_download.jpg")
        # File doesn't exist yet on disk, but we notify the cache
        self.assertFalse(cache.isfile(path))
        cache.notify_new_file(path, 5000)
        self.assertTrue(cache.isfile(path))
        self.assertEqual(cache.stat_size(path), 5000)

    def test_notify_updates_existing_entry(self) -> None:
        path = self._create_file("test.jpg", 100)
        cache = DirCache()
        self.assertEqual(cache.stat_size(path), 100)
        # EXIF injection changes size
        cache.notify_new_file(path, 188)
        self.assertEqual(cache.stat_size(path), 188)

    def test_getsize_is_alias_for_stat_size(self) -> None:
        path = self._create_file("test.jpg", 777)
        cache = DirCache()
        self.assertEqual(cache.getsize(path), cache.stat_size(path))

    def test_scan_caches_results(self) -> None:
        """Second call to isfile should use cached result, not re-scan."""
        path = self._create_file("test.jpg", 50)
        cache = DirCache()
        self.assertTrue(cache.isfile(path))
        # Delete the file on disk -- cache should still report it
        os.unlink(path)
        self.assertTrue(cache.isfile(path))

    def test_scan_nonexistent_directory_logs_warning(self) -> None:
        cache = DirCache()
        path = os.path.join("/nonexistent/dir/that/does/not/exist", "file.jpg")
        # Should not raise, but return False
        self.assertFalse(cache.isfile(path))

    def test_multiple_files_in_same_directory(self) -> None:
        self._create_file("a.jpg", 100)
        self._create_file("b.jpg", 200)
        self._create_file("c.mov", 300)
        cache = DirCache()
        self.assertTrue(cache.isfile(os.path.join(self._tmpdir, "a.jpg")))
        self.assertTrue(cache.isfile(os.path.join(self._tmpdir, "b.jpg")))
        self.assertTrue(cache.isfile(os.path.join(self._tmpdir, "c.mov")))
        self.assertEqual(cache.stat_size(os.path.join(self._tmpdir, "a.jpg")), 100)
        self.assertEqual(cache.stat_size(os.path.join(self._tmpdir, "b.jpg")), 200)
        self.assertEqual(cache.stat_size(os.path.join(self._tmpdir, "c.mov")), 300)
