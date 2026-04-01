"""Unit tests for icloudpd.manifest — SQLite asset manifest."""

import json
import os
import shutil
import sqlite3
import tempfile
from unittest import TestCase

from icloudpd.manifest import SCHEMA_VERSION, ManifestDB


class TestManifestDB(TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()
        self._db = ManifestDB(self._tmpdir)
        self._db.open()

    def tearDown(self) -> None:
        self._db.close()
        shutil.rmtree(self._tmpdir)

    def test_db_created_at_expected_path(self) -> None:
        self.assertTrue(os.path.isfile(os.path.join(self._tmpdir, ".icloudpd.db")))

    def test_schema_version_set(self) -> None:
        conn = sqlite3.connect(os.path.join(self._tmpdir, ".icloudpd.db"))
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        conn.close()
        self.assertEqual(version, SCHEMA_VERSION)

    def test_empty_db_has_zero_count(self) -> None:
        self.assertEqual(self._db.count(), 0)

    def test_upsert_and_lookup_all_fields(self) -> None:
        self._db.upsert(
            asset_id="ABC123",
            zone_id="PrimarySync",
            local_path="2024-01/IMG_0001.JPG",
            version_size=1884695,
            version_checksum="chk123",
            change_tag="49lb",
            item_type="public.jpeg",
            filename="IMG_0001.JPG",
            asset_date="2024-01-15T10:30:00+11:00",
            added_date="2024-01-15T12:00:00+11:00",
            is_favorite=1,
            is_hidden=0,
            is_deleted=0,
            original_width=4032,
            original_height=3024,
            duration=None,
            orientation=6,
            title="Beach sunset",
            description="A lovely sunset at the beach",
            keywords=json.dumps(["sunset", "beach", "travel"]),
            gps_latitude=51.500729,
            gps_longitude=-0.124625,
            gps_altitude=12.5,
        )
        row = self._db.lookup("ABC123", "PrimarySync", "2024-01/IMG_0001.JPG")
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row.asset_id, "ABC123")
        self.assertEqual(row.version_size, 1884695)
        self.assertEqual(row.item_type, "public.jpeg")
        self.assertEqual(row.filename, "IMG_0001.JPG")
        self.assertEqual(row.is_favorite, 1)
        self.assertEqual(row.original_width, 4032)
        self.assertEqual(row.original_height, 3024)
        self.assertEqual(row.orientation, 6)
        self.assertEqual(row.title, "Beach sunset")
        self.assertEqual(row.description, "A lovely sunset at the beach")
        assert row.keywords is not None
        self.assertEqual(json.loads(row.keywords), ["sunset", "beach", "travel"])
        assert row.gps_latitude is not None
        assert row.gps_longitude is not None
        assert row.gps_altitude is not None
        self.assertAlmostEqual(row.gps_latitude, 51.500729, places=5)
        self.assertAlmostEqual(row.gps_longitude, -0.124625, places=4)
        self.assertAlmostEqual(row.gps_altitude, 12.5, places=1)
        self.assertIsNotNone(row.downloaded_at)
        self.assertIsNotNone(row.last_updated_at)

    def test_lookup_missing_returns_none(self) -> None:
        self.assertIsNone(self._db.lookup("MISSING", "z", "x.jpg"))

    def test_upsert_updates_existing_row(self) -> None:
        self._db.upsert("ABC", "z", "a.jpg", 100, title="old")
        self._db.upsert("ABC", "z", "a.jpg", 200, title="new")
        self.assertEqual(self._db.count(), 1)
        row = self._db.lookup("ABC", "z", "a.jpg")
        assert row is not None
        self.assertEqual(row.version_size, 200)
        self.assertEqual(row.title, "new")

    def test_last_updated_at_changes_on_update(self) -> None:
        self._db.upsert("ABC", "z", "a.jpg", 100)
        row1 = self._db.lookup("ABC", "z", "a.jpg")
        assert row1 is not None
        import time
        time.sleep(0.01)
        self._db.upsert("ABC", "z", "a.jpg", 100, title="updated")
        row2 = self._db.lookup("ABC", "z", "a.jpg")
        assert row2 is not None
        self.assertEqual(row1.downloaded_at, row1.last_updated_at)
        # last_updated_at should change, downloaded_at should not
        self.assertNotEqual(row1.last_updated_at, row2.last_updated_at)

    def test_same_asset_different_paths(self) -> None:
        """Live photo: one asset produces JPEG + MOV."""
        self._db.upsert("LIVE1", "z", "2024-01/IMG_0001.JPG", 1000)
        self._db.upsert("LIVE1", "z", "2024-01/IMG_0001.MOV", 5000)
        self.assertEqual(self._db.count(), 2)

    def test_same_asset_different_zones(self) -> None:
        self._db.upsert("DUP1", "PrimarySync", "a.jpg", 100)
        self._db.upsert("DUP1", "SharedSync-XYZ", "a.jpg", 100)
        self.assertEqual(self._db.count(), 2)

    def test_lookup_by_path(self) -> None:
        self._db.upsert("ABC", "z", "2024-01/IMG.JPG", 1000)
        row = self._db.lookup_by_path("2024-01/IMG.JPG")
        assert row is not None
        self.assertEqual(row.asset_id, "ABC")

    def test_remove(self) -> None:
        self._db.upsert("ABC", "z", "a.jpg", 100)
        self._db.remove("ABC", "z", "a.jpg")
        self.assertEqual(self._db.count(), 0)

    def test_remove_by_path(self) -> None:
        self._db.upsert("ABC", "z", "a.jpg", 100)
        self._db.upsert("DEF", "z", "a.jpg", 200)
        self._db.remove_by_path("a.jpg")
        self.assertEqual(self._db.count(), 0)

    def test_context_manager(self) -> None:
        tmpdir2 = tempfile.mkdtemp()
        try:
            with ManifestDB(tmpdir2) as db:
                db.upsert("X", "z", "x.jpg", 1)
                self.assertEqual(db.count(), 1)
            self.assertTrue(os.path.isfile(os.path.join(tmpdir2, ".icloudpd.db")))
        finally:
            shutil.rmtree(tmpdir2)

    def test_persistence_across_opens(self) -> None:
        self._db.upsert("PERSIST", "z", "p.jpg", 42, title="hello")
        self._db.close()
        self._db.open()
        row = self._db.lookup("PERSIST", "z", "p.jpg")
        assert row is not None
        self.assertEqual(row.version_size, 42)
        self.assertEqual(row.title, "hello")

    def test_nullable_metadata_fields(self) -> None:
        self._db.upsert("ABC", "z", "a.jpg", 100)
        row = self._db.lookup("ABC", "z", "a.jpg")
        assert row is not None
        self.assertIsNone(row.version_checksum)
        self.assertIsNone(row.title)
        self.assertIsNone(row.gps_latitude)
        self.assertIsNone(row.duration)
        self.assertEqual(row.is_favorite, 0)

    def test_keywords_stored_as_json(self) -> None:
        kw = ["sunset", "beach"]
        self._db.upsert("ABC", "z", "a.jpg", 100, keywords=json.dumps(kw))
        row = self._db.lookup("ABC", "z", "a.jpg")
        assert row is not None
        assert row.keywords is not None
        self.assertEqual(json.loads(row.keywords), kw)


