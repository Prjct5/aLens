"""Normalisation, string similarity and quality-flag tests (handbook 6.3-6.6, 8.6)."""

from autolens.common.text import normalize_arabic, similarity, slev, sng
from autolens.scrapers.normalize.dictionary import ModelDictionary
from autolens.scrapers.normalize.flags import (
    add_price_outlier_flags,
    check_mileage,
    modified_zscore,
)
from autolens.scrapers.normalize.units import (
    map_body,
    map_fuel,
    map_transmission,
    parse_mileage_km,
    parse_price_egp,
    parse_year,
)


def test_arabic_digit_and_variant_normalisation():
    assert normalize_arabic("كورولا ٢٠١٨") == "كورولا 2018"
    assert normalize_arabic("الإسكندرية") == "الاسكندريه"
    assert normalize_arabic("Corolla, 2018!") == "corolla 2018"


def test_similarity_measures():
    assert slev("corolla", "coroloa") > 0.8
    assert sng("corolla toyota", "toyota corolla") > 0.5  # robust to word order
    assert similarity("Kia Rio", "Kia  Rio") == 1.0


def test_unit_parsing():
    assert parse_mileage_km("120,000 km") == 120000
    assert parse_mileage_km("120 alf") == 120000
    assert parse_mileage_km("١٢٠٬٠٠٠ كم") == 120000
    assert parse_price_egp("530,000 EGP") == 530000
    assert parse_year("2018") == 2018
    assert parse_year("0") is None
    assert map_transmission("اتوماتيك") == "automatic"
    assert map_fuel("Benzine") == "petrol"
    assert map_body("Hatchback") == "hatchback"


def test_mad_outlier_flag():
    assert modified_zscore(100, 50, 10, 5) == pytest_approx(3.3725)
    rows = [
        {"price_egp": 100000.0, "make_model_year": "Kia|Rio|2015", "dq_flags": {}}
        for _ in range(10)
    ]
    rows.append({"price_egp": 9_000_000.0, "make_model_year": "Kia|Rio|2015", "dq_flags": {}})
    add_price_outlier_flags(rows)
    assert rows[-1]["dq_flags"].get("price_outlier")
    assert not rows[0]["dq_flags"].get("price_outlier")


def test_multiword_make_is_not_split():
    class L:
        def __init__(self, make, model):
            self.make_raw, self.model_raw = make, model

    listings = [
        L("Land Rover", "Range Rover Sport"),
        L("Alfa Romeo", "Giulia"),
        L("Aston Martin", "DB11"),
        L("Great Wall", "Haval H6"),
        L("Rolls Royce", "Ghost"),
    ]
    d = ModelDictionary().fit(listings)
    for make, model in [(item.make_raw, item.model_raw) for item in listings]:
        mid, _ = d.map(make, model)
        assert d.canonical(mid)[:2] == (make, model)


def test_mileage_flags():
    r = {"mileage_km": 1.0, "year": 2010, "dq_flags": {}}
    check_mileage(r)
    assert r["dq_flags"]["mileage_placeholder"]
    assert r["dq_flags"]["mileage_implausible_low"]


def pytest_approx(value, tol=1e-3):
    class _A:
        def __eq__(self, other):
            return abs(other - value) < tol

    return _A()
