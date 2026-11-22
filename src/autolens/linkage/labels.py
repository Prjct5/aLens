"""Evaluation set construction - handbook 8.8.

The handbook asks two people to label ~1,000 pairs. For this run we generate a
*provisional silver set* from deterministic high-confidence rules and provide a
labelling view for human verification. The silver labels are documented as weak
supervision in docs/report/RQ1.md; they are used for threshold selection, never
for training the FS model (which is unsupervised).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def _numeric(listings, name):
    out = np.full(len(listings), np.nan)
    for i, r in enumerate(listings):
        v = r.get(name)
        if v is not None:
            out[i] = float(v)
    return out


def build_labels(
    listings: list[dict],
    pairs: list[tuple[int, int]],
    weights: np.ndarray,
    n_target: int = 3000,
    seed: int = 42,
) -> pd.DataFrame:
    """Vectorised high-confidence silver labels, stratified by source x weight bin."""
    rng = np.random.default_rng(seed)
    arr = np.asarray(pairs, dtype=np.int64).reshape(-1, 2)
    ia, ib = arr[:, 0], arr[:, 1]
    n = len(pairs)

    price = _numeric(listings, "price_egp")
    km = _numeric(listings, "mileage_km")
    year = _numeric(listings, "year")
    make = np.array([str(r.get("make_canon") or "") for r in listings])
    model = np.array([str(r.get("model_canon") or "") for r in listings])
    source = np.array([str(r.get("source") or "") for r in listings])
    trans = np.array([str(r.get("transmission") or "") for r in listings])
    fuel = np.array([str(r.get("fuel_type") or "") for r in listings])
    body = np.array([str(r.get("body_type") or "") for r in listings])

    pa, pb = price[ia], price[ib]
    ma, mb = km[ia], km[ib]
    price_ok = (
        ~np.isnan(pa)
        & ~np.isnan(pb)
        & (pa > 10_000)
        & (pb > 10_000)
        & (np.abs(pa - pb) / np.maximum(pa, pb) <= 0.10)
    )
    mmax = np.maximum(ma, mb)
    km_ratio = np.divide(np.abs(ma - mb), mmax, out=np.ones_like(mmax), where=mmax > 0)
    km_ok = ~np.isnan(ma) & ~np.isnan(mb) & (mmax > 0) & (km_ratio <= 0.05)
    attrs_ok = (
        (make[ia] == make[ib])
        & (model[ia] == model[ib])
        & (year[ia] == year[ib])
        & (trans[ia] == trans[ib])
        & (fuel[ia] == fuel[ib])
        & (body[ia] == body[ib])
        & (trans[ia] != "")
        & (fuel[ia] != "")
        & (body[ia] != "")
    )
    positive = (source[ia] != source[ib]) & price_ok & km_ok & attrs_ok

    certain_negative = (make[ia] != make[ib]) | (model[ia] != model[ib])
    gap = np.abs(ma - mb) / np.maximum(np.maximum(ma, mb), 1)
    hard_negative = ~certain_negative & ~np.isnan(ma) & ~np.isnan(mb) & (gap > 0.5)

    label = np.full(n, -1, dtype=np.int8)
    label[positive] = 1
    label[certain_negative | hard_negative] = 0

    idx = np.flatnonzero(label >= 0)
    if len(idx) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(
        {
            "pair_id": idx,
            "listing_key_a": [listings[i]["listing_key"] for i in ia[idx]],
            "listing_key_b": [listings[i]["listing_key"] for i in ib[idx]],
            "source_pair": [
                f"{source[a]}-{source[b]}" for a, b in zip(ia[idx], ib[idx], strict=True)
            ],
            "match_weight": weights[idx],
            "label": label[idx],
            "label_source": "silver_deterministic",
        }
    )

    # Stratified sample by source_pair x weight decile (8.8 step 1), with all
    # high-confidence positives kept so the metric is not driven by 5 examples.
    df["bin"] = pd.qcut(df["match_weight"].rank(method="first"), 10, labels=False)
    positives = df[df["label"] == 1]
    negatives = df[df["label"] == 0]
    groups = list(negatives.groupby(["source_pair", "bin"], observed=True))
    per_group = max(4, (n_target - len(positives)) // max(1, len(groups)))
    parts = [
        g.sample(n=min(len(g), per_group), random_state=int(rng.integers(1e9))) for _, g in groups
    ]
    sampled = pd.concat([positives] + parts).drop(columns=["bin"])
    return sampled.sample(frac=1, random_state=seed).reset_index(drop=True)


def save_labels(df: pd.DataFrame, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Parquet requires an optional engine. Preserve the data in a portable CSV
    # rather than aborting the whole linkage stage when pyarrow is unavailable.
    try:
        import pyarrow  # noqa: F401
    except ImportError:
        path = path.with_suffix(".csv")
        df.to_csv(path, index=False)
    else:
        df.to_parquet(path, index=False)
    return path
