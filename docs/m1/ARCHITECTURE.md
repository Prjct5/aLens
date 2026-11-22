# Project Architecture — How AutoLens M1 Works Internally

This document complements `GETTING_STARTED.md`. It explains **why** each stage exists and how the stages interact, not only **what** they do. For the official specification, see `docs/handbook_M1.pdf`.

## 1. The complete picture (data flow)

```text
Archive (CSV)
    |
    v
run_scrape  ---- raw payloads (.json.gz) ----> raw/ (R3, immutable)
    |
    v
run_normalize <---- canonical dictionary
    |
    v
run_fetch_images <---- 250 CC-licensed photos (outside the pipeline)
    |
    v
run_linkage ----> FS+EM + clustering ----> vehicle_id
    |
    v
Evaluation ----> Cohen's kappa (κ), when human labels are available
```

## 2. Governing principle: every stage is independent and idempotent

Every stage uses the same signature:

- `RunContext` carries `settings`, `db`, `store`, and `log` — **there is no global state**.
- Every table has a clear primary key and uses `INSERT OR REPLACE`; running the same date again does not create duplicates.
- `run_id = f"archive-{run_date}-{sha256(input_csv)[:10]}"` and `link_run_id` are both
  deterministic, so reruns do not create new run identities or new raw bytes. A
  conflicting write to an existing raw key raises `RawPayloadConflict`.
- The golden test (`test_e2e_golden.py`) runs the pipeline twice and checks raw-file SHA-256
  hashes plus every warehouse table, not only row counts.

## 3. Storage layer (why SQLite/files instead of Postgres/MinIO?)

The handbook requires Postgres + MinIO. This implementation uses the same **table and key names** with SQLite + the filesystem so tests can run without a network or server. The later switch is isolated:

| Local (default) | Production (M5/team) | File |
|---|---|---|
| `Warehouse` (SQLite) | `PostgresWarehouse` | `common/storage.py` ↔ `common/storage_pg.py` |
| `ObjectStore` (folders) | `MinioObjectStore` | the same two files |

`sql/ddl/staging.sql` is the authoritative production DDL (schemas `staging`/`ops`/`core`,
CHECK constraints, `payload_key`, `phash char(16)`, status values including
`open_source_commons`). `PostgresWarehouse` applies this DDL directly; it no longer
imports the SQLite DDL. Logical table names are translated automatically.

### The seven tables

| Table | Key | Purpose |
|---|---|---|
| `staging_parsed_listing` | (source, id, scrape_date) | Simplified listing version + payload |
| `staging_normalized_listing` | (source, id, scrape_date) | Canonical values + `dq_flags` |
| `ops_scrape_run` | (run_id, source) | Health metrics (`degraded`, `n_error`, etc.) |
| `core_vehicle_link` | (listing_key, link_run_id) | Each listing → `vehicle_id` |
| `core_vehicle_id_merge` | (old_id, new_id) | Identity-merge history |

## 4. Stage 1 — Scrape (collection)

`ArchiveSource` imitates the real `SourceScraper` interface:

- `discover()` → returns listing IDs from the CSV.
- `parse(payload, url, scraped_at)` → a **pure function**: the same bytes produce the same result. If a website layout changes later, we can update the parser and re-parse the raw data without scraping again (handbook 8.2).
- `fetch_images()` → an explicit no-op (the archive has no image URLs).
- `make_payload()` → **does not read any seller field** (name/phone), as required by rule R6/16.9.

> **Health note:** the run is recorded as `degraded=1` with `warning=archive_replay_not_live_snapshot` because the archive is one historical snapshot, not a live daily sweep. We do not claim otherwise.

## 5. Stage 2 — Normalize (cleaning)

- `ModelDictionary.fit()` mines aliases from repeated `make_raw/model_raw` values and builds a stable `model_id` (1,361 aliases). `map()` accepts exact or fuzzy matches (≥0.85).
- `units.py` converts Arabic-Indic digits, Arabic number words (including the word for thousand), and currency (USD uses a fixed rate of 48 — an academic assumption, not a real exchange rate).
- `flags.py` adds `price_below_floor`, `price_outlier` (modified z-score on ln(price)), `mileage_placeholder`, `year_invalid`, etc. **Rows are never deleted**; they are only flagged.

## 6. Stage 3 — Images

Default mode: 250 CC-licensed car photos from Wikimedia Commons in `quarantine/`:

- `scripts/fetch_open_images.py` downloads them politely (User-Agent + ≤1 request/second + 400px thumbnails).
- Each image: `image_id = sha256(bytes)` and a 64-bit `phash` via DCT (scipy).
- Listings with the same car type (make/model/year/...) receive the same image, allowing `photo_match` to work as it would with real images from M3.
- `outputs/open_images_attribution.csv` contains the license, photographer, and link for every image.
- **These are not the actual listing photos** — they are generic photos. This must be stated in any presentation.

