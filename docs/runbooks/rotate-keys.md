# Rotate API keys

1. Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
2. Hash: `python -c "import hashlib,sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest())" <key>`.
3. Put the new hash in `API_KEYS_SHA256` (comma separated; keep the old one until clients switch).
4. `docker compose up -d api`. Remove the old hash afterwards.

Database and MinIO passwords: change `.env`, then `ALTER ROLE ... PASSWORD` in PostgreSQL and
restart the stack.
