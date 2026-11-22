from __future__ import annotations

import inspect
from collections.abc import Callable
from datetime import date
from importlib import import_module
from types import ModuleType

from autolens.common.stage import RunContext

DQ_MODULE = "autolens.warehouse.dq"


def dq_gate(
    run_date: date,
    ctx: RunContext,
    importer: Callable[[str], ModuleType] = import_module,
) -> bool:
    """Delegate to M2's dq_gate when it exists; accepts dq_gate(run_date) or (run_date, ctx)."""
    try:
        module = importer(DQ_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name != DQ_MODULE:
            raise
        ctx.log.warning("dq gate not implemented yet: later stages are not protected")
        return True
    gate = module.dq_gate
    takes_ctx = len(inspect.signature(gate).parameters) >= 2
    return bool(gate(run_date, ctx) if takes_ctx else gate(run_date))
