# What M2, M3 and M4 plug into

Every stage is `run(run_date, ctx) -> StageResult`, idempotent, stateless between runs.
Create the module below and it is registered automatically (`OPTIONAL_STAGES` in
`src/autolens/pipelines/entrypoints.py`); for any other name add a line to `IMPLEMENTATIONS`. Order and names:
`src/autolens/pipelines/stages.py`. The golden test and the nightly Prefect flow use the same list.

| Member | Stages to implement | Consumes | Produces |
| --- | --- | --- | --- |
| M2 | `macro`, `load_core`, `dq`, `build_marts`, `analytics` | `staging.*`, `core.vehicle_link_current` | core star schema, marts, `ops.dq_result` |
| M3 | `privacy_blur`, `score_images` | `staging.image_fetch`, bucket `quarantine` | bucket `images`, `core.image_asset`, `features.image_*` |
| M4 | `text_features`, `score_prices`, `fraud`, `calibration_update` | `staging.parsed_listing.description_raw`, `marts.training_view`, `features.*` | `features.text_*`, `core.fact_model_outputs`, MLflow models |

Shared helpers: `autolens.common` (config, db, store, logging, stage, schemas, privacy).
`ctx.db` offers `fetch_all`, `fetch_one`, `execute`, `bulk_insert`, `transaction()`; the
`query`/`insert_many`/`count` methods exist for M1's SQLite-style code.

Adding a table: SQL in `sql/ddl/NNN_name.sql` (applied in filename order), Pydantic model in
`src/autolens/common/schemas/`, register it in `TABLE_MODELS`, run `make schemas`, add a fixture
named `<schema>.<table>.json` in `tests/fixtures/`. CI fails if DDL columns and model fields differ.
Numbers: platform 000-099, M1 100-199, M2 200-299, M3 300-399, M4 400-499; `NNN_name.sql` and `VNNN__name.sql` both work. Applied files are checksummed in `ops.schema_migrations`: add a new file instead of editing one.

Rules that CI cannot check: no seller names or phones anywhere, no unblurred images outside
`quarantine` (21-day lifecycle), no data or weights in git, split by time and group by vehicle.

## Module and function names that are picked up automatically

| Stage | Module | Function |
| --- | --- | --- |
| macro, load_core, dq, build_marts, analytics | see `docs/handoff/M2_ONBOARDING.md` | `run_macro`, `run_load_core`, `run_dq`, `run_build_marts`, `run_analytics` |
| privacy_blur, score_images | `autolens/vision/run.py` | `run_privacy`, `run_score_images` |
| text_features | `autolens/nlp/run.py` | `run_text_features` |
| score_prices, fraud, calibration_update | `autolens/pricing/run.py` | `run_score_prices`, `run_fraud`, `run_calibration_update` |

The M3 and M4 module names are a convention chosen by M5 (their handbooks give only the function names).
Use other names if you prefer and register them in `IMPLEMENTATIONS`.