class TestManifestMigration(TestCase):
    def test_migrate_from_v0_schema(self) -> None:
        """A pre-versioned DB (7 columns) should be migrated to the full schema."""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = os.path.join(tmpdir, ".icloudpd.db")
            # Create a v0 DB with only the original 7 columns
            conn = sqlite3.connect(db_path)
            conn.executescript("""\
                CREATE TABLE manifest (
                    asset_id TEXT NOT NULL,
                    zone_id TEXT NOT NULL DEFAULT '',
                    local_path TEXT NOT NULL,
                    version_size INTEGER NOT NULL,
                    version_checksum TEXT,
                    change_tag TEXT,
                    downloaded_at TEXT NOT NULL,
                    PRIMARY KEY (asset_id, zone_id, local_path)
                );
            """)
            conn.execute(
                "INSERT INTO manifest VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("OLD1", "z", "old.jpg", 999, None, "t1", "2026-01-01T00:00:00+00:00"),
            )
            conn.commit()
            conn.close()

            # Open with ManifestDB — should migrate
            db = ManifestDB(tmpdir)
            db.open()

            # Verify version was set
            version = db._db.execute("PRAGMA user_version").fetchone()[0]
            self.assertEqual(version, SCHEMA_VERSION)

            # Verify index was created during migration
            indexes = db._db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='manifest'"
            ).fetchall()
            index_names = [row[0] for row in indexes]
            self.assertIn("idx_manifest_path", index_names)

            # Verify old row survived with new columns as defaults
            row = db.lookup("OLD1", "z", "old.jpg")
            assert row is not None
            self.assertEqual(row.asset_id, "OLD1")
            self.assertEqual(row.version_size, 999)
            self.assertEqual(row.last_updated_at, "")  # default from migration
            self.assertIsNone(row.title)
            self.assertEqual(row.is_favorite, 0)

            # Verify new columns are writable
            db.upsert("NEW1", "z", "new.jpg", 500, title="test", is_favorite=1)
            row2 = db.lookup("NEW1", "z", "new.jpg")
            assert row2 is not None
            self.assertEqual(row2.title, "test")
            self.assertEqual(row2.is_favorite, 1)

            db.close()
        finally:
            shutil.rmtree(tmpdir)


