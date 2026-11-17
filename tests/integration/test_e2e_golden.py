from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from autolens.api.main import create_app
from autolens.common.config import Settings
from autolens.common.stage import make_context
from autolens.pipelines.stages import STAGES

SAMPLE_REQUEST = {"make": "Toyota", "model": "Corolla", "year": 2018, "mileage_km": 90000}


def run_all(run_date, ctx):
    return {name: fn(run_date, ctx) for name, fn in STAGES}


def counts(results):
    return {name: (r.rows_in, r.rows_out) for name, r in results.items()}


def test_golden_pipeline() -> None:
    run_date = date(2026, 1, 15)
    ctx = make_context(Settings(_env_file=None, environment="dev"), models="stub", connect=False)

    first = run_all(run_date, ctx)
    assert all(r.rows_out >= 0 for r in first.values())

    client = TestClient(create_app(ctx))
    r = client.post("/price/estimate", json=SAMPLE_REQUEST)
    assert r.status_code == 200 and r.json()["lo"] < r.json()["hi"]
    assert client.get("/market/index").status_code == 200
    assert client.get("/listings/hatla2ee:1000001/duplicates").status_code == 200

    second = run_all(run_date, ctx)
    assert counts(second) == counts(first)
