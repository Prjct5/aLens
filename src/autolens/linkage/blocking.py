"""Blocking: candidate pairs by (make, model, year +/- 1) - handbook 8.7.1."""

from __future__ import annotations

from collections import defaultdict
from math import comb


def generate_candidates(listings: list[dict], max_pairs: int = 2_000_000) -> list[tuple[int, int]]:
    """Pairs sharing canonical make, model and year within +/-1.

    Cross-source pairs and within-source reposts are both generated. Pairs with
    the same listing_key are skipped. A phash bucket second pass is supported
    by `generate_phash_candidates` when images are available.
    """
    blocks: dict[tuple, list[int]] = defaultdict(list)
    for i, row in enumerate(listings):
        make = row.get("make_canon") or row.get("make_raw") or ""
        model = row.get("model_canon") or row.get("model_raw") or ""
        year = row.get("year")
        if not make or not model or year is None:
            continue
        for y in (year - 1, year, year + 1):
            blocks[(make, model, y)].append(i)

    pairs: set[tuple[int, int]] = set()
    for idxs in blocks.values():
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                i, j = idxs[a], idxs[b]
                if listings[i].get("listing_key") == listings[j].get("listing_key"):
                    continue
                pair = (min(i, j), max(i, j))
                pairs.add(pair)
                if len(pairs) >= max_pairs:
                    return sorted(pairs)
    return sorted(pairs)


def generate_phash_candidates(
    listings: list[dict], hashes: dict[str, set[str]], max_hamming: int = 6
) -> list[tuple[int, int]]:
    """Second blocking pass by pHash bucket (8.7.1).

    `hashes` maps listing_key -> set of pHash hex strings. Only exact bucket
    collisions are produced here; near neighbours are handled in comparison.
    """
    buckets: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(listings):
        for h in hashes.get(row.get("listing_key", ""), set()):
            buckets[h].append(i)
    pairs = set()
    for idxs in buckets.values():
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                pairs.add((min(idxs[a], idxs[b]), max(idxs[a], idxs[b])))
    return sorted(pairs)


def reduction_ratio(n_pairs: int, n_listings: int) -> float:
    total = comb(n_listings, 2)
    return 1.0 - n_pairs / total if total else 0.0


def pairs_completeness(candidates: set[tuple], true_pairs: set[tuple]) -> float:
    return len(candidates & true_pairs) / len(true_pairs) if true_pairs else 0.0
