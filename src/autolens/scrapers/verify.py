from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd

from autolens.common.privacy import contains_contact_info
from autolens.common.stage import RunContext

NORMALIZED_COLUMNS = (
    "condition",
    "color",
    "payment_option",
    "make_canon",
    "model_canon",
    "year",
    "mileage_km",
    "price_egp",
    "transmission",
    "fuel_type",
    "body_type",
    "governorate_code",
)


def table_counts(db: Any, run_date: date) -> dict[str, int]:
    """Row counts scoped to this run date (image_fetch and merges are not date-keyed)."""
    rd = str(run_date)
    return {
        "staging_parsed_listing": db.count("staging_parsed_listing", "scrape_date=?", (rd,)),
        "staging_normalized_listing": db.count(
            "staging_normalized_listing", "scrape_date=?", (rd,)
        ),
        "staging_image_fetch": db.count("staging_image_fetch"),
        "ops_scrape_run": db.count("ops_scrape_run", "run_date=?", (rd,)),
        "core_vehicle_link": db.count("core_vehicle_link", "link_run_id=?", (f"link-{run_date}",)),
        "core_vehicle_id_merge": db.count("core_vehicle_id_merge"),
    }


def _scan_archive_for_contacts(data_dir: Path) -> dict[str, Any]:
    """Count cells with phone-like or e-mail text per column (counts and shapes only)."""
    path = data_dir / "Egypt_Used_Cars_clean.csv"
    if not path.exists():
        return {"file_found": False}
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    by_column: dict[str, int] = {}
    shapes: dict[str, Counter[str]] = {}
    rows_hit: set[int] = set()
    for col in (c for c in df.columns if c not in {"url", "listing_id"}):
        for idx, value in df[col].items():
            if len(value) >= 7 and contains_contact_info(value):
                by_column[col] = by_column.get(col, 0) + 1
                shape = re.sub(r"[A-Za-z]", "a", re.sub(r"\d", "9", value))[:24]
                shapes.setdefault(col, Counter())[shape] += 1
                rows_hit.add(int(idx))  # type: ignore[call-overload]
    return {
        "file_found": True,
        "rows": len(df),
        "columns": list(df.columns),
        "rows_with_contact_like_text": len(rows_hit),
        "cells_by_column": by_column,
        "top_shapes_by_column": {c: dict(v.most_common(3)) for c, v in shapes.items()},
        "has_description_column": "description" in df.columns,
    }