_V1_SCHEMA = """\
CREATE TABLE manifest (
    asset_id TEXT NOT NULL,
    zone_id TEXT NOT NULL DEFAULT '',
    local_path TEXT NOT NULL,
    version_size INTEGER NOT NULL,
    version_checksum TEXT,
    change_tag TEXT,
    downloaded_at TEXT NOT NULL,
    last_updated_at TEXT NOT NULL,
    item_type TEXT,
    filename TEXT,
    asset_date TEXT,
    added_date TEXT,
    is_favorite INTEGER DEFAULT 0,
    is_hidden INTEGER DEFAULT 0,
    is_deleted INTEGER DEFAULT 0,
    original_width INTEGER,
    original_height INTEGER,
    duration INTEGER,
    orientation INTEGER,
    title TEXT,
    description TEXT,
    keywords TEXT,
    gps_latitude REAL,
    gps_longitude REAL,
    gps_altitude REAL,
    PRIMARY KEY (asset_id, zone_id, local_path)
);
CREATE INDEX IF NOT EXISTS idx_manifest_path ON manifest(local_path);
"""

_V2_NEW_COLUMNS = [
    "gps_speed",
    "gps_timestamp",
    "timezone_offset",
    "asset_subtype",
    "hdr_type",
    "burst_flags",
    "burst_flags_ext",
    "burst_id",
    "original_orientation",
    "raw_fields",
]


