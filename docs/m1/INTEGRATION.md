# How M1's code was integrated into the shared repository

| M1 original | Now |
| --- | --- |
| `common/config.py` (`Settings`) | `scrapers/settings.py` (`M1Settings`, reads `PROJECT_ROOT`, `DATA_DIR`, ...) |
| `common/storage.py` (SQLite + filesystem) | `common/local_backend.py`, used for offline runs and unit tests |
| `common/storage_pg.py` | removed; shared `Database.query/insert_many/count` and `ObjectStore.put_raw/get_raw/raw_keys` do the same on PostgreSQL and MinIO |
| `common/schemas.py` | `common/schemas/` (staging, core, ops); `ParsedListingRow` is the table model |
| `common/stage.py`, `common/logging.py` | shared versions (logger accepts %-style args; `StageResult.metrics` added) |
| `ops/monitoring.py`, `ops/reposts.py` | `scrapers/monitoring.py`, `linkage/reposts.py` |
| `pipelines/entrypoints.py` | `pipelines/m1_stages.py` registers scrape, normalize, fetch_images, linkage |
| `sql/ddl/staging.sql` | `sql/ddl/100_staging_m1.sql`, `110_core_links_m1.sql` (typed parsed table) |
| scripts | `scripts/m1/` |

Behaviour changes made during integration:

1. `staging.parsed_listing` now stores typed columns plus `payload_key` (was a JSON blob).
   Normalize reads typed rows; a deterministic sample is re-parsed from raw and compared
   (`metrics.reparse_mismatches`).
2. Contact details are scrubbed from descriptions before they enter the raw payload
   (`autolens.common.privacy`).
3. `photo_match` only uses real listing photos (`fetched`, `promoted`).
4. Linkage reports `candidate_pairs_truncated`, falls back to singleton clusters when there are
   no pairs or labels, and marks its evaluation as provisional.
5. The off-peak window uses the Africa/Cairo timezone (summer time included).
6. A missing archive file returns a warning instead of crashing the stage.
7. Lint fixes (`zip(strict=True)`, unused loop variables, line length).
8. Three archive columns that staging used to drop are now kept: `condition`, `exterior_color`
   and `payment_options` (raw in `staging.parsed_listing`; `condition`, `color`,
   `payment_option` in `staging.normalized_listing`).
9. Fuel mapping fix: any text containing "gas" was mapped to petrol, which mislabelled
   1,092 natural-gas cars. They are now `cng` (new additive value in the contract).
10. Windows fix: `local_backend.raw_keys` compared against `/` and returned nothing on Windows.
