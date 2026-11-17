from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field

from autolens.common.schemas._base import ContractModel, ImageId


class ImageScores(ContractModel):
    image_id: ImageId
    model_version: str
    view_label: str | None = None
    view_probs: dict[str, float] | None = None
    damage_boxes: list[dict[str, Any]] | None = None
    damage_score: float | None = None
    blur_var: float | None = None
    exposure: float | None = None
    quality_score: float | None = None
    stock_suspect: bool | None = None
    scored_at: datetime


class ImageEmbedding(ContractModel):
    image_id: ImageId
    model_version: str
    dim: int
    vector: list[float]


class ListingImageAgg(ContractModel):
    listing_key: str
    run_date: date
    n_photos: int
    view_coverage: float | None = Field(default=None, ge=0, le=1)
    damage_score_max: float | None = None
    quality_mean: float | None = None
    verify_conf: float | None = None
    verify_mismatch: bool | None = None
    photo_reuse_count: int | None = None


class TextAttributes(ContractModel):
    listing_key: str
    description_hash: str
    extractor_version: str
    accident: Literal["none", "minor", "major", "unknown"] = "unknown"
    accident_conf: float | None = None
    n_repainted_parts: int | None = None
    repainted_parts: list[str] | None = None
    n_owners: int | None = None
    license_status: str | None = None
    factory_condition_claim: bool | None = None
    negotiable: bool | None = None
    installments: bool | None = None
    language_mix: dict[str, float] | None = None
    desc_len: int | None = None
    scored_at: datetime


class TextEmbedding(ContractModel):
    listing_key: str
    description_hash: str
    model_name: str
    vector: list[float]