class TestManifestV2Migration(TestCase):
    """Tests for v1 -> v2 schema migration (10 new columns)."""

    def _create_v1_db(self, tmpdir: str) -> str:
        db_path = os.path.join(tmpdir, ".icloudpd.db")
        conn = sqlite3.connect(db_path)
        conn.executescript(_V1_SCHEMA)
        conn.execute("PRAGMA user_version=1")
        conn.commit()
        conn.close()
        return db_path

    def test_v1_to_v2_migration(self) -> None:
        """Opening a v1 DB should migrate it to v2, adding all 10 new columns."""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = self._create_v1_db(tmpdir)

            # Seed a row before migration
            conn = sqlite3.connect(db_path)
            conn.execute(
                "INSERT INTO manifest "
                "(asset_id, zone_id, local_path, version_size, downloaded_at, "
                "last_updated_at, title) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("V1ROW", "z", "photo.jpg", 512, "2025-01-01T00:00:00+00:00",
                 "2025-01-01T00:00:00+00:00", "old title"),
            )
            conn.commit()
            conn.close()

            db = ManifestDB(tmpdir)
            db.open()

            # PRAGMA user_version should now be 2
            version = db._db.execute("PRAGMA user_version").fetchone()[0]
            self.assertEqual(version, 4)

            # All 10 new columns must exist
            cols = {
                row[1]
                for row in db._db.execute("PRAGMA table_info(manifest)").fetchall()
            }
            for col in _V2_NEW_COLUMNS:
                self.assertIn(col, cols, f"Column '{col}' missing after migration")

            # Existing data preserved
            row = db.lookup("V1ROW", "z", "resOriginal")
            assert row is not None
            self.assertEqual(row.asset_id, "V1ROW")
            self.assertEqual(row.version_size, 512)
            self.assertEqual(row.title, "old title")

            db.close()
        finally:
            shutil.rmtree(tmpdir)

    def test_fresh_db_has_v2_columns(self) -> None:
        """A brand-new ManifestDB should contain all 35 columns."""
        tmpdir = tempfile.mkdtemp()
        try:
            db = ManifestDB(tmpdir)
            db.open()

            cols = [
                row[1]
                for row in db._db.execute("PRAGMA table_info(manifest)").fetchall()
            ]
            self.assertEqual(len(cols), 37)
            for col in _V2_NEW_COLUMNS:
                self.assertIn(col, cols)

            db.close()
        finally:
            shutil.rmtree(tmpdir)

    def test_upsert_with_new_columns(self) -> None:
        """All v2 fields should round-trip through upsert/lookup."""
        tmpdir = tempfile.mkdtemp()
        try:
            db = ManifestDB(tmpdir)
            db.open()

            raw = json.dumps({"customKey": 42})
            db.upsert(
                asset_id="V2FULL",
                zone_id="z",
                local_path="v2.jpg",
                version_size=1024,
                gps_speed=12.5,
                gps_timestamp="2025-06-01T08:30:00Z",
                timezone_offset=39600,
                asset_subtype=2,
                hdr_type=1,
                burst_flags=7,
                burst_flags_ext=15,
                burst_id="B-001",
                original_orientation=3,
                raw_fields=raw,
            )

            row = db.lookup("V2FULL", "z", "resOriginal")
            assert row is not None
            assert row.gps_speed is not None
            self.assertAlmostEqual(row.gps_speed, 12.5, places=1)
            self.assertEqual(row.gps_timestamp, "2025-06-01T08:30:00Z")
            self.assertEqual(row.timezone_offset, 39600)
            self.assertEqual(row.asset_subtype, 2)
            self.assertEqual(row.hdr_type, 1)
            self.assertEqual(row.burst_flags, 7)
            self.assertEqual(row.burst_flags_ext, 15)
            self.assertEqual(row.burst_id, "B-001")
            self.assertEqual(row.original_orientation, 3)
            assert row.raw_fields is not None
            self.assertEqual(json.loads(row.raw_fields), {"customKey": 42})

            db.close()
        finally:
            shutil.rmtree(tmpdir)

    def test_new_columns_default_to_none(self) -> None:
        """Inserting without v2 fields should leave them as None."""
        tmpdir = tempfile.mkdtemp()
        try:
            db = ManifestDB(tmpdir)
            db.open()

            db.upsert("MINIMAL", "z", "min.jpg", 100)

            row = db.lookup("MINIMAL", "z", "resOriginal")
            assert row is not None
            self.assertIsNone(row.gps_speed)
            self.assertIsNone(row.gps_timestamp)
            self.assertIsNone(row.timezone_offset)
            self.assertIsNone(row.asset_subtype)
            self.assertIsNone(row.hdr_type)
            self.assertIsNone(row.burst_flags)
            self.assertIsNone(row.burst_flags_ext)
            self.assertIsNone(row.burst_id)
            self.assertIsNone(row.original_orientation)
            self.assertIsNone(row.raw_fields)

            db.close()
        finally:
            shutil.rmtree(tmpdir)

    def test_v1_migration_preserves_existing_gps(self) -> None:
        """GPS data from v1 rows must survive migration; new GPS columns are None."""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = self._create_v1_db(tmpdir)

            conn = sqlite3.connect(db_path)
            conn.execute(
                "INSERT INTO manifest "
                "(asset_id, zone_id, local_path, version_size, downloaded_at, "
                "last_updated_at, gps_latitude, gps_longitude, gps_altitude) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("GPS1", "z", "geo.jpg", 256, "2025-01-01T00:00:00+00:00",
                 "2025-01-01T00:00:00+00:00", -33.7, 151.2, 10.0),
            )
            conn.commit()
            conn.close()

            db = ManifestDB(tmpdir)
            db.open()

            row = db.lookup("GPS1", "z", "resOriginal")
            assert row is not None
            assert row.gps_latitude is not None
            assert row.gps_longitude is not None
            assert row.gps_altitude is not None
            self.assertAlmostEqual(row.gps_latitude, -33.7, places=1)
            self.assertAlmostEqual(row.gps_longitude, 151.2, places=1)
            self.assertAlmostEqual(row.gps_altitude, 10.0, places=1)
            self.assertIsNone(row.gps_speed)
            self.assertIsNone(row.gps_timestamp)

            db.close()
        finally:
            shutil.rmtree(tmpdir)


