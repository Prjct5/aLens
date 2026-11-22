"""Blocking tests (handbook 8.7.1)."""

from autolens.linkage.blocking import (
    generate_candidates,
    pairs_completeness,
    reduction_ratio,
)


def test_blocking_finds_year_plus_minus_one_and_skips_self():
    listings = [
        {"listing_key": "a:1", "make_canon": "Kia", "model_canon": "Rio", "year": 2013},
        {"listing_key": "b:1", "make_canon": "Kia", "model_canon": "Rio", "year": 2014},
        {"listing_key": "c:1", "make_canon": "BMW", "model_canon": "X5", "year": 2013},
        {"listing_key": "a:1", "make_canon": "Kia", "model_canon": "Rio", "year": 2013},
    ]
    pairs = generate_candidates(listings)
    assert (0, 1) in pairs  # year 2013 vs 2014 -> within +/-1
    assert (0, 3) not in pairs  # same listing_key must be skipped
    assert (0, 2) not in pairs  # different make/model
    assert reduction_ratio(len(pairs), len(listings)) == pytest_approx(1 - len(pairs) / 6)


def test_metrics():
    assert pairs_completeness({(0, 1), (1, 2)}, {(0, 1), (2, 3)}) == 0.5
    assert reduction_ratio(0, 100) == 1.0


def pytest_approx(value):
    class _A:
        def __eq__(self, other):
            return abs(other - value) < 1e-9

    return _A()
