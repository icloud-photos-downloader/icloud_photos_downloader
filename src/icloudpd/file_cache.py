"""File cache module to track which files exist on disk for faster synchronization"""

import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from icloudpd.config import UserConfig


class FileCache:
    """SQLite-based cache to track files on disk"""

    def __init__(self, cache_db_path: str, logger: logging.Logger) -> None:
        self.cache_db_path = cache_db_path
        self.logger = logger
        self.lock = threading.Lock()
        self._ensure_cache_db()

    def _ensure_cache_db(self) -> None:
        """Create cache database if it doesn't exist"""
        with self.lock:
            conn = sqlite3.connect(self.cache_db_path, timeout=30.0)
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS file_cache (
                        file_path TEXT PRIMARY KEY,
                        file_size INTEGER,
                        mtime REAL,
                        last_verified REAL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_file_path ON file_cache(file_path)
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def file_exists(self, file_path: str, verify_disk: bool = False) -> bool:
        """Check if file exists in cache
        
        Args:
            file_path: Path to check
            verify_disk: If True, verify file exists on disk even if in cache.
                        If False (default), trust cache completely (faster).
                        Use True only for /syncall command.
        """
        with self.lock:
            conn = sqlite3.connect(self.cache_db_path, timeout=30.0)
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT file_path FROM file_cache WHERE file_path = ?",
                    (file_path,),
                )
                result = cursor.fetchone()
                if result:
                    # File is in cache
                    if verify_disk:
                        # Only verify on disk if explicitly requested (e.g., /syncall)
                        if os.path.isfile(file_path):
                            # Update last_verified timestamp
                            cursor.execute(
                                "UPDATE file_cache SET last_verified = ? WHERE file_path = ?",
                                (time.time(), file_path),
                            )
                            conn.commit()
                            return True
                        else:
                            # File was deleted, remove from cache
                            cursor.execute("DELETE FROM file_cache WHERE file_path = ?", (file_path,))
                            conn.commit()
                            return False
                    else:
                        # Trust cache completely (much faster) - cache is rebuilt every 24h
                        return True
                return False
            finally:
                conn.close()

    def add_file(self, file_path: str, file_size: Optional[int] = None) -> None:
        """Add file to cache"""
        try:
            if file_size is None and os.path.isfile(file_path):
                file_size = os.path.getsize(file_path)
            mtime = os.path.getmtime(file_path) if os.path.isfile(file_path) else time.time()

            with self.lock:
                conn = sqlite3.connect(self.cache_db_path, timeout=30.0)
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO file_cache (file_path, file_size, mtime, last_verified)
                        VALUES (?, ?, ?, ?)
                        """,
                        (file_path, file_size, mtime, time.time()),
                    )
                    conn.commit()
                finally:
                    conn.close()
        except Exception as e:
            self.logger.debug(f"Error adding file to cache: {e}")

    def remove_file(self, file_path: str) -> None:
        """Remove file from cache"""
        with self.lock:
            conn = sqlite3.connect(self.cache_db_path, timeout=30.0)
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM file_cache WHERE file_path = ?", (file_path,))
                conn.commit()
            finally:
                conn.close()

    def rebuild_cache(self, directory: str, user_config: UserConfig) -> None:
        """Rebuild cache by scanning disk directory"""
        self.logger.info("Rebuilding file cache by scanning disk...")
        start_time = time.time()
        file_count = 0

        directory_path = Path(directory)
        if not directory_path.exists():
            self.logger.warning(f"Directory {directory} does not exist, skipping cache rebuild")
            return

        # Clear existing cache for this directory
        with self.lock:
            conn = sqlite3.connect(self.cache_db_path, timeout=30.0)
            try:
                cursor = conn.cursor()
                # Only remove files from this directory
                cursor.execute(
                    "DELETE FROM file_cache WHERE file_path LIKE ?",
                    (f"{directory}%",),
                )
                conn.commit()
            finally:
                conn.close()

        # Scan directory and add files to cache
        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        if os.path.isfile(file_path):
                            self.add_file(file_path)
                            file_count += 1
                            if file_count % 1000 == 0:
                                self.logger.debug(f"Scanned {file_count} files...")
                    except Exception as e:
                        self.logger.debug(f"Error scanning file {file_path}: {e}")

            elapsed = time.time() - start_time
            self.logger.info(
                f"Cache rebuild completed: {file_count} files scanned in {elapsed:.2f} seconds"
            )
        except Exception as e:
            self.logger.error(f"Error rebuilding cache: {e}")

    def should_rebuild_cache(self, rebuild_interval_hours: int = 24) -> bool:
        """Check if cache should be rebuilt based on last rebuild time"""
        cache_dir = os.path.dirname(self.cache_db_path)
        rebuild_flag_file = os.path.join(cache_dir, ".cache_last_rebuild")

        if not os.path.exists(rebuild_flag_file):
            return True

        try:
            last_rebuild = os.path.getmtime(rebuild_flag_file)
            hours_since_rebuild = (time.time() - last_rebuild) / 3600
            return hours_since_rebuild >= rebuild_interval_hours
        except Exception:
            return True

    def mark_cache_rebuilt(self) -> None:
        """Mark cache as recently rebuilt"""
        cache_dir = os.path.dirname(self.cache_db_path)
        rebuild_flag_file = os.path.join(cache_dir, ".cache_last_rebuild")
        try:
            Path(rebuild_flag_file).touch()
        except Exception as e:
            self.logger.debug(f"Error marking cache as rebuilt: {e}")

    def get_cache_stats(self) -> dict:
        """Get cache statistics"""
        with self.lock:
            conn = sqlite3.connect(self.cache_db_path, timeout=30.0)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM file_cache")
                total_files = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM file_cache WHERE last_verified > ?",
                    (time.time() - 86400,),  # Last 24 hours
                )
                recently_verified = cursor.fetchone()[0]

                return {
                    "total_files": total_files,
                    "recently_verified": recently_verified,
                }
            finally:
                conn.close()

    def get_last_sync_date(self) -> Optional[float]:
        """Get the last sync date (timestamp) from cache metadata"""
        cache_dir = os.path.dirname(self.cache_db_path)
        sync_date_file = os.path.join(cache_dir, ".last_sync_date")
        
        if not os.path.exists(sync_date_file):
            return None
        
        try:
            with open(sync_date_file, 'r') as f:
                timestamp = float(f.read().strip())
                return timestamp
        except (ValueError, IOError):
            return None

    def set_last_sync_date(self, timestamp: float) -> None:
        """Set the last sync date (timestamp) in cache metadata"""
        cache_dir = os.path.dirname(self.cache_db_path)
        sync_date_file = os.path.join(cache_dir, ".last_sync_date")
        
        try:
            with open(sync_date_file, 'w') as f:
                f.write(str(timestamp))
        except IOError as e:
            self.logger.debug(f"Error saving last sync date: {e}")

    def get_all_cached_paths(self) -> set[str]:
        """Get all file paths from cache as a set for fast lookup
        
        Returns:
            Set of all file paths in cache
        """
        with self.lock:
            conn = sqlite3.connect(self.cache_db_path, timeout=30.0)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT file_path FROM file_cache")
                paths = {row[0] for row in cursor.fetchall()}
                return paths
            finally:
                conn.close()