def build_report(
    ctx: RunContext,
    run_date: date,
    stage_results: list[dict[str, Any]],
    data_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    db = ctx.db
    rd = str(run_date)
    report: dict[str, Any] = {"run_date": rd, "stages": stage_results}

    report["table_rows"] = table_counts(db, run_date)

    parsed = pd.DataFrame(
        db.query(
            "SELECT source, source_listing_id, url, description_raw "
            "FROM staging_parsed_listing WHERE scrape_date=?",
            (rd,),
        )
    )
    prov: dict[str, Any] = {}
    if not parsed.empty:
        parsed["host"] = parsed["url"].map(lambda u: urlparse(u or "").netloc.lower())
        parsed["id_shape"] = parsed["source_listing_id"].map(
            lambda v: "digits" if re.fullmatch(r"\d+", str(v)) else f"prefix:{str(v)[:1]}"
        )
        for source, grp in parsed.groupby("source"):
            prov[str(source)] = {
                "rows": len(grp),
                "url_hosts": dict(Counter(grp["host"]).most_common(5)),
                "id_shapes": dict(Counter(grp["id_shape"]).most_common(5)),
            }
        report["description_rows_with_contact_info"] = int(
            parsed["description_raw"].map(contains_contact_info).sum()
        )
    report["source_provenance"] = prov

    norm = pd.DataFrame(
        db.query("SELECT * FROM staging_normalized_listing WHERE scrape_date=?", (rd,))
    )
    if not norm.empty:
        report["normalized_null_share"] = {
            c: round(float(norm[c].isna().mean()), 4) for c in NORMALIZED_COLUMNS if c in norm
        }
        flags: Counter[str] = Counter()
        for raw in norm["dq_flags"]:
            parsed_flags = json.loads(raw) if isinstance(raw, str) else (raw or {})
            flags.update(k for k, v in parsed_flags.items() if v)
        report["dq_flag_counts"] = dict(flags)
        for col in ("condition", "payment_option", "fuel_type", "body_type"):
            if col in norm:
                report[f"{col}_counts"] = {
                    str(k): int(v) for k, v in norm[col].fillna("(null)").value_counts().items()
                }
        report["mapping_confidence_mean"] = round(float(norm["mapping_confidence"].mean()), 4)

    links = pd.DataFrame(
        db.query(
            "SELECT listing_key, vehicle_id FROM core_vehicle_link WHERE link_run_id=?",
            (f"link-{run_date}",),
        )
    )
    if not links.empty:
        sizes = links.groupby("vehicle_id").size()
        links["source"] = links["listing_key"].str.split(":").str[0]
        n_sources = links.groupby("vehicle_id")["source"].nunique()
        report["clusters"] = {
            "n_listings": len(links),
            "n_vehicles": int(sizes.size),
            "size_distribution": {
                int(k): int(v) for k, v in sizes.value_counts().sort_index().items()
            },
            "max_size": int(sizes.max()),
            "vehicles_spanning_multiple_sources": int((n_sources > 1).sum()),
            "vehicles_with_multiple_listings": int((sizes > 1).sum()),
        }

    out = output_dir
    metrics_path = Path(out) / "linkage_metrics.json"
    if metrics_path.exists():
        m = json.loads(metrics_path.read_text(encoding="utf-8"))
        keep = (
            "n_listings",
            "n_candidate_pairs",
            "candidate_pairs_truncated",
            "reduction_ratio",
            "listings_with_real_photo_hash",
            "n_labelled_pairs",
            "label_positive_rate",
            "fs_metrics",
            "fs_ci95",
            "supervised",
            "review_band_share",
            "evaluation_status",
            "human_ground_truth_available",
        )
        report["linkage_metrics"] = {k: m.get(k) for k in keep if k in m}
    unmapped = Path(out) / "unmapped_review.csv"
    if unmapped.exists():
        try:
            report["unmapped_review_rows"] = len(pd.read_csv(unmapped))
        except pd.errors.EmptyDataError:
            report["unmapped_review_rows"] = 0

    report["raw_objects_for_run_date"] = len(ctx.store.raw_keys(run_date=rd))
    report["archive_contact_scan"] = _scan_archive_for_contacts(data_dir)
    return report


def render_text(report: dict[str, Any]) -> str:
    lines = [f"M1 VERIFY REPORT   run_date={report['run_date']}", ""]
    lines.append("== stages")
    for s in report["stages"]:
        lines.append(f"{s['stage']:<14} {s['seconds']:>8}s  in={s['rows_in']} out={s['rows_out']}")
        for w in s["warnings"]:
            lines.append(f"    warning: {w}")
        if s["metrics"]:
            lines.append(f"    metrics: {json.dumps(s['metrics'], default=str)}")
    lines.append("")
    for key in (
        "table_rows",
        "raw_objects_for_run_date",
        "source_provenance",
        "normalized_null_share",
        "dq_flag_counts",
        "condition_counts",
        "payment_option_counts",
        "fuel_type_counts",
        "body_type_counts",
        "mapping_confidence_mean",
        "clusters",
        "linkage_metrics",
        "unmapped_review_rows",
        "description_rows_with_contact_info",
        "archive_contact_scan",
        "idempotency",
        "checks",
    ):
        if key in report:
            lines.append(f"== {key}")
            lines.append(json.dumps(report[key], indent=2, default=str))
            lines.append("")
    return "\n".join(lines)
