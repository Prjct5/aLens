from pathlib import Path

import pandas as pd

from autolens.linkage.labels import save_labels


def test_label_export_without_required_parquet_engine(tmp_path: Path):
    sample = pd.DataFrame({"listing_key_a": ["a:1"], "label": [1]})
    output = save_labels(sample, tmp_path / "pairs.parquet")
    assert output.exists()
    if output.suffix == ".csv":
        actual = pd.read_csv(output)
    else:
        actual = pd.read_parquet(output)
    pd.testing.assert_frame_equal(actual, sample)
