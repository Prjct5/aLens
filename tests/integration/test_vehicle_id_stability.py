"""R11/R12: the same vehicle keeps the same vehicle_id across daily runs."""

from __future__ import annotations

from datetime import date, timedelta

from tests.integration.test_m1_golden import _context


def test_vehicle_id_stable_across_two_days(tmp_path):
    ctx = _context(tmp_path)
    day1 = date(2026, 1, 15)
    day2 = day1 + timedelta(days=1)

    for d in (day1, day2):
        from autolens.linkage.run import run_linkage
        from autolens.scrapers.run import run_normalize, run_scrape

        run_scrape(d, ctx)
        run_normalize(d, ctx)
        run_linkage(d, ctx)

    def ids(day):
        rows = ctx.db.query(
            "SELECT listing_key, vehicle_id FROM core_vehicle_link WHERE link_run_id=?",
            (f"link-{day}",),
        )
        return {r["listing_key"]: r["vehicle_id"] for r in rows}

    a, b = ids(day1), ids(day2)
    assert a and b and a.keys() == b.keys()
    assert a == b, "existing listings must keep their vehicle_id on the next day"
    ctx.db.close()
