# Getting Started — AutoLens Egypt M1

This guide provides a practical introduction to the project. Technical terms (scraping, linkage, FS+EM, etc.) retain the same names used in the code. For the official specification, see `docs/handbook_M1.pdf`.

## 1. What does the project do?

The project works with used-car listings from three Egyptian websites: Hatla2ee, ContactCars, and Dubizzle. The same car may appear on more than one website. Our task is to:

1. **Collect** listings from the supplied archive (35,394 listings).
2. **Normalize** names and numbers (for example, Toyota and its Arabic spelling map to one canonical name; normalize mileage, price, year, and other fields).
3. **Link** listings that describe the same car and assign them one stable `vehicle_id`.
4. **Evaluate** whether the links are correct, while being transparent that the current evaluation is provisional.

Final output: the `core.vehicle_link` table (each listing mapped to a `vehicle_id`) plus the `RQ1` report.

## 2. Two ways to run the project

### Method A — Your computer (recommended for development)

```bash
make install                # one-time setup (dev + parquet + vision)
make up                     # ensure folders exist and the environment is ready
make run                    # full pipeline (seconds without images)
make test                   # 46 tests
make verify                 # 16/16 file-presence checks
```

The real images (250 photos from Wikimedia Commons) are already included in `quarantine/` inside the FULL ZIP, so no download is needed. If you have a copy without images:

```bash
PYTHONPATH=src python scripts/fetch_open_images.py --n 250   # requires internet once
```

### Method B — Google Colab (for any team member)

1. Upload `AutoLens_M1_project_FULL.zip` in the first cell.
2. Run all notebook cells.
3. The notebook automatically detects the folder name and paths; no edits are required.
4. At the end, it downloads `linkage_metrics.json` and `open_images_attribution.csv`.

The `colab_quickstart.ipynb` notebook is included in the project. Upload it to Colab as well (File → Upload notebook).

## 3. Folder structure (where everything is)

```text
├── data/                       raw archive (Egypt_Used_Cars_clean.csv)
├── data_reference/             canonical dictionary (models.csv, aliases.csv)
├── data_labels/                evaluation samples + human-review template
│   ├── linkage_pairs_v1.parquet    silver labels (automatic, not human)
│   ├── human_review_template.csv   empty; must be completed by reviewers
│   └── human_labels_frozen.csv     generated after human review
├── raw/<source>/<date>/<id>.json.gz  immutable raw payloads (R3)
├── quarantine/<sha256>.jpg     250 licensed photos + optional synthetic images
├── outputs/                    all results and tables
│   ├── autolens.db             SQLite database (all tables)
│   ├── linkage_metrics.json    final metrics + scientific-integrity status
│   ├── open_images_attribution.csv  image owners and licenses
│   ├── alerts.json             daily health alerts
├── src/autolens/               all application code (see ARCHITECTURE.md)
├── scripts/                    helper scripts (images, human review, Splink, etc.)
├── tests/                      46 tests (contract / unit / integration)
├── docs/                       documentation, handbook, and reports
└── colab_quickstart.ipynb      quick-start notebook
```

## 4. What happens when you run `make run`?

There are four stages. Each uses the signature `run(run_date, ctx) -> StageResult`:

| # | Stage | File | What happens |
|---|---|---|---|
| 1 | `run_scrape` | `scrapers/run.py` | Reads the archive → saves raw `.json.gz` payloads → records `ops_scrape_run` (`degraded=1` because this is an archive, not live scraping). |
| 2 | `run_normalize` | `scrapers/run.py` | Re-parses raw data → builds the dictionary → normalizes numbers and words → adds `dq_flags`. |
| 3 | `run_fetch_images` | `scrapers/images.py` | Keeps stored images if present; if there are no stored images or URLs, returns zero rows (honest behavior). |
| 4 | `run_linkage` | `linkage/run.py` | Blocking → comparison vectors → FS+EM → thresholds → clustering → `vehicle_id` + report. |

Full details, including a diagram, are in `docs/ARCHITECTURE.md`.

## 5. Five important things to know before presenting

1. **The 1.00 scores are not real accuracy.** Evaluation uses silver labels generated from the same fields used for matching, so it is circular. `evaluation_status = provisional_silver_labels_only`.
2. **The images are real but generic.** There are 250 licensed car photos from Wikimedia Commons; they are not the actual listing photos. License and photographer details are in `open_images_attribution.csv`.
3. **There is no live scraping.** Only the archive is used. `LiveSourceScraper` is ready but disabled until permission is obtained.
4. **Human evaluation has not been completed.** Two reviewers must label at least 1,000 pairs (`scripts/label_app.py`), then `finalize_human_labels.py` calculates κ and creates a frozen test set.
5. **The repost rate has not been measured.** There is only one snapshot, so `measurable=False`.

The complete list is in `docs/REMAINING_REQUIREMENTS.md`.

## 6. Other useful files

| If you want to know... | Open |
|---|---|
| What is implemented and what is missing | `docs/REMAINING_REQUIREMENTS.md` |
| How linkage works in detail | `docs/ARCHITECTURE.md` |
| RQ1 results and metrics | `docs/report/RQ1.md` |
| Daily commands and incidents | `docs/runbook.md` |
| Table and field definitions | `docs/parsed_schema.md` |
| Data-source documentation | `docs/sources/*.md` |
| FS+EM model card | `docs/model_cards/linkage_fs_em.md` |
| Contracts and DDL | `contracts/`, `sql/ddl/staging.sql` |
| Full developer handover | `docs/DEVELOPER_GUIDE.md` |

## 7. Corrections applied in this build

- Clustering now keeps the **strongest** edges when a cluster reaches its size cap.
- Scrape `run_id` is deterministic (`archive-<date>-<input-sha>`), and raw objects are
  immutable: a conflicting rewrite raises `RawPayloadConflict` instead of overwriting.
- The golden test compares raw-file hashes and all warehouse tables across reruns.
- Multi-word makes (Land Rover, Alfa Romeo, Aston Martin, Great Wall, Rolls Royce) are
  preserved by the canonical dictionary.
- Human-label train/test splitting is group-aware by listing, preventing leakage.
- `PostgresWarehouse` applies the authoritative PostgreSQL DDL from
  `sql/ddl/staging.sql` (schemas, types, status values) instead of the SQLite DDL.
- The labelling UI no longer calls the bundled photos synthetic; it labels them as
  generic open-licensed Commons images.

## 8. Troubleshooting

- **`ModuleNotFoundError: autolens`** → run `pip install -e .` or set `PYTHONPATH=src`.
- **Images are missing** → run `scripts/fetch_open_images.py` (requires internet).
- **`assert z` in Colab** → make sure you uploaded the ZIP before selecting Run all.
- **A test fails** → run `python -m pytest tests -q` from the project folder and share the errors.
- **A question about protection or scientific integrity** → check `docs/REMAINING_REQUIREMENTS.md` before making a claim.
