from __future__ import annotations

from pathlib import Path

from autolens.common.local_backend import ObjectStore


def test_raw_keys_use_forward_slashes_and_filter(tmp_path: Path) -> None:
    store = ObjectStore(tmp_path)
    store.put_raw("hatla2ee", "2026-01-15", "1", {"a": 1})
    store.put_raw("dubizzle", "2026-01-15", "2", {"a": 2})
    store.put_raw("dubizzle", "2026-01-16", "3", {"a": 3})
    assert store.raw_keys() == sorted(store.raw_keys())
    assert len(store.raw_keys(run_date="2026-01-15")) == 2
    assert store.raw_keys(source="dubizzle", run_date="2026-01-16") == [
        "raw/dubizzle/2026-01-16/3.json.gz"
    ]
    assert all("\\" not in k for k in store.raw_keys())
