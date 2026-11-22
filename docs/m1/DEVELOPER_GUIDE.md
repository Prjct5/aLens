# AutoLens Egypt — M1 Developer Guide

**Purpose:** practical handover guide for a developer who is receiving the M1 codebase and needs to understand, run, test, debug, and extend it.

> **Scope and honesty:** this guide describes the implementation in this repository, not an idealised production system. The current default workflow replays the supplied CSV archive. It does not perform a live daily scrape. Local storage defaults to SQLite and filesystem directories; PostgreSQL/MinIO adapters are optional. The 250 Wikimedia Commons images are licensed generic car images, not photos of the specific listings. Linkage metrics based on generated silver labels are provisional and are not human-validated accuracy.

## 1. What M1 owns

M1 (Data Acquisition & Linkage) turns used-car listing records from Hatla2ee, ContactCars, and Dubizzle into normalized records and links records that appear to describe the same physical vehicle.

The main outputs are:

- normalized listing rows in `staging_normalized_listing`;
- image metadata in `staging_image_fetch`;
- vehicle-to-listing assignments in `core_vehicle_link`;
- merge history in `core_vehicle_id_merge`;
- run metrics and review files under `outputs/` and `data_labels/`.

The main entry point is `src/autolens/pipelines/entrypoints.py`. The pipeline executes four stages in order: archive acquisition, normalization, image processing, and record linkage.

## 2. Repository map

```text
Default Project/
├── data/                         Input CSV archive
├── data_reference/               Canonical make/model dictionary and aliases
├── data_labels/                  Generated candidate labels and human-review files
├── raw/                          Immutable raw payloads, grouped by source/date/id
├── quarantine/                   Image files addressed by SHA-256
├── outputs/                      SQLite database, metrics, CSV/JSON reports
├── src/autolens/
│   ├── common/                   Settings, schemas, storage, stage context, helpers
│   ├── pipelines/                 CLI entry point and pipeline orchestration
│   ├── scrapers/                  Source interface, archive/live adapters, images
│   │   └── normalize/             Dictionary mapping, unit conversion, quality flags
│   ├── linkage/                   Blocking, comparisons, FS+EM, evaluation, clustering
│   └── ops/                       Monitoring and repost measurement
├── scripts/                       Human labelling, image fetch, dictionary and analysis tools
├── tests/                         Contract, unit, and integration tests
├── docs/                          Architecture, runbook, source notes, reports
├── sql/ddl/                        Reference SQL DDL
├── colab_quickstart.ipynb          Google Colab quick-start notebook
├── Makefile                        Common developer commands
└── pyproject.toml                  Python package and dependency definitions
```

### Where to start reading

1. `README.md` — short project map and commands.
2. `docs/GETTING_STARTED.md` — first run instructions.
3. `docs/ARCHITECTURE.md` — detailed stage and data-flow explanation.
4. `src/autolens/pipelines/entrypoints.py` — actual orchestration.
5. `src/autolens/common/stage.py` and `common/config.py` — stage context and configuration.
6. `docs/runbook.md` — operational procedures and known limitations.
7. `docs/REMAINING_REQUIREMENTS.md` — what is still needed before claiming full handbook compliance.

## 3. Environment setup

### Requirements

- Python 3.11 or newer.
- `pip` and `venv`.
- Git is recommended for collaborative development.
- Internet is needed to install packages unless they are already cached. The archive replay and tests do not require live access to the car websites.

### Linux / macOS

From the repository root (`Default Project/`):

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,parquet,vision]"
```

If editable installation is unavailable in a restricted/offline environment, and the base dependencies are already installed, run commands with the source directory on `PYTHONPATH`:

```bash
PYTHONPATH=src python -m pytest tests -q
PYTHONPATH=src python -m autolens.pipelines.entrypoints --run-date 2026-01-15
```

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,parquet,vision]"
```

### What the install groups mean

