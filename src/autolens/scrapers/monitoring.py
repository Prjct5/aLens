"""Scraper health + nightly alerts (handbook R13, pitfall 6, 15.2).

Operates on ``ops_scrape_run``. The nightly workflow (GitHub Actions) calls
``check_health`` and opens an issue when success < 90% or a parse-failure/null
rate jumps above the 7-day baseline. Archive replays are always ``degraded=1``,
so they never masquerade as a live daily sweep.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from autolens.common.local_backend import Warehouse

SUCCESS_FLOOR = 0.90
BASELINE_DAYS = 7
JUMP_FACTOR = 2.0


def daily_coverage(db: Warehouse, run_date: date) -> pd.DataFrame:
    """Per-source daily coverage against the previous observation (R4)."""
    rows = db.query(
        "SELECT source, run_date, n_listings_seen, n_new, n_gone, n_error, "
        "n_parse_fail, http_429_count, degraded FROM ops_scrape_run WHERE run_date<=? "
        "ORDER BY source, run_date",
        (str(run_date),),
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["prev_seen"] = df.groupby("source")["n_listings_seen"].shift(1)
    df["coverage"] = (df["n_listings_seen"] / df["prev_seen"]).where(df["prev_seen"] > 0)
    df["success"] = 1 - (df["n_error"] + df["n_parse_fail"]) / df["n_listings_seen"].where(
        df["n_listings_seen"] > 0
    )
    return df


def check_health(db: Warehouse, run_date: date, output_dir: Path) -> dict:
    """Return alerts for the nightly workflow; write them to outputs/alerts.json."""
    df = daily_coverage(db, run_date)
    alerts: list[dict] = []
    if df.empty:
        return {"run_date": str(run_date), "alerts": [], "status": "no_runs"}

    # Multiple replays of the same date exist; only the latest run per source counts.
    current = df[df["run_date"] == str(run_date)].drop_duplicates("source", keep="last")
    baseline = df[df["run_date"] < str(run_date)].tail(BASELINE_DAYS)

    for r in current.itertuples(index=False):
        if r.degraded:
            alerts.append(
                {
                    "source": r.source,
                    "severity": "warning",
                    "type": "archive_replay_not_live",
                    "message": "degraded replay: gone/error/freshness cannot be established",
                }
            )
        if pd.notna(r.success) and r.success < SUCCESS_FLOOR:
            alerts.append(
                {
                    "source": r.source,
                    "severity": "critical",
                    "type": "success_below_floor",
                    "message": f"success={r.success:.3f} < {SUCCESS_FLOOR}",
                }
            )
        if not baseline.empty:
            base_fail = baseline["n_parse_fail"].mean()
            if base_fail > 0 and r.n_parse_fail > JUMP_FACTOR * base_fail:
                alerts.append(
                    {
                        "source": r.source,
                        "severity": "critical",
                        "type": "parse_failure_spike",
                        "message": (
                            f"parse failures {r.n_parse_fail} > {JUMP_FACTOR}x "
                            f"baseline {base_fail:.1f}"
                        ),
                    }
                )
            if r.http_429_count > 0:
                alerts.append(
                    {
                        "source": r.source,
                        "severity": "critical",
                        "type": "http_429",
                        "message": f"{r.http_429_count} 429s: stop, back off, do not evade",
                    }
                )

    report = {
        "run_date": str(run_date),
        "n_sources": int(len(current)),
        "alerts": alerts,
        "status": "ok" if not alerts else "attention_required",
        "caveat": "archive replay cannot establish live daily coverage >=95%",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "alerts.json").write_text(json.dumps(report, indent=2))
    return report
