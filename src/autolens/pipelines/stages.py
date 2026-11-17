from __future__ import annotations

from datetime import date

from autolens.common.stage import RunContext, Stage, StageResult
from autolens.pipelines.entrypoints import IMPLEMENTATIONS

STAGE_NAMES: tuple[str, ...] = (
    "scrape",
    "macro",
    "normalize",
    "fetch_images",
    "privacy_blur",
    "linkage",
    "load_core",
    "dq",
    "score_images",
    "text_features",
    "build_marts",
    "score_prices",
    "fraud",
    "calibration_update",
    "analytics",
    "monitoring",
)

GATED_AFTER_DQ: frozenset[str] = frozenset(
    {
        "score_images",
        "text_features",
        "build_marts",
        "score_prices",
        "fraud",
        "calibration_update",
        "analytics",
    }
)


def _stub(name: str) -> Stage:
    def run(run_date: date, ctx: RunContext) -> StageResult:
        return StageResult(name, run_date, 0, 0, ["stub"])

    run.__name__ = f"stub_{name}"
    return run


STAGES: list[tuple[str, Stage]] = [
    (name, IMPLEMENTATIONS.get(name, _stub(name))) for name in STAGE_NAMES
]
