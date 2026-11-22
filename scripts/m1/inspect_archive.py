"""Describe the archive CSV: categorical values, blanks, id shapes (no personal data printed)."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

import pandas as pd

from autolens.common.privacy import contains_contact_info

CATEGORICAL = (
    "source",
    "condition",
    "payment_options",
    "exterior_color",
    "body_type",
    "transmission",
    "fuel_type",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    args = parser.parse_args()
    df = pd.read_csv(
        Path(args.data_dir) / "Egypt_Used_Cars_clean.csv", dtype=str, keep_default_na=False
    )
    print(f"rows={len(df)} columns={list(df.columns)}\n")
    for col in CATEGORICAL:
        if col not in df:
            continue
        blank = float((df[col].str.strip() == "").mean())
        print(f"[{col}] distinct={df[col].nunique()} blank_share={blank:.3f}")
        for value, n in df[col].value_counts().head(8).items():
            print(f"    {n:>6}  {ascii(value[:60])}")
    for col in ("year", "kilometers", "price", "age"):
        if col in df:
            num = pd.to_numeric(df[col], errors="coerce")
            print(
                f"[{col}] numeric_share={num.notna().mean():.3f} "
                + num.describe().round(1).to_dict().__repr__()
            )
    print("\n[contact-like cells by column] (shapes only, digits masked as 9)")
    for col in (c for c in df.columns if c != "url"):
        hits = [v for v in df[col] if len(v) >= 7 and contains_contact_info(v)]
        if hits:
            shapes = Counter(re.sub(r"[A-Za-z]", "a", re.sub(r"\d", "9", v))[:24] for v in hits)
            print(f"  {col}: {len(hits)} cells, top shapes {shapes.most_common(3)}")
    print("\n[id shapes per source]")
    for source, grp in df.groupby("source"):
        shapes = Counter(
            re.sub(r"[A-Za-z]", "a", re.sub(r"\d", "9", v))[:16] for v in grp["listing_id"]
        )
        print(f"  {source}: {shapes.most_common(4)}")
    dup = df.duplicated(
        subset=[c for c in df.columns if c not in {"listing_id", "url"}], keep=False
    )
    print(f"\nrows identical to another row on every attribute except id/url: {int(dup.sum())}")


if __name__ == "__main__":
    main()
