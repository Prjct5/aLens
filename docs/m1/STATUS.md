# M1 completion status — honest, evidence-based update

This file is the single source of truth for what is **implemented**, what is
**code-ready but needs external input**, and what must **never be claimed**
without real evidence. See also `docs/report/RQ1.md`.

## 1. Fully implemented and tested locally

| Item | Where | Evidence |
|---|---|---|
| Scraper interface, pure parsers, raw immutability | `src/autolens/scrapers/base.py`, `archive.py`, `common/storage.py` | 46 tests pass; deterministic `archive-<date>-<sha>` run_id; raw key conflict raises instead of overwriting; golden test compares raw hashes + all tables |
| Normalisation, canonical dictionary, flags | `scrapers/normalize/*` | mapping rate 1.0 on archive; multi-word makes (Land Rover, Alfa Romeo, …) preserved |
| Blocking, comparison vectors, FS+EM, supervised, clustering | `src/autolens/linkage/*` | unit + integration tests, worked handbook example |
| Stable `vehicle_id`, cluster cap, id merges | `linkage/cluster.py` | strongest edges kept first under cap; two-day id-stability test |
| **Image quarantine + SHA-256 + pHash + `photo_match`** | `scripts/fetch_open_images.py`, `scrapers/images.py`, `linkage/comparison.py` | 250 real CC photos, 35,394 image rows, 46 tests |
| **Image provenance transparency** | `outputs/open_images_attribution.csv`, `status='open_source_commons'` + optional `synthetic_images_manifest.csv` | clear label and licence on every image source |
| **Human labelling tooling (view, κ, adjudication, frozen 80/20 split, test evaluation)** | `scripts/label_app.py`, `scripts/finalize_human_labels.py`, `scripts/kappa.py` | group-aware split prevents listing leakage; deterministic; caption corrected for open-source photos |
| **Compliant live-fetch scaffold (robots, UA, ≥1 req/s, off-peak, stop-on-429)** | `src/autolens/scrapers/live.py` | `tests/unit/test_ops_and_dictionary.py` |
| **Health metrics + nightly alerts** | `src/autolens/ops/monitoring.py`, `.github/workflows/nightly.yml` | `outputs/alerts.json` |
| **Repost rule + recall measurement** | `src/autolens/ops/reposts.py` | returns `measurable=False` on single snapshot |
| **Price-list dictionary seeding** | `scrapers/normalize/price_dictionary.py`, `scripts/seed_dictionary_from_prices.py` | merge test preserves ids |
| **Production storage adapters + CI** | `common/storage_pg.py`, `sql/ddl/staging.sql`, `.github/workflows/ci.yml` | PG adapter now applies the authoritative PG DDL (schemas, types, status values); still needs a real server to validate |

## 2. Needs real external input before any compliance claim

1. **Source permission / terms / robots evidence.** `docs/sources/*.md` record the
   archive-based verdict; live verification must be completed and approved by the
   team. `LiveSourceScraper` is ready but disabled by default
   (`AUTOLENS_LIVE_ENABLED`, see `docs/runbook.md`). A CSV replay is not live scraping.
2. **Daily index sweeps.** Need real multi-day observations to measure ≥95%
   coverage, `gone/error` states and freshness. Archive replay is flagged
   `degraded=1` and does **not** claim these.
3. **Lawful images — NOW PARTIALLY ADDRESSED.** `scripts/fetch_open_images.py`
   downloaded 250 real car photos from Wikimedia Commons under free licences
   (CC0 / Public domain / CC BY / CC BY-SA), with full attribution in
   `outputs/open_images_attribution.csv`. Stored in `quarantine/` keyed by SHA-256,
   pHash-computed, assigned to all 35,394 listings as `status='open_source_commons'`
   (250 distinct pHashes shared by same-car seeds). **Honest caveat:** these are
   generic open-licensed car photos, NOT photographs of the specific listed
   vehicles and NOT scraped from target sites. They exercise the image pipeline
   and `photo_match` with real imagery but are not evidence a listing had a photo.
   Synthetic placeholders remain available via `AUTOLENS_SYNTHETIC_IMAGES=1` for
   offline demos (default is now OFF).
4. **Official weekly new-car price list.** Drop an approved CSV at
   `data_reference/official_new_car_prices.csv` and run
   `scripts/seed_dictionary_from_prices.py` (R8).
5. **Two human annotators.** Run `streamlit run scripts/label_app.py -- --reviewer 1`
   and `--reviewer 2`, then `python scripts/finalize_human_labels.py`. Needs ≥1,000
   sampled pairs, Cohen's κ, adjudication, and the frozen 20% test subset. Silver
   P/R/F1 = 1.00 must **not** be reported as genuine accuracy.
6. **Reviewed multi-day sample for reposts.** `ops/reposts.py` returns
   `measurable=False` until reviews exist. Nightly alerts need real runs.
7. **PostgreSQL / MinIO / team CI.** Adapters exist but need drivers, credentials
   and the team's orchestration (M5); local SQLite/filesystem remains the default.

## 3. Explicit non-claims

- No live scraping has been performed; no source permission is asserted.
- The 250 downloaded photos are real but generic open-licensed car images, not
  photographs of the specific listings; attribution is in `open_images_attribution.csv`.
- No human ground truth exists yet; all P/R/F1 numbers are provisional silver-label
  sanity checks (`evaluation_status=provisional_silver_labels_only`).
- The Splink baseline is **unsupervised EM only** (`method=splink_fs_em_unsupervised_only`),
  P=1.00 but recall≈0.23 on silver pairs — do not describe it as label-trained.
- `make verify` checks file presence, not behavioural compliance.

## Findings from the integration run (added by M5, 2026-11-21)

- Real cross-posts exist in the archive (14 verified through `h`-prefixed dubizzle ids) and the
  linker found none of them. Use them as an independent evaluation set (`check_cross_posts.py`,
  `diagnose_pairs.py`) and fix: graded closeness features, handling of missing fields in the
  threshold, tie-breaking when splitting large groups, and the new `color`, `condition` and
  `payment_option` fields as extra evidence.
- The archive has no city, description or photos, so `governorate_code` is 98.9% null and
  text/image features cannot be built from it.
- 2,195 listings are new cars (out of the used-car scope).
- Diagnosis of the 14 known cross-posts: 12 fall 0.013 bits below the cut-off (body_type missing
  in one listing), 2 are in different blocks (model naming). Fix candidates, in order: second
  blocking pass on (make, year, exact price, exact mileage); drop features with m close to u from
  the decision; add exact-match levels for price and mileage; use `color`, `condition` and
  `payment_option`; evaluate against real cross-posts, not silver labels.
- RQ1 cannot be answered honestly from this archive (no photos, descriptions or city).
