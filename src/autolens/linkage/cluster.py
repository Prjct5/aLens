"""Clustering with stable vehicle_id and size-aware splitting (8.7.5)."""

from __future__ import annotations

from collections import defaultdict


class DSU:
    """Union-find (handbook Listing 8.4)."""

    def __init__(self):
        self.p: dict = {}
        self.size: dict = {}

    def find(self, x):
        self.p.setdefault(x, x)
        self.size.setdefault(x, 1)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        self.p[rb] = ra
        self.size[ra] += self.size[rb]
        return True


def components(edges) -> list[set]:
    """Connected components from (a, b, weight) edges (Listing 8.4)."""
    d = DSU()
    nodes = set()
    for a, b, _ in edges:
        d.union(a, b)
        nodes.update((a, b))
    groups: dict = defaultdict(set)
    for node in nodes:
        groups[d.find(node)].add(node)
    return list(groups.values())


def split_large_components(
    edges: list[tuple[str, str, float]], max_cluster: int
) -> tuple[list[tuple[str, str, float]], int]:
    """Keep components <= max_cluster by keeping the STRONGEST edges first.

    The handbook (8.7.5) says to remove the weakest edge repeatedly. That is
    equivalent to processing edges from strongest to weakest and keeping an edge
    only when it does not exceed the cap. Processing in ascending order (the old
    behaviour) could retain a weak edge and reject a strong one, which is wrong.
    Ties are broken by endpoints so the result is deterministic.
    """
    kept, dropped = [], 0
    d = DSU()
    for a, b, w in sorted(edges, key=lambda e: (-e[2], e[0], e[1])):
        ra, rb = d.find(a), d.find(b)
        if ra == rb:
            kept.append((a, b, w))
            continue
        if d.size[ra] + d.size[rb] <= max_cluster:
            d.union(a, b)
            kept.append((a, b, w))
        else:
            dropped += 1
    return kept, dropped


def assign_vehicle_ids(
    edges: list[tuple[str, str, float]],
    previous: dict[str, int],
    all_keys: list[str] | None = None,
    max_cluster: int = 9,
) -> tuple[dict[str, int], list[tuple[int, int]]]:
    """Assign stable ids; keep smallest existing id per component, record merges."""
    kept_edges, _ = split_large_components(edges, max_cluster)
    comps = components(kept_edges)
    next_id = max(previous.values(), default=0) + 1
    mapping: dict[str, int] = {}
    merges: list[tuple[int, int]] = []
    for comp in comps:
        existing = sorted({previous[k] for k in comp if k in previous})
        if existing:
            keep = existing[0]
            for old in existing[1:]:
                merges.append((old, keep))
        else:
            keep = next_id
            next_id += 1
        for k in comp:
            mapping[k] = keep
    # Every listing gets a vehicle_id, including those with no accepted edges.
    for k in all_keys or []:
        if k in mapping:
            continue
        mapping[k] = previous.get(k) or next_id
        if k not in previous:
            next_id += 1
    return mapping, merges


def link_rows(
    mapping: dict[str, int],
    edges: list[tuple[str, str, float]],
    link_run_id: str,
    max_cluster: int = 9,
) -> list[dict]:
    """Build core.vehicle_link rows from the final clusters."""
    kept_edges, _ = split_large_components(edges, max_cluster)
    sizes = defaultdict(int)
    for comp in components(kept_edges):
        root = mapping[next(iter(comp))]
        sizes[root] = len(comp)
    wmin, wmax = defaultdict(lambda: 1e9), defaultdict(lambda: -1e9)
    for a, _b, w in kept_edges:
        root = mapping[a]
        wmin[root] = min(wmin[root], w)
        wmax[root] = max(wmax[root], w)
    return [
        {
            "listing_key": k,
            "vehicle_id": vid,
            "link_run_id": link_run_id,
            "cluster_size": max(1, sizes[vid]),
            "min_edge_weight": 0.0 if wmin[vid] > 1e8 else wmin[vid],
            "max_edge_weight": 0.0 if wmax[vid] < -1e8 else wmax[vid],
            "method": "fs_em_v1",
        }
        for k, vid in sorted(mapping.items())
    ]
