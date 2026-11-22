# RQ1 – Linkage results (M1)

> **Read this first.** The evaluation below uses *provisional silver labels* derived
> deterministically from the same structured fields used as comparison features.
> Therefore P/R/F1 = 1.00 is **not** a valid estimate of real-world performance: it
> is a sanity check that the implementation separates obvious matches from obvious
> non-matches. The handbook's protocol (two humans labelling ~1,000 pairs, Cohen's κ,
> a frozen untouched test subset) is specified in `src/autolens/linkage/labels.py`
> and must be executed before reporting an RQ1 number in the final report.

## 1. Data collection

| Source | Listings | Observation window | Success |
|---|---|---:|---:|
| Hatla2ee | 10,633 | single supplied snapshot (2026-01-15) | 100% parsed |
| ContactCars | 6,384 | single supplied snapshot | 100% parsed |
| Dubizzle | 18,377 | single supplied snapshot | 100% parsed |
| **Total** | **35,394** | | **0 parse failures** |

All three sources were consumed from the supplied archives, not from live websites.
`ops.scrape_run` records one row per source with counts and timestamps. Live polite
scraping (rate limit, robots.txt, off-peak, User-Agent, back-off) is configured in
`rate_limiter.py`; it cannot be exercised without network access.

## 2. Normalisation

- Canonical dictionary mined from 1,361 distinct make/model strings; every accepted
  alias is committed to `data_reference/models.csv` and `aliases.csv`.
- Mapping rate on the supplied archive: **100%** (exact alias hits).
- Quality flags: `price_below_floor` (price = 1,000 EGP placeholder), `price_outlier`
  (modified z-score on ln(price) > 3.5 within model-year groups), `mileage_placeholder`,
  `mileage_implausible_high`, `year_invalid`, etc. Flags never delete rows.

## 3. Linkage design

- **Blocking:** `(make_canon, model_canon, year ± 1)`, same-listing pairs skipped.
  1,102,506 candidate pairs from 35,394 listings → reduction ratio **0.99824**.
- **Comparison features (9):** `same_year`, `mileage_close` (≤5%), `same_governorate`,
  `price_close` (≤10%), `same_transmission`, `same_fuel`, `same_body`, `desc_sim`,
  `photo_match`. Three-level encoding: agree / disagree / **missing** (missing
  contributes no evidence). `desc_sim` remains entirely missing (no M4 text).
  `photo_match` is populated from 250 real open-licensed car photos (Wikimedia
  Commons, CC0/CC BY/CC BY-SA, full attribution in `outputs/open_images_attribution.csv`),
  keyed by SHA-256 and pHash (Hamming ≤5/64 bits). Same-car listings share a photo.
  **Caveat:** these are generic open-licensed images, not photos of the specific
  listed vehicles; they exercise the pipeline with real imagery but are not
  evidence a listing had a photo.
- **Fellegi–Sunter + EM:** implemented from scratch (`linkage/fs.py`), log-domain E-step,
  M-step excluding missing comparisons, prior capped at 0.05 as a guard against the
  degenerate local optimum described in handbook §6.6. Parameters in
  `outputs/fs_parameters.csv`.
- **Supervised comparators:** logistic regression and histogram gradient boosting on the
  same comparison vector, with **group-aware** cross-validation by connected component
  so no listing appears in both train and test (pitfall 2).
- **Ablation:** `photo_match` / `desc_sim` cannot be measured on this archive; the code
  path exists and will contribute automatically when images/text arrive from M3/M4.

## 4. Results (provisional)

| Method | Precision | Recall | F1 | 95% CI (F1) |
|---|---:|---:|---:|---|
| FS + EM (binary thresholds) | 1.00 | 1.00 | 1.00 | [1.00, 1.00] |
| Logistic regression (group CV) | 1.00 | 1.00 | 1.00 | – |
| Gradient boosting (group CV) | 1.00 | 1.00 | 1.00 | – |
| Splink FS+EM (unsupervised only) | 1.00 | 0.228 | 0.372 | [0.333, 0.417] |

Labelled sample: 2,973 pairs (766 positives, 2,207 negatives) — all **silver** labels,
not human ground truth. Splink's low recall is a genuine finding: its EM priors,
trained without labels, do not fit this archive; its method name in
`output=splink_metrics.json` is `splink_fs_em_unsupervised_only` (it is NOT
label-trained). Human labelling tooling now exists
(`scripts/label_app.py` + `scripts/finalize_human_labels.py`) but no human has
labelled the pairs yet.

**Ablation (code-ready, evidence pending):**
- `remove photo_match` — set `AUTOLENS_SYNTHETIC_IMAGES=0` and re-run; `photo_match`
  becomes all-missing and contributes no weight.
- `remove desc_sim` — already the case (no M4 descriptions); it is all-missing.
- Honest ablation numbers require human labels and real images (REMAINING #3/#5).

**Why these numbers are optimistic (threats to validity):**
1. Silver positives were *defined* by near-equality on year/km/price/attributes – the
   same signals FS uses. This is circular by construction.
2. A single snapshot cannot validate repost linking (which needs disappearance/re-post).
3. Listing-specific image/text evidence is absent. The bundled Commons pHashes exercise
   `photo_match` but are generic photos, not the listed vehicles, so they are not real
   image evidence for a match decision.
4. The prior hit the 0.05 guard; with real labels it should be re-estimated.

## 5. Error analysis and limitations

- ≈7.6k pairs accepted above threshold; ~32k clusters produced from 35,394 listings
  (mean cluster size 1.1). Cluster cap = sources × 3 = 9; the strongest edges are kept
  first when a cluster is full (`cluster.py`).
- Hard cases by construction: wrong year (±1 block), different mileage because of time,
  price changes, missing governorate, and cross-source field sparsity.
- Cross-source duplicates with matching make/model/year/km/price are rare in this
  archive; a human labelling pass is required to measure honest recall.

## 6. What to do next (owner: M1, Weeks 3–4)

1. Run `streamlit run scripts/label_app.py -- --reviewer 1` and `--reviewer 2`.
   Both annotators label ≥1,000 stratified pairs from
   `data_labels/human_review_template.csv` as `match` / `non_match` / `unsure`.
2. Run `python scripts/finalize_human_labels.py` → Cohen's κ, adjudication,
   `data_labels/human_labels_frozen.csv` (deterministic 80/20 train/test split,
   test subset frozen for evaluation only) and `outputs/human_evaluation.json`.
3. Re-run thresholds and re-estimate EM parameters on the human labels; replace
   this provisional table entirely. Never report the silver 1.00 as accuracy.
4. Obtain lawful images (replace synthetics, same storage/hash contract) and M4
   description embeddings; re-run the ablation: `remove photo_match`, `remove desc_sim`.
5. Obtain permission-verified live access, run real daily sweeps, then measure
   repost recall with `src/autolens/ops/reposts.py` on reviewed multi-day data.
