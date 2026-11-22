# Hand-off: M1 (acquisition and linkage) to M2 (warehouse and analytics)

Status: M1 stages run end to end on PostgreSQL and MinIO inside the shared pipeline and are
covered by CI (golden e2e, idempotency, contract and DDL parity tests).

## What M1 produces (all keyed by `listing_key = source || ':' || source_listing_id`)

| Object | Kind | Notes |
| --- | --- | --- |
| `raw/<source>/<run_date>/<id>.json.gz` | MinIO bucket `raw` | Immutable, byte-reproducible. Overwriting with different content raises `RawPayloadConflict`. |
| `staging.parsed_listing` | table | Typed, one row per listing per `scrape_date`. Column `payload_key` points to the raw object. Descriptions are scrubbed of phones and e-mails. |
| `staging.normalized_listing` | table | Canonical make/model (`model_id`), `year`, `mileage_km`, `price_egp`, `transmission`, `fuel_type` (petrol, diesel, hybrid, electric, cng, other), `body_type`, `condition` (new/used), `color`, `payment_option`, `dq_flags` (jsonb), `mapping_confidence`. Flags never delete rows. |
| `staging.image_fetch` | table | Empty until real photos exist. `status` in fetched, failed, promoted, open_source_commons, synthetic_placeholder. Only fetched/promoted are real listing photos. |
| `core.vehicle_link` / `core.vehicle_link_current` | table / view | Listing to `vehicle_id`. The view shows the latest `link_run_id` (`link-YYYY-MM-DD`). Ids are stable across runs; merges go to `core.vehicle_id_merge`. |
| `ops.scrape_run` | table | One row per source per run. `degraded = true` for archive replays. |
| `data_reference/models.csv`, `aliases.csv` | files in git | Canonical make/model dictionary (ids are stable). Load into `core.dim_model`. |

Table definitions: `sql/ddl/100_staging_m1.sql`, `110_core_links_m1.sql`. Pydantic models:
`src/autolens/common/schemas/`. Column changes follow the contract process (README).

## Archive profile (measured on the real run: 35,394 rows, 2026-01-15)

| Fact | Value |
| --- | --- |
| Rows per source | dubizzle 18,377, hatla2ee 10,633, contactcars 6,384 (URL host matches source for every row) |
| `condition` | 33,199 used, 2,195 new. New cars are out of the used-car scope: filter them in `load_core` / marts |
| `fuel_type` | benzine 31,397, diesel 1,671, natural gas (cng) 1,092, hybrid 644, electric 590 |
| Unknown / null | body_type 47%, color 46%, governorate_code 98.9% (the archive has no city column), payment_option 72% |
| DQ flags | mileage_implausible_low 499, mileage_placeholder 386, mileage_implausible_high 218, price_outlier 8, price_below_floor 4, price_above_ceiling 1 |
| Linkage | 1.10M candidate pairs, 32,318 vehicles for 35,394 listings, 528 vehicles across more than one source, 60 clusters at the size cap of 9 (inspect before trusting) |
| Run time (laptop, SQLite) | scrape 37 s, normalize 5 s, linkage 78 s |

Only 10 rows are identical to another row on every attribute except id and url, so most
linked groups come from near matches, and some will be coincidences between common cars.

## Linkage reliability (measured on the real run, 2026-11-21)

An independent check exists in the archive: 871 dubizzle ids have the form `h` + 7 digits, and
14 of them equal a hatla2ee id in the archive (`scripts/m1/check_cross_posts.py`). Those 14 are
real cross-posts: same make and year, identical price and mileage for most (price differs by
at most 3.2% at the 90th percentile).

| Result | Value |
| --- | --- |
| Known cross-posts present in `core.vehicle_link` | 14 |
| Put into the same `vehicle_id` | **0** |
| Cross-source vehicles the linker reports | 518 (none of the 14 among them) |

So `vehicle_id` is provisional: recall on real duplicates is 0 of 14, and the 518 reported
cross-source groups are unverified (probably mostly similar cars, not the same car).
The reported F1 of 1.0 comes from labels built from the same attributes and says nothing about this.

