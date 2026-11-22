"""Synthetic image pipeline + photo_match feature (honest placeholder path)."""

from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image

from autolens.linkage.comparison import build_matrix, compare_pair
from autolens.scrapers.images import image_id_from_bytes, phash
from autolens.scrapers.synthetic_images import (
    MANIFEST_NOTE,
    SYNTHETIC_STATUS,
    image_seed,
    synthetic_image_bytes,
)


def test_synthetic_image_is_deterministic_and_seed_sensitive():
    a = synthetic_image_bytes("Toyota|Camry|2020|AT|petrol|sedan")
    b = synthetic_image_bytes("Toyota|Camry|2020|AT|petrol|sedan")
    c = synthetic_image_bytes("BMW|5 Series|2020|AT|diesel|sedan")
    assert a == b
    assert a != c
    assert image_id_from_bytes(a) == image_id_from_bytes(b)
    assert len(image_id_from_bytes(a)) == 64


def test_seed_ignores_source_and_price():
    base = {
        "make_canon": "Toyota",
        "model_canon": "Camry",
        "year": 2020,
        "transmission": "AT",
        "fuel_type": "petrol",
        "body_type": "sedan",
    }
    one = dict(base, source="hatla2ee", price_egp=100000)
    two = dict(base, source="dubizzle", price_egp=150000)
    assert image_seed(one) == image_seed(two)


def test_phash_of_identical_seed_is_equal():
    a = synthetic_image_bytes("seed-1")
    b = synthetic_image_bytes("seed-1")
    pa = phash(np.asarray(Image.open(BytesIO(a)).convert("RGB")))
    pb = phash(np.asarray(Image.open(BytesIO(b)).convert("RGB")))
    assert pa == pb and len(pa) == 16


def test_photo_match_feature_uses_phash():
    listings = [
        {
            "phash": "0000000000000000",
            "year": 2020,
            "mileage_km": 10000,
            "price_egp": 100000,
            "governorate_code": "C",
            "transmission": "AT",
            "fuel_type": "petrol",
            "body_type": "sedan",
        },
        {
            "phash": "0000000000000000",
            "year": 2020,
            "mileage_km": 11000,
            "price_egp": 101000,
            "governorate_code": "C",
            "transmission": "AT",
            "fuel_type": "petrol",
            "body_type": "sedan",
        },
        {
            "phash": "ffffffffffffffff",
            "year": 2015,
            "mileage_km": 200000,
            "price_egp": 50000,
            "governorate_code": "A",
            "transmission": "MT",
            "fuel_type": "diesel",
            "body_type": "hatchback",
        },
    ]
    K, names = build_matrix(listings, [(0, 1), (0, 2)])
    assert names[-1] == "photo_match"
    assert K[0, -1] == 1  # same pHash -> match
    assert K[1, -1] == 0  # different pHash -> disagree
    assert compare_pair(listings[0], listings[1])[-1] == 1
    assert compare_pair({"phash": None}, {})[-1] == -1  # missing is not disagreement
    assert SYNTHETIC_STATUS == "synthetic_placeholder"
    assert "NOT_A_REAL" in MANIFEST_NOTE
