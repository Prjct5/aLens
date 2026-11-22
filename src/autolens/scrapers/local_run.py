from __future__ import annotations

import argparse
import json
import time
from datetime import date
from typing import Any

from autolens.common.local_backend import ObjectStore, Warehouse
from autolens.common.logging import configure_logging, get_logger
from autolens.common.stage import RunContext, Stage
from autolens.linkage.run import run_linkage
from autolens.scrapers.images import run_fetch_images
from autolens.scrapers.run import run_normalize, run_scrape
from autolens.scrapers.settings import M1Settings

M1_STAGE_FUNCS: tuple[tuple[str, Stage], ...] = (
    ("scrape", run_scrape),
    ("normalize", run_normalize),
    ("fetch_images", run_fetch_images),
    ("linkage", run_linkage),
)
M1_STAGE_NAMES = tuple(name for name, _ in M1_STAGE_FUNCS)


def build_local_context(settings: M1Settings) -> RunContext:
    """SQLite + filesystem context: no services needed (offline / laptop mode)."""
    settings.ensure_dirs()
    configure_logging(settings.log_level)
    return RunContext(
        settings=settings,  # type: ignore[arg-type]
        db=Warehouse(settings.db_path),
        store=ObjectStore(settings.root),
        log=get_logger("m1", settings.log_level),
    )


def run_stages(
    run_date: date,
    ctx: RunContext,
    stages: tuple[tuple[str, Stage], ...] = M1_STAGE_FUNCS,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, fn in stages:
        started = time.perf_counter()
        result = fn(run_date, ctx)
        out.append(
            {
                "stage": name,
                "seconds": round(time.perf_counter() - started, 2),
                "rows_in": result.rows_in,
                "rows_out": result.rows_out,
                "warnings": result.warnings,
                "metrics": result.metrics,
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Run M1 stages locally (SQLite + filesystem)")
    parser.add_argument("--run-date", default=None, help="YYYY-MM-DD (default: RUN_DATE env)")
    args = parser.parse_args()
    settings = M1Settings.from_env()
    run_date = date.fromisoformat(args.run_date or settings.run_date)
    ctx = build_local_context(settings)
    print(json.dumps(run_stages(run_date, ctx), indent=2, default=str))


if __name__ == "__main__":
    main()
