from __future__ import annotations

from typing import Protocol

from autolens.common.schemas.api import (
    ListingCheckRequest,
    ListingCheckResponse,
    MarketIndexPoint,
    MarketIndexResponse,
    PriceEstimateRequest,
    PriceEstimateResponse,
)
from autolens.common.time import today_cairo


class ModelProvider(Protocol):
    def estimate(self, req: PriceEstimateRequest) -> PriceEstimateResponse: ...
    def check(self, req: ListingCheckRequest) -> ListingCheckResponse: ...
    def market_index(self) -> MarketIndexResponse: ...
    def versions(self) -> dict[str, str]: ...


class StubModelProvider:
    version = "stub-0"

    def estimate(self, req: PriceEstimateRequest) -> PriceEstimateResponse:
        median = float(max(50_000, 600_000 - (2026 - req.year) * 25_000 - req.mileage_km * 0.5))
        return PriceEstimateResponse(
            median=median,
            lo=median * 0.9,
            hi=median * 1.1,
            confidence_level=0.8,
            calibrated_at=str(today_cairo()),
            model_version=self.version,
            inputs_used={
                "tabular": True,
                "text": bool(req.description),
                "images": bool(req.photos_base64),
            },
            warnings=["stub model: placeholder values, not a real estimate"],
        )

    def check(self, req: ListingCheckRequest) -> ListingCheckResponse:
        return ListingCheckResponse(
            suspicion_score=0.0,
            reasons=[],
            model_version=self.version,
            warnings=["stub model: no real checks performed"],
        )

    def market_index(self) -> MarketIndexResponse:
        today = today_cairo()
        points = [MarketIndexPoint(week_start=today, index=100.0, ci_lo=98.0, ci_hi=102.0, n_obs=0)]
        return MarketIndexResponse(
            base_week=today, data_window=f"{today} to {today} (stub)", points=points
        )

    def versions(self) -> dict[str, str]:
        return {"price": self.version, "fraud": self.version}
