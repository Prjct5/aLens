CREATE TABLE IF NOT EXISTS ops.pipeline_run (
  pipeline_run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id text NOT NULL,
  run_date date NOT NULL,
  stage text NOT NULL,
  status text NOT NULL CHECK (status IN ('success', 'failed', 'skipped')),
  rows_in integer,
  rows_out integer,
  warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
  error text,
  started_at timestamptz NOT NULL,
  finished_at timestamptz
);

CREATE INDEX IF NOT EXISTS ix_pipeline_run_date_stage ON ops.pipeline_run (run_date, stage);

CREATE TABLE IF NOT EXISTS ops.model_monitor (
  monitor_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_date date NOT NULL,
  model_name text NOT NULL,
  metric text NOT NULL,
  value double precision,
  threshold double precision,
  status text NOT NULL CHECK (status IN ('ok', 'watch', 'alert')),
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_model_monitor_date_model ON ops.model_monitor (run_date, model_name, metric);

CREATE TABLE IF NOT EXISTS ops.api_request (
  hour timestamptz NOT NULL,
  endpoint text NOT NULL,
  n_requests integer NOT NULL,
  n_5xx integer NOT NULL,
  p50_ms double precision,
  p95_ms double precision,
  PRIMARY KEY (hour, endpoint)
);
