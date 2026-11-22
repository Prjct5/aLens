"""Repost detection + recall measurement (handbook R12, 8.4/R4).

Rule (documented in docs/report/RQ1.md): a listing that disappears from a source
and later reappears with the same canonical make/model/year/km band/price band is
merged into the same ``vehicle_id`` as its earlier observation. Recall is measured
only against a reviewed multi-day sample (handbook R12 acceptance criterion).

This module computes the metric when such observations exist. With a single
supplied archive it returns ``measurable=False`` rather than inventing reposts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from autolens.common.local_backend import Warehouse


def repost_rule_match(a: dict, b: dict, km_band: float = 0.10, price_band: float = 0.20) -> bool:
    """Documented repost rule: same car attributes within tolerance bands."""
    if a.get("source") == b.get("source") and a.get("source_listing_id") == b.get(
        "source_listing_id"
    ):
        return True  # identical listing id across days
    keys = ("make_canon", "model_canon", "year", "transmission", "fuel_type", "body_type")
    if any(a.get(k) != b.get(k) for k in keys):
        return False
    for field, band in (("mileage_km", km_band), ("price_egp", price_band)):
        x, y = a.get(field), b.get(field)
        if x is None or y is None:
            continue
        m = max(float(x), float(y))
        if m and abs(float(x) - float(y)) / m > band:
            return False
    return True


def measure_repost_recall(
    db: Warehouse, dates: list[str], output_dir: Path, reviewed: pd.DataFrame | None = None
) -> dict:
    """Measure repost recall against reviewed observations, or explain why not.

    ``reviewed`` columns: listing_key_a, listing_key_b, true_repost (0/1).
    Predicted repost = same vehicle_id in core_vehicle_link for the two keys.
    """
    dates = sorted(dates)
    runs = db.query(
        "SELECT DISTINCT scrape_date FROM staging_normalized_listing ORDER BY scrape_date"
    )
    available = [r["scrape_date"] for r in runs]
    distinct_days = len(set(available) & set(dates))
    if distinct_days < 2 or reviewed is None:
        return {
            "measurable": False,
            "reason": (
                "single-snapshot archive; no reviewed multi-day observations"
                if distinct_days < 2
                else "reviewed repost sample not supplied"
            ),
            "observed_days": available,
            "rule": "same make/model/year/transmission/fuel/body, km<=10%, price<=20%",
        }

    links = db.query("SELECT listing_key, vehicle_id FROM core_vehicle_link")
    vehicle = {r["listing_key"]: r["vehicle_id"] for r in links}
    truth = reviewed["true_repost"].astype(int).to_numpy()
    pred = (
        reviewed["listing_key_a"].map(vehicle) == reviewed["listing_key_b"].map(vehicle)
    ).to_numpy()
    tp = int(((pred) & (truth == 1)).sum())
    fp = int(((pred) & (truth == 0)).sum())
    fn = int(((~pred) & (truth == 1)).sum())
    recall = tp / (tp + fn) if (tp + fn) else None
    precision = tp / (tp + fp) if (tp + fp) else None
    result = {
        "measurable": True,
        "n_reviewed": int(len(reviewed)),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "recall": recall,
        "precision": precision,
        "rule": "same vehicle_id after FS+EM clustering across daily runs",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "repost_metrics.json").write_text(json.dumps(result, indent=2))
    return result
