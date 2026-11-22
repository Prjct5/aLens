from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from autolens.common.schemas._base import ContractModel, ImageId, PHash, Source, listing_key

TRANSMISSIONS = ("manual", "automatic")
FUEL_TYPES = ("petrol", "diesel", "hybrid", "electric", "cng", "other")
IMAGE_STATUSES = (
    "fetched",
    "failed",
    "promoted",
    "open_source_commons",
    "synthetic_placeholder",
)
REAL_IMAGE_STATUSES = ("fetched", "promoted")


class ParsedListing(ContractModel):
    """One parsed listing (record returned by a scraper's parse())."""

    source: Source
    source_listing_id: str
    url: str
    scrape_date: date
    scraped_at: datetime
    run_id: str
    make_raw: str | None = None
    model_raw: str | None = None
    year_raw: str | None = None
    km_raw: str | None = None
    price_raw: str | None = None
    transmission_raw: str | None = None
    fuel_raw: str | None = None
    body_raw: str | None = None
    city_raw: str | None = None
    condition_raw: str | None = None
    color_raw: str | None = None
    payment_raw: str | None = None
    description_raw: str | None = None
    year: int | None = None
    mileage_km: float | None = None
    price_egp: float | None = None
    currency: str = "EGP"

    @property
    def key(self) -> str:
        return listing_key(self.source, self.source_listing_id)


class ParsedListingRow(ParsedListing):
    """staging.parsed_listing: the parsed record plus the key of its raw object."""

    payload_key: str | None = None


class NormalizedListing(ContractModel):
    """staging.normalized_listing: same key, canonical values."""

    source: Source
    source_listing_id: str
    scrape_date: date
    model_id: int | None = None
    make_canon: str | None = None
    model_canon: str | None = None
    trim_canon: str | None = None
    year: int | None = None
    mileage_km: float | None = None
    price_egp: float | None = None
    governorate_code: str | None = None
    transmission: Literal["manual", "automatic"] | None = None
    fuel_type: Literal["petrol", "diesel", "hybrid", "electric", "cng", "other"] | None = None
    body_type: str | None = None
    condition: Literal["new", "used"] | None = None
    color: str | None = None
    payment_option: Literal["cash", "installment", "cash_or_installment", "exchange"] | None = None
    dq_flags: dict[str, bool] = Field(default_factory=dict)
    mapping_confidence: float | None = Field(default=0.0, ge=0, le=1)

    @property
    def key(self) -> str:
        return listing_key(self.source, self.source_listing_id)


class ImageRef(ContractModel):
    """Image reference yielded by a scraper's fetch_images()."""

    listing_key: str
    position: int = Field(ge=0)
    image_id: ImageId
    source_url: str
    width: int | None = None
    height: int | None = None
    phash: PHash | None = None
    status: str = "fetched"
    quarantine_key: str | None = None


class ImageFetch(ContractModel):
    """staging.image_fetch: images in quarantine."""

    listing_key: str
    position: int = Field(ge=0)
    image_id: ImageId
    source_url: str | None = None
    fetched_at: datetime | None = None
    width: int | None = None
    height: int | None = None
    phash: PHash | None = None
    status: Literal["fetched", "failed", "promoted", "open_source_commons", "synthetic_placeholder"]
    quarantine_key: str | None = None
