"""Scraper interface tests (handbook 8.2, R3/R6)."""

import json
from datetime import date, datetime

from autolens.scrapers.archive import ArchiveSource, governorate_from_url
from autolens.scrapers.base import SourceScraper


class Dummy(SourceScraper):
    source = "hatla2ee"

    def discover(self, run_date):
        return iter([])

    def parse(self, payload, url, scraped_at):
        return None

    def fetch_images(self, listing):
        return iter([])


def test_is_gone_only_for_real_removals():
    s = Dummy()
    assert s.is_gone(404, b"")
    assert s.is_gone(410, b"")
    assert s.is_gone(200, b"<h1>No longer available</h1>")
    assert not s.is_gone(500, b"")
    assert not s.is_gone(200, b"<html>listing</html>")


def test_parse_is_pure_and_keeps_raw_strings():
    adapter = ArchiveSource("dubizzle", __import__("pathlib").Path("data"))
    payload = json.dumps(
        {
            "source": "dubizzle",
            "source_listing_id": "x1",
            "url": "https://www.dubizzle.com.eg/en/ad/used-kia-rio-2013-for-sale-cairo-IDx1.html",
            "scraped_at": "2026-01-15T01:00:00+00:00",
            "run_id": "r1",
            "fields": {
                "make_raw": "Kia",
                "model_raw": "Rio",
                "year_raw": "2013",
                "km_raw": "122,000",
                "price_raw": "530,000",
            },
        }
    ).encode()
    url = "https://www.dubizzle.com.eg/en/ad/used-kia-rio-2013-for-sale-cairo-IDx1.html"
    a = adapter.parse(payload, url, "2026-01-15T01:00:00+00:00")
    b = adapter.parse(payload, url, "2026-01-15T01:00:00+00:00")
    assert a.model_dump() == b.model_dump(), "parse must be deterministic"
    assert a.make_raw == "Kia" and a.price_raw == "530,000"
    assert a.scrape_date == date(2026, 1, 15)
    assert isinstance(a.scraped_at, datetime)
    assert governorate_from_url(a.url) == "CAI"
