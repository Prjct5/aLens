"""Static-archive adapters for the three sources.

The handbook assumes live websites. The team supplied saved datasets instead,
so each adapter implements the exact SourceScraper interface over those files:
`discover()` yields URLs, `parse()` is a pure bytes->ParsedListing function, and
`fetch_images()` is an honest no-op (the archives contain no images).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from autolens.common.privacy import scrub_contact_info
from autolens.common.schemas import ImageRef, ParsedListing
from autolens.scrapers.base import SourceScraper

_CITY_RE = re.compile(r"for-sale-(?:in-)?([a-z\-]+)-ID", re.IGNORECASE)
_CITY_TO_GOV = {
    "alexandria": "ALX",
    "cairo": "CAI",
    "giza": "GIZ",
    "nasr-city": "CAI",
    "kafr-el-sheikh": "KFS",
    "tanta": "GHB",
    "mansoura": "DKA",
    "hurghada": "BNS",
    "sharm": "SIN",
}


def governorate_from_url(url: str) -> str | None:
    m = _CITY_RE.search(url or "")
    if not m:
        return None
    city = m.group(1).lower()
    for key, code in _CITY_TO_GOV.items():
        if key in city:
            return code
    return None


class ArchiveSource(SourceScraper):
    """One adapter per source, configured by `source`."""

    min_interval_s = 1.0

    def __init__(self, source: str, data_dir: Path, min_interval_s: float = 1.0):
        if source not in ("hatla2ee", "contactcars", "dubizzle"):
            raise ValueError(f"unknown source {source}")
        self.source = source
        self.data_dir = Path(data_dir)
        self.min_interval_s = max(1.0, min_interval_s)  # config only upward
        self._df: pd.DataFrame | None = None

    @classmethod
    def for_parsing(cls, source: str, data_dir: Path) -> ArchiveSource:
        """Adapter used only for the pure parse(); never reads the CSV."""
        return cls(source, data_dir)

    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            path = self.data_dir / "Egypt_Used_Cars_clean.csv"
            all_df = pd.read_csv(path, dtype=str, keep_default_na=False)
            self._df = all_df[all_df["source"] == self.source].reset_index(drop=True)
        return self._df

    def discover(self, run_date) -> Iterator[str]:
        """Yield listing URLs (index sweep equivalent for a saved archive)."""
        yield from self.df["url"].tolist()

    def make_payload(self, row: pd.Series, scraped_at: str, run_id: str) -> bytes:
        """Build the immutable raw payload that a live scraper would have saved."""
        payload = {
            "source": self.source,
            "source_listing_id": row["listing_id"],
            "url": row["url"],
            "scraped_at": scraped_at,
            "run_id": run_id,
            "fields": {
                "make_raw": row.get("make") or None,
                "model_raw": row.get("model") or None,
                "year_raw": row.get("year") or None,
                "km_raw": row.get("kilometers") or None,
                "price_raw": row.get("price") or None,
                "transmission_raw": row.get("transmission") or None,
                "fuel_raw": row.get("fuel_type") or None,
                "body_raw": row.get("body_type") or None,
                "city_raw": row.get("city") or None,
                "condition_raw": row.get("condition") or None,
                "color_raw": row.get("exterior_color") or None,
                "payment_raw": row.get("payment_options") or None,
                "description_raw": scrub_contact_info(row.get("description") or None),
            },
            # No seller names/phones exist in these archives (R6).
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")

    def parse(self, payload: bytes, url: str, scraped_at: str) -> ParsedListing:
        """Pure parse: bytes in, validated record out. Never touches network."""
        data = json.loads(payload)
        f = data["fields"]

        def to_int(v):
            try:
                return int(float(str(v).replace(",", "")))
            except (TypeError, ValueError):
                return None

        def to_float(v):
            try:
                return float(str(v).replace(",", ""))
            except (TypeError, ValueError):
                return None

        return ParsedListing(
            source=data["source"],
            source_listing_id=str(data["source_listing_id"]),
            url=url,
            scrape_date=date.fromisoformat(scraped_at[:10]),
            scraped_at=datetime.fromisoformat(scraped_at.replace("Z", "+00:00")),
            run_id=data["run_id"],
            make_raw=f.get("make_raw"),
            model_raw=f.get("model_raw"),
            year_raw=str(f["year_raw"]) if f.get("year_raw") not in (None, "") else None,
            km_raw=str(f["km_raw"]) if f.get("km_raw") not in (None, "") else None,
            price_raw=str(f["price_raw"]) if f.get("price_raw") not in (None, "") else None,
            transmission_raw=f.get("transmission_raw") or None,
            fuel_raw=f.get("fuel_raw") or None,
            body_raw=f.get("body_raw") or None,
            city_raw=f.get("city_raw") or governorate_from_url(url),
            condition_raw=f.get("condition_raw") or None,
            color_raw=f.get("color_raw") or None,
            payment_raw=f.get("payment_raw") or None,
            description_raw=f.get("description_raw"),
            year=to_int(f.get("year_raw")),
            mileage_km=to_float(f.get("km_raw")),
            price_egp=to_float(f.get("price_raw")),
            currency="EGP",
        )

    def fetch_images(self, listing: ParsedListing) -> Iterator[ImageRef]:
        """No images in the supplied archives - yield nothing (documented in D6)."""
        return
        yield  # pragma: no cover - keeps this a generator
