"""SQLite asset manifest for identity-based sync tracking.

The manifest DB is the single source of truth for everything icloudpd knows
about your library. It stores identity (which iCloud asset maps to which local
file), sync state (has this asset changed?), and all metadata the API provides.

XMP sidecars are an export format generated from the same API data. The DB and
XMP are independent — XMP generation does not read from the DB.

The manifest lives at {download_dir}/.icloudpd.db and travels with the library.
"""

import contextlib
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 4

_FRESH_SCHEMA = """\
CREATE TABLE IF NOT EXISTS manifest (
    asset_id TEXT NOT NULL,
    zone_id TEXT NOT NULL DEFAULT '',
    asset_resource TEXT NOT NULL DEFAULT 'resOriginal',
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
    gps_speed REAL,
    gps_timestamp TEXT,
    timezone_offset INTEGER,
    asset_subtype INTEGER,
    hdr_type INTEGER,
    burst_flags INTEGER,
    burst_flags_ext INTEGER,
    burst_id TEXT,
    original_orientation INTEGER,
    raw_fields TEXT,
    file_mtime REAL,
    PRIMARY KEY (asset_id, zone_id, asset_resource)
);
CREATE INDEX IF NOT EXISTS idx_manifest_path ON manifest(local_path);
"""

# Columns added between schema versions, for migration from older DBs.
# Each entry: (version_introduced, ALTER TABLE statement)
_MIGRATIONS: list[tuple[int, str]] = [
    (2, "ALTER TABLE manifest ADD COLUMN gps_speed REAL"),
    (2, "ALTER TABLE manifest ADD COLUMN gps_timestamp TEXT"),
    (2, "ALTER TABLE manifest ADD COLUMN timezone_offset INTEGER"),
    (2, "ALTER TABLE manifest ADD COLUMN asset_subtype INTEGER"),
    (2, "ALTER TABLE manifest ADD COLUMN hdr_type INTEGER"),
    (2, "ALTER TABLE manifest ADD COLUMN burst_flags INTEGER"),
    (2, "ALTER TABLE manifest ADD COLUMN burst_flags_ext INTEGER"),
    (2, "ALTER TABLE manifest ADD COLUMN burst_id TEXT"),
    (2, "ALTER TABLE manifest ADD COLUMN original_orientation INTEGER"),
    (2, "ALTER TABLE manifest ADD COLUMN raw_fields TEXT"),
    (3, "ALTER TABLE manifest ADD COLUMN asset_resource TEXT NOT NULL DEFAULT 'resOriginal'"),
    (4, "ALTER TABLE manifest ADD COLUMN file_mtime REAL"),
]


@dataclass(frozen=True)
class ManifestRow:
    """A single manifest entry."""

    asset_id: str
    zone_id: str
    asset_resource: str
    local_path: str
    version_size: int
    version_checksum: str | None
    change_tag: str | None
    downloaded_at: str
    last_updated_at: str
    item_type: str | None
    filename: str | None
    asset_date: str | None
    added_date: str | None
    is_favorite: int
    is_hidden: int
    is_deleted: int
    original_width: int | None
    original_height: int | None
    duration: int | None
    orientation: int | None
    title: str | None
    description: str | None
    keywords: str | None
    gps_latitude: float | None
    gps_longitude: float | None
    gps_altitude: float | None
    gps_speed: float | None
    gps_timestamp: str | None
    timezone_offset: int | None
    asset_subtype: int | None
    hdr_type: int | None
    burst_flags: int | None
    burst_flags_ext: int | None
    burst_id: str | None
    original_orientation: int | None
    raw_fields: str | None
    file_mtime: float | None


_ALL_COLUMNS = (
    "asset_id, zone_id, asset_resource, local_path, version_size, version_checksum, "
    "change_tag, downloaded_at, last_updated_at, item_type, filename, "
    "asset_date, added_date, is_favorite, is_hidden, is_deleted, "
    "original_width, original_height, duration, orientation, "
    "title, description, keywords, gps_latitude, gps_longitude, gps_altitude, "
    "gps_speed, gps_timestamp, timezone_offset, asset_subtype, hdr_type, "
    "burst_flags, burst_flags_ext, burst_id, original_orientation, raw_fields, "
    "file_mtime"
)