Alternative mode: `AUTOLENS_SYNTHETIC_IMAGES=1` generates locally drawn images for explanation only (offline demo).

## 7. Stage 4 — Linkage (the core of the project)

This is the most important stage. Its steps are performed in this order.

### 7a. Blocking (reducing the search space)

Instead of comparing every listing with every other listing (35k² = 1.2 billion pairs), we group only records with the same `(make_canon, model_canon, year ± 1)`. The result is **1,102,506 candidate pairs**.

### 7b. Comparison vectors

For each pair, we calculate 9 fields, each with 3 possible levels:

- `1` = agree
- `0` = disagree
- `-1` = missing (data is unavailable — this adds no evidence and is not a disagreement)

Fields: `same_year`, `mileage_close(≤5%)`, `same_governorate`, `price_close(≤10%)`, `same_transmission`, `same_fuel`, `same_body`, `desc_sim` (missing), and `photo_match` (from pHash).

### 7c. FS+EM (Fellegi–Sunter) — implemented in this project

The equation is `match_weight = log2(m/u)` for each field, and the total weight is the sum of the field weights.

- `m_k` = probability of agreement when the pair is a match.
- `u_k` = probability of agreement when the pair is not a match.
- They are estimated with EM (E-step in log space; M-step ignores `-1` = missing).
- The prior is capped at 0.05 to avoid a degenerative local optimum (handbook 6.6).
- The result is `fs_parameters.csv`, containing `m/u` for each field and their interpretation.

### 7d. Thresholds and evaluation

- `choose_thresholds` selects `T_upper` (high precision) and `T_lower` (lower recall).
- Evaluation on 2,973 silver pairs gives P/R/F1 = 1.00. **This is a sanity check, not an accuracy estimate**, because the labels are circular.
- Splink (the professional library) was run as an unsupervised baseline: P=1.00 but recall≈0.23.
- Supervised models (logreg + GBM) use group CV to avoid leakage (pitfall 2).

### 7e. Clustering

- Accepted pairs above the threshold become edges → DSU (union-find) → clusters.
- Each cluster has a stable `vehicle_id` (the smallest ID wins), and the cap is 9 (sources × 3).
- `split_large_components` sorts edges **strongest first** and keeps the strongest edges
  when the cap is reached; a weak edge can no longer displace a strong one.
- Result: **32,318 vehicles** from 35,394 listings (average cluster size 1.1).

## 8. Human evaluation (outside the pipeline — still required)

This is the most important open gap:

Two reviewers (reviewers 1 and 2)
   ├─▶ Cohen's κ (inter-reviewer agreement; unsure is excluded)
   ├─▶ adjudication (resolve disagreements)
   ├─▶ human_labels_frozen.csv (80% train / 20% frozen test split, group-aware by listing)
   └─▶ outputs/human_evaluation.json (P/R/F1 + bootstrap CIs on test only)

Golden rules:

- The threshold is selected on **train** only — the test set is frozen for final measurement.
- `unsure` is excluded from κ and from the main score.
- Silver labels must **never** be called ground truth.

## 9. Monitoring and alerts (R13)

- `ops/monitoring.py` calculates success rate and coverage and writes `outputs/alerts.json`.
- `.github/workflows/nightly.yml` opens a GitHub issue if success < 90%, there is a spike in parse failures, or a 429 response occurs.
- `ops/reposts.py` calculates repost recall only when multi-day data and human review are available. Currently, it honestly returns `measurable=False`.

## 10. Limitations and scientific integrity (very important before presenting)

| What we have | What we do not have |
|---|---|
| Tested prototype (46 tests + golden e2e) | Live scraping with legal permission |
| Real licensed photos (generic) | The actual listing photos |
| FS+EM + Splink + supervised models | Human evaluation of ≥1,000 pairs + κ |
| Repost measurement (code ready) | Multi-day data |
| SQLite/files (same contracts as PG/MinIO) | Actual Postgres/MinIO services |

> **Suggested defense statement:**
> "The project is implemented as a complete, tested prototype and follows scientific-integrity requirements (no unsupported claims about accuracy, images, or live scraping). Full compliance with the handbook requires the external evidence listed in `docs/REMAINING_REQUIREMENTS.md`."

## 11. Quick code map

```text
├── common/        config, schemas (Pydantic contracts), storage, stage interface, text utilities
├── pipelines/     entrypoints.py — entry point + run_all()
└── tests/         contract/ + unit/ + integration/ (46 tests)
```