- Base dependencies: pandas, numpy, pydantic, scipy, scikit-learn.
- `dev`: pytest and pytest-cov.
- `parquet`: pyarrow, for Parquet exports (otherwise some outputs can be CSV).
- `vision`: Pillow and imagehash-related optional image tooling.
- `scraping`, `linkage`, `nlp`, and `production`: optional integrations; they are not all required for the local golden pipeline.

## 4. Run the project

Run these commands from `Default Project/` with the virtual environment active:

```bash
make up
make test
make run
```

What they do:

| Command | Behaviour |
|---|---|
| `make up` | Creates expected local folders and checks core imports. It does **not** start Docker, PostgreSQL, MinIO, MLflow, or Prefect. |
| `make test` | Runs `python -m pytest tests -q`. |
| `make run` | Runs all four pipeline stages for the date configured in the Makefile (`2026-01-15`). |
| `make lint` | Compiles source and tests to catch syntax errors. |
| `make verify` | Checks handbook-requirement file coverage; it is not a behavioural compliance test. |

To choose another run date, call the module directly:

```bash
PYTHONPATH=src python -m autolens.pipelines.entrypoints --run-date YYYY-MM-DD
```

The date is parsed as ISO format. The current default in `Settings` is `2026-01-15`.

## 5. Pipeline walkthrough

The orchestration is in `src/autolens/pipelines/entrypoints.py`. `run_all()` builds a `RunContext`, executes the stages in sequence, and closes the database connection.

| Order | Stage | Main implementation | What it does |
|---|---|---|---|
| 1 | Acquisition / archive replay | `scrapers/run.py`, `scrapers/archive.py` | Reads the supplied archive through the common scraper interface and stores raw payloads. The current run is marked degraded because this is not a live website snapshot. |
| 2 | Normalization | `scrapers/run.py`, `scrapers/normalize/` | Canonicalizes makes/models and units, validates fields, and records data-quality flags without silently deleting suspicious rows. |
| 3 | Image stage | `scrapers/images.py`, `scripts/fetch_open_images.py` | Processes available image records and perceptual hashes. The bundled Commons photos are generic licensed images, not listing-specific photos. |
| 4 | Linkage | `linkage/run.py` and `linkage/` | Generates candidate pairs, builds comparison vectors, estimates Fellegi–Sunter parameters with EM, scores pairs, selects thresholds, and clusters accepted links into vehicle IDs. |

### Linkage substeps

1. **Blocking** (`linkage/blocking.py`): limits comparisons to plausible candidate pairs rather than comparing every listing with every other listing.
2. **Comparison** (`linkage/comparison.py`): creates field-level agreement/disagreement/missing values for each pair.
3. **Fellegi–Sunter + EM** (`linkage/fs.py`): estimates match/non-match agreement probabilities and calculates pair weights.
4. **Evaluation and supervised comparisons** (`linkage/evaluate.py`, `supervised.py`): calculates provisional metrics and comparator model scores.
5. **Clustering and IDs** (`linkage/cluster.py`): converts accepted pairs to graph edges and assigns vehicle IDs while applying the configured cluster-size cap and preserving prior IDs where possible.

## 6. Configuration

Configuration is read in `src/autolens/common/config.py` from environment variables. Defaults are relative to `PROJECT_ROOT` (default `.`).

| Variable | Default | Meaning |
|---|---|---|
| `PROJECT_ROOT` | `.` | Project root directory. |
| `DATA_DIR` | `data` | Input data directory. |
| `OUTPUT_DIR` | `outputs` | Output directory. |
| `RAW_DIR` | `raw` | Raw payload directory. |
| `QUARANTINE_DIR` | `quarantine` | Image quarantine directory. |
| `DB_PATH` | `outputs/autolens.db` | Local SQLite database path. |
| `RUN_DATE` | `2026-01-15` | Default run date. |
| `SCRAPER_MIN_INTERVAL_S` | `1.0` | Minimum interval used by compliant scraper components. |
| `SCRAPER_CONCURRENCY` | `2` | Scraper concurrency setting. |
| `SCRAPER_USER_AGENT` | `AutoLens-Egypt/0.1 ...` | Scraper identification string. Replace the placeholder contact before any approved live use. |
| `LOG_LEVEL` | `INFO` | Logging verbosity. |

