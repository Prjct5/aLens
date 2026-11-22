# M2 onboarding: Mohamed Shreif (warehouse and analytics)

Everything below was checked against your handbook (Part II, chapters 8 to 10).

## What is ready for you

| Need | Where |
| --- | --- |
| Local stack: PostgreSQL, MinIO, MLflow, Prefect, API, dashboard | `make up` (see README; on Windows run the commands in the Makefile) |
| Migration runner | `python -m autolens.warehouse.migrate`, records versions and checksums in `ops.schema_migrations`, refuses to run if an applied file was edited |
| Schemas `staging core features marts ops` | `sql/ddl/000_schemas.sql` |
| M1 data in `staging.*`, `core.vehicle_link_current`, `core.vehicle_id_merge`, `ops.scrape_run` | run M1's stages, see "Get real data" |
| Pipeline slots for `macro load_core dq build_marts analytics` | auto-registered, see below |
| CI: migrations on an empty database, SQL lint, contract parity, golden e2e | `.github/workflows/ci.yml` |
| Read-only roles `api_ro`, `dashboard_ro` and write role `pipeline` | `docker/postgres-init/01-init.sh`, grants in `sql/ddl/020_roles_grants.sql` |

## Your code is picked up automatically

Create the module and function with the names from your handbook (10.2) and the pipeline,
the golden test and the nightly flow run it. No edit to shared files is needed.

| Stage (order in `pipelines/stages.py`) | Module | Function |
| --- | --- | --- |
| `macro` | `autolens/warehouse/macro.py` | `run_macro(run_date, ctx)` |
| `load_core` | `autolens/warehouse/load.py` | `run_load_core(run_date, ctx)` |
| `dq` | `autolens/warehouse/dq.py` | `run_dq(run_date, ctx)` and `dq_gate(run_date)` (or `dq_gate(run_date, ctx)`) |
| `build_marts` | `autolens/features/build.py` | `run_build_marts(run_date, ctx)` |
| `analytics` | `autolens/analytics/run.py` | `run_analytics(run_date, ctx)` |

Return `StageResult(stage, run_date, rows_in, rows_out, warnings, metrics)`. `metrics` is stored in
`ops.pipeline_run.metrics`. A module that exists without its function is an import error, so typos
show up in your own PR. When `dq_gate` returns false the flow skips `score_images`, `text_features`,
`build_marts`, `score_prices`, `fraud`, `calibration_update` and `analytics`.

## Migrations

- Name files `V2NN__name.sql` (or `2NN_name.sql`). Number ranges: 000-099 platform, 100-199 M1,
  **200-299 you**, 300-399 M3, 400-499 M4. Both naming styles are ordered by number.
- Your handbook example `V001__...` would run before M1's tables exist, so start at `V201`.
- One `CREATE TABLE` per statement, ending with `);` at the start of a line. Several columns per line are fine.
- CI compares every table in `sql/ddl/` that is listed in `TABLE_MODELS`
  (`src/autolens/common/schemas/__init__.py`) with its Pydantic model. The models for
  `core.dim_date`, `core.dim_listing`, `core.fact_listing_snapshot` and `core.dim_vehicle` already
  mirror your Listing 8.1 (a test checks this). If you change a column: edit the model, run `make schemas`,
  label the PR `contract-change`.
- Tables that are not in `TABLE_MODELS` yet (`dim_model`, `new_car_price`, `fact_macro_daily`,
  `ops.dq_result`, marts) are free for now. Add models when the columns settle so CI can guard them.

## Get real data to develop against

The archive CSV is not in git (public repository). Ask Merna for `Egypt_Used_Cars_clean.csv` (35,394 rows).

```powershell
make up        # or: docker compose -f docker/docker-compose.yml --env-file .env up -d
python scripts/m1/verify_m1.py --data-dir <folder with the csv> --postgres
```

This fills `staging.parsed_listing`, `staging.normalized_listing`, `core.vehicle_link` and
`ops.scrape_run` in PostgreSQL (about 3 minutes) and writes a report. Without the CSV, the 60-row
sample in `tests/fixtures/scrapers/` is what CI uses.

## Facts about the data that change your design

Details and numbers: `docs/handoff/M1_TO_M2.md`.

1. One snapshot only (`2026-01-15`). Everything is `live`; `gone` and `error` cannot be derived, and
   there is no price history. Build the loaders for daily data but expect single-day results.
2. `vehicle_id` is provisional (0 of 14 known cross-posts were linked). Use `listing_key` as the unit
   of analysis for now, and keep `vehicle_id` nullable in facts.
3. `condition = 'new'` is 6.2% of rows; the project scope is used cars. Filter in `load_core` or marts.
4. No city, description or photos in the archive: `governorate_code` is 98.9% null.
5. `payment_option`, `color`, `condition` are new fields in `staging.normalized_listing`.
6. `core.dim_model` is yours to load from `data_reference/models.csv` (canonical make/model ids, kept stable by M1).

## Suggested first pull requests (your handbook's sequence)

1. `feat/m2-ddl-v1`: `V201__core_dims.sql` and the facts; CI runs the clean-database migration.
2. `feat/m2-loaders`: `run_load_core`, idempotent; test "replaying the same day twice changes nothing".
3. `feat/m2-macro`: `run_macro` (stub values are fine until sources are verified).
4. `feat/m2-dq-gate`: `ops.dq_result`, `run_dq`, `dq_gate`.
5. `feat/m2-feature-marts-stub`: stub `marts.listing_features` and `training_view` so M4 can start.

Analytics tables for the API (your 8.10): the API's `/market/index` response already uses the columns
of `marts.price_index_weekly` (`week_start, index, ci_lo, ci_hi, n_obs`, plus `spec_version`, `estimated_at`).
