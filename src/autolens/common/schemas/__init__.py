from __future__ import annotations

from pydantic import BaseModel

from autolens.common.schemas import api, core, features, ops, staging
from autolens.common.schemas._base import SOURCES, listing_key

CONTRACT_VERSION = 1

TABLE_MODELS: dict[str, type[BaseModel]] = {
    "staging.parsed_listing": staging.ParsedListing,
    "staging.normalized_listing": staging.NormalizedListing,
    "staging.image_fetch": staging.ImageFetch,
    "core.vehicle_link": core.VehicleLink,
    "core.vehicle_id_merge": core.VehicleIdMerge,
    "core.fact_listing_snapshot": core.FactListingSnapshot,
    "core.dim_listing": core.DimListing,
    "core.dim_model": core.DimModel,
    "core.new_car_price": core.NewCarPrice,
    "core.fact_macro_daily": core.FactMacroDaily,
    "core.image_asset": core.ImageAsset,
    "core.listing_image": core.ListingImage,
    "core.fact_model_outputs": core.FactModelOutput,
    "features.image_scores": features.ImageScores,
    "features.image_embedding": features.ImageEmbedding,
    "features.listing_image_agg": features.ListingImageAgg,
    "features.text_attributes": features.TextAttributes,
    "features.text_embedding": features.TextEmbedding,
    "ops.pipeline_run": ops.PipelineRunRow,
    "ops.model_monitor": ops.ModelMonitorRow,
    "ops.api_request": ops.ApiRequestRow,
}

API_MODELS: dict[str, type[BaseModel]] = {
    "api.PriceEstimateRequest": api.PriceEstimateRequest,
    "api.PriceEstimateResponse": api.PriceEstimateResponse,
    "api.ListingCheckRequest": api.ListingCheckRequest,
    "api.ListingCheckResponse": api.ListingCheckResponse,
    "api.DuplicatesResponse": api.DuplicatesResponse,
    "api.MarketIndexResponse": api.MarketIndexResponse,
    "api.ErrorBody": api.ErrorBody,
}

CONTRACT_MODELS: dict[str, type[BaseModel]] = {**TABLE_MODELS, **API_MODELS}

__all__ = [
    "API_MODELS",
    "CONTRACT_MODELS",
    "CONTRACT_VERSION",
    "SOURCES",
    "TABLE_MODELS",
    "listing_key",
]
