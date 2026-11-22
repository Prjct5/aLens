"""Look for the missing hatla2ee ids behind dubizzle's `h<id>` listings in the other CSV files.

Prints file names, column names and match counts only (never cell values).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    main_csv = data_dir / "Egypt_Used_Cars_clean.csv"
    df = pd.read_csv(main_csv, dtype=str, keep_default_na=False)
    dub = df[(df["source"] == "dubizzle") & df["listing_id"].str.fullmatch(r"h\d+")]
    wanted = set(dub["listing_id"].str[1:])
    in_archive = set(df.loc[df["source"] == "hatla2ee", "listing_id"])
    missing = wanted - in_archive
    print(
        f"h-prefixed dubizzle ids: {len(wanted)}; matched in archive: "
        f"{len(wanted & in_archive)}; unmatched: {len(missing)}"
    )
    print()
    for path in sorted(data_dir.glob("*.csv")):
        if path.resolve() == main_csv.resolve():
            continue
        try:
            other = pd.read_csv(path, dtype=str, keep_default_na=False, low_memory=False)
        except (UnicodeDecodeError, pd.errors.ParserError) as exc:
            print(f"{path.name}: unreadable ({type(exc).__name__})")
            continue
        print(f"{path.name}: rows={len(other)} columns={list(other.columns)}")
        hits = {}
        for col in other.columns:
            n = int(other[col].isin(missing).sum())
            if n:
                hits[col] = n
        print(f"    columns containing unmatched h-ids (column: matches): {hits or 'none'}")
        print()


if __name__ == "__main__":
    main()
