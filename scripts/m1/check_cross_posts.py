"""Test whether dubizzle ids like 'h7302649' are hatla2ee ids (cross-posted listings).

Prints aggregates only. If the pipeline has been run, also reports how many of these
known cross-posts the linkage put into the same vehicle (an independent recall check,
not derived from the attributes the linker uses).
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

import pandas as pd


def quantiles(series: pd.Series) -> dict[str, float]:
    return {f"p{int(q * 100)}": round(float(series.quantile(q)), 4) for q in (0.1, 0.5, 0.9)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--work-dir", default=None, help="work dir of a previous verify run")
    parser.add_argument("--run-date", default="2026-01-15")
    args = parser.parse_args()

    df = pd.read_csv(
        Path(args.data_dir) / "Egypt_Used_Cars_clean.csv", dtype=str, keep_default_na=False
    )
    dub = df[df["source"] == "dubizzle"]
    hat = df[df["source"] == "hatla2ee"]
    pref = dub[dub["listing_id"].str.fullmatch(r"h\d+")].copy()
    pref["num"] = pref["listing_id"].str[1:]
    out: dict[str, object] = {
        "dubizzle_rows": len(dub),
        "dubizzle_h_prefixed_ids": len(pref),
        "h_ids_also_hatla2ee_ids": int(pref["num"].isin(set(hat["listing_id"])).sum()),
    }
    merged = pref.merge(hat, left_on="num", right_on="listing_id", suffixes=("_d", "_h"))
    out["matched_pairs"] = len(merged)
    if len(merged):
        same = lambda col: float(  # noqa: E731
            (merged[f"{col}_d"].str.lower() == merged[f"{col}_h"].str.lower()).mean()
        )
        out["share_same_make"] = round(same("make"), 3)
        out["share_same_model"] = round(same("model"), 3)
        out["share_same_year"] = round(same("year"), 3)
        out["share_same_transmission"] = round(same("transmission"), 3)
        out["share_same_fuel"] = round(same("fuel_type"), 3)
        pd_, ph = pd.to_numeric(merged["price_d"]), pd.to_numeric(merged["price_h"])
        out["price_rel_diff"] = quantiles(
            (pd_ - ph).abs() / pd.concat([pd_, ph], axis=1).max(axis=1)
        )
        kd, kh = pd.to_numeric(merged["kilometers_d"]), pd.to_numeric(merged["kilometers_h"])
        out["km_rel_diff"] = quantiles(
            (kd - kh).abs() / pd.concat([kd, kh], axis=1).max(axis=1).clip(lower=1)
        )

        if args.work_dir:
            os.environ["PROJECT_ROOT"] = str(Path(args.work_dir).resolve())
            from autolens.scrapers.settings import M1Settings

            db_path = M1Settings.from_env().db_path
            if Path(db_path).exists():
                con = sqlite3.connect(db_path)
                links = dict(
                    con.execute(
                        "SELECT listing_key, vehicle_id FROM core_vehicle_link WHERE link_run_id=?",
                        (f"link-{args.run_date}",),
                    ).fetchall()
                )
                both = linked = 0
                for _, r in merged.iterrows():
                    a, b = f"dubizzle:{r['listing_id_d']}", f"hatla2ee:{r['listing_id_h']}"
                    if a in links and b in links:
                        both += 1
                        linked += int(links[a] == links[b])
                out["pairs_present_in_links"] = both
                out["pairs_in_same_vehicle"] = linked
                out["recall_on_known_cross_posts"] = round(linked / both, 4) if both else None
            else:
                out["note"] = f"no pipeline database at {db_path}"
    for key, value in out.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
