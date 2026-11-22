"""Clustering / stable-id tests (handbook 8.7.5)."""

from autolens.linkage.cluster import (
    DSU,
    assign_vehicle_ids,
    components,
    split_large_components,
)


def test_dsu_and_components():
    d = DSU()
    d.union("a", "b")
    d.union("b", "c")
    assert d.find("a") == d.find("c")
    comps = components([("a", "b", 5.0), ("b", "c", 4.0)])
    assert comps == [{"a", "b", "c"}]


def test_cluster_size_cap():
    edges = [(f"n{i}", f"n{i + 1}", float(i)) for i in range(10)]
    kept, dropped = split_large_components(edges, max_cluster=3)
    assert dropped > 0
    assert all(len(c) <= 3 for c in components(kept))


def test_strongest_edge_survives_when_cluster_cap_is_full():
    # Same two competing edges from node "a"; only one fits under cap=2.
    edges = [("a", "b", 1.0), ("a", "c", 100.0)]
    kept, dropped = split_large_components(edges, max_cluster=2)
    assert dropped == 1
    assert kept == [("a", "c", 100.0)]


def test_stable_ids_and_merges():
    edges = [("a:1", "b:1", 6.0)]
    mapping, merges = assign_vehicle_ids(edges, {}, max_cluster=3)
    assert mapping["a:1"] == mapping["b:1"]
    first = mapping["a:1"]

    # Next run: previously separate id joins the cluster, smallest id wins.
    edges2 = [("a:1", "b:1", 6.0), ("b:1", "c:1", 6.0)]
    mapping2, merges2 = assign_vehicle_ids(
        edges2, {"a:1": first, "b:1": first}, all_keys=["a:1", "b:1", "c:1"], max_cluster=3
    )
    assert mapping2["a:1"] == first
    assert mapping2["c:1"] == first
    assert merges2 == []
