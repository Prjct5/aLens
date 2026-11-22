CREATE TABLE IF NOT EXISTS core.vehicle_link (
  listing_key text NOT NULL,
  vehicle_id bigint NOT NULL,
  link_run_id text NOT NULL,
  cluster_size integer NOT NULL,
  min_edge_weight double precision,
  max_edge_weight double precision,
  method text NOT NULL,
  PRIMARY KEY (listing_key, link_run_id)
);

CREATE INDEX IF NOT EXISTS ix_vehicle_link_vehicle ON core.vehicle_link (vehicle_id);

CREATE TABLE IF NOT EXISTS core.vehicle_id_merge (
  old_id bigint NOT NULL,
  new_id bigint NOT NULL,
  merged_at timestamptz NOT NULL,
  PRIMARY KEY (old_id, new_id)
);

CREATE OR REPLACE VIEW core.vehicle_link_current AS
SELECT link.*
FROM core.vehicle_link AS link
WHERE link.link_run_id = (SELECT max(latest.link_run_id) FROM core.vehicle_link AS latest);
