"""Tests for monitoring, reposts, live polite fetch and price-list seeding."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from autolens.common.db import LOGICAL_TABLES, translate_sql
from autolens.common.local_backend import ObjectStore, RawPayloadConflict
from autolens.linkage.reposts import measure_repost_recall, repost_rule_match
from autolens.scrapers.live import BlockedError, LiveSourceScraper
from autolens.scrapers.monitoring import check_health, daily_coverage
from autolens.scrapers.normalize.dictionary import ModelDictionary
from autolens.scrapers.normalize.price_dictionary import seed_from_price_list
from autolens.scrapers.rate_limiter import PolitePolicy
from tests.integration.test_m1_golden import _context


def _seed_runs(ctx, day: date, **overrides):
    base = dict(
        run_id=f"r-{day}",
        source="hatla2ee",
        run_date=str(day),
        started_at="t",
        finished_at="t",
        n_index_pages=1,
        n_listings_seen=100,
        n_new=0,
        n_gone=0,
        n_error=0,
        n_parse_fail=0,
        http_429_count=0,
        degraded=1,
    )
    base.update(overrides)
    ctx.db.insert_many("ops_scrape_run", [base])


def test_monitoring_flags_archive_replay_and_success(tmp_path):
    ctx = _context(tmp_path)
    d1, d2 = date(2026, 1, 15), date(2026, 1, 16)
    _seed_runs(ctx, d1)
    _seed_runs(ctx, d2, n_error=15)  # 15% errors -> below 90% success
    cov = daily_coverage(ctx.db, d2)
    assert "coverage" in cov.columns
    report = check_health(ctx.db, d2, tmp_path / "outputs")
    kinds = {a["type"] for a in report["alerts"]}
    assert "archive_replay_not_live" in kinds
    assert "success_below_floor" in kinds
    assert (tmp_path / "outputs" / "alerts.json").exists()


def test_reposts_not_measurable_without_multiday_review(tmp_path):
    ctx = _context(tmp_path)
    result = measure_repost_recall(ctx.db, ["2026-01-15"], tmp_path / "outputs")
    assert result["measurable"] is False
    assert "single-snapshot" in result["reason"]


def test_repost_rule():
    a = {
        "source": "hatla2ee",
        "source_listing_id": "1",
        "make_canon": "Toyota",
        "model_canon": "Camry",
        "year": 2020,
        "transmission": "AT",
        "fuel_type": "petrol",
        "body_type": "sedan",
        "mileage_km": 100,
        "price_egp": 1000,
    }
    b = dict(a, source="dubizzle", source_listing_id="2", mileage_km=105, price_egp=1050)
    assert repost_rule_match(a, b)
    assert not repost_rule_match(a, dict(b, year=2010))


def test_live_scraper_robots_and_blocking(monkeypatch):
    policy = PolitePolicy(min_interval_s=1.0, off_peak_only=False)
    s = LiveSourceScraper("https://example.test", policy=policy)
    monkeypatch.setattr(s, "assert_allowed", lambda path="/": None)

    class R:
        status_code = 200
        text = ""
        content = b"ok"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(s._client, "get", lambda url: R())
    assert s.fetch("/car/1").payload == b"ok"

    class Blocked:
        status_code = 429
        text = "too many requests"
        content = b""

        def raise_for_status(self):
            pass

    monkeypatch.setattr(s._client, "get", lambda url: Blocked())
    with pytest.raises(BlockedError):
        s.fetch("/car/2")
    s.close()


def test_raw_object_is_immutable(tmp_path):
    store = ObjectStore(tmp_path)
    payload = {"source": "hatla2ee", "source_listing_id": "1", "n": 1}
    key = store.put_raw("hatla2ee", "2026-01-15", "1", payload)
    # Same logical bytes: accepted as a no-op.
    assert store.put_raw("hatla2ee", "2026-01-15", "1", dict(payload)) == key
    # Different content under the same key must raise, never overwrite.
    with pytest.raises(RawPayloadConflict):
        store.put_raw("hatla2ee", "2026-01-15", "1", dict(payload, n=2))


def test_shared_database_translates_logical_names_and_placeholders():
    out = translate_sql(
        "SELECT * FROM staging_parsed_listing WHERE source=? AND x LIKE '%a%'", True
    )
    assert "staging.parsed_listing" in out
    assert "source=%s" in out and "LIKE '%%a%%'" in out
    assert translate_sql("SELECT 1", False) == "SELECT 1"
    assert LOGICAL_TABLES["core_vehicle_link"][0] == "core.vehicle_link"


def test_price_list_seeding_preserves_existing_ids(tmp_path):
    ref = tmp_path / "data_reference"
    ref.mkdir()
    d = ModelDictionary()
    d.fit(
        [
            type("L", (), {"make_raw": "Toyota", "model_raw": "Camry"})(),
            type("L", (), {"make_raw": "Honda", "model_raw": "Civic"})(),
        ]
    )
    d.save(ref)
    before = ModelDictionary.load(ref)
    prices_df = pd.DataFrame(
        [
            {"make": "Toyota", "model": "Camry", "price_egp": 900000},
            {"make": "Nissan", "model": "Altima", "price_egp": 800000},
        ]
    )
    prices_df["make"] = prices_df["make"].str.title()
    prices_df["model"] = prices_df["model"].str.title()
    out = seed_from_price_list(prices_df, ref)
    after = ModelDictionary.load(ref)
    assert len(after.models) == len(before.models) + 1
    assert any(r["model"] == "Altima" for r in out.to_dict("records"))
    assert set(before.models).issubset(set(after.models))
