"""Common scraper interface - handbook Listing 8.1."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import date

from autolens.common.schemas import ImageRef, ParsedListing


class SourceScraper(ABC):
    source: str
    min_interval_s: float = 1.0  # override from config only *upward* (R5)

    @abstractmethod
    def discover(self, run_date: date) -> Iterator[str]:
        """Yield listing URLs seen on index/search pages today."""

    @abstractmethod
    def parse(self, payload: bytes, url: str, scraped_at: str) -> ParsedListing:
        """Pure function: bytes in, validated record out. NO network access.

        Must never read or return seller name/phone (R6).
        """

    @abstractmethod
    def fetch_images(self, listing: ParsedListing) -> Iterator[ImageRef]:
        """Download (politely) up to N images; yield bytes + metadata."""

    def is_gone(self, status: int, payload: bytes) -> bool:
        """404/410 or the site's 'ad removed' page. 5xx/timeouts are NOT gone."""
        if status in (404, 410):
            return True
        marker = b"no longer available"
        return status == 200 and marker in payload.lower()