Diagnosis on the real data (`scripts/m1/diagnose_pairs.py`): 12 of the 14 pairs score 5.38 and the
cut-off is 5.393, a gap of 0.013 bits. The cut-off sits exactly on the weight of the single most
common pattern (all fields agree, body_type observed: 7,579 of 7,589 accepted edges), and these
pairs miss it only because body_type is unknown in one listing, a field that carries almost no
information (m 0.921 vs u 0.914). The other 2 pairs were never compared because the two sites
name the model differently. In addition, the estimated parameters do not describe real
duplicates: EM gives P(mileage agrees | match) = 0.25, while mileage agrees in 13 of the 14 real pairs.
The strongest field (price) has a likelihood ratio of about 2.4, so attribute-only evidence
cannot identify a vehicle with confidence; photos, descriptions and city are needed.

Likely mechanisms: the comparison features are yes/no tolerances, so identical
price and mileage score the same as "within 10% and 5%"; a missing field (body_type is null
for 47% of rows) lowers a pair's weight below the threshold; and groups larger than 9 are cut
greedily with ties broken by listing key.

**Until M1 fixes this: use `listing_key` as the unit of analysis, treat `vehicle_id` as
provisional, and do not report vehicle counts, duplicate rates or time-on-market per vehicle.**
The leakage rule "group by vehicle" is only as good as `vehicle_id`: missed duplicates can put
the same car in train and test.

## What M2 can rely on

- Run date: `scrape_date` / `run_date` is the Africa/Cairo calendar date.
- Re-running a date never duplicates rows (upserts on the primary keys).
- `listing_key` of every normalized row exists in `core.vehicle_link` for the same run.

## Read this before building on it (known limits)

1. The data is an archive replay of one snapshot (`scrape_date = 2026-01-15`), not live daily
   scrapes. There is no price history, and `is_live`/`days_since_first_seen` cannot be derived yet.
2. `mapping_rate` is 1.0 because the dictionary is mined from the same data. It is not an
   accuracy estimate. An official new-car price list is still missing.
3. 871 dubizzle ids look like `h` + 7 digits, the shape of a hatla2ee id. `scripts/m1/check_cross_posts.py` checks whether they are real cross-posts; if they are, they are an independent test set for linkage recall.
4. Linkage accuracy is provisional (see the section above): silver labels come from the same attributes the model
   uses, and no human labels exist yet. Do not report precision/recall as results.
5. `photo_match` is switched off until real listing photos exist (placeholder photos are
   assigned from the listing's own attributes and would leak the blocking attributes).
6. `ops.pipeline_run.warnings` for the `linkage` stage says whether candidate pairs were
   truncated; check `metrics.candidate_pairs_truncated` before trusting cluster counts.

## Stage slots for M2

Register implementations in `src/autolens/pipelines/entrypoints.py`:

| Stage name | Owner | Reads | Writes |
| --- | --- | --- | --- |
| `macro` | M2 | CBE/fuel sources | `core.fact_macro_daily` |
| `load_core` | M2 | `staging.normalized_listing`, `core.vehicle_link_current` | `core.dim_*`, `core.fact_listing_snapshot` (SCD2) |
| `dq` | M2 | core tables | `ops.dq_result` (add DDL as `2xx_*.sql`) |
| `build_marts` | M2 | core, features | `marts.*` |
| `analytics` | M2 | marts | index, depreciation, survival tables |

`dq_gate(run_date, ctx)` lives in `src/autolens/pipelines/gates.py` and currently returns true;
replace it with a check of your blocker results. Stages after `dq` are skipped when it fails.

## Try it

```bash
make up && make migrate
python scripts/m1/verify_m1.py --data-dir <folder with Egypt_Used_Cars_clean.csv> --postgres
```

Then in psql: `SELECT count(*) FROM staging.normalized_listing;` and
`SELECT * FROM core.vehicle_link_current LIMIT 5;`.
