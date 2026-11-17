from __future__ import annotations

from datetime import date

from autolens.common.stage import RunContext


def dq_gate(run_date: date, ctx: RunContext) -> bool:
    return True
