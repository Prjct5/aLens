from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class PriceEstimateRequest(BaseModel):
    make: str
    model: str
    trim: str | None = None
    year: int = Field(ge=1980, le=2027)
    mileage_km: int = Field(ge=0, le=2_000_000)
    transmission: Literal["manual", "automatic"] | None = None
    fuel_type: str | None = None
    governorate: str | None = None
    description: str | None = Field(None, max_length=5000)
    photos_base64: list[str] = Field(default_factory=list, max_length=8)


class PriceEstimateResponse(BaseModel):
    currency: Literal["EGP"] = "EGP"
    median: float
    lo: float
    hi: float
    confidence_level: float
    calibrated_at: str
    model_version: str
    inputs_used: dict[str, bool]
    warnings: list[str] = []
    disclaimer: str = (
        "Typical asking-price range for comparable cars, not an appraisal or a transaction price."
    )


class ListingCheckRequest(BaseModel):
    make: str
    model: str
    year: int = Field(ge=1980, le=2027)
    mileage_km: int = Field(ge=0, le=2_000_000)
    asking_price_egp: float = Field(gt=0)
    description: str | None = Field(None, max_length=5000)
    photos_base64: list[str] = Field(default_factory=list, max_length=8)


class ListingCheckResponse(BaseModel):
    suspicion_score: float = Field(ge=0, le=1)
    reasons: list[str] = []
    model_version: str
    warnings: list[str] = []
    disclaimer: str = "Automated signal only. A high score is a reason to look closer, not proof."


class DuplicatesResponse(BaseModel):
    listing_key: str
    vehicle_id: int | None = None
    duplicates: list[str] = []
    cluster_size: int = 1


class MarketIndexPoint(BaseModel):
    week_start: date
    index: float
    lo: float
    hi: float
    n_listings: int


class MarketIndexResponse(BaseModel):
    base_week: date
    data_window: str
    points: list[MarketIndexPoint]
    limitations: str = (
        "Asking prices, not transaction prices. Delisting is a proxy for sale, not proof of one."
    )


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    suggestions: list[str] = []
