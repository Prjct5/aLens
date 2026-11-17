DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pipeline') THEN
    GRANT USAGE, CREATE ON SCHEMA staging, core, features, marts, ops TO pipeline;
    GRANT ALL ON ALL TABLES IN SCHEMA staging, core, features, marts, ops TO pipeline;
    GRANT ALL ON ALL SEQUENCES IN SCHEMA staging, core, features, marts, ops TO pipeline;
    ALTER DEFAULT PRIVILEGES IN SCHEMA staging, core, features, marts, ops
      GRANT ALL ON TABLES TO pipeline;
    ALTER DEFAULT PRIVILEGES IN SCHEMA staging, core, features, marts, ops
      GRANT ALL ON SEQUENCES TO pipeline;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'api_ro') THEN
    GRANT USAGE ON SCHEMA core, features, marts, ops TO api_ro;
    GRANT SELECT ON ALL TABLES IN SCHEMA core, features, marts, ops TO api_ro;
    ALTER DEFAULT PRIVILEGES IN SCHEMA core, features, marts, ops
      GRANT SELECT ON TABLES TO api_ro;
    GRANT INSERT ON ops.api_request TO api_ro;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dashboard_ro') THEN
    GRANT USAGE ON SCHEMA core, marts, ops TO dashboard_ro;
    GRANT SELECT ON ALL TABLES IN SCHEMA core, marts, ops TO dashboard_ro;
    ALTER DEFAULT PRIVILEGES IN SCHEMA core, marts, ops
      GRANT SELECT ON TABLES TO dashboard_ro;
  END IF;
END
$$;
