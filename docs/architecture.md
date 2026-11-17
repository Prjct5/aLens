# Architecture

Layers: raw (immutable payloads) -> staging -> core (star schema, full history) -> marts.
Every layer can be rebuilt from the previous one.

Services (docker compose, single host): PostgreSQL, MinIO, MLflow (tracking and registry),
Prefect (orchestration), API (FastAPI), dashboard (Streamlit), pipeline worker (serves the
daily flow at 02:00 Africa/Cairo).

Flow: `src/autolens/pipelines/stages.py` defines ordered stages. The Prefect flow and the golden
test both iterate the same list. Stages communicate only through PostgreSQL and MinIO.

Contracts: Pydantic models in `src/autolens/common/schemas/` are the source of truth. CI re-exports
JSON Schemas and `openapi.json` and fails on drift, checks fixtures against schemas, and checks
DDL columns against models.

Models: registered in MLflow with aliases `challenger` and `champion`. Promotion goes through
the `model-gate` workflow (`src/autolens/mlops/gates.yaml`).

Environments: local (`make up`), staging (push to `main`), production (version tag, approval).
