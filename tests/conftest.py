from __future__ import annotations

import os
from pathlib import Path

import pytest

from autolens.common.config import Settings

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, environment="dev", api_keys_sha256="")


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


def require_services() -> bool:
    return os.environ.get("REQUIRE_SERVICES") == "1"
