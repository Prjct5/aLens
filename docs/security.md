# Security and privacy

- Secrets only in `.env` (git-ignored), GitHub Secrets/Environments. Never in code or logs.
- Database roles: `autolens` (owner, migrations), `pipeline` (write to staging, core, features,
  marts, ops), `api_ro` and `dashboard_ro` (read-only on core, marts, ops; api_ro may insert
  into ops.api_request), `mlflow` (own database). Grants live in `sql/ddl/020_roles_grants.sql`.
- Object store: only M1 writes to `raw` and `quarantine`; only M3 writes to `images`.
  The `quarantine` bucket has a 21-day expiry lifecycle rule; the nightly health check
  verifies it and alerts on objects older than 14 days.
- Logs never contain description text, photos or seller data.
- API: `X-API-Key` (SHA-256 hashes in `API_KEYS_SHA256`), per-key rate limit, CORS limited to
  the dashboard origin. With `ENVIRONMENT=dev` and no keys configured, auth is open: never run
  that way outside a laptop.
- Public repository: self-hosted runners never run `pull_request` workflows.
