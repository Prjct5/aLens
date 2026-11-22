"""Streamlit labelling view for RQ1 (handbook 8.8 step 2).

Run:
    streamlit run scripts/label_app.py -- --reviewer 1

Each reviewer records match / non_match / unsure into a private CSV
(``data_labels/reviewer_<n>.csv``). Re-running resumes saved answers.
`unsure` pairs are reported separately and excluded from headline κ (8.8 step 3).
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "data_labels" / "human_review_template.csv"
DB = ROOT / "outputs" / "autolens.db"
LABELS = ("match", "non_match", "unsure")


def _load_pairs() -> pd.DataFrame:
    if not TEMPLATE.exists():
        raise SystemExit("run the pipeline first: make run")
    return pd.read_csv(TEMPLATE)


def _listing(key: str) -> dict:
    source, sid = key.split(":", 1)
    with sqlite3.connect(DB) as con:
        row = con.execute(
            "SELECT year, mileage_km, price_egp, governorate_code, transmission, "
            "fuel_type, body_type FROM staging_normalized_listing "
            "WHERE source=? AND source_listing_id=? ORDER BY scrape_date DESC LIMIT 1",
            (source, sid),
        ).fetchone()
    cols = (
        "year",
        "mileage_km",
        "price_egp",
        "governorate_code",
        "transmission",
        "fuel_type",
        "body_type",
    )
    return dict(zip(cols, row, strict=True)) if row else {}


def _photos(key: str) -> list[str]:
    with sqlite3.connect(DB) as con:
        rows = con.execute(
            "SELECT quarantine_key FROM staging_image_fetch "
            "WHERE listing_key=? ORDER BY position LIMIT 3",
            (key,),
        ).fetchall()
    return [str(ROOT / r[0]) for r in rows if r[0] and (ROOT / r[0]).exists()]


def _card(key: str, st) -> None:
    st.subheader(key)
    info = _listing(key)
    st.write(
        f"**Year:** {info.get('year', '?')} · **Km:** {info.get('mileage_km', '?')} · "
        f"**Price:** {info.get('price_egp', '?')} EGP · "
        f"**Gov:** {info.get('governorate_code', '?')}"
    )
    st.write(
        f"Transmission: {info.get('transmission', '?')} · "
        f"Fuel: {info.get('fuel_type', '?')} · Body: {info.get('body_type', '?')}"
    )
    paths = _photos(key)
    if paths:
        st.caption(
            "Generic open-licensed Commons photos (status=open_source_commons). "
            "Not photos of this listing — photo similarity is illustrative only, "
            "not evidence that two listings describe the same car."
        )
        st.image(paths, width=160)
    else:
        st.caption("No photos available")


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewer", type=int, required=True, choices=[1, 2])
    args = parser.parse_args(argv)

    import streamlit as st

    st.set_page_config(page_title=f"AutoLens labelling — reviewer {args.reviewer}")
    st.title(f"RQ1 pair labelling — reviewer {args.reviewer}")
    st.info(
        "Label match / non_match / unsure. Unsure pairs are excluded from κ. "
        "Answers are saved continuously; re-run to resume."
    )

    pairs = _load_pairs()
    out = ROOT / "data_labels" / f"reviewer_{args.reviewer}.csv"
    saved: dict[str, str] = {}
    if out.exists():
        prev = pd.read_csv(out)
        saved = dict(zip(prev["pair_id"], prev["label"], strict=True))

    if "idx" not in st.session_state:
        st.session_state["idx"] = 0
    st.session_state["idx"] = st.number_input(
        "Pair index",
        min_value=0,
        max_value=len(pairs) - 1,
        value=int(st.session_state["idx"]),
        step=1,
    )
    idx = int(st.session_state["idx"])
    r = pairs.iloc[idx]
    st.write(
        f"**{idx + 1} / {len(pairs)}** · pair weight = {float(r['match_weight']):.3f} · "
        f"source pair = {r['source_pair']}"
    )

    c1, c2 = st.columns(2)
    with c1:
        _card(str(r["listing_key_a"]), st)
    with c2:
        _card(str(r["listing_key_b"]), st)

    pair_id = f"{r['listing_key_a']}||{r['listing_key_b']}"
    current = saved.get(pair_id)
    choice = st.radio("Your label", LABELS, index=LABELS.index(current) if current in LABELS else 0)
    if st.button("Save & next"):
        saved[pair_id] = choice
        pd.DataFrame([{"pair_id": k, "label": v} for k, v in saved.items()]).to_csv(
            out, index=False
        )
        st.success(f"Saved: {choice} ({len(saved)} pairs recorded)")
        st.session_state["idx"] = min(idx + 1, len(pairs) - 1)


if __name__ == "__main__":
    main()
