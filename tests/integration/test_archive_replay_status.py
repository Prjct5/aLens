from datetime import date, timedelta

from autolens.scrapers.run import run_scrape
from tests.integration.test_m1_golden import _context


def test_archive_replay_does_not_invent_new_listings_or_live_coverage(tmp_path):
    ctx = _context(tmp_path)
    first = date(2026, 1, 15)
    run_scrape(first, ctx)
    run_scrape(first + timedelta(days=1), ctx)
    rows = ctx.db.query(
        "SELECT n_new, n_gone, degraded FROM ops_scrape_run WHERE run_date=?",
        (str(first + timedelta(days=1)),),
    )
    assert len(rows) == 3
    assert all(r["n_new"] == 0 and r["n_gone"] == 0 and r["degraded"] == 1 for r in rows)
