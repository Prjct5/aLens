from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from autolens.common.schemas._base import ContractModel, ImageId, PHash, Source


class ParsedListing(ContractModel):
    """staging.parsed_listing. Draft columns: to be frozen at the Contract v1 meeting."""

    source: Source
    source_listing_id: str
    scrape_date: date
    scraped_at: datetime
    run_id: str
    url: str
    status: Literal["live", "gone", "error"] = "live"
    title: str | None = None
    make_raw: str | None = None
    model_raw: str | None = None
    trim_raw: str | None = None
    year_raw: str | None = None
    mileage_raw: str | None = None
    price_raw: str | None = None
    currency_raw: str | None = None
    location_raw: str | None = None
    transmission_raw: str | None = None
    fuel_raw: str | None = None
    body_type_raw: str | None = None
    seller_type: Literal["dealer", "individual"] | None = None
    description: str | None = None
    image_urls: list[str] = Field(default_factory=list)
    raw_key: str | None = None
    parser_version: str | None = None


class NormalizedListing(ContractModel):
    source: Source
    source_listing_id: str
    scrape_date: date
    model_id: int | None = None
    make_canon: str | None = None
    model_canon: str | None = None
    trim_canon: str | None = None
    year: int | None = None
    mileage_km: int | None = None
    price_egp: float | None = None
    governorate_code: str | None = None
    transmission: Literal["manual", "automatic"] | None = None
    fuel_type: Literal["petrol", "diesel", "hybrid", "electric", "other"] | None = None
    body_type: str | None = None
    dq_flags: dict[str, bool] = Field(default_factory=dict)
    mapping_confidence: float | None = Field(default=None, ge=0, le=1)


class ImageFetch(ContractModel):
    listing_key: str
    position: int = Field(ge=0)
    image_id: ImageId
    source_url: str
    fetched_at: datetime
    width: int | None = None
    height: int | None = None
    phash: PHash | None = None
    status: Literal["fetched", "failed", "promoted"]
    quarantine_key: str | None = None
