# Backup and restore

Backup (weekly, to an external disk):

```bash
docker compose -f docker/docker-compose.yml exec -T postgres pg_dump -U autolens -Fc autolens > autolens.dump
docker compose -f docker/docker-compose.yml exec -T postgres pg_dump -U autolens -Fc mlflow > mlflow.dump
```

MinIO: sync buckets `raw`, `images`, `mlflow` with `mc mirror`.

Restore (test it once):

```bash
cat autolens.dump | docker compose -f docker/docker-compose.yml exec -T postgres pg_restore -U autolens -d autolens --clean --if-exists
```
