# Runbook (M1)

## Normal daily run
```bash
make up
make run                 # all four stages; idempotent for the same RUN_DATE
make test
```
Outputs: `outputs/autolens.db`, `outputs/linkage_metrics.json`, `outputs/unmapped_review.csv`,
`raw/<source>/<run_date>/<id>.json.gz`.

## Restart a failed source
1. Check `ops.scrape_run` for `degraded=1`, `n_error`, `http_429_count`.
2. If 429/403 or CAPTCHA: **stop**, lower rate, wait with exponential back-off, notify team. Never evade.
3. Re-run `run_scrape(run_date, ctx)` for that source only. Raw objects are keyed by
   source/date/id: identical bytes are a no-op; different content raises
   `RawPayloadConflict` instead of overwriting. Archive `run_id` is deterministic
   (`archive-<date>-<input-sha>`), so reruns do not create new run identities.
4. Re-parse from raw with `run_normalize`; never edit raw payloads (rule 15.9.2).

## Layout change / parser bug
Update `ArchiveSource.parse()` (or the live site's parser), add the new page as a fixture
in `tests/fixtures/`, then re-parse all stored raw payloads. Because `parse()` is a pure
function of saved bytes, no re-scraping is needed (8.2).

## Add a source
1. Write `docs/sources/<source>.md` (D1) and get the verdict approved.
2. Add a `SourceScraper` subclass in `src/autolens/scrapers/`, register it in `SOURCES`,
   add fixtures + contract tests, add it to the golden test (11.4).
3. Contract changes (new source enum value) require the process in 15.7: issue, additive
   change, regenerate schemas, all consumers approve, golden test green.

## Human labelling (8.8) — required before reporting RQ1 accuracy
```bash
streamlit run scripts/label_app.py -- --reviewer 1    # independent reviewer 1
streamlit run scripts/label_app.py -- --reviewer 2    # independent reviewer 2
python scripts/finalize_human_labels.py              # kappa + adjudication + frozen 80/20 split
```
`data_labels/human_labels_frozen.csv` is the frozen set: keep the `test` rows untouched
for final evaluation. The 80/20 split is **group-aware by listing** (pairs sharing a
listing never cross train/test). `outputs/human_evaluation.json` scores FS on that test
split with the threshold chosen on `train` only and bootstrap CIs. `unsure` pairs are
excluded from κ.

## Images (R7)
250 real open-licensed car photos (Wikimedia Commons, CC0/CC BY/CC BY-SA) are in
`quarantine/`, attributed in `outputs/open_images_attribution.csv`, and assigned to
all listings as `status='open_source_commons'` by `scripts/fetch_open_images.py`.
They are generic photos, NOT of the specific listed vehicles. Re-run that script to
refresh. Synthetic placeholders are OFF by default; enable for offline demos with
`AUTOLENS_SYNTHETIC_IMAGES=1`. To use target-site photos later (needs permission):
implement `LiveSourceScraper` + approved parser, store in `quarantine/<sha256>.jpg`,
write `status='fetched'` rows — the pHash/`photo_match` path works unchanged.
`run_fetch_images` preserves existing rows when synthetic is off and there are no URLs.

## Live scraping (R1/R4/R5) — hand-off
`src/autolens/scrapers/live.py` enforces robots.txt, identifiable UA, ≥1 req/s, off-peak
and **stops** on 403/429/CAPTCHA. It is not wired into `make run` until the team approves
`docs/sources/*.md` with live permission/terms evidence. Never lower the rate or evade.

## Monitoring (R13)
`ops/monitoring.py::check_health` writes `outputs/alerts.json`; the nightly GitHub Actions
workflow (`.github/workflows/nightly.yml`) opens an issue on critical alerts (success < 90%,
parse-failure spike, 429s). `ops/reposts.py::measure_repost_recall` returns
`measurable=False` until reviewed multi-day data exists — do not report a repost rate yet.

## Production storage (REMAINING #7)
Set `AUTOLENS_STORAGE_BACKEND=postgres_minio` and install `.[production]` in the team's
environment to use `common/storage_pg.py`, which now applies the authoritative
`sql/ddl/staging.sql` (schemas `staging`/`ops`/`core`, PG types and status values) rather
than the SQLite DDL. Logical table names are translated automatically. Local
SQLite/filesystem remains the default for the golden test; PG/MinIO still need a real
team server to validate end-to-end.
