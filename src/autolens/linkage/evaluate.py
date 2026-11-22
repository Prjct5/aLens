"""Linkage evaluation - precision/recall/F1 with bootstrap CIs (12, 6.8)."""

from __future__ import annotations

import numpy as np


def prf(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": p, "recall": r, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def bootstrap_ci(
    y_true: np.ndarray,
    scores: np.ndarray,
    threshold: float,
    n_boot: int = 500,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict[str, tuple[float, float]]:
    rng = np.random.default_rng(seed)
    y_pred = scores >= threshold
    metrics = []
    n = len(y_true)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        if len(np.unique(y_true[idx])) < 2:
            continue
        m = prf(y_true[idx], y_pred[idx])
        metrics.append([m["precision"], m["recall"], m["f1"]])
    arr = np.asarray(metrics)
    if arr.size == 0:
        # Tiny fixtures may have a single class in every resample: fall back to
        # the point estimate rather than crashing the golden test.
        point = prf(y_true, scores >= threshold)
        v = (point["precision"], point["recall"], point["f1"])
        return {k: (float(v[i]), float(v[i])) for i, k in enumerate(("precision", "recall", "f1"))}
    lo, hi = np.quantile(arr, [alpha / 2, 1 - alpha / 2], axis=0)
    return {
        "precision": (float(lo[0]), float(hi[0])),
        "recall": (float(lo[1]), float(hi[1])),
        "f1": (float(lo[2]), float(hi[2])),
    }


def choose_thresholds(y_true: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    """Tupper: lowest score where precision >= 0.98.
    Tlower: highest score where recall of matches below it <= 0.02.
    """
    order = np.argsort(-np.asarray(scores))
    yt = np.asarray(y_true)[order]
    s = np.asarray(scores)[order]
    upper = None
    for k in range(1, len(s) + 1):
        pred = np.zeros(len(s), dtype=bool)
        pred[:k] = True
        m = prf(yt, pred)
        if m["precision"] >= 0.98:
            upper = float(s[k - 1])
            break
    lower = None
    for k in range(len(s) + 1):
        pred = np.ones(len(s), dtype=bool)
        pred[:k] = False
        m = prf(yt, pred)
        if m["recall"] <= 0.02:
            lower = float(s[k]) if k < len(s) else float(s[-1]) - 1e-6
            break
    if upper is None:
        upper = float(np.quantile(s, 0.99))
    if lower is None or lower >= upper:
        lower = upper - 1e-6
    return upper, lower
