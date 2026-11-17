from __future__ import annotations

import hashlib
import os
from pathlib import Path

import psycopg

from autolens.common.config import get_settings
from autolens.common.logging import configure_logging, get_logger

DEFAULT_DDL_DIR = Path(__file__).resolve().parents[3] / "sql" / "ddl"


def migrate(database_url: str | None = None, ddl_dir: Path | None = None) -> list[str]:
    url = database_url or get_settings().database_url
    directory = ddl_dir or Path(os.environ.get("DDL_DIR", DEFAULT_DDL_DIR))
    applied: list[str] = []
    with psycopg.connect(url) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS public.schema_migration ("
            "filename text PRIMARY KEY, checksum text NOT NULL, "
            "applied_at timestamptz NOT NULL DEFAULT now())"
        )
        conn.commit()
        done = {r[0] for r in conn.execute("SELECT filename FROM public.schema_migration")}
        for path in sorted(directory.glob("*.sql")):
            if path.name in done:
                continue
            text = path.read_text(encoding="utf-8")
            conn.execute(text.encode())
            conn.execute(
                "INSERT INTO public.schema_migration (filename, checksum) VALUES (%s, %s)",
                (path.name, hashlib.sha256(text.encode()).hexdigest()),
            )
            conn.commit()
            applied.append(path.name)
    return applied


def main() -> None:
    configure_logging(get_settings().log_level)
    log = get_logger("migrate")
    applied = migrate()
    log.info("migrations applied", applied=applied, count=len(applied))


if __name__ == "__main__":
    main()
