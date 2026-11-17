.PHONY: install hooks up down ps logs test lint fmt e2e integration migrate seed schemas openapi clean

COMPOSE = docker compose -f docker/docker-compose.yml --env-file .env

.env:
	cp .env.example .env

install:
	python -m pip install -e ".[dev,api,pipelines]"

hooks:
	pre-commit install

up: .env
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f --tail=100

migrate:
	python -m autolens.warehouse.migrate

seed:
	python -m autolens.common.seed_fixtures

lint:
	ruff check . && ruff format --check . && mypy src/autolens/common src/autolens/api && sqlfluff lint sql

fmt:
	ruff check --fix . && ruff format .

test:
	pytest tests/unit tests/contract -q

e2e:
	pytest tests/integration/test_e2e_golden.py -q

integration:
	pytest tests/integration -q

schemas:
	python -m autolens.common.export_schemas
	python -m autolens.api.export_openapi

clean:
	$(COMPOSE) down -v
