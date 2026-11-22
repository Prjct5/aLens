from __future__ import annotations

import json
from pathlib import Path

from autolens.api.export_openapi import OPENAPI_PATH, generate
from autolens.common import export_schemas
from autolens.common.schemas import CONTRACT_VERSION, TABLE_MODELS
from tests.helpers.ddl import ddl_columns, ddl_columns_from_dir

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"
DDL = ROOT / "sql" / "ddl"


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


def test_ddl_columns_match_pydantic_models() -> None:
    ddl = ddl_columns_from_dir(DDL)
    assert "ops.pipeline_run" in ddl
    for table, columns in ddl.items():
        if table in TABLE_MODELS:
            assert sorted(columns) == sorted(TABLE_MODELS[table].model_fields), table


M2_EXCERPT = ROOT / "tests" / "fixtures" / "sql" / "m2_handbook_core_excerpt.sql"


def test_models_match_the_m2_handbook_ddl_excerpt() -> None:
    """The contract models mirror the table definitions in M2's handbook (Listing 8.1)."""
    tables = ddl_columns(M2_EXCERPT.read_text(encoding="utf-8"))
    assert set(tables) == {
        "core.dim_date",
        "core.dim_listing",
        "core.fact_listing_snapshot",
        "core.dim_vehicle",
    }
    for table, columns in tables.items():
        assert sorted(columns) == sorted(TABLE_MODELS[table].model_fields), table
