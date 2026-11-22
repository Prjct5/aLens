# Parsed schema document (D3)

`staging.parsed_listing` – one row per listing per `scrape_date`.
Primary key: `(source, source_listing_id, scrape_date)`.

| Field | Type | Meaning | Null rate (archive) | Example | Known problems |
|---|---|---|---|---|---|
| source | enum | hatla2ee / contactcars / dubizzle | 0% | `dubizzle` | – |
| source_listing_id | string | site's own id | 0% | `h7302649` | mixed numeric/prefixed formats |
| scrape_date | date | Africa/Cairo calendar date | 0% | 2026-01-15 | single snapshot supplied |
| scraped_at | timestamptz | UTC fetch time | 0% | 2026-01-15T01:…Z | – |
| run_id | string | deterministic archive run id | 0% | `archive-2026-01-15-ae8f0560d4` | derived from run date + input CSV SHA-256; no random UUID |
| url | string | listing URL | 0% | … | city slug only on Dubizzle |
| make_raw | string | raw make | 0% | `Mercedes-Benz` | spelling variants |
| model_raw | string | raw model | 0% | `B150` | spelling variants, Franco |
| year_raw | string | raw year | 0% | `2007` | values up to 2027 and 0 |
| km_raw | string | raw mileage | 0% | `100000.0` | `k`/`alf`/Arabic-digit forms expected on live sites |
| price_raw | string | raw price | 0% | `1000.0` | **1,000 EGP placeholder is common** – flagged `price_below_floor` |
| transmission_raw | string | raw gearbox | 0% | `Automatic` | – |
| fuel_raw | string | raw fuel | 0% | `Diesel` | maps to petrol/diesel/… |
| body_raw | string | raw body | 0% | `Hatchback` | `Unknown` values -> NULL |
| description_raw | string | text | not in main archive | – | supplementary hatla2ee archive only |
| city_raw | string | city/governorate | high | `CAI` | 27-governorate seed table owned by M2 |

`staging.normalized_listing` adds canonical values and `dq_flags` (JSONB). Flags are
never deleted; they mark `price_below_floor`, `price_outlier`, `mileage_placeholder`,
`mileage_implausible_high/low`, `year_invalid`, etc.

**Number of exact duplicate rows in the archive:** 0. **Duplicate `listing_id`:** 0.
Within-source reposts across days cannot be measured from a single snapshot; the
mechanism is implemented in `linkage/cluster.py` and documented in the runbook.
