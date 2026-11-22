"""Local storage layer.

The handbook specifies PostgreSQL (warehouse) + MinIO (object store). This
implementation uses SQLite and a filesystem object store with *identical table
and key names*, so every stage obeys the same contracts and can be swapped to
the production services by changing this module only.
"""

from __future__ import annotations

import gzip
import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from autolens.common.store import RawPayloadConflict

# ---------------------------------------------------------------------------
# Warehouse (SQLite)
# ---------------------------------------------------------------------------

DDL = """
CREATE TABLE IF NOT EXISTS staging_parsed_listing (
    source TEXT NOT NULL,
    source_listing_id TEXT NOT NULL,
    scrape_date TEXT NOT NULL,
    scraped_at TEXT NOT NULL,
    run_id TEXT NOT NULL,
    url TEXT,
    make_raw TEXT,
    model_raw TEXT,
    year_raw TEXT,
    km_raw TEXT,
    price_raw TEXT,
    transmission_raw TEXT,
    fuel_raw TEXT,
    body_raw TEXT,
    city_raw TEXT,
    condition_raw TEXT,
    color_raw TEXT,
    payment_raw TEXT,
    description_raw TEXT,
    year INTEGER,
    mileage_km REAL,
    price_egp REAL,
    currency TEXT,
    payload_key TEXT,
    PRIMARY KEY (source, source_listing_id, scrape_date)
);
CREATE TABLE IF NOT EXISTS staging_normalized_listing (
    source TEXT NOT NULL,
    source_listing_id TEXT NOT NULL,
    scrape_date TEXT NOT NULL,
    model_id INTEGER,
    make_canon TEXT,
    model_canon TEXT,
    trim_canon TEXT,
    year INTEGER,
    mileage_km REAL,
    price_egp REAL,
    governorate_code TEXT,
    transmission TEXT,
    fuel_type TEXT,
    body_type TEXT,
    condition TEXT,
    color TEXT,
    payment_option TEXT,
    dq_flags TEXT,
    mapping_confidence REAL,
    PRIMARY KEY (source, source_listing_id, scrape_date)
);
CREATE TABLE IF NOT EXISTS staging_image_fetch (
    listing_key TEXT NOT NULL,
    position INTEGER NOT NULL,
    image_id TEXT NOT NULL,
    source_url TEXT,
    fetched_at TEXT,
    width INTEGER,
    height INTEGER,
    phash TEXT,
    status TEXT,
    quarantine_key TEXT,
    PRIMARY KEY (listing_key, position)
);
CREATE TABLE IF NOT EXISTS ops_scrape_run (
    run_id TEXT NOT NULL,
    source TEXT NOT NULL,
    run_date TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    n_index_pages INTEGER DEFAULT 0,
    n_listings_seen INTEGER DEFAULT 0,
    n_new INTEGER DEFAULT 0,
    n_gone INTEGER DEFAULT 0,
    n_error INTEGER DEFAULT 0,
    n_parse_fail INTEGER DEFAULT 0,
    http_429_count INTEGER DEFAULT 0,
    degraded INTEGER DEFAULT 0,
    PRIMARY KEY (run_id, source)
);
CREATE TABLE IF NOT EXISTS core_vehicle_link (
    listing_key TEXT NOT NULL,
    vehicle_id INTEGER NOT NULL,
    link_run_id TEXT NOT NULL,
    cluster_size INTEGER NOT NULL,
    min_edge_weight REAL NOT NULL,
    max_edge_weight REAL NOT NULL,
    method TEXT NOT NULL,
    PRIMARY KEY (listing_key, link_run_id)
);
CREATE TABLE IF NOT EXISTS core_vehicle_id_merge (
    old_id INTEGER NOT NULL,
    new_id INTEGER NOT NULL,
    merged_at TEXT NOT NULL,
    PRIMARY KEY (old_id, new_id)
);
CREATE INDEX IF NOT EXISTS idx_parsed_run ON staging_parsed_listing(run_id);
CREATE INDEX IF NOT EXISTS idx_norm_run ON staging_normalized_listing(scrape_date);
CREATE INDEX IF NOT EXISTS idx_link_run ON core_vehicle_link(link_run_id);
"""


class Warehouse:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(DDL)
        self.conn.commit()

    def insert_many(self, table: str, rows: Iterable[dict[str, Any]]) -> int:
        rows = list(rows)
        if not rows:
            return 0
        cols = list(rows[0].keys())
        placeholders = ",".join("?" for _ in cols)
        sql = f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
        self.conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
        self.conn.commit()
        return len(rows)

    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        cur = self.conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def count(self, table: str, where: str = "", params: tuple = ()) -> int:
        sql = f"SELECT COUNT(*) AS n FROM {table}"
        if where:
            sql += f" WHERE {where}"
        return int(self.conn.execute(sql, params).fetchone()["n"])

    def execute(self, sql: str, params: tuple = ()) -> int:
        """Run a write statement and commit; returns affected row count."""
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur.rowcount

    def close(self) -> None:
        self.conn.close()


# ---------------------------------------------------------------------------
# Object store (filesystem stand-in for MinIO buckets)
# ---------------------------------------------------------------------------


class ObjectStore:
    """Buckets: raw, quarantine, images, exports (16.2)."""

    def __init__(self, root: Path):
        self.root = Path(root)
        for bucket in ("raw", "quarantine", "images", "exports"):
            (self.root / bucket).mkdir(parents=True, exist_ok=True)

    def raw_key(self, source: str, run_date: str, source_listing_id: str) -> str:
        return f"raw/{source}/{run_date}/{source_listing_id}.json.gz"

    def put_raw(
        self, source: str, run_date: str, source_listing_id: str, payload: dict[str, Any]
    ) -> str:
        key = self.raw_key(source, run_date, source_listing_id)
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        # mtime=0 keeps the compressed bytes byte-for-byte reproducible, so a
        # rerun produces the same SHA-256 for the same logical payload.
        blob = gzip.compress(data, mtime=0)
        if path.exists():
            existing = gzip.decompress(path.read_bytes())
            if existing != data:
                raise RawPayloadConflict(
                    f"raw payload {key} already exists with different content; "
                    "immutable raw objects must never be overwritten"
                )
            return key
        path.write_bytes(blob)
        return key

    def get_raw(self, key: str) -> dict[str, Any]:
        data = gzip.decompress((self.root / key).read_bytes())
        return json.loads(data)

    def raw_keys(self, source: str | None = None, run_date: str | None = None) -> list[str]:
        """Logical keys (always forward slashes, also on Windows)."""
        keys = sorted(
            p.relative_to(self.root).as_posix() for p in (self.root / "raw").glob("**/*.json.gz")
        )
        return [
            k
            for k in keys
            if (source is None or f"/{source}/" in f"/{k}")
            and (run_date is None or f"/{run_date}/" in f"/{k}")
        ]
