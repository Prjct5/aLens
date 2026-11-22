"""Quality flags - handbook 8.6. Flags mark suspicious values, never delete rows."""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np


def median(values) -> float:
    return float(np.median(values)) if len(values) else 0.0


def modified_zscore(value: float, med: float, mad: float, spread: float) -> float:
    """z_mod = 0.6745 * (x - median) / MAD, MAD = median(|x - median|) (8.6)."""
    if mad > 0:
        return 0.6745 * (value - med) / mad
    return 0.6745 * (value - med) / (spread or 1.0)


def add_price_outlier_flags(rows: list[dict], group_key="make_model_year") -> None:
    """Flag |z_mod| > 3.5 on ln(price) inside (model, year) groups.

    Group medians/MADs are computed once per group (not per row) so the check
    stays linear in the number of listings.
    """
    groups: dict = defaultdict(list)
    for r in rows:
        p = r.get("price_egp")
        if p and p > 0:
            groups[r.get(group_key)].append(math.log(p))
    stats = {}
    for key, vals in groups.items():
        med = median(vals)
        mad = median([abs(x - med) for x in vals])
        if mad == 0:
            # Degenerate group (e.g. 10 identical prices + one 9M outlier):
            # scale by 1% of the median so a single extreme value is flagged.
            mad = max(abs(med) * 0.001, 1e-6)
        stats[key] = (med, mad, float(np.std(vals)))
    for r in rows:
        p = r.get("price_egp")
        if not p or p <= 0:
            r["dq_flags"]["price_missing"] = True
            continue
        med, mad, spread = stats[r.get(group_key)]
        z = modified_zscore(math.log(p), med, mad, spread)
        if abs(z) > 3.5:
            r["dq_flags"]["price_outlier"] = True
        if p < 10_000:
            r["dq_flags"]["price_below_floor"] = True
        if p > 50_000_000:
            r["dq_flags"]["price_above_ceiling"] = True


def check_mileage(r: dict) -> None:
    km, year = r.get("mileage_km"), r.get("year")
    if km is None:
        r["dq_flags"]["mileage_missing"] = True
        return
    if km < 0:
        r["dq_flags"]["mileage_negative"] = True
    if km > 600_000:
        r["dq_flags"]["mileage_implausible_high"] = True
    if year and 2026 - year >= 2 and 0 < km < 100:
        r["dq_flags"]["mileage_implausible_low"] = True
    if km in (1.0, 11.0, 111.0, 11111.0, 111111.0):
        r["dq_flags"]["mileage_placeholder"] = True


def check_year(r: dict, valid_range: tuple[int, int] = (1950, 2027)) -> None:
    y = r.get("year")
    if y is None:
        r["dq_flags"]["year_invalid"] = True
    elif not (valid_range[0] <= y <= valid_range[1]):
        r["dq_flags"]["year_out_of_range"] = True
