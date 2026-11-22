"""Run the M1 stages on a real data folder and write a verification report.

Local mode (default): SQLite + filesystem, no services needed.
--postgres: shared PostgreSQL + S3 (MinIO) through the same code the pipeline uses.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import date
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir", required=True, help="folder containing Egypt_Used_Cars_clean.csv"
    )
    parser.add_argument("--work-dir", default="work", help="outputs, local DB, raw objects")
    parser.add_argument("--run-date", default="2026-01-15")
    parser.add_argument("--report-dir", default="M1_VERIFY")
    parser.add_argument("--postgres", action="store_true")
    parser.add_argument("--skip-idempotency", action="store_true")
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    work_dir = Path(args.work_dir).resolve()
    report_dir = Path(args.report_dir).resolve()
    marker = work_dir / ".autolens_work"
    if work_dir.exists() and any(work_dir.iterdir()) and not args.postgres:
        if not marker.exists():
            print(
                f"{work_dir} exists but was not created by this script; delete it once "
                "(Remove-Item -Recurse -Force) or pass another --work-dir.",
                file=sys.stderr,
            )
            return 2
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    marker.write_text("created by verify_m1.py; safe to delete\n")
    report_dir.mkdir(parents=True, exist_ok=True)
    os.environ["PROJECT_ROOT"] = str(work_dir)
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ.setdefault("REFERENCE_DIR", str(work_dir / "data_reference"))
    run_date = date.fromisoformat(args.run_date)

    from autolens.scrapers.local_run import M1_STAGE_FUNCS, M1_STAGE_NAMES, run_stages
    from autolens.scrapers.settings import M1Settings
    from autolens.scrapers.verify import build_report, render_text, table_counts

    if args.postgres:
        from autolens.common.config import Settings
        from autolens.common.stage import make_context
        from autolens.pipelines.m1_stages import M1_STAGES
        from autolens.warehouse.migrate import migrate

        settings = Settings()
        print("applying migrations ...", flush=True)
        migrate(settings.database_url)
        ctx = make_context(settings, connect=True)
        ctx.store.ensure_buckets()
        stages = tuple((n, M1_STAGES[n]) for n in M1_STAGE_NAMES)
        m1_settings = M1Settings.from_env()
    else:
        from autolens.scrapers.local_run import build_local_context

        m1_settings = M1Settings.from_env()
        ctx = build_local_context(m1_settings)
        stages = M1_STAGE_FUNCS

    print(f"mode={'postgres' if args.postgres else 'local'} data={data_dir}", flush=True)
    t0 = time.perf_counter()
    results = run_stages(run_date, ctx, stages)
    for r in results:
        print(f"  {r['stage']:<13} {r['seconds']:>8}s rows_out={r['rows_out']}", flush=True)

    report = build_report(ctx, run_date, results, data_dir, m1_settings.output_dir)
    report["mode"] = "postgres" if args.postgres else "local"
    report["total_seconds"] = round(time.perf_counter() - t0, 1)

    checks = {}
    if not args.skip_idempotency:
        before = report["table_rows"]
        again = run_stages(
            run_date, ctx, tuple(s for s in stages if s[0] in ("scrape", "normalize"))
        )
        after = table_counts(ctx.db, run_date)
        checks["idempotency_scrape_normalize"] = {
            "rows_before": before,
            "rows_after_rerun": after,
            "identical": before == after,
            "rerun_stages": [x["stage"] for x in again],
        }
        report["idempotency"] = checks["idempotency_scrape_normalize"]
    parsed = report["table_rows"]["staging_parsed_listing"]
    checks["rows_parsed_equal_normalized"] = (
        parsed == report["table_rows"]["staging_normalized_listing"]
    )
    checks["raw_objects_equal_parsed"] = report.get("raw_objects_for_run_date") == parsed
    checks["no_contact_info_in_descriptions"] = (
        report.get("description_rows_with_contact_info", 0) == 0
    )
    checks["candidate_pairs_not_truncated"] = not (
        report.get("linkage_metrics", {}).get("candidate_pairs_truncated", False)
    )
    report["checks"] = checks

    (report_dir / "report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    (report_dir / "report.txt").write_text(render_text(report), encoding="utf-8")
    print(f"\nreport: {report_dir / 'report.txt'}")
    print("checks:", json.dumps(checks, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
