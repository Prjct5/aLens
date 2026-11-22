"""Explain why known cross-posts were (not) linked. Prints aggregates and per-pair numbers only.

Run after verify_m1.py (needs its work dir):
  python scripts/m1/diagnose_pairs.py --data-dir <archive folder> --work-dir work
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd


def known_pairs(data_dir: Path) -> list[tuple[str, str]]:
    df = pd.read_csv(data_dir / "Egypt_Used_Cars_clean.csv", dtype=str, keep_default_na=False)
    dub = df[(df["source"] == "dubizzle") & df["listing_id"].str.fullmatch(r"h\d+")]
    hat = set(df.loc[df["source"] == "hatla2ee", "listing_id"])
    return [(f"dubizzle:{i}", f"hatla2ee:{i[1:]}") for i in dub["listing_id"] if i[1:] in hat]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--work-dir", default="work")
    parser.add_argument("--run-date", default="2026-01-15")
    args = parser.parse_args()

    os.environ["PROJECT_ROOT"] = str(Path(args.work_dir).resolve())
    os.environ["DATA_DIR"] = str(Path(args.data_dir).resolve())

    from autolens.linkage.blocking import generate_candidates
    from autolens.linkage.cluster import DSU, components, split_large_components
    from autolens.linkage.comparison import build_matrix
    from autolens.linkage.fs import fs_em, match_weight
    from autolens.linkage.run import _load_listings
    from autolens.scrapers.local_run import build_local_context
    from autolens.scrapers.settings import M1Settings

    settings = M1Settings.from_env()
    ctx = build_local_context(settings)
    run_date = date.fromisoformat(args.run_date)
    listings = _load_listings(ctx, run_date)
    n = len(listings)
    index = {r["listing_key"]: i for i, r in enumerate(listings)}

    metrics = json.loads((settings.output_dir / "linkage_metrics.json").read_text("utf-8"))
    upper = float(metrics["t_upper"])
    pairs = generate_candidates(listings, max_pairs=settings.max_candidate_pairs)
    G, names = build_matrix(listings, pairs)
    m, u, _, _ = fs_em(G, p0=0.001, m0=0.9, u0=0.1)
    w = match_weight(G, m, u)

    pa = np.asarray(pairs, dtype=np.int64)
    codes = pa[:, 0] * n + pa[:, 1]
    accepted = np.flatnonzero(w >= upper)
    keys = [r["listing_key"] for r in listings]
    edges = [(keys[pa[r, 0]], keys[pa[r, 1]], float(w[r])) for r in accepted]
    comps = components(edges)
    comp_size = {k: len(c) for c in comps for k in c}
    kept, dropped = split_large_components(edges, 9)
    final = DSU()
    for a, b, _ in kept:
        final.union(a, b)

    print(f"listings={n} candidate_pairs={len(pairs)} t_upper={upper:.3f}")
    print(f"accepted_edges={len(accepted)} components_before_cap={len(comps)}")
    sizes = sorted((len(c) for c in comps), reverse=True)
    print(f"largest_components_before_cap={sizes[:10]}")
    print(f"components_over_cap={sum(1 for s in sizes if s > 9)} edges_dropped_by_cap={dropped}")
    top = Counter(round(float(x), 3) for x in w[accepted]).most_common(3)
    print(f"most_common_accepted_weights(weight,count)={top}")
    print(
        "feature m/u:",
        {
            nm: (round(float(a), 3), round(float(b), 3))
            for nm, a, b in zip(names, m, u, strict=True)
        },
    )

    outcome: Counter[str] = Counter()
    print("\nknown cross-post pairs:")
    for k, (ka, kb) in enumerate(known_pairs(Path(args.data_dir))):
        i, j = sorted((index[ka], index[kb]))
        code = i * n + j
        pos = int(np.searchsorted(codes, code))
        if pos >= len(codes) or codes[pos] != code:
            outcome["not_a_candidate_pair (blocking)"] += 1
            print(f"  pair {k:02d}: NOT in candidate pairs (different block)")
            continue
        weight = float(w[pos])
        pattern = dict(zip(names, (int(x) for x in G[pos]), strict=True))
        rank = float((w >= weight).mean())
        if weight < upper:
            outcome["below_threshold"] += 1
            verdict = "below threshold"
        elif final.find(ka) != final.find(kb):
            outcome["accepted_but_split_by_cap"] += 1
            verdict = "accepted, then split by cluster cap"
        else:
            outcome["linked"] += 1
            verdict = "linked"
        print(
            f"  pair {k:02d}: weight={weight:.2f} top_share={rank:.4f} "
            f"component_size={comp_size.get(ka, 1)} -> {verdict}; pattern={pattern}"
        )
    print("\noutcomes:", dict(outcome))


if __name__ == "__main__":
    main()
