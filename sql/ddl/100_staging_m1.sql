CREATE TABLE IF NOT EXISTS staging.parsed_listing (
  source text NOT NULL CHECK (source IN ('hatla2ee', 'contactcars', 'dubizzle')),
  source_listing_id text NOT NULL,
  url text NOT NULL,
  scrape_date date NOT NULL,
  scraped_at timestamptz NOT NULL,
  run_id text NOT NULL,
  make_raw text,
  model_raw text,
  year_raw text,
  km_raw text,
  price_raw text,
  transmission_raw text,
  fuel_raw text,
  body_raw text,
  city_raw text,
  condition_raw text,
  color_raw text,
  payment_raw text,
  description_raw text,
  year integer,
  mileage_km double precision,
  price_egp double precision,
  currency text NOT NULL DEFAULT 'EGP',
  payload_key text,
  PRIMARY KEY (source, source_listing_id, scrape_date)
);

CREATE TABLE IF NOT EXISTS staging.normalized_listing (
  source text NOT NULL CHECK (source IN ('hatla2ee', 'contactcars', 'dubizzle')),
  source_listing_id text NOT NULL,
  scrape_date date NOT NULL,
  model_id integer,
  make_canon text,
  model_canon text,
  trim_canon text,
  year integer,
  mileage_km double precision,
  price_egp double precision,
  governorate_code text,
  transmission text CHECK (transmission IN ('manual', 'automatic') OR transmission IS NULL),
  fuel_type text CHECK (
    fuel_type IN ('petrol', 'diesel', 'hybrid', 'electric', 'cng', 'other')
    OR fuel_type IS NULL
  ),
  body_type text,
  condition text CHECK (condition IN ('new', 'used') OR condition IS NULL),
  color text,
  payment_option text CHECK (
    payment_option IN ('cash', 'installment', 'cash_or_installment', 'exchange')
    OR payment_option IS NULL
  ),
  dq_flags jsonb NOT NULL DEFAULT '{}'::jsonb,
  mapping_confidence double precision CHECK (mapping_confidence BETWEEN 0 AND 1),
  PRIMARY KEY (source, source_listing_id, scrape_date)
);

CREATE TABLE IF NOT EXISTS staging.image_fetch (
  listing_key text NOT NULL,
  position integer NOT NULL,
  image_id text NOT NULL CHECK (image_id ~ '^[0-9a-f]{64}$'),
  source_url text,
  fetched_at timestamptz,
  width integer,
  height integer,
  phash text,
  status text NOT NULL CHECK (
    status IN ('fetched', 'failed', 'promoted', 'open_source_commons', 'synthetic_placeholder')
  ),
  quarantine_key text,
  PRIMARY KEY (listing_key, position)
);

CREATE TABLE IF NOT EXISTS ops.scrape_run (
  run_id text NOT NULL,
  source text NOT NULL,
  run_date date NOT NULL,
  started_at timestamptz NOT NULL,
  finished_at timestamptz NOT NULL,
  n_index_pages integer NOT NULL DEFAULT 0,
  n_listings_seen integer NOT NULL DEFAULT 0,
  n_new integer NOT NULL DEFAULT 0,
  n_gone integer NOT NULL DEFAULT 0,
  n_error integer NOT NULL DEFAULT 0,
  n_parse_fail integer NOT NULL DEFAULT 0,
  http_429_count integer NOT NULL DEFAULT 0,
  degraded boolean NOT NULL DEFAULT false,
  PRIMARY KEY (run_id, source)
);

CREATE INDEX IF NOT EXISTS ix_scrape_run_date ON ops.scrape_run (run_date, source);
