"""Golden end-to-end test (handbook 15.3): all stages on committed fixtures.

Runs entirely offline with a temporary SQLite DB and object store, and asserts
idempotency (running twice yields identical row counts).
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import date
from pathlib import Path

from autolens.common.local_backend import ObjectStore, Warehouse
from autolens.common.logging import get_logger
from autolens.common.stage import RunContext
from autolens.linkage.run import run_linkage
from autolens.scrapers.images import run_fetch_images
from autolens.scrapers.run import run_normalize, run_scrape
from autolens.scrapers.settings import M1Settings as Settings

RUN_DATE = date(2026, 1, 15)
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "scrapers" / "listings_sample.csv"


def _context(tmp_path: Path) -> RunContext:
    (tmp_path / "data").mkdir(exist_ok=True)
    shutil.copy(FIXTURE, tmp_path / "data" / "Egypt_Used_Cars_clean.csv")
    settings = Settings(
        root=tmp_path,
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "outputs",
        raw_dir=tmp_path / "raw",
        quarantine_dir=tmp_path / "quarantine",
        db_path=tmp_path / "outputs" / "test.db",
        run_date=str(RUN_DATE),
        min_interval_s=1.0,
        concurrency=2,
        user_agent="AutoLens-Egypt/0.1 (test)",
        log_level="ERROR",
    )
    settings.ensure_dirs()
    return RunContext(
        settings=settings,  # type: ignore[arg-type]
        db=Warehouse(settings.db_path),
        store=ObjectStore(tmp_path),
        log=get_logger("golden", "ERROR"),
    )


TABLES = (
    "staging_parsed_listing",
    "staging_normalized_listing",
    "staging_image_fetch",
    "ops_scrape_run",
    "core_vehicle_link",
    "core_vehicle_id_merge",
)


def _snapshot(ctx: RunContext) -> dict:
    return {t: ctx.db.query(f"SELECT * FROM {t}") for t in TABLES}


def _raw_hashes(root: Path) -> dict:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((root / "raw").rglob("*.json.gz"))
    }


def test_golden_pipeline(tmp_path):
    ctx = _context(tmp_path)
    results = []
    for stage in (run_scrape, run_normalize, run_fetch_images):
        results.append(stage(RUN_DATE, ctx))
    results.append(run_linkage(RUN_DATE, ctx))

    assert [r.stage for r in results] == ["scrape", "normalize", "fetch_images", "linkage"]
    assert results[0].rows_out == 60
    assert results[1].rows_out == 60
    assert ctx.db.count("staging_parsed_listing") == 60
    assert ctx.db.count("staging_normalized_listing") == 60
    assert ctx.db.count("core_vehicle_link") == 60
    assert ctx.db.count("ops_scrape_run") == 3

    first_run_id = results[0].metrics["run_id"]
    assert first_run_id.startswith("archive-"), "archive replay run_id must be deterministic"
    before = _snapshot(ctx)
    raw_before = _raw_hashes(tmp_path)

    second_scrape = run_scrape(RUN_DATE, ctx)
    assert second_scrape.metrics["run_id"] == first_run_id
    run_normalize(RUN_DATE, ctx)
    run_linkage(RUN_DATE, ctx)

    after = _snapshot(ctx)
    raw_after = _raw_hashes(tmp_path)
    assert before == after, "every table must be byte-for-byte stable across reruns"
    assert raw_before == raw_after and raw_before, "raw object hashes must be immutable"
    ctx.db.close()
