"""Stage entry points: run_scrape and run_normalize (handbook 11.3)."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, time

import pandas as pd

from autolens.common.schemas import ParsedListing, ScrapeRun
from autolens.common.stage import RunContext, StageResult
from autolens.scrapers.archive import ArchiveSource
from autolens.scrapers.normalize.dictionary import ModelDictionary
from autolens.scrapers.normalize.flags import (
    add_price_outlier_flags,
    check_mileage,
    check_year,
)
from autolens.scrapers.normalize.units import (
    map_body,
    map_color,
    map_condition,
    map_fuel,
    map_payment,
    map_transmission,
    parse_mileage_km,
    parse_price_egp,
    parse_year,
)

SOURCES = ("hatla2ee", "contactcars", "dubizzle")


def run_scrape(run_date: date, ctx: RunContext) -> StageResult:
    """Sweep each archive source, store immutable raw payloads and parse them."""
    settings = ctx.settings
    settings.ensure_dirs()
    # Archive replay must be deterministic: a UUID run_id and a wall-clock
    # scraped_at changed the raw bytes on every rerun, breaking immutability and
    # idempotency. Derive both from the archive bytes + run date instead.
    archive_path = settings.data_dir / "Egypt_Used_Cars_clean.csv"
    if not archive_path.exists():
        ctx.log.warning("archive file missing: %s", archive_path)
        return StageResult(
            "scrape", run_date, 0, 0, [f"archive_missing: {archive_path} (set DATA_DIR)"]
        )
    archive_bytes = archive_path.read_bytes()
    input_digest = hashlib.sha256(archive_bytes).hexdigest()[:10]
    run_id = f"archive-{run_date.isoformat()}-{input_digest}"
    observation_at = datetime.combine(run_date, time.min, tzinfo=UTC)
    scraped_at = observation_at.isoformat()
    rows_in = rows_out = 0
    warnings: list[str] = []
    scrape_runs = []

    for source in SOURCES:
        adapter = ArchiveSource(source, settings.data_dir, settings.min_interval_s)
        started = finished = observation_at
        raw_rows, parsed_rows = [], []
        for _, row in adapter.df.iterrows():
            rows_in += 1
            payload = adapter.make_payload(row, scraped_at, run_id)
            key = ctx.store.put_raw(source, str(run_date), row["listing_id"], json_payload(payload))
            parsed = adapter.parse(payload, row["url"], scraped_at)
            raw_rows.append({**parsed.model_dump(mode="json"), "payload_key": key})
            parsed_rows.append(parsed)
            rows_out += 1
        # Archive files are a single historical observation, not a live sweep.
        # Reusing them on a later date must not fabricate new listings, sales,
        # disappearances, or independent daily coverage.
        seen_before = {
            r["source_listing_id"]
            for r in ctx.db.query(
                "SELECT DISTINCT source_listing_id FROM staging_parsed_listing "
                "WHERE source=? AND scrape_date<?",
                (source, str(run_date)),
            )
        }
        n_new = sum(r["source_listing_id"] not in seen_before for r in raw_rows)
        ctx.db.insert_many("staging_parsed_listing", raw_rows)
        sr = ScrapeRun(
            run_id=run_id,
            source=source,
            run_date=run_date,
            started_at=started,
            finished_at=finished,
            n_index_pages=1,
            n_listings_seen=len(parsed_rows),
            n_new=n_new,
        )
        scrape_runs.append(
            {
                "run_id": sr.run_id,
                "source": sr.source,
                "run_date": str(sr.run_date),
                "started_at": sr.started_at.isoformat(),
                "finished_at": sr.finished_at.isoformat(),
                "n_index_pages": sr.n_index_pages,
                "n_listings_seen": sr.n_listings_seen,
                "n_new": sr.n_new,
                "degraded": True,  # archive replay cannot establish live/gone coverage
            }
        )
    ctx.db.insert_many("ops_scrape_run", scrape_runs)
    warnings.append("archive_replay_not_live_snapshot: gone/error and freshness unverified")
    ctx.log.info("archive replay complete run_id=%s rows=%d", run_id, rows_out)
    return StageResult("scrape", run_date, rows_in, rows_out, warnings, {"run_id": run_id})


def json_payload(payload: bytes) -> dict:
    """Unpack bytes so the object store can gzip them; keeps raw bytes recoverable."""
    import json

    return json.loads(payload)


def _verify_reparse(ctx: RunContext, run_date: date, rows: list[dict]) -> int:
    """Re-parse a deterministic sample from immutable raw and compare with staging (R3)."""
    import json

    sample = sorted(rows, key=lambda r: (r["source"], r["source_listing_id"]))[
        : ctx.settings.reparse_sample
    ]
    if not sample:
        return 0
    adapters: dict[str, ArchiveSource] = {}
    mismatches = 0
    for r in sample:
        payload = ctx.store.get_raw(r["payload_key"])
        adapter = adapters.setdefault(
            r["source"], ArchiveSource.for_parsing(r["source"], ctx.settings.data_dir)
        )
        again = adapter.parse(
            json.dumps(payload).encode("utf-8"), r["url"], r["scraped_at"]
        ).model_dump(mode="json")
        stored = {k: v for k, v in r.items() if k != "payload_key"}
        again_cmp = ParsedListing(**again).model_dump(mode="json")
        if ParsedListing(**stored).model_dump(mode="json") != again_cmp:
            mismatches += 1
    if mismatches:
        ctx.log.warning("re-parse from raw differs from staging for %d rows", mismatches)
    return mismatches


def run_normalize(run_date: date, ctx: RunContext) -> StageResult:
    """raw -> staging.parsed -> staging.normalized with dictionary + quality flags."""
    rows = ctx.db.query(
        "SELECT * FROM staging_parsed_listing WHERE scrape_date=?", (str(run_date),)
    )
    import json

    mismatches = _verify_reparse(ctx, run_date, rows)
    listings = [ParsedListing(**{k: v for k, v in r.items() if k != "payload_key"}) for r in rows]

    dictionary = ModelDictionary().fit(listings)
    dictionary.save(ctx.settings.reference_path)

    normalized = []
    unmapped = []
    for lst in listings:
        mid, confidence = dictionary.map(lst.make_raw, lst.model_raw)
        make, model, trim = dictionary.canonical(mid)
        dq: dict[str, bool] = {}
        r = {
            "make_model_year": f"{make or lst.make_raw}|{model or lst.model_raw}|{lst.year}",
            "year": parse_year(lst.year_raw),
            "mileage_km": parse_mileage_km(lst.km_raw),
            "price_egp": parse_price_egp(lst.price_raw, lst.currency),
            "dq_flags": dq,
        }
        check_year(r)
        check_mileage(r)
        normalized.append(
            {
                "source": lst.source,
                "source_listing_id": lst.source_listing_id,
                "scrape_date": str(run_date),
                "model_id": mid,
                "make_canon": make,
                "model_canon": model,
                "trim_canon": trim,
                "year": r["year"],
                "mileage_km": r["mileage_km"],
                "price_egp": r["price_egp"],
                "governorate_code": lst.city_raw,
                "transmission": map_transmission(lst.transmission_raw),
                "fuel_type": map_fuel(lst.fuel_raw),
                "body_type": map_body(lst.body_raw),
                "condition": map_condition(lst.condition_raw),
                "color": map_color(lst.color_raw),
                "payment_option": map_payment(lst.payment_raw),
                "dq_flags": json.dumps(dq),
                "mapping_confidence": confidence,
            }
        )
        if mid is None:
            unmapped.append(
                {
                    "source": lst.source,
                    "make_raw": lst.make_raw,
                    "model_raw": lst.model_raw,
                    "best_score": confidence,
                }
            )

    # add_price_outlier_flags expects dq_flags as dict; apply before serialising.
    for row in normalized:
        row["dq_flags"] = json.loads(row["dq_flags"])

    add_price_outlier_flags(normalized, group_key="make_model_year")
    for row in normalized:
        row["dq_flags"] = json.dumps(row["dq_flags"])

    ctx.db.insert_many("staging_normalized_listing", normalized)
    ctx.settings.output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(unmapped).to_csv(ctx.settings.output_dir / "unmapped_review.csv", index=False)
    mapped = sum(1 for n in normalized if n["model_id"] is not None)
    mapping_rate = mapped / len(normalized) if normalized else 0.0
    ctx.log.info("normalize: %d rows, mapping rate %.4f", len(normalized), mapping_rate)
    return StageResult(
        "normalize",
        run_date,
        len(listings),
        len(normalized),
        ["dictionary_mined_from_archive: mapping_rate is not an independent accuracy estimate"]
        + ([f"reparse_mismatch: {mismatches} sampled rows differ from raw"] if mismatches else []),
        {
            "mapping_rate": mapping_rate,
            "n_unmapped": len(unmapped),
            "reparse_mismatches": mismatches,
        },
    )
