"""Apply an approved official new-car price list to the canonical dictionary.

Usage:
    python scripts/seed_dictionary_from_prices.py [path/to/price_list.csv]

Default path: data_reference/official_new_car_prices.csv (not supplied — R8 gap).
The file must have columns: make, model, price_egp.
"""

from __future__ import annotations

import sys
from pathlib import Path

from autolens.scrapers.normalize.price_dictionary import load_price_list, seed_from_price_list

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else (ROOT / "data_reference" / "official_new_car_prices.csv")
    )
    if not path.exists():
        print(
            f"official price list not supplied: {path}\n"
            "R8 remains partially met: canonical names are mined from used-car listings.\n"
            "Obtain a lawful weekly price list, save it at that path, re-run this script."
        )
        return 1
    prices = load_price_list(path)
    out = seed_from_price_list(prices, ROOT / "data_reference")
    print(f"seeded {len(out)} canonical make/model rows from {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
