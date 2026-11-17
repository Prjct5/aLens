# Roll back a deployment

Deployments are identified by commit SHA.

```bash
export IMAGE_TAG=<previous good sha>
docker compose --env-file .env -f docker/docker-compose.yml pull
docker compose --env-file .env -f docker/docker-compose.yml up -d
```

Or re-run the `cd` workflow for the previous good commit. Migrations are add-only for one
release so the previous version still works.

A bad merge on `main`: revert it in the GitHub UI, notify the team, fix on a branch.
