from __future__ import annotations

import os
import shutil
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from autolens.api.main import create_app
from autolens.common.config import Settings
from autolens.common.db import Database
from autolens.common.stage import make_context
from autolens.common.store import ObjectStore
from autolens.common.time import utcnow
from autolens.pipelines.runlog import record_pipeline_run
from autolens.pipelines.stages import STAGES
from autolens.warehouse.migrate import migrate

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "scrapers" / "listings_sample.csv"
RUN_DATE = date(2030, 1, 15)
SAMPLE_REQUEST = {"make": "Toyota", "model": "Corolla", "year": 2018, "mileage_km": 90000}


def _require(exc: Exception) -> None:
    if os.environ.get("REQUIRE_SERVICES") == "1":
        raise exc
    pytest.skip(f"services not available: {exc}")


@pytest.fixture(scope="module")
def platform(tmp_path_factory: pytest.TempPathFactory):
    url = os.environ.get("DATABASE_URL")
    if not url or not os.environ.get("S3_ENDPOINT"):
        _require(RuntimeError("DATABASE_URL / S3_ENDPOINT not set"))
    root = tmp_path_factory.mktemp("m1root")
    (root / "data").mkdir()
    shutil.copy(FIXTURE, root / "data" / "Egypt_Used_Cars_clean.csv")
    os.environ["PROJECT_ROOT"] = str(root)
    os.environ["DATA_DIR"] = "data"
    settings = Settings(_env_file=None, environment="dev")
    try:
        migrate(settings.database_url)
        ctx = make_context(settings, models="stub", connect=True)
        ctx.store.ensure_buckets()
    except Exception as exc:  # noqa: BLE001
        _require(exc)
    yield ctx
    ctx.db.close()


def _clean(db: Database, store: ObjectStore) -> None:
    link_run = f"link-{RUN_DATE}"
    db.execute("DELETE FROM staging_parsed_listing WHERE scrape_date=?", (str(RUN_DATE),))
    db.execute("DELETE FROM staging_normalized_listing WHERE scrape_date=?", (str(RUN_DATE),))
    db.execute("DELETE FROM ops_scrape_run WHERE run_date=?", (str(RUN_DATE),))
    db.execute("DELETE FROM core_vehicle_link WHERE link_run_id=?", (link_run,))
    for key in store.raw_keys(run_date=str(RUN_DATE)):
        bucket, _, rest = key.partition("/")
        store.delete(bucket, rest)


def _counts(db: Database) -> dict[str, int]:
    return {
        "parsed": db.count("staging_parsed_listing", "scrape_date=?", (str(RUN_DATE),)),
        "normalized": db.count("staging_normalized_listing", "scrape_date=?", (str(RUN_DATE),)),
        "scrape_run": db.count("ops_scrape_run", "run_date=?", (str(RUN_DATE),)),
        "links": db.count("core_vehicle_link", "link_run_id=?", (f"link-{RUN_DATE}",)),
    }


def _run_all(ctx) -> None:
    for name, fn in STAGES:
        started = utcnow()
        result = fn(RUN_DATE, ctx)
        assert result.rows_out >= 0, name
        record_pipeline_run(ctx, name, RUN_DATE, result, "success", started)


def test_golden_pipeline_on_postgres_and_object_store(platform) -> None:
    ctx = platform
    _clean(ctx.db, ctx.store)
    n_fixture = 60

    _run_all(ctx)
    first = _counts(ctx.db)
    assert first["parsed"] == first["normalized"] == first["links"] > 0
    assert first["scrape_run"] == 3
    assert len(ctx.store.raw_keys(run_date=str(RUN_DATE))) == first["parsed"]
    assert first["parsed"] <= n_fixture

    row = ctx.db.fetch_one(
        "SELECT metrics FROM ops.pipeline_run WHERE stage = 'normalize' "
        "AND run_date = %s ORDER BY pipeline_run_id DESC LIMIT 1",
        (RUN_DATE,),
    )
    assert row is not None and "mapping_rate" in row["metrics"]

    current = ctx.db.fetch_all("SELECT count(*) AS n FROM core.vehicle_link_current")
    assert current[0]["n"] >= first["links"]

    client = TestClient(create_app(ctx))
    r = client.post("/price/estimate", json=SAMPLE_REQUEST)
    assert r.status_code == 200 and r.json()["lo"] < r.json()["hi"]

    _run_all(ctx)
    assert _counts(ctx.db) == first


def test_no_contact_details_in_staging(platform) -> None:
    from autolens.common.privacy import contains_contact_info

    rows = platform.db.query(
        "SELECT description_raw FROM staging_parsed_listing WHERE scrape_date=?",
        (str(RUN_DATE),),
    )
    assert not any(contains_contact_info(r["description_raw"]) for r in rows)
