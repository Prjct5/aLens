"""Comparison vectors - handbook 8.7.2.

Three levels per field: 1 = agree, 0 = disagree, -1 = missing. Missing is NOT a
disagreement (section 8.7.2 warning box), so FS/EM estimates m and u only over
observed comparisons for each field.
"""

from __future__ import annotations

import numpy as np

# 8.7.2 features + image evidence. `photo_match` is only populated when the
# image stage produced pHashes (synthetic placeholders or lawful M3 images).
FEATURE_NAMES = (
    "same_year",
    "mileage_close",
    "same_governorate",
    "price_close",
    "same_transmission",
    "same_fuel",
    "same_body",
    "desc_sim",
    "photo_match",
)

PHASH_MAX_HAMMING = 5  # of 64 bits; same car photo survives re-encoding


def _cmp(a, b, equal_fn) -> int:
    if a is None or b is None:
        return -1
    if isinstance(a, str) and a == "":
        return -1
    if isinstance(b, str) and b == "":
        return -1
    return 1 if equal_fn(a, b) else 0


def compare_pair(a: dict, b: dict, desc_threshold: float = 0.35) -> list[int]:
    """Single-pair reference implementation (used by unit tests)."""

    def close_mileage(x, y):
        m = max(x, y)
        return abs(x - y) / m <= 0.05 if m else True

    def close_price(x, y):
        m = max(x, y)
        return abs(x - y) / m <= 0.10 if m else False

    return [
        _cmp(a.get("year"), b.get("year"), lambda x, y: x == y),
        _cmp(a.get("mileage_km"), b.get("mileage_km"), close_mileage),
        _cmp(a.get("governorate_code"), b.get("governorate_code"), lambda x, y: x == y),
        _cmp(a.get("price_egp"), b.get("price_egp"), close_price),
        _cmp(a.get("transmission"), b.get("transmission"), lambda x, y: x == y),
        _cmp(a.get("fuel_type"), b.get("fuel_type"), lambda x, y: x == y),
        _cmp(a.get("body_type"), b.get("body_type"), lambda x, y: x == y),
        _cmp(
            a.get("desc_vec"),
            b.get("desc_vec"),
            lambda x, y: float(np.dot(x, y)) >= desc_threshold,
        ),
        _cmp(a.get("phash"), b.get("phash"), lambda x, y: _hamming(x, y) <= PHASH_MAX_HAMMING),
    ]


def _hamming(a: str, b: str) -> int:
    """Hamming distance between two 16-hex pHash strings."""
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def _numeric_field(listings: list[dict], name: str) -> np.ndarray:
    vals = [r.get(name) for r in listings]
    out = np.full(len(vals), np.nan)
    for i, v in enumerate(vals):
        if v is not None:
            try:
                out[i] = float(v)
            except (TypeError, ValueError):
                pass
    return out


def _string_field(listings: list[dict], name: str) -> np.ndarray:
    vals = [r.get(name) for r in listings]
    return np.array(
        [str(v) if v is not None and str(v) != "" else None for v in vals], dtype=object
    )


def _string_agree(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """1 agree / 0 disagree / -1 missing, vectorised for object arrays."""
    out = np.full(len(a), -1, dtype=np.int8)
    both = (a != None) & (b != None)  # noqa: E711 - object-array None check
    out[both] = (a[both] == b[both]).astype(np.int8)
    return out


def build_matrix(
    listings: list[dict], pairs: list[tuple[int, int]], desc_threshold: float = 0.35
) -> tuple[np.ndarray, list[str]]:
    """Vectorised version of compare_pair over all candidate pairs."""
    pairs_arr = np.asarray(pairs, dtype=np.int64).reshape(-1, 2)
    ia, ib = pairs_arr[:, 0], pairs_arr[:, 1]
    K = np.empty((len(pairs), len(FEATURE_NAMES)), dtype=np.int8)

    year = _numeric_field(listings, "year")
    km = _numeric_field(listings, "mileage_km")
    price = _numeric_field(listings, "price_egp")
    gov = _string_field(listings, "governorate_code")
    trans = _string_field(listings, "transmission")
    fuel = _string_field(listings, "fuel_type")
    body = _string_field(listings, "body_type")

    def numeric_agree(a, b, tol_fn):
        out = np.full(len(a), -1, dtype=np.int8)
        both = ~np.isnan(a) & ~np.isnan(b)
        out[both] = tol_fn(a[both], b[both]).astype(np.int8)
        return out

    K[:, 0] = numeric_agree(year[ia], year[ib], lambda x, y: x == y)

    def km_close(x, y):
        m = np.maximum(x, y)
        ratio = np.divide(np.abs(x - y), m, out=np.zeros_like(m), where=m > 0)
        return np.where(m > 0, ratio <= 0.05, True)

    K[:, 1] = numeric_agree(km[ia], km[ib], km_close)
    K[:, 2] = _string_agree(gov[ia], gov[ib])

    def price_close(x, y):
        m = np.maximum(x, y)
        ratio = np.divide(np.abs(x - y), m, out=np.full_like(m, np.inf), where=m > 0)
        return np.where(m > 0, ratio <= 0.10, False)

    K[:, 3] = numeric_agree(price[ia], price[ib], price_close)
    K[:, 4] = _string_agree(trans[ia], trans[ib])
    K[:, 5] = _string_agree(fuel[ia], fuel[ib])
    K[:, 6] = _string_agree(body[ia], body[ib])
    K[:, 7] = -1  # no descriptions in the supplied archives (M4)
    K[:, 8] = _phash_agree(listings, ia, ib)
    return K, list(FEATURE_NAMES)


def _phash_agree(listings: list[dict], ia: np.ndarray, ib: np.ndarray) -> np.ndarray:
    """1 if pHashes are within PHASH_MAX_HAMMING, 0 if different, -1 if missing."""
    out = np.full(len(ia), -1, dtype=np.int8)
    for idx, (x, y) in enumerate(zip(ia, ib, strict=True)):
        hx = listings[int(x)].get("phash")
        hy = listings[int(y)].get("phash")
        if hx and hy:
            out[idx] = 1 if _hamming(hx, hy) <= PHASH_MAX_HAMMING else 0
    return out
