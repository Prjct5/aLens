from __future__ import annotations

import json
import re
from pathlib import Path

from autolens.api.export_openapi import OPENAPI_PATH, generate
from autolens.common import export_schemas
from autolens.common.schemas import CONTRACT_VERSION, TABLE_MODELS

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"
DDL = ROOT / "sql" / "ddl"
NON_COLUMNS = {"primary", "unique", "constraint", "foreign", "check", "exclude"}


def test_json_schemas_match_pydantic() -> None:
    assert export_schemas.check() == []


def test_contract_version_file_matches_code() -> None:
    text = (ROOT / "contracts" / "CONTRACT_VERSION").read_text().strip()
    assert int(text) == CONTRACT_VERSION


def test_openapi_matches_committed() -> None:
    assert OPENAPI_PATH.read_text(encoding="utf-8") == generate()


def test_fixtures_validate_against_contract() -> None:
    files = sorted(FIXTURES.glob("*.*.json"))
    assert files, "no fixtures found"
    for path in files:
        table = path.name.removesuffix(".json")
        assert table in TABLE_MODELS, f"fixture for unknown table {table}"
        for row in json.loads(path.read_text(encoding="utf-8")):
            TABLE_MODELS[table].model_validate(row)


def _ddl_columns() -> dict[str, list[str]]:
    tables: dict[str, list[str]] = {}
    pattern = re.compile(
        r"CREATE TABLE(?: IF NOT EXISTS)?\s+([\w.]+)\s*\((.*?)\n\);", re.DOTALL | re.IGNORECASE
    )
    for path in sorted(DDL.glob("*.sql")):
        for name, body in pattern.findall(path.read_text(encoding="utf-8")):
            cols = []
            for line in body.splitlines():
                token = line.strip().split(" ")[0].strip(",").lower()
                if token and token not in NON_COLUMNS:
                    cols.append(token)
            tables[name.lower()] = cols
    return tables


def test_ddl_columns_match_pydantic_models() -> None:
    ddl = _ddl_columns()
    assert "ops.pipeline_run" in ddl
    for table, columns in ddl.items():
        if table in TABLE_MODELS:
            assert sorted(columns) == sorted(TABLE_MODELS[table].model_fields), table
