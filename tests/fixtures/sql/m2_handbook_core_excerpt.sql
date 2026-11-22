-- Verbatim excerpt of M2's handbook, Listing 8.1 (used only to test the contract models).
CREATE TABLE core.dim_date (
  date_key int PRIMARY KEY,                -- yyyymmdd
  date date UNIQUE NOT NULL, year smallint, month smallint,
  iso_week smallint, week_start date, dow smallint
);

CREATE TABLE core.dim_listing (
  listing_key text PRIMARY KEY,
  source text NOT NULL, source_listing_id text NOT NULL, url text NOT NULL,
  first_seen date NOT NULL, last_seen date NOT NULL, last_live_date date,
  seller_type text, posted_at timestamptz
);

CREATE TABLE core.fact_listing_snapshot (
  listing_key text NOT NULL REFERENCES core.dim_listing(listing_key),
  date_key int NOT NULL REFERENCES core.dim_date(date_key),
  vehicle_id bigint,
  status text NOT NULL CHECK (status IN ('live','gone','error')),
  price_egp numeric(14,2),
  days_since_first_seen int NOT NULL,
  PRIMARY KEY (listing_key, date_key)
);

CREATE TABLE core.dim_vehicle (              -- SCD Type 2
  vehicle_sk bigserial PRIMARY KEY,
  vehicle_id bigint NOT NULL,
  model_id int, year smallint, mileage_km int, transmission text,
  fuel_type text, governorate_code text,
  representative_listing_key text, description_hash text,
  row_hash text NOT NULL,
  valid_from date NOT NULL,
  valid_to date NOT NULL DEFAULT DATE '9999-12-31',
  is_current boolean NOT NULL DEFAULT true,
  CHECK (valid_from < valid_to)
);
CREATE UNIQUE INDEX one_current_vehicle ON core.dim_vehicle(vehicle_id) WHERE is_current;
