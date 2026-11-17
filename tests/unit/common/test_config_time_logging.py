from __future__ import annotations

import io
import json
import logging
from datetime import UTC, datetime

import pytest

from autolens.common.config import Settings
from autolens.common.logging import JsonFormatter, get_logger
from autolens.common.time import CAIRO, to_cairo_date, today_cairo


def test_settings_defaults_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEYS_SHA256", "AA, bb ")
    s = Settings(_env_file=None)
    assert s.timezone == "Africa/Cairo"
    assert s.api_key_hashes == {"aa", "bb"}
    assert s.is_dev


def test_cairo_date_boundary() -> None:
    late_utc = datetime(2026, 1, 14, 22, 30, tzinfo=UTC)
    assert to_cairo_date(late_utc).isoformat() == "2026-01-15"
    assert CAIRO.key == "Africa/Cairo"
    assert today_cairo() is not None


def test_naive_datetime_rejected() -> None:
    with pytest.raises(ValueError):
        to_cairo_date(datetime(2026, 1, 1))


def test_structured_logger_emits_json_fields() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("autolens.test_json")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    log = get_logger("test_json", run_id="r1", stage="s1", run_date="2026-01-15")
    log.warning("blur failed", image_id="abc", err="boom")
    payload = json.loads(stream.getvalue())
    assert payload["msg"] == "blur failed"
    assert payload["run_id"] == "r1" and payload["stage"] == "s1"
    assert payload["image_id"] == "abc" and payload["level"] == "WARNING"
