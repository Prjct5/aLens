from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

from autolens.scrapers.normalize.units import map_color, map_condition, map_fuel, map_payment
from autolens.scrapers.run import run_normalize, run_scrape
from tests.integration.test_m1_golden import FIXTURE, RUN_DATE, _context


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Benzine", "petrol"),
        ("Natural Gas", "cng"),
        ("CNG", "cng"),
        ("Diesel", "diesel"),
        ("Hybrid", "hybrid"),
        ("Electric", "electric"),
        ("something else", "other"),
        (None, None),
    ],
)
def test_fuel_mapping_keeps_natural_gas_separate(raw, expected) -> None:
    assert map_fuel(raw) == expected


def test_condition_color_payment_mappers() -> None:
    assert map_condition("New") == "new" and map_condition("Used") == "used"
    assert map_condition("Unknown") is None and map_condition(None) is None
    assert map_color("Blue- Navy Blue") == "blue" and map_color("Black") == "black"
    assert map_color("Unknown") is None and map_color("") is None
    assert map_payment("Cash or Installment") == "cash_or_installment"
    assert map_payment("Installments") == "installment" and map_payment("Cash") == "cash"
    assert map_payment("Exchange") == "exchange"
    assert map_payment("Not specified") is None and map_payment(None) is None


def test_new_columns_flow_from_archive_to_normalized(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    csv = ctx.settings.data_dir / "Egypt_Used_Cars_clean.csv"
    df = pd.read_csv(csv, dtype=str, keep_default_na=False)
    df["condition"] = ["New" if i % 2 else "Used" for i in range(len(df))]
    df["exterior_color"] = "Blue- Navy Blue"
    df["payment_options"] = "Cash or Installment"
    df.loc[0, "fuel_type"] = "Natural Gas"
    df.to_csv(csv, index=False)

    run_scrape(RUN_DATE, ctx)
    parsed = ctx.db.query(
        "SELECT condition_raw, color_raw, payment_raw FROM staging_parsed_listing"
    )
    assert {r["condition_raw"] for r in parsed} == {"New", "Used"}
    run_normalize(RUN_DATE, ctx)
    rows = ctx.db.query(
        "SELECT condition, color, payment_option, fuel_type FROM staging_normalized_listing"
    )
    assert {r["condition"] for r in rows} == {"new", "used"}
    assert {r["color"] for r in rows} == {"blue"}
    assert {r["payment_option"] for r in rows} == {"cash_or_installment"}
    assert "cng" in {r["fuel_type"] for r in rows}


def test_sample_without_new_columns_still_parses(tmp_path: Path) -> None:
    assert "condition" not in pd.read_csv(FIXTURE).columns
    ctx = _context(tmp_path)
    run_scrape(RUN_DATE, ctx)
    run_normalize(RUN_DATE, ctx)
    rows = ctx.db.query("SELECT condition, color, payment_option FROM staging_normalized_listing")
    assert rows and all(r["condition"] is None and r["payment_option"] is None for r in rows)


def test_cross_post_checker_reports_matches(tmp_path: Path, capsys, monkeypatch) -> None:
    rows = [
        {
            "listing_id": "7000001",
            "source": "hatla2ee",
            "make": "Kia",
            "model": "Rio",
            "year": "2018",
            "kilometers": "90000",
            "price": "500000",
            "transmission": "Automatic",
            "fuel_type": "Benzine",
        },
        {
            "listing_id": "h7000001",
            "source": "dubizzle",
            "make": "Kia",
            "model": "Rio",
            "year": "2018",
            "kilometers": "91000",
            "price": "495000",
            "transmission": "Automatic",
            "fuel_type": "Benzine",
        },
        {
            "listing_id": "h9999999",
            "source": "dubizzle",
            "make": "Kia",
            "model": "Rio",
            "year": "2018",
            "kilometers": "1",
            "price": "1",
            "transmission": "Automatic",
            "fuel_type": "Benzine",
        },
    ]
    pd.DataFrame(rows).to_csv(tmp_path / "Egypt_Used_Cars_clean.csv", index=False)
    path = Path(__file__).resolve().parents[3] / "scripts" / "m1" / "check_cross_posts.py"
    spec = importlib.util.spec_from_file_location("check_cross_posts", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(sys, "argv", ["x", "--data-dir", str(tmp_path)])
    module.main()
    out = capsys.readouterr().out
    assert "dubizzle_h_prefixed_ids: 2" in out
    assert "h_ids_also_hatla2ee_ids: 1" in out
    assert "share_same_make: 1.0" in out
