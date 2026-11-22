"""Run the Splink comparison and append it to the RQ1 metrics JSON."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from autolens.common.local_backend import ObjectStore, Warehouse
from autolens.common.logging import get_logger
from autolens.common.stage import RunContext
from autolens.linkage.run import _load_listings
from autolens.linkage.splink_compare import run_splink_comparison
from autolens.scrapers.settings import M1Settings as Settings


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    settings = Settings.from_env()
    db_path = root / "outputs" / "autolens.db"
    ctx = RunContext(
        settings=settings,
        db=Warehouse(db_path),
        store=ObjectStore(root),
        log=get_logger("splink"),
    )
    listings = _load_listings(ctx, date.fromisoformat(settings.run_date))
    labels = pd.read_csv(root / "outputs" / "labelled_pairs.csv")
    result = run_splink_comparison(listings, labels, root / "outputs" / "splink_metrics.json")
    print(json.dumps(result, indent=2)[:2000])

    metrics_path = root / "outputs" / "linkage_metrics.json"
    metrics = json.loads(metrics_path.read_text())
    metrics["splink"] = result
    metrics_path.write_text(json.dumps(metrics, indent=2))
    ctx.db.close()


if __name__ == "__main__":
    main()
