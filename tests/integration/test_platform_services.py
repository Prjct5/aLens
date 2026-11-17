from __future__ import annotations

import os
from datetime import date

import pytest

from autolens.common.config import Settings
from autolens.common.db import Database
from autolens.common.logging import get_logger
from autolens.common.stage import RunContext, StageResult
from autolens.common.time import utcnow
from autolens.pipelines.runlog import record_pipeline_run
from autolens.warehouse.migrate import migrate

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def db() -> Database:
    url = os.environ.get("DATABASE_URL")
    try:
        if not url:
            raise RuntimeError("DATABASE_URL not set")
        database = Database(url)
    except Exception as exc:
        if os.environ.get("REQUIRE_SERVICES") == "1":
            raise
        pytest.skip(f"PostgreSQL not available: {exc}")
    yield database
    database.close()


def test_migrations_are_idempotent(db: Database) -> None:
    url = os.environ["DATABASE_URL"]
    migrate(url)
    assert migrate(url) == []
    assert db.table_exists("ops.pipeline_run")


def test_record_pipeline_run_roundtrip(db: Database) -> None:
    migrate(os.environ["DATABASE_URL"])
    ctx = RunContext(
        settings=Settings(_env_file=None), log=get_logger("it"), db=db, run_id="it-run"
    )
    result = StageResult("scrape", date(2026, 1, 15), 3, 2, ["w"])
    record_pipeline_run(ctx, "scrape", date(2026, 1, 15), result, "success", utcnow())
    row = db.fetch_one(
        "SELECT stage, status, rows_out, warnings FROM ops.pipeline_run WHERE run_id = %s",
        ("it-run",),
    )
    assert row is not None
    assert row["status"] == "success" and row["rows_out"] == 2 and row["warnings"] == ["w"]
