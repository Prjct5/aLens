from __future__ import annotations

import json

import httpx
import pytest

from autolens.mlops.drift import psi, psi_status
from autolens.mlops.gate import evaluate_gate, load_policy
from autolens.mlops.health import LABEL, Alert, sync_issues


def test_psi_identical_is_zero_and_shift_is_detected() -> None:
    base = [float(i) for i in range(1000)]
    assert psi(base, base) == pytest.approx(0, abs=1e-6)
    shifted = [x + 600 for x in base]
    assert psi_status(psi(base, shifted)) == "alert"


def test_gate_blocks_regression_and_passes_equal() -> None:
    policy = load_policy("price-gbm")
    champ = {"pinball_q50": 0.100, "coverage_80": 0.80, "latency_ms_median": 100}
    same = evaluate_gate("price-gbm", "2", policy, dict(champ), champ)
    assert same["passed"]
    worse = evaluate_gate("price-gbm", "3", policy, {**champ, "pinball_q50": 0.110}, champ)
    assert not worse["passed"]
    low_cov = evaluate_gate("price-gbm", "4", policy, {**champ, "coverage_80": 0.70}, champ)
    assert not low_cov["passed"]
    missing = evaluate_gate("price-gbm", "5", policy, {"pinball_q50": 0.1}, champ)
    assert not missing["passed"]


def test_gate_without_champion_uses_absolute_rules_only() -> None:
    policy = load_policy("vision-view")
    assert evaluate_gate("vision-view", "1", policy, {"macro_f1": 0.5}, None)["passed"]


def test_unknown_model_policy() -> None:
    with pytest.raises(KeyError):
        load_policy("nope")


def test_issue_sync_opens_comments_and_closes() -> None:
    issues = [
        {"number": 1, "title": "[alert] still firing"},
        {"number": 2, "title": "[alert] cleared"},
        {"number": 3, "title": "unrelated issue"},
    ]
    calls: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        calls.append((request.method, request.url.path, body))
        if request.method == "GET":
            return httpx.Response(200, json=issues)
        return httpx.Response(201, json={})

    client = httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler))
    alerts = [Alert("still firing", "b", "m5"), Alert("brand new", "b", "m3")]
    summary = sync_issues(client, "o/r", alerts)
    assert summary == {
        "opened": ["[alert] brand new"],
        "commented": ["[alert] still firing"],
        "closed": ["[alert] cleared"],
    }
    opened = next(c for c in calls if c[0] == "POST" and c[1].endswith("/issues"))
    assert LABEL in opened[2]["labels"] and "m3" in opened[2]["labels"]
    assert not any(c[1].endswith("/3") for c in calls)
