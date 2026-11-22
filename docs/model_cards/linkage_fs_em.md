# Model card – FS+EM linkage (M1)

**Name:** `fs_em_v1` · **Owner:** M1 (Merna Mohamed) · **Version:** 1.0
**Purpose:** decide whether two listings describe the same physical vehicle (RQ1).

**Inputs:** comparison vector of 9 three-level fields (agree/disagree/missing) over
candidate pairs from blocking; no seller data. The 9th field is `photo_match` from
generic open-licensed image pHashes (not listing-specific photos).
**Output:** match weight in bits, posterior probability, accepted pairs, review band,
vehicle clusters with stable ids.

**Training:** unsupervised EM over all candidate pairs (this dataset: 1,102,506 pairs).
No labelled data is used to fit m/u/prior. Supervised comparators are trained on the
provisional silver labels with group-aware cross-validation only for comparison.

**Intended use:** hand-off of `core.vehicle_link` to M2/M4; analytics and price modelling.
**Out of scope:** actual sale-price matching, seller identity, fraud decisions.

**Ethics/privacy:** no names/phones read or stored; images stay in quarantine until M3
blurs them (16.9). No raw data is committed to git.

**Known limitations:** conditional independence of fields is violated (mileage and price
are correlated), so weights are over-confident; `photo_match` uses generic Commons
photos rather than listing images; description text is unavailable; silver-label
evaluation is circular. See `docs/report/RQ1.md`.

**Reproduction:** `make run` → `outputs/linkage_metrics.json` and `outputs/fs_parameters.csv`.
