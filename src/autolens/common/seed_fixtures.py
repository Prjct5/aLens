from __future__ import annotations

import json
from pathlib import Path

import psycopg

from autolens.common.config import get_settings
from autolens.common.db import Database
from autolens.common.logging import configure_logging, get_logger

FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures"


def seed(fixtures_dir: Path = FIXTURES) -> dict[str, int]:
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("seed")
    db = Database.from_settings(settings)
    loaded: dict[str, int] = {}
    try:
        for path in sorted(fixtures_dir.glob("*.*.json")):
            table = path.name.removesuffix(".json")
            rows = json.loads(path.read_text(encoding="utf-8"))
            if not rows:
                continue
            columns = list(rows[0].keys())
            values = [
                [
                    json.dumps(v) if isinstance(v, dict | list) else v
                    for v in (r[c] for c in columns)
                ]
                for r in rows
            ]
            try:
                loaded[table] = db.bulk_insert(
                    table, columns, values, on_conflict="ON CONFLICT DO NOTHING"
                )
            except psycopg.errors.UndefinedTable:
                log.warning("table missing, skipped", table=table)
    finally:
        db.close()
    return loaded


if __name__ == "__main__":
    print(seed())
