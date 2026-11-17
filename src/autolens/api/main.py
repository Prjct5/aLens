from __future__ import annotations

import hashlib
import uuid
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from autolens.api.models import ModelProvider, StubModelProvider
from autolens.api.ratelimit import RateLimiter
from autolens.common.config import Settings, get_settings
from autolens.common.schemas import CONTRACT_VERSION
from autolens.common.schemas.api import (
    DuplicatesResponse,
    ErrorBody,
    ListingCheckRequest,
    ListingCheckResponse,
    MarketIndexResponse,
    PriceEstimateRequest,
    PriceEstimateResponse,
)
from autolens.common.stage import RunContext

API_VERSION = "1.0"


def _error(status: int, code: str, message: str, request: Request) -> JSONResponse:
    body = ErrorBody(
        code=code,
        message=message,
        request_id=getattr(request.state, "request_id", ""),
    )
    return JSONResponse(status_code=status, content=body.model_dump())


def create_app(ctx: RunContext | None = None, models: ModelProvider | None = None) -> FastAPI:
    settings: Settings = ctx.settings if ctx else get_settings()
    provider: ModelProvider = models or StubModelProvider()
    limiter = RateLimiter(settings.api_rate_limit_per_minute)

    app = FastAPI(
        title="AutoLens Egypt API",
        version=API_VERSION,
        description="Price ranges, listing checks, duplicates and market index (Egypt).",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.dashboard_origin],
        allow_methods=["GET", "POST"],
        allow_headers=["X-API-Key", "Content-Type", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error(422, "validation_error", "Invalid request body or parameters.", request)

    @app.exception_handler(HTTPException)
    async def http_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return _error(exc.status_code, f"http_{exc.status_code}", str(exc.detail), request)

    def require_api_key(request: Request) -> str:
        hashes = settings.api_key_hashes
        key = request.headers.get("X-API-Key", "")
        if not hashes and settings.is_dev:
            return "dev"
        digest = hashlib.sha256(key.encode()).hexdigest()
        if not key or digest not in hashes:
            raise HTTPException(status_code=401, detail="Missing or invalid API key.")
        if not limiter.allow(digest):
            raise HTTPException(status_code=429, detail="Rate limit exceeded.")
        return digest

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "api_version": API_VERSION,
            "contract_version": CONTRACT_VERSION,
            "models": provider.versions(),
        }

    router = APIRouter(dependencies=[Depends(require_api_key)])

    @router.post("/price/estimate", response_model=PriceEstimateResponse, tags=["price"])
    def price_estimate(req: PriceEstimateRequest) -> PriceEstimateResponse:
        return provider.estimate(req)

    @router.post("/listings/check", response_model=ListingCheckResponse, tags=["listings"])
    def listings_check(req: ListingCheckRequest) -> ListingCheckResponse:
        return provider.check(req)

    @router.get(
        "/listings/{listing_id}/duplicates", response_model=DuplicatesResponse, tags=["listings"]
    )
    def listing_duplicates(listing_id: str) -> DuplicatesResponse:
        return DuplicatesResponse(listing_key=listing_id)

    @router.get("/market/index", response_model=MarketIndexResponse, tags=["market"])
    def market_index() -> MarketIndexResponse:
        return provider.market_index()

    app.include_router(router)
    return app
