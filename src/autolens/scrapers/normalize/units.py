"""Defensive field parsing - handbook Listing 8.2 and section 8.6."""

from __future__ import annotations

import re

from autolens.common.text import to_ascii_digits

_THOUSAND_WORDS = ("alf", "alef", " thousand", "k")


def to_number(text: str | None) -> float | None:
    """Extract the first number from a dirty string, handling Arabic digits."""
    if not text:
        return None
    t = to_ascii_digits(str(text).lower()).replace(",", "").replace("٬", "")
    m = re.search(r"\d+(?:\.\d+)?", t)
    return float(m.group()) if m else None


def parse_mileage_km(raw: str | None) -> float | None:
    """'120,000 km' -> 120000; '120 k' -> 120000; '120 alf' -> 120000."""
    if not raw:
        return None
    t = to_ascii_digits(str(raw).lower()).replace(",", "").replace("٬", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(k|alf|alef|thousand)?\b", t)
    if not m:
        return None
    value = float(m.group(1))
    if m.group(2):
        value *= 1000
    return value


def parse_price_egp(raw: str | None, currency: str = "EGP") -> float | None:
    """Price to EGP numeric. USD/range need a documented rule + flag (8.6)."""
    if not raw:
        return None
    t = to_ascii_digits(str(raw).upper()).replace(",", "").replace("٬", "")
    # Range e.g. '100000-120000': take the midpoint, flag elsewhere.
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", t)]
    if not nums:
        return None
    value = sum(nums) / len(nums)
    if "USD" in t or "$" in str(raw):
        # Documented rule: fixed academic conversion rate, flagged in dq_flags.
        value *= 48.0
    return value


def parse_year(raw: str | None) -> int | None:
    v = to_number(raw)
    if v is None:
        return None
    y = int(v)
    return y if 1950 <= y <= 2030 else None


def map_transmission(raw: str | None) -> str | None:
    if not raw:
        return None
    t = raw.lower()
    if "auto" in t or "اتومات" in t:
        return "automatic"
    if "manual" in t or "عادي" in t or "يدوي" in t:
        return "manual"
    return None


def map_fuel(raw: str | None) -> str | None:
    if not raw:
        return None
    t = raw.lower()
    for token, value in (
        ("natural gas", "cng"),
        ("cng", "cng"),
        ("غاز", "cng"),
        ("diesel", "diesel"),
        ("solar", "diesel"),
        ("سولار", "diesel"),
        ("hybrid", "hybrid"),
        ("هجين", "hybrid"),
        ("electric", "electric"),
        ("كهرب", "electric"),
        ("petrol", "petrol"),
        ("benzine", "petrol"),
        ("gasoline", "petrol"),
        ("بنزين", "petrol"),
    ):
        if token in t:
            return value
    return "other" if t.strip() else None


def map_body(raw: str | None) -> str | None:
    if not raw:
        return None
    t = raw.lower().strip()
    for token, value in (
        ("sedan", "sedan"),
        ("sadan", "sedan"),
        ("سيدان", "sedan"),
        ("hatchback", "hatchback"),
        ("هاتشباك", "hatchback"),
        ("suv", "suv"),
        ("jeep", "suv"),
        ("دفع رباعي", "suv"),
        ("pickup", "pickup"),
        ("truck", "pickup"),
        ("coupe", "coupe"),
        ("wagon", "wagon"),
        ("estate", "wagon"),
        ("van", "van"),
        ("minivan", "van"),
    ):
        if token in t:
            return value
    return None


_UNKNOWN = {"", "unknown", "not specified", "n/a", "none"}


def map_condition(raw: str | None) -> str | None:
    t = (raw or "").strip().lower()
    return t if t in {"new", "used"} else None


def map_color(raw: str | None) -> str | None:
    """Canonical lower-case colour family ('Blue- Navy Blue' -> 'blue'); unknown -> None."""
    t = (raw or "").split("-")[0].strip().lower()
    return None if t in _UNKNOWN else t


def map_payment(raw: str | None) -> str | None:
    t = " ".join((raw or "").lower().split())
    if t in _UNKNOWN:
        return None
    return {
        "cash": "cash",
        "installment": "installment",
        "installments": "installment",
        "cash or installment": "cash_or_installment",
        "cash or installments": "cash_or_installment",
        "exchange": "exchange",
    }.get(t)