class TestManifestDedup(TestCase):
    """Tests for multi-asset dedup support in manifest."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()
        self._db = ManifestDB(self._tmpdir)
        self._db.open()

    def tearDown(self) -> None:
        self._db.close()
        shutil.rmtree(self._tmpdir)

    def test_lookup_by_path_returns_earliest_downloaded(self) -> None:
        # Insert two assets with same path
        self._db.upsert(asset_id="asset_B", zone_id="zone", local_path="photo.jpg", version_size=100)
        self._db.upsert(asset_id="asset_A", zone_id="zone", local_path="photo.jpg", version_size=200)
        result = self._db.lookup_by_path("photo.jpg")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.asset_id, "asset_B")  # First inserted = earliest downloaded

    def test_count_by_path_multiple_assets(self) -> None:
        self._db.upsert(asset_id="a1", zone_id="z", local_path="p.jpg", version_size=1)
        self._db.upsert(asset_id="a2", zone_id="z", local_path="p.jpg", version_size=2)
        self.assertEqual(self._db.count_by_path("p.jpg"), 2)

    def test_count_by_path_no_match(self) -> None:
        self.assertEqual(self._db.count_by_path("missing.jpg"), 0)

    def test_update_path_basic(self) -> None:
        self._db.upsert(asset_id="a1", zone_id="z", local_path="old.jpg", version_size=100)
        self._db.update_path("a1", "z", "old.jpg", "new.jpg")
        self.assertIsNone(self._db.lookup("a1", "z", "old.jpg"))
        result = self._db.lookup("a1", "z", "new.jpg")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.version_size, 100)

    def test_update_path_nonexistent(self) -> None:
        self._db.update_path("missing", "z", "old.jpg", "new.jpg")
        # No error, no effect
        self.assertIsNone(self._db.lookup_by_path("new.jpg"))

    def test_lookup_by_path_detects_collision(self) -> None:
        """lookup_by_path returns the earliest owner, enabling collision detection."""
        self._db.upsert(asset_id="a1", zone_id="z", local_path="shared.jpg", version_size=1)
        self._db.upsert(asset_id="a2", zone_id="z", local_path="shared.jpg", version_size=2)
        owner = self._db.lookup_by_path("shared.jpg")
        self.assertIsNotNone(owner)
        self.assertEqual(owner.asset_id, "a1")  # earliest download wins

class TestManifestJournalMode(TestCase):
    """Tests for DELETE journal mode (replacing WAL)."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()
        self._db = ManifestDB(self._tmpdir)
        self._db.open()

    def tearDown(self) -> None:
        self._db.close()
        shutil.rmtree(self._tmpdir)

    def test_journal_mode_is_delete(self) -> None:
        mode = self._db._db.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(mode, "delete")

    def test_synchronous_is_full(self) -> None:
        sync = self._db._db.execute("PRAGMA synchronous").fetchone()[0]
        self.assertEqual(sync, 2)  # 2 = FULL

    def test_no_wal_shm_files_created(self) -> None:
        db_path = os.path.join(self._tmpdir, ".icloudpd.db")
        self._db.upsert(
            asset_id="A1", zone_id="z",
            local_path="test.jpg", version_size=100,
        )
        self._db.flush()
        self.assertFalse(os.path.exists(db_path + "-wal"))
        self.assertFalse(os.path.exists(db_path + "-shm"))

    def test_wal_db_converted_to_delete_on_open(self) -> None:
        """Opening an existing WAL-mode DB converts it to DELETE."""
        self._db.close()
        conn = sqlite3.connect(os.path.join(self._tmpdir, ".icloudpd.db"))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.close()
        self._db.open()
        mode = self._db._db.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(mode, "delete")

    def test_data_survives_wal_to_delete_conversion(self) -> None:
        self._db.upsert(
            asset_id="X", zone_id="z",
            local_path="x.jpg", version_size=100, title="survive",
        )
        self._db.close()
        conn = sqlite3.connect(os.path.join(self._tmpdir, ".icloudpd.db"))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.close()
        self._db.open()
        row = self._db.lookup("X", "z")
        assert row is not None
        self.assertEqual(row.title, "survive")
