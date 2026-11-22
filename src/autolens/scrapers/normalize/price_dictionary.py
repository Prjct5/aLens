"""Seed the canonical make/model dictionary from an official price list (R8, 8.5).

The current dictionary was mined from used-car listings. Handbook R8 requires an
official *new-car price list* as the source of canonical spellings. This module
accepts such a list (CSV: make, model, price_egp, [year]) and produces clean
make/model rows merged into ``data_reference/models.csv``; existing aliases stay
valid (they remain evidence from the archive).

No official list was supplied, so nothing is applied automatically. A team member
must place an approved file at ``data_reference/official_new_car_prices.csv`` and
run ``python scripts/seed_dictionary_from_prices.py``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from autolens.common.text import normalize_arabic
from autolens.scrapers.normalize.dictionary import ModelDictionary

REQUIRED_COLUMNS = {"make", "model", "price_egp"}
FIELDS = ("model_id", "make", "model", "trim", "body_type", "segment", "n_observations")


def load_price_list(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"price list missing columns: {sorted(missing)}")
    df["make"] = df["make"].map(lambda s: normalize_arabic(str(s)).title())
    df["model"] = df["model"].map(lambda s: normalize_arabic(str(s)).title())
    return df.dropna(subset=["price_egp"])


def seed_from_price_list(price_df: pd.DataFrame, reference_dir: Path) -> pd.DataFrame:
    """Merge official canonical names into models.csv, preserving alias evidence.

    Existing integer model ids are kept; new official names get fresh ids.
    Returns the updated models DataFrame.
    """
    reference_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    if (reference_dir / "models.csv").exists() and (reference_dir / "aliases.csv").exists():
        existing = ModelDictionary.load(reference_dir)
        records = [dict(row) for row in existing.models.values()]
    seen = {ModelDictionary.key(r["make"], r["model"]) for r in records}
    next_id = max((int(r["model_id"]) for r in records), default=0) + 1

    for row in price_df.itertuples(index=False):
        key = ModelDictionary.key(row.make, row.model)
        if key in seen:
            continue
        records.append(
            {
                "model_id": next_id,
                "make": row.make,
                "model": row.model,
                "trim": "",
                "body_type": "",
                "segment": "",
                "n_observations": 0,
            }
        )
        seen.add(key)
        next_id += 1

    out = pd.DataFrame(records)[list(FIELDS)]
    out.to_csv(reference_dir / "models.csv", index=False)
    return out