Example:

```bash
PROJECT_ROOT="$PWD" RUN_DATE=2026-01-15 LOG_LEVEL=INFO \
  PYTHONPATH=src python -m autolens.pipelines.entrypoints --run-date 2026-01-15
```

## 7. Outputs and how to inspect them

After a successful run, inspect:

- `outputs/autolens.db` — local SQLite warehouse containing staging, ops, and core tables.
- `outputs/linkage_metrics.json` — pair counts, feature names, FS parameters, thresholds, and evaluation status/metrics.
- `outputs/fs_parameters.csv` — estimated `m` and `u` values by comparison feature.
- `outputs/labelled_pairs.csv` — generated labelled-pair view; these are not human labels.
- `data_labels/linkage_pairs_v1.parquet` — generated silver-label pair data when Parquet support is installed.
- `data_labels/human_review_template.csv` — blank template for independent human review.
- `outputs/open_images_attribution.csv` — image source/licence attribution.
- `outputs/alerts.json` — health-check output when monitoring is run.
- `raw/` and `quarantine/` — stored raw payloads and image objects.

Use SQLite tools (for example, DB Browser for SQLite) to inspect the database. Do not edit generated database rows manually as a substitute for changing the pipeline.

## 8. Tests and quality checks

Run the complete suite before and after making changes:

```bash
make test
```

Useful focused commands:

```bash
python -m pytest tests/unit -q
python -m pytest tests/contract -q
python -m pytest tests/integration -q
python -m pytest tests/integration/test_e2e_golden.py -q
```

Test folders:

- `tests/unit/`: individual functions and edge cases.
- `tests/contract/`: schema and contract checks.
- `tests/integration/`: multi-stage behaviour, ID stability, and golden pipeline checks.

Also run:

```bash
make lint
make verify
```

Remember: `make verify` checks the presence/coverage of expected files. Passing it does not prove that a requirement is fully operational.

## 9. Human labelling and valid evaluation

The current automatically generated silver labels are useful for development checks but are derived from project fields and are not independent ground truth. A displayed P/R/F1 of 1.00 must not be described as validated real-world accuracy.

For a human evaluation, the repository provides:

```bash
streamlit run scripts/label_app.py -- --reviewer 1
streamlit run scripts/label_app.py -- --reviewer 2
python scripts/finalize_human_labels.py
```

