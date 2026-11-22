from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from autolens.common.schemas._base import ContractModel, ImageId, PHash, Source


class VehicleLink(ContractModel):
    listing_key: str
    vehicle_id: int
    link_run_id: str
    cluster_size: int
    min_edge_weight: float | None = None
    max_edge_weight: float | None = None
    method: str


class VehicleIdMerge(ContractModel):
    old_id: int
    new_id: int
    merged_at: datetime


class FactListingSnapshot(ContractModel):
    """status keeps 'error' (unknown) distinct from 'gone' (disappeared); see M2 handbook 8.1."""

    listing_key: str
    date_key: int
    vehicle_id: int | None = None
    status: Literal["live", "gone", "error"]
    price_egp: float | None = None
    days_since_first_seen: int


Day = date


class DimDate(ContractModel):
    date_key: int
    date: Day
    year: int | None = None
    month: int | None = None
    iso_week: int | None = None
    week_start: Day | None = None
    dow: int | None = None


class DimListing(ContractModel):
    listing_key: str
    source: Source
    source_listing_id: str
    url: str
    first_seen: date
    last_seen: date
    last_live_date: date | None = None
    seller_type: str | None = None
    posted_at: datetime | None = None


class DimVehicle(ContractModel):
    """SCD Type 2 vehicle dimension."""

    vehicle_sk: int | None = None
    vehicle_id: int
    model_id: int | None = None
    year: int | None = None
    mileage_km: int | None = None
    transmission: str | None = None
    fuel_type: str | None = None
    governorate_code: str | None = None
    representative_listing_key: str | None = None
    description_hash: str | None = None
    row_hash: str
    valid_from: date
    valid_to: date = date(9999, 12, 31)
    is_current: bool = True


class DimModel(ContractModel):
    model_id: int
    make: str
    model: str
    trim: str | None = None
    body_type: str | None = None
    segment: str | None = None


class NewCarPrice(ContractModel):
    model_id: int
    valid_from: date
    valid_to: date | None = None
    price_egp: float


class FactMacroDaily(ContractModel):
    date_key: int
    usd_egp: float | None = None
    fuel_92: float | None = None
    fuel_95: float | None = None
    fuel_diesel: float | None = None


class ImageAsset(ContractModel):
    image_id: ImageId
    width: int
    height: int
    phash: PHash | None = None
    object_key: str
    n_faces_blurred: int
    n_plates_blurred: int
    blur_model_version: str
    promoted_at: datetime


class ListingImage(ContractModel):
    listing_key: str
    position: int
    image_id: ImageId


class FactModelOutput(ContractModel):
    output_id: int | None = None
    listing_key: str
    vehicle_id: int | None = None
    model_name: str
    model_version: str
    run_date: date
    is_oof: bool = False
    output: dict[str, Any]
    created_at: datetime | None = None
