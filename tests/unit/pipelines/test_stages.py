from __future__ import annotations

from datetime import date

from autolens.common.config import Settings
from autolens.common.stage import make_context
from autolens.pipelines.entrypoints import IMPLEMENTATIONS
from autolens.pipelines.stages import GATED_AFTER_DQ, STAGE_NAMES, STAGES


def test_stage_registry_is_complete_and_ordered() -> None:
    assert [n for n, _ in STAGES] == list(STAGE_NAMES)
    assert GATED_AFTER_DQ <= set(STAGE_NAMES)
    assert STAGE_NAMES.index("dq") < min(STAGE_NAMES.index(s) for s in GATED_AFTER_DQ)


def test_stub_stages_run_without_services() -> None:
    from autolens.pipelines.stages import _stub

    ctx = make_context(Settings(_env_file=None), models="stub", connect=False)
    for name in STAGE_NAMES:
        res = _stub(name)(date(2026, 1, 15), ctx)
        assert res.stage == name and res.rows_out >= 0


def test_m1_stages_are_registered() -> None:
    from autolens.pipelines.m1_stages import M1_STAGES

    registered = dict(STAGES)
    for name, fn in M1_STAGES.items():
        assert registered[name] is fn
    assert set(M1_STAGES) == {"scrape", "normalize", "fetch_images", "linkage"}


def test_implementations_override_stub() -> None:
    import importlib

    import autolens.pipelines.stages as stages
    from autolens.common.stage import StageResult

    def real(run_date: date, ctx: object) -> StageResult:
        return StageResult("scrape", run_date, 1, 1)

    original = IMPLEMENTATIONS["scrape"]
    IMPLEMENTATIONS["scrape"] = real  # type: ignore[assignment]
    try:
        importlib.reload(stages)
        assert dict(stages.STAGES)["scrape"] is real
    finally:
        IMPLEMENTATIONS["scrape"] = original
        importlib.reload(stages)