class ManifestDB:
    """SQLite-backed asset manifest for tracking downloaded files."""

    _MAX_WRITE_RETRIES = 3
    _RETRY_BASE_DELAY = 0.1

    def __init__(self, download_dir: str) -> None:
        self._db_path = os.path.join(download_dir, ".icloudpd.db")
        self._conn: sqlite3.Connection | None = None
        self._dirty = False
        self._pending_count = 0
        self._flush_interval = 500
        self.zone_id: str = ""

    @property
    def _db(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("ManifestDB is not open")
        return self._conn

    def open(self) -> None:
        """Open the manifest DB, creating schema or migrating if needed."""
        self._conn = sqlite3.connect(self._db_path, timeout=10)
        self._conn.execute("PRAGMA journal_mode=DELETE")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._dirty = False
        self._pending_count = 0

        current_version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if current_version == 0:
            # Fresh DB or pre-versioned DB — check if table exists
            tables = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='manifest'"
            ).fetchone()
            if tables is None:
                # Brand new DB
                self._conn.executescript(_FRESH_SCHEMA)
            else:
                # Pre-versioned DB (has table but no user_version) — migrate
                self._migrate_from_v0()
            self._conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            self._conn.commit()
        elif current_version < SCHEMA_VERSION:
            self._run_migrations(current_version)

    def _migrate_from_v0(self) -> None:
        """Migrate from the original 7-column schema to the full schema."""
        existing = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(manifest)").fetchall()  # type: ignore[union-attr]
        }
        new_columns = [
            ("last_updated_at", "TEXT NOT NULL DEFAULT ''"),
            ("item_type", "TEXT"),
            ("filename", "TEXT"),
            ("asset_date", "TEXT"),
            ("added_date", "TEXT"),
            ("is_favorite", "INTEGER DEFAULT 0"),
            ("is_hidden", "INTEGER DEFAULT 0"),
            ("is_deleted", "INTEGER DEFAULT 0"),
            ("original_width", "INTEGER"),
            ("original_height", "INTEGER"),
            ("duration", "INTEGER"),
            ("orientation", "INTEGER"),
            ("title", "TEXT"),
            ("description", "TEXT"),
            ("keywords", "TEXT"),
            ("gps_latitude", "REAL"),
            ("gps_longitude", "REAL"),
            ("gps_altitude", "REAL"),
            ("gps_speed", "REAL"),
            ("gps_timestamp", "TEXT"),
            ("timezone_offset", "INTEGER"),
            ("asset_subtype", "INTEGER"),
            ("hdr_type", "INTEGER"),
            ("burst_flags", "INTEGER"),
            ("burst_flags_ext", "INTEGER"),
            ("burst_id", "TEXT"),
            ("original_orientation", "INTEGER"),
            ("raw_fields", "TEXT"),
            ("asset_resource", "TEXT NOT NULL DEFAULT 'resOriginal'"),
            ("file_mtime", "REAL"),
        ]
        for col_name, col_def in new_columns:
            if col_name not in existing:
                self._conn.execute(f"ALTER TABLE manifest ADD COLUMN {col_name} {col_def}")  # type: ignore[union-attr]
        logger.info("Migrated manifest DB from v0 to v%d (%d columns added)",
                     SCHEMA_VERSION, sum(1 for c, _ in new_columns if c not in existing))
        self._rebuild_pk()
        self._conn.execute(  # type: ignore[union-attr]
            "CREATE INDEX IF NOT EXISTS idx_manifest_path ON manifest(local_path)"
        )

    def _run_migrations(self, from_version: int) -> None:
        """Run incremental migrations from from_version to SCHEMA_VERSION."""
        for version, sql in _MIGRATIONS:
            if version > from_version:
                with contextlib.suppress(sqlite3.OperationalError):
                    self._conn.execute(sql)  # type: ignore[union-attr]
        if from_version < 3:
            self._rebuild_pk()
        self._conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")  # type: ignore[union-attr]
        self._conn.commit()  # type: ignore[union-attr]

    def _rebuild_pk(self) -> None:
        """Rebuild the manifest table with the correct PK (asset_id, zone_id, asset_resource)."""
        conn = self._conn
        assert conn is not None
        conn.execute("ALTER TABLE manifest RENAME TO manifest_old")
        conn.executescript(_FRESH_SCHEMA)
        # Copy data, keeping only one row per (asset_id, zone_id, asset_resource)
        cols = _ALL_COLUMNS
        conn.execute(
            f"INSERT OR IGNORE INTO manifest ({cols}) "
            f"SELECT {cols} FROM manifest_old"
        )
        conn.execute("DROP TABLE manifest_old")
        conn.commit()

    def close(self) -> None:
        """Close the manifest DB, committing any pending writes."""
        if self._conn:
            if self._dirty:
                try:
                    self._conn.commit()
                except sqlite3.OperationalError as e:
                    if "locked" in str(e):
                        logger.warning("Manifest commit on close failed: %s", e)
                    else:
                        raise
                self._dirty = False
                self._pending_count = 0
            self._conn.close()
            self._conn = None

    def flush(self) -> None:
        """Commit pending writes without closing."""
        if self._conn and self._dirty:
            try:
                self._conn.commit()
                self._dirty = False
                self._pending_count = 0
            except sqlite3.OperationalError as e:
                if "locked" in str(e):
                    logger.warning("Manifest flush failed: %s", e)
                else:
                    raise

    def __enter__(self) -> "ManifestDB":
        self.open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def lookup(self, asset_id: str, zone_id: str, asset_resource: str) -> ManifestRow | None:
        """Look up a manifest entry by identity."""
        row = self._db.execute(
            f"SELECT {_ALL_COLUMNS} FROM manifest "
            "WHERE asset_id = ? AND zone_id = ? AND asset_resource = ?",
            (asset_id, zone_id, asset_resource),
        ).fetchone()
        if row is None:
            return None
        return ManifestRow(*row)

    def lookup_by_path(self, local_path: str) -> ManifestRow | None:
        """Look up the earliest-downloaded manifest entry for a local path."""
        row = self._db.execute(
            f"SELECT {_ALL_COLUMNS} FROM manifest "
            "WHERE local_path = ? ORDER BY downloaded_at ASC LIMIT 1",
            (local_path,),
        ).fetchone()
        if row is None:
            return None
        return ManifestRow(*row)

    def upsert(
        self,
        asset_id: str,
        zone_id: str,
        local_path: str,
        version_size: int,
        asset_resource: str = "resOriginal",
        version_checksum: str | None = None,
        change_tag: str | None = None,
        item_type: str | None = None,
        filename: str | None = None,
        asset_date: str | None = None,
        added_date: str | None = None,
        is_favorite: int = 0,
        is_hidden: int = 0,
        is_deleted: int = 0,
        original_width: int | None = None,
        original_height: int | None = None,
        duration: int | None = None,
        orientation: int | None = None,
        title: str | None = None,
        description: str | None = None,
        keywords: str | None = None,
        gps_latitude: float | None = None,
        gps_longitude: float | None = None,
        gps_altitude: float | None = None,
        gps_speed: float | None = None,
        gps_timestamp: str | None = None,
        timezone_offset: int | None = None,
        asset_subtype: int | None = None,
        hdr_type: int | None = None,
        burst_flags: int | None = None,
        burst_flags_ext: int | None = None,
        burst_id: str | None = None,
        original_orientation: int | None = None,
        raw_fields: str | None = None,
    ) -> None:
        """Insert or update a manifest entry. Auto-flushes every 500 writes."""
        now = datetime.now(tz=timezone.utc).isoformat()
        params = (
            asset_id, zone_id, asset_resource, local_path, version_size, version_checksum,
            change_tag, now, now, item_type, filename,
            asset_date, added_date, is_favorite, is_hidden, is_deleted,
            original_width, original_height, duration, orientation,
            title, description, keywords, gps_latitude, gps_longitude, gps_altitude,
            gps_speed, gps_timestamp, timezone_offset, asset_subtype, hdr_type,
            burst_flags, burst_flags_ext, burst_id, original_orientation, raw_fields,
            None,  # file_mtime: NULL for new rows, preserved on conflict
        )
        sql = (
            f"INSERT INTO manifest ({_ALL_COLUMNS}) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(asset_id, zone_id, asset_resource) DO UPDATE SET "
            "local_path=excluded.local_path, "
            "version_size=excluded.version_size, "
            "version_checksum=excluded.version_checksum, "
            "change_tag=excluded.change_tag, "
            "last_updated_at=excluded.last_updated_at, "
            "item_type=excluded.item_type, "
            "filename=excluded.filename, "
            "asset_date=excluded.asset_date, "
            "added_date=excluded.added_date, "
            "is_favorite=excluded.is_favorite, "
            "is_hidden=excluded.is_hidden, "
            "is_deleted=excluded.is_deleted, "
            "original_width=excluded.original_width, "
            "original_height=excluded.original_height, "
            "duration=excluded.duration, "
            "orientation=excluded.orientation, "
            "title=excluded.title, "
            "description=excluded.description, "
            "keywords=excluded.keywords, "
            "gps_latitude=excluded.gps_latitude, "
            "gps_longitude=excluded.gps_longitude, "
            "gps_altitude=excluded.gps_altitude, "
            "gps_speed=excluded.gps_speed, "
            "gps_timestamp=excluded.gps_timestamp, "
            "timezone_offset=excluded.timezone_offset, "
            "asset_subtype=excluded.asset_subtype, "
            "hdr_type=excluded.hdr_type, "
            "burst_flags=excluded.burst_flags, "
            "burst_flags_ext=excluded.burst_flags_ext, "
            "burst_id=excluded.burst_id, "
            "original_orientation=excluded.original_orientation, "
            "raw_fields=excluded.raw_fields"
            # file_mtime deliberately NOT updated — only set via update_file_mtime()
        )
        for attempt in range(self._MAX_WRITE_RETRIES):
            try:
                self._db.execute(sql, params)
                self._dirty = True
                self._pending_count += 1
                if self._pending_count >= self._flush_interval:
                    self.flush()
                return
            except sqlite3.OperationalError as e:
                if "locked" in str(e) and attempt < self._MAX_WRITE_RETRIES - 1:
                    logger.debug(
                        "Manifest write retry %d for %s: %s",
                        attempt + 1, local_path, e,
                    )
                    time.sleep(self._RETRY_BASE_DELAY * (attempt + 1))
                else:
                    logger.warning("Manifest write failed for %s: %s", local_path, e)
                    return
            except sqlite3.Error as e:
                logger.warning("Manifest write failed for %s: %s", local_path, e)
                return

    def update_path(self, asset_id: str, zone_id: str, asset_resource: str, new_path: str) -> None:
        """Update local_path for an existing manifest entry."""
        try:
            self._db.execute(
                "UPDATE manifest SET local_path = ?, last_updated_at = ? "
                "WHERE asset_id = ? AND zone_id = ? AND asset_resource = ?",
                (new_path, datetime.now(tz=timezone.utc).isoformat(),
                 asset_id, zone_id, asset_resource),
            )
            self._dirty = True
            self._pending_count += 1
        except sqlite3.Error as e:
            logger.warning(
                "Manifest path update failed for %s -> %s: %s",
                asset_resource, new_path, e,
            )

    def update_file_mtime(
        self, asset_id: str, zone_id: str, asset_resource: str, mtime: float
    ) -> None:
        """Record file mtime after successful metadata write."""
        try:
            self._db.execute(
                "UPDATE manifest SET file_mtime = ? "
                "WHERE asset_id = ? AND zone_id = ? AND asset_resource = ?",
                (mtime, asset_id, zone_id, asset_resource),
            )
            self._dirty = True
            self._pending_count += 1
        except sqlite3.Error as e:
            logger.warning("Manifest mtime update failed: %s", e)

    def count_by_path(self, local_path: str) -> int:
        """Count how many manifest entries reference a given local path."""
        row = self._db.execute(
            "SELECT COUNT(*) FROM manifest WHERE local_path = ?",
            (local_path,),
        ).fetchone()
        return row[0] if row else 0

    def remove(self, asset_id: str, zone_id: str, asset_resource: str) -> None:
        """Remove a manifest entry."""
        self._db.execute(
            "DELETE FROM manifest WHERE asset_id = ? AND zone_id = ? AND asset_resource = ?",
            (asset_id, zone_id, asset_resource),
        )
        self._dirty = True

    def remove_by_path(self, local_path: str) -> None:
        """Remove all manifest entries for a local path (used by autodelete)."""
        self._db.execute(
            "DELETE FROM manifest WHERE local_path = ?",
            (local_path,),
        )
        self._dirty = True

    def count(self) -> int:
        """Return the total number of manifest entries."""
        row = self._db.execute("SELECT COUNT(*) FROM manifest").fetchone()
        return row[0] if row else 0

    def find_orphaned(self, seen_asset_ids: set[str]) -> list[ManifestRow]:
        """Return manifest rows whose asset_id is not in the seen set."""
        all_rows = self._db.execute(
            "SELECT * FROM manifest"
        ).fetchall()
        col_names = [desc[0] for desc in self._db.execute(
            "SELECT * FROM manifest LIMIT 0"
        ).description or []]
        orphans: list[ManifestRow] = []
        for row in all_rows:
            row_dict = dict(zip(col_names, row, strict=False))
            if row_dict["asset_id"] not in seen_asset_ids:
                orphans.append(ManifestRow(**row_dict))
        return orphans
