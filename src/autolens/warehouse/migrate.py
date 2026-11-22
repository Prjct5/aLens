from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

import psycopg

from autolens.common.config import get_settings
from autolens.common.logging import configure_logging, get_logger

DEFAULT_DDL_DIR = Path(__file__).resolve().parents[3] / "sql" / "ddl"
NAME_RE = re.compile(r"^V?(\d+)(?:__|_)")


class MigrationError(RuntimeError):
    pass


def migration_files(directory: Path) -> list[Path]:
    """`NNN_name.sql` and `VNNN__name.sql` are accepted, ordered by number then name."""
    files = []
    for path in directory.glob("*.sql"):
        if not NAME_RE.match(path.name):
            raise MigrationError(f"{path.name}: migration names must start with NNN_ or VNNN__")
        files.append(path)
    return sorted(files, key=lambda p: (int(NAME_RE.match(p.name).group(1)), p.name))  # type: ignore[union-attr]


def migrate(database_url: str | None = None, ddl_dir: Path | None = None) -> list[str]:
    url = database_url or get_settings().database_url
    directory = ddl_dir or Path(os.environ.get("DDL_DIR", DEFAULT_DDL_DIR))
    applied: list[str] = []
    with psycopg.connect(url) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS ops")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ops.schema_migrations ("
            "filename text PRIMARY KEY, version integer NOT NULL, checksum text NOT NULL, "
            "applied_at timestamptz NOT NULL DEFAULT now())"
        )
        conn.commit()
        done = dict(conn.execute("SELECT filename, checksum FROM ops.schema_migrations").fetchall())
        for path in migration_files(directory):
            text = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(text.encode()).hexdigest()
            if path.name in done:
                if done[path.name] != checksum:
                    raise MigrationError(
                        f"{path.name} was edited after it was applied; never edit an applied "
                        "migration, add a new one"
                    )
                continue
            conn.execute(text.encode())
            conn.execute(
                "INSERT INTO ops.schema_migrations (filename, version, checksum) "
                "VALUES (%s, %s, %s)",
                (path.name, int(NAME_RE.match(path.name).group(1)), checksum),  # type: ignore[union-attr]
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
