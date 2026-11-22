"""Generate a side-by-side HTML labelling view for the evaluation pairs (8.8 step 2).

No Streamlit dependency: open the generated HTML in a browser, two annotators label
match / non_match / unsure, and save the result as CSV for Cohen's kappa.
"""

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    pairs = root / "outputs" / "labelled_pairs.csv"
    if not pairs.exists():
        raise SystemExit("run the pipeline first: make run")
    df = pd.read_csv(pairs).head(200)
    rows = []
    for r in df.itertuples(index=False):
        rows.append(
            "<tr><td>"
            + html.escape(str(r.listing_key_a))
            + "</td><td>"
            + html.escape(str(r.listing_key_b))
            + "</td><td>"
            + f"{r.match_weight:.2f}"
            + "</td>"
            "<td><label>M <input type='radio' name='"
            + html.escape(str(r.pair_id))
            + "' value='match'></label>"
            "<label>N <input type='radio' name='"
            + html.escape(str(r.pair_id))
            + "' value='non_match'></label>"
            "<label>? <input type='radio' name='"
            + html.escape(str(r.pair_id))
            + "' value='unsure'></label></td></tr>"
        )
    out = root / "outputs" / "label_view.html"
    out.write_text(
        "<html><head><meta charset='utf-8'><title>AutoLens linkage labelling</title></head>"
        "<body><h1>RQ1 pair labelling</h1><p>Label each pair; export answers separately.</p>"
        "<table border=1 cellpadding=4><tr><th>A</th><th>B</th><th>weight</th><th>label</th></tr>"
        + "".join(rows)
        + "</table></body></html>",
        encoding="utf-8",
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
