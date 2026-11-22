# AutoLens Egypt — M1: Data Acquisition & Linkage

Local prototype implementing **parts of** the **Merna.pdf** handbook (AutoLens Egypt, role M1) against the
supplied used-car datasets.

**Important:** This is not yet fully compliant with the handbook. See [remaining requirements](docs/REMAINING_REQUIREMENTS.md).

## Documentation — start here

- [Getting Started](docs/GETTING_STARTED.md) — a practical overview of what the project does, how to run it locally or on Colab, and what to know before presenting it.
- [System Architecture](docs/ARCHITECTURE.md) — explains the data flow, the four stages, why each stage exists, and includes diagrams and a code map.
- [RQ1 Report](docs/report/RQ1.md) — results and metrics, with scientific-integrity caveats.
- [Daily Runbook](docs/runbook.md) — commands, images, incidents, and monitoring.
- [Developer Guide](docs/DEVELOPER_GUIDE.md) — handover guide covering installation, execution, files and stages, tests, configuration, modifications, and troubleshooting.
- [Remaining Requirements](docs/REMAINING_REQUIREMENTS.md) — an honest list of what is still missing.

## What is implemented or prototyped

| Handbook item | Implementation |
|---|---|
| R1 source verification | `docs/sources/*.md` + compliant live scaffold `scrapers/live.py` (disabled until permission) |
| R2 scraper interface | `src/autolens/scrapers/base.py`, `archive.py`, `live.py` |
| R3 immutable raw | `common/storage.py::ObjectStore.put_raw` (`.json.gz`, keyed by source/date/id); deterministic `archive-<date>-<sha>` run_id, conflicting rewrites raise `RawPayloadConflict` |
| R4 daily snapshot | `scrapers/run.py::run_scrape` + `ops.scrape_run` + `ops/monitoring.py` (coverage) |
| R5 politeness | `scrapers/rate_limiter.py`, `live.py` (≤1 req/s, robots.txt, UA, off-peak, stop-on-429) |
| R6 no personal data | schema forbids seller fields; parsers never read them |
| R7 images + pHash | `scripts/fetch_open_images.py` (250 real CC-licensed car photos from Wikimedia Commons, attributed), `scrapers/images.py`, `photo_match` feature; synthetic fallback optional |
| R8 canonical dictionary | `scrapers/normalize/dictionary.py` (multi-word makes preserved), `price_dictionary.py` (official price-list seeding) |
| R9 normalisation + flags | `scrapers/normalize/units.py`, `flags.py` |
| R10 FS+EM + supervised | `linkage/fs.py`, `supervised.py`, `evaluate.py`, `splink_compare.py`, human-label tooling |
| R11 stable ids + cap | `linkage/cluster.py` (strongest edges kept first when cap is full) |
| R12 reposts | `ops/reposts.py` (rule + recall; not measurable on single snapshot) |
| R13 health metrics | `ops.scrape_run`, `ops/monitoring.py`, `.github/workflows/nightly.yml` |
| R14 idempotent + golden test | `tests/integration/test_e2e_golden.py` (46 tests total) |

## Run

```bash
make install
make up
make run        # runs scrape -> normalize -> fetch_images -> linkage
make test       # 46 tests incl. worked example and golden e2e
make verify     # checks handbook requirement coverage
```

Or directly:
```bash
PYTHONPATH=src python3 -m autolens.pipelines.entrypoints --run-date 2026-01-15
```

Additional tooling (needs external input — see REMAINING_REQUIREMENTS):
```bash
# Two annotators label >=1000 pairs in a browser, then:
streamlit run scripts/label_app.py -- --reviewer 1
streamlit run scripts/label_app.py -- --reviewer 2
python scripts/finalize_human_labels.py     # kappa, adjudication, frozen test, CIs

python scripts/seed_dictionary_from_prices.py   # after adding an official price list
python scripts/run_splink_comparison.py        # optional Splink baseline
python -c "from autolens.ops.monitoring import check_health; ..."  # nightly alerts
```

## Dataset used

- `data/Egypt_Used_Cars_clean.csv` — 35,394 listings across hatla2ee/contactcars/dubizzle.
- `data/hatla2ee_*.csv` — supplementary Hatla2ee archive with descriptions (text-feature
  development for M4; not a fourth source).

## Real results and honest caveats

See `docs/report/RQ1.md`. Headline: 1,102,506 candidate pairs, reduction ratio 0.99824,
7,642 accepted pairs, 32,318 clusters. Evaluation uses **provisional silver labels**
derived from the same fields used for matching, so P/R/F1 = 1.00 is a sanity check, not
a valid performance estimate. Human labelling (§8.8) is still required.

## Notes on substitutions

The handbook specifies live scraping, PostgreSQL, MinIO, Splink, sentence-transformers
and imagehash. This prototype keeps the same contracts but uses honest local
substitutions where external input/permission is missing:
- the supplied archive stands in for live pages (same `SourceScraper` interface); it is
  recorded as `degraded=1`, **not** claimed as live scraping,
- SQLite + filesystem buckets stand in for PostgreSQL/MinIO (same table/key names),
- Levenshtein/n-gram similarity is implemented locally instead of rapidfuzz,
- FS+EM is implemented from scratch as required; Splink is an optional unsupervised baseline,
- pHash uses scipy DCT over 250 **generic open-licensed** Commons photos (attributed);
  they are not photos of the listed vehicles; description text is not available.

Every stage keeps the same entry points (`run(run_date, ctx) -> StageResult`) so M5's
Prefect flows can wire them without changes.

## Label export & images (honesty notes)

The linkage stage writes Parquet if `pyarrow` is installed (`pip install -e ".[parquet]"`), otherwise CSV. The separate `data_labels/human_review_template.csv` is **unlabelled** and needs two human reviewers. All `evaluation_status` in `outputs/linkage_metrics.json` is `provisional_silver_labels_only`.

The 35,394 listings are assigned 250 **real, open-licensed car photos** downloaded from Wikimedia Commons (CC0 / Public domain / CC BY / CC BY-SA) by `scripts/fetch_open_images.py`, with full attribution in `outputs/open_images_attribution.csv`. Each is stored once in `quarantine/` keyed by SHA-256, pHash-computed, and shared by same-car listings; rows are marked `status='open_source_commons'`. **Caveat:** these are generic car photos, not photographs of the specific listings and not scraped from target sites. Synthetic placeholders are available for offline demos via `AUTOLENS_SYNTHETIC_IMAGES=1` (default OFF).
