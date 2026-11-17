from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from autolens.common.config import Settings, get_settings


def _identifier(qualified: str) -> sql.Identifier:
    return sql.Identifier(*qualified.split("."))


class Database:
    def __init__(self, url: str, min_size: int = 1, max_size: int = 5) -> None:
        self._pool = ConnectionPool(
            url, min_size=min_size, max_size=max_size, kwargs={"row_factory": dict_row}, open=False
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
        with self.transaction() as conn:
            return conn.execute(query, params).rowcount

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

    def table_exists(self, qualified: str) -> bool:
        row = self.fetch_one("SELECT to_regclass(%s) AS oid", (qualified,))
        return bool(row and row["oid"] is not None)

    def close(self) -> None:
        self._pool.close()
