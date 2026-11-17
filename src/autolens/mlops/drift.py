from __future__ import annotations

import math
from collections.abc import Sequence


def _quantile_edges(values: Sequence[float], bins: int) -> list[float]:
    ordered = sorted(values)
    n = len(ordered)
    edges = []
    for i in range(1, bins):
        pos = i * (n - 1) / bins
        lo = int(math.floor(pos))
        hi = min(lo + 1, n - 1)
        edges.append(ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo))
    return edges


def _shares(values: Sequence[float], edges: list[float], eps: float) -> list[float]:
    counts = [0] * (len(edges) + 1)
    for v in values:
        idx = sum(1 for e in edges if v > e)
        counts[idx] += 1
    total = max(len(values), 1)
    return [max(c / total, eps) for c in counts]


def psi(
    expected: Sequence[float], actual: Sequence[float], bins: int = 10, eps: float = 1e-4
) -> float:
    if not expected or not actual:
        raise ValueError("expected and actual must be non-empty")
    edges = _quantile_edges(expected, bins)
    e = _shares(expected, edges, eps)
    a = _shares(actual, edges, eps)
    return sum((ai - ei) * math.log(ai / ei) for ai, ei in zip(a, e, strict=True))


def psi_status(value: float) -> str:
    if value > 0.25:
        return "alert"
    if value >= 0.1:
        return "watch"
    return "ok"
