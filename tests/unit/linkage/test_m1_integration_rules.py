from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from autolens.linkage.run import _load_listings, run_linkage
from autolens.scrapers.archive import ArchiveSource
from autolens.scrapers.live import LiveSourceScraper
from autolens.scrapers.run import run_normalize, run_scrape
from tests.integration.test_m1_golden import RUN_DATE, _context

PHASH = "a" * 16


def _prepared(tmp_path: Path):
    ctx = _context(tmp_path)
    run_scrape(RUN_DATE, ctx)
    run_normalize(RUN_DATE, ctx)
    return ctx


def _add_image(ctx, status: str) -> str:
    row = ctx.db.query("SELECT source, source_listing_id FROM staging_normalized_listing LIMIT 1")[
        0
    ]
    key = f"{row['source']}:{row['source_listing_id']}"
    ctx.db.insert_many(
        "staging_image_fetch",
        [
            {
                "listing_key": key,
                "position": 0,
                "image_id": "b" * 64,
                "source_url": None,
                "fetched_at": None,
                "width": 8,
                "height": 8,
                "phash": PHASH,
                "status": status,
                "quarantine_key": None,
            }
        ],
    )
    return key


def test_placeholder_photos_are_ignored_by_linkage(tmp_path: Path) -> None:
    ctx = _prepared(tmp_path)
    key = _add_image(ctx, "open_source_commons")
    listings = {r["listing_key"]: r for r in _load_listings(ctx, RUN_DATE)}
    assert listings[key]["phash"] is None


def test_real_photos_are_used_by_linkage(tmp_path: Path) -> None:
    ctx = _prepared(tmp_path)
    key = _add_image(ctx, "fetched")
    listings = {r["listing_key"]: r for r in _load_listings(ctx, RUN_DATE)}
    assert listings[key]["phash"] == PHASH


def test_linkage_warns_when_photo_match_inactive_and_when_truncated(tmp_path: Path) -> None:
    ctx = _prepared(tmp_path)
    result = run_linkage(RUN_DATE, ctx, max_pairs=3)
    joined = " ".join(result.warnings)
    assert "photo_match_inactive" in joined
    assert "candidate_pairs_truncated" in joined
    assert result.metrics["candidate_pairs_truncated"] is True
    assert "no_labelled_pairs" in joined


def test_linkage_marks_evaluation_as_provisional(tmp_path: Path) -> None:
    ctx = _prepared(tmp_path)
    result = run_linkage(RUN_DATE, ctx)
    assert any("evaluation_provisional" in w for w in result.warnings)
    assert result.metrics["candidate_pairs_truncated"] is False


def test_normalize_reports_reparse_and_circular_dictionary(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    run_scrape(RUN_DATE, ctx)
    result = run_normalize(RUN_DATE, ctx)
    assert result.metrics["reparse_mismatches"] == 0
    assert any("dictionary_mined_from_archive" in w for w in result.warnings)


def test_missing_archive_is_reported_not_raised(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    (tmp_path / "data" / "Egypt_Used_Cars_clean.csv").unlink()
    result = run_scrape(RUN_DATE, ctx)
    assert result.rows_out == 0 and "archive_missing" in result.warnings[0]


def test_off_peak_uses_cairo_time_with_dst() -> None:
    scraper = LiveSourceScraper("https://example.invalid")
    assert scraper._off_peak(datetime(2026, 1, 15, 23, 30, tzinfo=UTC))
    assert scraper._off_peak(datetime(2026, 7, 15, 22, 30, tzinfo=UTC))
    assert not scraper._off_peak(datetime(2026, 1, 15, 8, 0, tzinfo=UTC))
    assert not scraper._off_peak(datetime(2026, 7, 15, 12, 0, tzinfo=UTC))


def test_archive_description_is_scrubbed() -> None:
    import pandas as pd

    adapter = ArchiveSource.for_parsing("hatla2ee", Path("."))
    row = pd.Series(
        {
            "listing_id": "1",
            "url": "u",
            "description": "كلمني على 01012345678 او a@b.com",
            "make": "Toyota",
        }
    )
    payload = adapter.make_payload(row, "2026-01-15T00:00:00+00:00", "r")
    assert b"01012345678" not in payload and b"a@b.com" not in payload
