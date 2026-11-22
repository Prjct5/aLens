"""Splink comparison for RQ1 (handbook 8.7.3 step 1).

Runs the production-grade Splink Fellegi-Sunter implementation on the same
listings and blocking rule, then scores its match weights on the evaluation
pairs so the RQ1 chapter can report FS (own), Splink and supervised side by side.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from autolens.linkage.evaluate import bootstrap_ci, choose_thresholds, prf


def _frame(listings: list[dict]) -> pd.DataFrame:
    rows = []
    for r in listings:
        rows.append(
            {
                "unique_id": r["listing_key"],
                "source_dataset": r["source"],
                "make": r.get("make_canon"),
                "model": r.get("model_canon"),
                "year": r.get("year"),
                "mileage_km": r.get("mileage_km"),
                "price_egp": r.get("price_egp"),
                "transmission": r.get("transmission"),
                "fuel": r.get("fuel_type"),
                "body": r.get("body_type"),
            }
        )
    return pd.DataFrame(rows)


def run_splink_comparison(
    listings: list[dict], labels: pd.DataFrame, output_path: Path | None = None
) -> dict:
    """Return Splink P/R/F1 on the labelled pairs, or an error dict."""
    from splink import (
        DuckDBAPI,
        Linker,
        SettingsCreator,
        block_on,
    )
    from splink import (
        comparison_level_library as cll,
    )
    from splink import (
        comparison_library as cl,
    )

    df = _frame(listings)
    # Numeric comparisons use the same tolerance bands as our FS model so the
    # comparison measures modelling choices, not an artificially weak baseline.
    settings = SettingsCreator(
        link_type="link_and_dedupe",
        comparisons=[
            cl.ExactMatch("make"),
            cl.ExactMatch("model"),
            cl.CustomComparison(
                [
                    cll.NullLevel("year"),
                    cll.ExactMatchLevel("year"),
                    cll.AbsoluteDifferenceLevel("year", 1),
                    cll.ElseLevel(),
                ]
            ),
            cl.CustomComparison(
                [
                    cll.NullLevel("mileage_km"),
                    cll.ExactMatchLevel("mileage_km"),
                    cll.AbsoluteDifferenceLevel("mileage_km", 5000),
                    cll.AbsoluteDifferenceLevel("mileage_km", 20000),
                    cll.ElseLevel(),
                ]
            ),
            cl.CustomComparison(
                [
                    cll.NullLevel("price_egp"),
                    cll.ExactMatchLevel("price_egp"),
                    cll.PercentageDifferenceLevel("price_egp", 0.15),
                    cll.PercentageDifferenceLevel("price_egp", 0.35),
                    cll.ElseLevel(),
                ]
            ),
            cl.ExactMatch("transmission"),
            cl.ExactMatch("fuel"),
            cl.ExactMatch("body"),
        ],
        blocking_rules_to_generate_predictions=[block_on("make", "model")],
        probability_two_random_records_match=0.001,
        unique_id_column_name="unique_id",
        source_dataset_column_name="source_dataset",
        max_iterations=25,
    )
    db_api = DuckDBAPI()  # Splink 5 requires explicit registration
    linker = Linker(db_api.register(df), settings)
    linker.training.estimate_u_using_random_sampling(max_pairs=1_000_000)
    # Two EM sessions: the first trains year/km/price/etc. under make+model
    # blocking; the second trains make/model under a different blocking rule.
    # (A single session leaves m untrained for the columns it blocks on.)
    linker.training.estimate_parameters_using_expectation_maximisation(block_on("make", "model"))
    linker.training.estimate_parameters_using_expectation_maximisation(
        block_on("year", "transmission")
    )
    predictions = linker.inference.predict(
        threshold_match_weight=-20, warning_mode="never"
    ).as_pandas_dataframe()

    truth = {
        tuple(sorted((r.listing_key_a, r.listing_key_b))): int(r.label)
        for r in labels.itertuples(index=False)
    }

    def score(pred_df: pd.DataFrame) -> dict:
        pred_df = pred_df.copy()
        pred_df["pair"] = [
            tuple(sorted((a, b)))
            for a, b in zip(pred_df["unique_id_l"], pred_df["unique_id_r"], strict=True)
        ]
        scores = pred_df.groupby("pair")["match_weight"].max().to_dict()
        common = sorted(set(scores) & set(truth))
        y = np.array([truth[k] for k in common])
        s = np.array([scores[k] for k in common])
        if len(y) == 0:
            return {"error": "no labelled pairs appeared in Splink predictions"}
        upper, lower = choose_thresholds(y, s)
        return {
            "n_evaluated_pairs": len(y),
            "t_upper": upper,
            "t_lower": lower,
            "metrics": prf(y, s >= upper),
            "ci95": {k: list(v) for k, v in bootstrap_ci(y, s, upper).items()},
        }

    result = {
        "method": "splink_fs_em_unsupervised_only",
        "variants": {
            "unsupervised_em": score(predictions),
        },
        "splink_settings": {
            "blocking": ["make", "model"],
            "comparisons": [
                "make",
                "model",
                "year(±1)",
                "km(0/5k/20k)",
                "price(0/15%/35%)",
                "transmission",
                "fuel",
                "body",
            ],
            "link_type": "link_and_dedupe",
        },
    }

    if output_path:
        Path(output_path).write_text(json.dumps(result, indent=2))
    return result