Two reviewers should label the required sampled pairs independently. The finalization script calculates agreement (including Cohen's kappa), handles adjudication, creates a frozen train/test split, and evaluates on the held-out test set. Follow the exact procedure and minimum sample requirements in `docs/runbook.md` and `docs/REMAINING_REQUIREMENTS.md` before publishing accuracy claims.

## 10. Adding or changing code safely

### Change a parser or source

1. Read the relevant source note under `docs/sources/`.
2. Update the appropriate scraper/parser under `src/autolens/scrapers/`.
3. Add or update a small, privacy-safe fixture under `tests/fixtures/`.
4. Add tests for both normal and failure cases.
5. Re-run the full tests and update the relevant documentation.

### Change normalization

- Dictionary mapping lives in `scrapers/normalize/dictionary.py` and related reference data.
- Unit parsing lives in `scrapers/normalize/units.py`.
- Quality flags live in `scrapers/normalize/flags.py`.
- Preserve the rule that suspicious records are flagged rather than silently dropped.

### Change linkage

- Candidate generation: `linkage/blocking.py`.
- Feature definitions: `linkage/comparison.py`.
- FS/EM scoring: `linkage/fs.py`.
- Thresholds and metrics: `linkage/evaluate.py`.
- Cluster construction and stable IDs: `linkage/cluster.py`.
- End-to-end linkage orchestration: `linkage/run.py`.

When changing a feature, check its effect on the comparison matrix, model parameters, thresholds, tests, output schema, and documentation. Avoid evaluating on labels that were generated from the same feature being evaluated.

### Stage interface

Pipeline stages are designed around `run(run_date, ctx) -> StageResult`. `RunContext` provides settings, database access, object storage, and logging. Keep stage behaviour deterministic where possible and safe to rerun for the same date.

## 11. Live scraping: important restriction

`src/autolens/scrapers/live.py` is a compliant scaffold, not proof that live scraping has been performed. It is disabled from the default pipeline until the team has checked and approved the source terms, robots rules, and permission evidence. Never work around a 403, 429, CAPTCHA, or a site's refusal. Do not claim archive replay is a live snapshot.

Before enabling live collection, complete the source review documents, replace the placeholder contact in the user-agent, obtain team approval, and follow the restrictions in `docs/runbook.md` and the handbook.

## 12. Current limitations / handover checklist

Before describing this repository as fully compliant or production-ready, the receiving developer/team must address the evidence-dependent items below:

- [ ] Verify and document source terms, robots rules, and permission for live collection.
- [ ] Implement and validate real multi-day live snapshots and source freshness/coverage monitoring.
- [ ] Obtain lawful listing-specific images where permitted; the included Commons images are generic only.
- [ ] Complete independent human annotation and held-out evaluation; do not report silver-label scores as real accuracy.
- [ ] Obtain reviewed multi-day data before reporting repost recall/rates.
- [ ] Configure and test PostgreSQL/MinIO and team orchestration/credentials if production deployment requires them.
- [ ] Run the notebook in the team's actual Google Colab account/environment if Colab is the delivery route; local notebook inspection is not a Colab execution test.

The detailed status table is maintained in `docs/REMAINING_REQUIREMENTS.md`; operational instructions are in `docs/runbook.md`.

## 13. Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| `ModuleNotFoundError: autolens` | Package not installed or `src` not on Python path | Activate the virtual environment, install with `pip install -e ".[dev,parquet,vision]"`, or use `PYTHONPATH=src`. |
| Missing Python package | Dependencies were not installed or optional group omitted | Install the required group from `pyproject.toml`; use `.[dev,parquet,vision]` for the normal development setup. |
| Parquet writer unavailable | `pyarrow` is not installed | Install `.[parquet]`; otherwise use the CSV outputs where provided. |
| Input file not found | Command run from the wrong directory or `PROJECT_ROOT` points elsewhere | Run from `Default Project/` or set `PROJECT_ROOT` to its absolute path. |
| No normalized rows | Input archive missing/empty or acquisition stage did not complete | Check `data/`, the acquisition stage output, and the run logs before running linkage. |
| Live source returns 403/429/CAPTCHA | Site refusal or rate limiting | Stop collection, do not evade; notify the team and follow the source review/runbook. |
| Metrics show perfect scores | Provisional silver labels may be circular | Check `evaluation_status`; complete independent human annotation before making accuracy claims. |

## 14. Handover: first 30 minutes for the next developer

1. Read this guide and `docs/REMAINING_REQUIREMENTS.md`.
2. Create and activate a Python 3.11 virtual environment.
3. Install `.[dev,parquet,vision]`.
4. Run `make up`, `make test`, and `make run`.
5. Open `outputs/linkage_metrics.json` and `outputs/autolens.db` to inspect the generated results.
6. Read `docs/ARCHITECTURE.md`, then trace one stage from its entry point into its implementation.
7. Pick one small change, add a test first, implement it, and rerun the test suite.

**If you need one source of truth for unfinished work, use `docs/REMAINING_REQUIREMENTS.md`.** Do not infer completion from the presence of a module or script alone.
