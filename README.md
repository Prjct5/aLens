# AutoLens Egypt

![Project Logo](docs/logo.png)


## Quick start (any member, under 15 minutes)

```bash
git clone https://github.com/Prjct5/aLens.git
cd aLens
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev,api,pipelines]"   # add your own groups: scraping, linkage, warehouse, vision, nlp, pricing, analytics
pre-commit install
make up                            # PostgreSQL, MinIO, MLflow, Prefect, API, dashboard, pipeline worker
make migrate                       # apply sql/ddl/*.sql
make test                          # unit + contract tests (no services needed)
make e2e                           # golden end-to-end test
```

`make up` creates `.env` from `.env.example` on first run. Never commit `.env`.

## Services (after `make up`)

| Service | URL |
| --- | --- |
| API (OpenAPI docs) | http://localhost:8000/docs |
| Dashboard | http://localhost:8501 |
| MLflow | http://localhost:5000 |
| Prefect | http://localhost:4200 |
| MinIO console | http://localhost:9001 |
| PostgreSQL | localhost:5432 (database `autolens`) |

## Make targets

`install hooks up down ps logs migrate seed lint fmt test e2e integration schemas clean`

## Layout

```
src/autolens/   common, scrapers, linkage, warehouse, features, analytics, vision, nlp,
                pricing, pipelines, api, dashboard, mlops
sql/ddl/        database migrations (applied in filename order)
contracts/      exported JSON Schemas, openapi.json, CONTRACT_VERSION
tests/          unit/<area>, contract, integration, fixtures
docker/         compose file and Dockerfiles
docs/           TEAM, architecture, security, runbooks, report, model cards
scripts/        apply_github_settings.sh, fill_codeowners.py
```

## Adding your stage to the pipeline

Implement `run(run_date, ctx) -> StageResult` (idempotent), then register it in
`src/autolens/pipelines/entrypoints.py`:

```python
from autolens.scrapers.run import run_scrape

IMPLEMENTATIONS["scrape"] = run_scrape
```

Stage names and order are defined in `src/autolens/pipelines/stages.py`.
The golden test and the Prefect flow use the same list.

## Changing a shared schema

1. Open an issue using the *Contract change* template.
2. Edit the Pydantic model in `src/autolens/common/schemas/`.
3. `make schemas`, update DDL and fixtures, bump `CONTRACT_VERSION` in
   `src/autolens/common/schemas/__init__.py`, label the PR `contract-change`.
4. Every consuming member approves.

## Rules

Public repository: no data, images, model weights, `.env` or credentials in git.
Fixtures are synthetic or trimmed. Branch from `main`, name branches `<type>/<member>-<topic>`,
use Conventional Commits, squash-merge, one code-owner approval, green CI.
