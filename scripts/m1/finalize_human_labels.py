"""Turn two reviewer CSVs into a frozen, human-labelled evaluation set (8.8).

Steps:
  1. read reviewer_1.csv / reviewer_2.csv (pair_id = "keyA||keyB", label in
     match/non_match/unsure),
  2. Cohen's kappa on the doubly-labelled subset (unsure excluded from κ),
  3. adjudicate disagreements (reviewer_2's value wins by default; override with
     adjudicated.csv: pair_id,label if a human adjudicator provided one),
  4. freeze a deterministic 80/20 split; the 20% test subset is never used for
     threshold selection,
  5. evaluate FS + supervised scores on the test subset with bootstrap CIs and
     write outputs/human_evaluation.json.

Usage:
    python scripts/finalize_human_labels.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

from autolens.linkage.cluster import DSU
from autolens.linkage.evaluate import bootstrap_ci, prf

ROOT = Path(__file__).resolve().parents[1]
DL = ROOT / "data_labels"
OUT = ROOT / "outputs"
LABELS = ("match", "non_match", "unsure")
TO_INT = {"match": 1, "non_match": 0}


def _read_reviewer(n: int) -> pd.DataFrame:
    p = DL / f"reviewer_{n}.csv"
    if not p.exists():
        raise SystemExit(f"missing {p} — run scripts/label_app.py for reviewer {n}")
    df = pd.read_csv(p).drop_duplicates("pair_id", keep="last")
    bad = set(df["label"]) - set(LABELS)
    if bad:
        raise SystemExit(f"invalid labels in {p}: {bad}")
    return df.set_index("pair_id")["label"]


def kappa_report(a: pd.Series, b: pd.Series) -> dict:
    common = a.index.intersection(b.index)
    a, b = a.loc[common], b.loc[common]
    usable = a.isin(["match", "non_match"]) & b.isin(["match", "non_match"])
    au, bu = a[usable].map(TO_INT), b[usable].map(TO_INT)
    return {
        "overlapping_pairs": int(len(common)),
        "usable_pairs_excluding_unsure": int(usable.sum()),
        "n_unsure_in_overlap": int((~usable).sum()),
        "cohens_kappa": float(cohen_kappa_score(au, bu)) if len(au) > 1 else None,
        "raw_agreement": float((au == bu).mean()) if len(au) else None,
    }


def adjudicate(a: pd.Series, b: pd.Series) -> pd.DataFrame:
    all_ids = a.index.union(b.index)
    rows = []
    adjudicated_path = DL / "adjudicated.csv"
    overrides = {}
    if adjudicated_path.exists():
        overrides = dict(
            zip(*[pd.read_csv(adjudicated_path)[c] for c in ("pair_id", "label")], strict=True)
        )
    for pid in all_ids:
        va, vb = a.get(pid), b.get(pid)
        if isinstance(va, float) and pd.isna(va):
            va = None
        if isinstance(vb, float) and pd.isna(vb):
            vb = None
        definite_a = va in ("match", "non_match")
        definite_b = vb in ("match", "non_match")
        if pid in overrides:
            label, source = overrides[pid], "human_adjudicator"
        elif definite_a and definite_b and va == vb:
            label, source = va, "two_reviewers_agree"
        elif definite_a and definite_b:
            label, source = vb, "reviewer_2_tiebreak"
        elif definite_a or definite_b:
            # 'unsure' is not a competing answer when the other reviewer was decisive.
            label = va if definite_a else vb
            source = "single_definite_reviewer"
        else:
            label, source = "unsure", "no_definite_label"
        rows.append(
            {
                "pair_id": pid,
                "reviewer_1_label": va,
                "reviewer_2_label": vb,
                "label": label,
                "label_source": source,
            }
        )
    return pd.DataFrame(rows)


def evaluate_test(pairs: pd.DataFrame, frozen: pd.DataFrame) -> dict:
    """Score FS match_weight on the frozen human test subset."""
    weights = pairs.set_index("pair_key")["match_weight"]
    test = frozen[frozen["split"] == "test"].copy()
    test["label_int"] = test["label"].map(TO_INT)
    test = test.dropna(subset=["label_int"])
    test["score"] = test["pair_id"].map(weights)
    test = test.dropna(subset=["score"])
    if test.empty:
        return {"error": "no human-labelled pairs overlap the scored candidate pairs"}
    y = test["label_int"].astype(int).to_numpy()
    s = test["score"].astype(float).to_numpy()
    # Threshold chosen on TRAIN only (never on this test subset).
    train = frozen[frozen["split"] == "train"]
    train = train[train["label"].isin(["match", "non_match"])].copy()
    train["score"] = train["pair_id"].map(weights)
    train = train.dropna(subset=["score"])
    if not train.empty:
        ty = train["label"].map(TO_INT).astype(int).to_numpy()
        ts = train["score"].astype(float).to_numpy()
        pos, neg = ts[ty == 1], ts[ty == 0]
        threshold = float(np.percentile(neg, 95)) if len(neg) else float(np.median(ts))
        threshold = min(threshold, float(np.percentile(pos, 5)) if len(pos) else threshold)
    else:
        threshold = float(np.median(s))
    metrics = prf(y, s >= threshold)
    return {
        "n_test_pairs": int(len(y)),
        "threshold_from_train": threshold,
        "metrics": metrics,
        "ci95": {k: list(v) for k, v in bootstrap_ci(y, s, threshold).items()},
    }


def group_aware_split(pair_ids, test_fraction: float = 0.20, seed: int = 42) -> dict:
    """Assign train/test by connected component of listing keys.

    Splitting on ``pair_id`` alone puts two pairs that share a listing into
    different subsets, which leaks the same vehicle/listing into both train and
    test. Here every listing touched by a pair is unioned with its partner; all
    pairs in one component share a split. The component's stable SHA-256 hash
    decides the subset, so reruns freeze the same split.
    """
    ids = [str(p) for p in pair_ids]
    dsu = DSU()
    endpoints: dict[str, tuple[str, str]] = {}
    for pid in ids:
        parts = pid.split("||")
        a, b = (parts[0], parts[1]) if len(parts) == 2 else (pid, pid)
        endpoints[pid] = (a, b)
        dsu.union(a, b)
    components: dict[str, list[str]] = {}
    for pid in ids:
        root = dsu.find(endpoints[pid][0])
        components.setdefault(root, []).append(pid)
    split: dict[str, str] = {}
    for root, members in components.items():
        digest = hashlib.sha256(f"{seed}|{root}".encode()).hexdigest()
        bucket = int(digest[:8], 16) / 0xFFFFFFFF
        subset = "test" if bucket < test_fraction else "train"
        for pid in members:
            split[pid] = subset
    return split


def main() -> None:
    a, b = _read_reviewer(1), _read_reviewer(2)
    report = {"kappa": kappa_report(a, b)}
    merged = adjudicate(a, b)
    usable = merged[merged["label"].isin(["match", "non_match"])].copy()
    # Group-aware frozen split: pairs sharing a listing never cross train/test.
    split = group_aware_split(usable["pair_id"].tolist())
    usable["split"] = usable["pair_id"].map(split)
    usable.to_csv(DL / "human_labels_frozen.csv", index=False)
    report["n_human_labelled_usable_pairs"] = int(len(usable))
    report["n_test_pairs"] = int((usable["split"] == "test").sum())
    report["label_source_counts"] = usable["label_source"].value_counts().to_dict()

    pairs = pd.read_csv(OUT / "labelled_pairs.csv")
    pairs["pair_key"] = pairs["listing_key_a"] + "||" + pairs["listing_key_b"]
    report["fs_on_human_test"] = evaluate_test(pairs, usable)

    out = OUT / "human_evaluation.json"
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2)[:2500])
    print(f"\nwrote {out} and {DL / 'human_labels_frozen.csv'}")


if __name__ == "__main__":
    main()
