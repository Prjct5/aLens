from __future__ import annotations

from datetime import date, datetime
from typing import Any

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
    listing_key: str
    vehicle_id: int | None = None
    date_key: int
    price_egp: float | None = None
    is_live: bool
    days_since_first_seen: int


class DimListing(ContractModel):
    listing_key: str
    source: Source
    url: str
    first_seen: date
    last_seen: date
    seller_type: str | None = None


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
