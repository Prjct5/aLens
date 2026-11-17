from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

from autolens.api.main import create_app
from autolens.api.ratelimit import RateLimiter
from autolens.common.config import Settings
from autolens.common.logging import get_logger
from autolens.common.stage import RunContext

SAMPLE = {"make": "Toyota", "model": "Corolla", "year": 2018, "mileage_km": 90000}


def make_client(**overrides: object) -> TestClient:
    settings = Settings(_env_file=None, **overrides)  # type: ignore[arg-type]
    ctx = RunContext(settings=settings, log=get_logger("test"))
    return TestClient(create_app(ctx))


def test_health_is_open() -> None:
    r = make_client(environment="production", api_keys_sha256="x").get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_estimate_returns_interval_never_point_only() -> None:
    r = make_client().post("/price/estimate", json=SAMPLE)
    body = r.json()
    assert r.status_code == 200
    assert body["lo"] < body["median"] < body["hi"]
    assert body["currency"] == "EGP" and "disclaimer" in body


def test_validation_error_uses_error_body() -> None:
    r = make_client().post("/price/estimate", json={**SAMPLE, "year": 1500})
    assert r.status_code == 422
    assert set(r.json()) >= {"code", "message", "request_id"}
    assert r.headers["X-Request-ID"] == r.json()["request_id"]


def test_auth_required_outside_dev() -> None:
    key = "secret-key"
    digest = hashlib.sha256(key.encode()).hexdigest()
    client = make_client(environment="production", api_keys_sha256=digest)
    assert client.post("/price/estimate", json=SAMPLE).status_code == 401
    assert (
        client.post("/price/estimate", json=SAMPLE, headers={"X-API-Key": "bad"}).status_code == 401
    )
    ok = client.post("/price/estimate", json=SAMPLE, headers={"X-API-Key": key})
    assert ok.status_code == 200


def test_rate_limit_per_key() -> None:
    key = "k"
    digest = hashlib.sha256(key.encode()).hexdigest()
    client = make_client(
        environment="production", api_keys_sha256=digest, api_rate_limit_per_minute=2
    )
    codes = [client.get("/market/index", headers={"X-API-Key": key}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_other_endpoints_respond() -> None:
    c = make_client()
    assert c.get("/market/index").status_code == 200
    assert c.get("/listings/hatla2ee:1/duplicates").json()["listing_key"] == "hatla2ee:1"
    chk = {"make": "Kia", "model": "Rio", "year": 2020, "mileage_km": 10, "asking_price_egp": 1}
    assert c.post("/listings/check", json=chk).status_code == 200


def test_rate_limiter_window() -> None:
    now = [0.0]
    rl = RateLimiter(1, clock=lambda: now[0])
    assert rl.allow("a") and not rl.allow("a")
    now[0] = 61
    assert rl.allow("a")
