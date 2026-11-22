"""Supervised comparators with group-aware cross-validation (8.7.3, pitfall 2)."""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from autolens.linkage.cluster import DSU


def group_folds(pairs: list[tuple[int, int]], n_splits: int = 5) -> np.ndarray:
    """Fold by connected component so no listing appears in train and test.

    The pair graph defines components; each component gets one fold, chosen by
    a stable hash of its root, balancing approximately by component count.
    """
    dsu = DSU()
    for a, b in pairs:
        dsu.union(a, b)
    roots = {i: dsu.find(i) for i in {x for p in pairs for x in p}}
    fold_of_root: dict[int, int] = {}
    folds = np.zeros(len(pairs), dtype=int)
    for r, (a, _b) in enumerate(pairs):
        root = roots[a]
        if root not in fold_of_root:
            fold_of_root[root] = len(fold_of_root) % n_splits
        folds[r] = fold_of_root[root]
    return folds


def model_factories():
    return {
        "logreg": lambda: make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=1000, random_state=42)
        ),
        "gbm": lambda: HistGradientBoostingClassifier(
            max_iter=150, random_state=42, early_stopping=False
        ),
    }


def cross_validated_scores(
    X: np.ndarray, y: np.ndarray, pairs: list[tuple[int, int]], n_splits: int = 5
) -> dict[str, dict]:
    """Out-of-fold scores and P/R/F1 for each supervised comparator."""
    folds = group_folds(pairs, n_splits)
    results = {}
    for name, factory in model_factories().items():
        oof = np.zeros(len(y))
        for fold in range(n_splits):
            train, test = folds != fold, folds == fold
            if test.sum() == 0 or train.sum() == 0 or len(np.unique(y[train])) < 2:
                continue
            model = factory()
            model.fit(X[train], y[train])
            oof[test] = model.predict_proba(X[test])[:, 1]
        label = oof >= 0.5
        results[name] = {
            "oof_scores": oof,
            "precision": float(precision_score(y, label, zero_division=0)),
            "recall": float(recall_score(y, label, zero_division=0)),
            "f1": float(f1_score(y, label, zero_division=0)),
        }
    return results
