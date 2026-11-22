"""Human-label tooling: kappa, adjudication, frozen split and test evaluation."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

# Import the script as a module (it lives in scripts/, not a package).
SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "m1" / "finalize_human_labels.py"
spec = importlib.util.spec_from_file_location("finalize_human_labels", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_kappa_excludes_unsure():
    a = pd.Series({"p1": "match", "p2": "non_match", "p3": "match", "p4": "match"}, name="label")
    b = pd.Series(
        {"p1": "match", "p2": "non_match", "p3": "non_match", "p4": "unsure"}, name="label"
    )
    r = mod.kappa_report(a, b)
    assert r["overlapping_pairs"] == 4
    assert r["usable_pairs_excluding_unsure"] == 3
    assert r["n_unsure_in_overlap"] == 1
    assert -1 <= r["cohens_kappa"] <= 1


def test_adjudication_agreement_and_tiebreak(tmp_path):
    a = pd.Series({"p1": "match", "p2": "non_match", "p3": "match"})
    b = pd.Series({"p1": "match", "p2": "match", "p3": "unsure"})
    out = mod.adjudicate(a, b)
    by_id = out.set_index("pair_id")
    assert by_id.loc["p1", "label_source"] == "two_reviewers_agree"
    assert by_id.loc["p2", "label_source"] == "reviewer_2_tiebreak"
    assert by_id.loc["p2", "label"] == "match"
    assert by_id.loc["p3", "label"] == "match"  # only reviewer 1 answered


def test_group_aware_split_keeps_shared_listings_together():
    pairs = ["a||b", "b||c", "c||d", "x||y", "m||n"]
    split = mod.group_aware_split(pairs)
    for pid in pairs:
        assert pid in split and split[pid] in {"train", "test"}
    # a-b-c-d form one connected component: they must all get the same subset.
    assert len({split[p] for p in pairs[:3]}) == 1
    # Deterministic across calls (frozen split).
    assert mod.group_aware_split(pairs) == split


def test_evaluate_test_uses_train_threshold(tmp_path):
    pairs = pd.DataFrame(
        {
            "pair_key": ["a||b", "c||d", "e||f", "g||h"],
            "match_weight": [5.0, -5.0, 4.5, -4.5],
        }
    )
    frozen = pd.DataFrame(
        {
            "pair_id": ["a||b", "c||d", "e||f", "g||h"],
            "label": ["match", "non_match", "match", "non_match"],
            "split": ["train", "train", "test", "test"],
        }
    )
    r = mod.evaluate_test(pairs, frozen)
    assert r["n_test_pairs"] == 2
    assert "metrics" in r and "ci95" in r
    assert "threshold_from_train" in r
