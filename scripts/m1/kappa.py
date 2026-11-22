"""Cohen's kappa for two human annotators (handbook 8.8 step 3).

Usage:
  python scripts/kappa.py annotator1.csv annotator2.csv

Each CSV must have columns: pair_id, label  (label in {match, non_match, unsure}).
`unsure` pairs are excluded from the headline metric (8.8).
"""

from __future__ import annotations

import sys

import pandas as pd
from sklearn.metrics import cohen_kappa_score


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    a = pd.read_csv(sys.argv[1]).set_index("pair_id")["label"]
    b = pd.read_csv(sys.argv[2]).set_index("pair_id")["label"]
    common = a.index.intersection(b.index)
    a, b = a.loc[common], b.loc[common]
    valid = a.isin(["match", "non_match"]) & b.isin(["match", "non_match"])
    a, b = a[valid], b[valid]
    print(f"overlapping pairs: {len(common)}, usable (excluding unsure): {len(a)}")
    print(f"Cohen's kappa: {cohen_kappa_score(a, b):.3f}")
    print(f"raw agreement: {(a == b).mean():.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
