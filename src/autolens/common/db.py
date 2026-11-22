from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from autolens.common.config import Settings, get_settings


def _identifier(qualified: str) -> sql.Identifier:
    return sql.Identifier(*qualified.split("."))


# Logical (SQLite-style) table names used by the M1 stages -> schema-qualified names
# and primary keys (used to emulate INSERT OR REPLACE with an upsert).
LOGICAL_TABLES: dict[str, tuple[str, tuple[str, ...]]] = {
    "staging_parsed_listing": (
        "staging.parsed_listing",
        ("source", "source_listing_id", "scrape_date"),
    ),
    "staging_normalized_listing": (
        "staging.normalized_listing",
        ("source", "source_listing_id", "scrape_date"),
    ),
    "staging_image_fetch": ("staging.image_fetch", ("listing_key", "position")),
    "ops_scrape_run": ("ops.scrape_run", ("run_id", "source")),
    "core_vehicle_link": ("core.vehicle_link", ("listing_key", "link_run_id")),
    "core_vehicle_id_merge": ("core.vehicle_id_merge", ("old_id", "new_id")),
}
_LOGICAL_RE = re.compile(r"\b(" + "|".join(LOGICAL_TABLES) + r")\b")
INSERT_CHUNK = 5000


def translate_sql(query: str, has_params: bool) -> str:
    """Map logical table names to schema-qualified ones and `?` to `%s`."""
    query = _LOGICAL_RE.sub(lambda m: LOGICAL_TABLES[m.group(1)][0], query)
    if has_params:
        query = query.replace("%", "%%").replace("?", "%s")
    return query


def _adapt_value(value: Any) -> Any:
    if type(value).__module__ == "numpy" and hasattr(value, "item"):
        return value.item()
    return value


def _plain_row(row: dict[str, Any]) -> dict[str, Any]:
    """Return values the way SQLite did: ISO strings, floats, JSON text."""
    out: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, datetime | date):
            out[key] = value.isoformat()
        elif isinstance(value, Decimal):
            out[key] = float(value)
        elif isinstance(value, dict | list):
            out[key] = json.dumps(value)
        else:
            out[key] = value
    return out


class Database:
    def __init__(self, url: str, min_size: int = 1, max_size: int = 5) -> None:
        self._pool = ConnectionPool(
            url,
            min_size=min_size,
            max_size=max_size,
            kwargs={"row_factory": dict_row, "options": "-c timezone=UTC"},
            open=False,
        )
        self._pool.open(wait=True, timeout=30)

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> Database:
        return cls((settings or get_settings()).database_url)

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection[Any]]:
        with self._pool.connection() as conn:
            yield conn

    @contextmanager
    def transaction(self) -> Iterator[psycopg.Connection[Any]]:
        with self._pool.connection() as conn, conn.transaction():
            yield conn

    def execute(self, query: str, params: Sequence[Any] | None = None) -> int:
        params = params or None
        with self.transaction() as conn:
            return conn.execute(translate_sql(query, params is not None), params).rowcount

    def fetch_all(self, query: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
        with self.connection() as conn:
            return list(conn.execute(query, params).fetchall())

    def fetch_one(self, query: str, params: Sequence[Any] | None = None) -> dict[str, Any] | None:
        with self.connection() as conn:
            return conn.execute(query, params).fetchone()

    def bulk_insert(
        self,
        table: str,
        columns: Sequence[str],
        rows: Sequence[Sequence[Any]],
        on_conflict: str | None = None,
    ) -> int:
        if not rows:
            return 0
        stmt = sql.SQL("INSERT INTO {table} ({cols}) VALUES ({vals})").format(
            table=_identifier(table),
            cols=sql.SQL(", ").join(sql.Identifier(c) for c in columns),
            vals=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        )
        if on_conflict:
            stmt = stmt + sql.SQL(" ") + sql.SQL(on_conflict)
        with self.transaction() as conn, conn.cursor() as cur:
            cur.executemany(stmt, rows)
            return len(rows)

    def query(self, query: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        """SQLite-compatible read: `?` placeholders, logical names, plain Python values."""
        bound = tuple(_adapt_value(p) for p in params) or None
        with self.connection() as conn:
            rows = conn.execute(translate_sql(query, bound is not None), bound).fetchall()
        return [_plain_row(r) for r in rows]

    def count(self, table: str, where: str = "", params: Sequence[Any] = ()) -> int:
        stmt = f"SELECT COUNT(*) AS n FROM {table}"
        if where:
            stmt += f" WHERE {where}"
        return int(self.query(stmt, params)[0]["n"])

    def insert_many(self, table: str, rows: Iterable[dict[str, Any]]) -> int:
        """Upsert dict rows (emulates INSERT OR REPLACE) in one transaction."""
        batch = list(rows)
        if not batch:
            return 0
        qualified, pk = LOGICAL_TABLES.get(table, (table, ()))
        columns = list(batch[0].keys())
        stmt = sql.SQL("INSERT INTO {table} ({cols}) VALUES ({vals})").format(
            table=_identifier(qualified),
            cols=sql.SQL(", ").join(sql.Identifier(c) for c in columns),
            vals=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        )
        if pk:
            updates = [c for c in columns if c not in pk]
            conflict = sql.SQL(" ON CONFLICT ({pk}) ").format(
                pk=sql.SQL(", ").join(sql.Identifier(c) for c in pk)
            )
            if updates:
                assign = sql.SQL(", ").join(
                    sql.SQL("{c} = EXCLUDED.{c}").format(c=sql.Identifier(c)) for c in updates
                )
                stmt = stmt + conflict + sql.SQL("DO UPDATE SET ") + assign
            else:
                stmt = stmt + conflict + sql.SQL("DO NOTHING")
        values = [[_adapt_value(r[c]) for c in columns] for r in batch]
        with self.transaction() as conn, conn.cursor() as cur:
            for start in range(0, len(values), INSERT_CHUNK):
                cur.executemany(stmt, values[start : start + INSERT_CHUNK])
        return len(batch)

    def table_exists(self, qualified: str) -> bool:
        row = self.fetch_one("SELECT to_regclass(%s) AS oid", (qualified,))
        return bool(row and row["oid"] is not None)

    def close(self) -> None:
        self._pool.close()
