from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from autolens.common.config import Settings, get_settings
from autolens.common.logging import StructuredLogger, configure_logging, get_logger


@dataclass
class StageResult:
    stage: str
    run_date: date
    rows_in: int
    rows_out: int
    warnings: list[str] = field(default_factory=list)


@dataclass
class RunContext:
    settings: Settings
    log: StructuredLogger
    db: Any = None
    store: Any = None
    mlflow: Any = None
    models: str = "real"
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)


class Stage(Protocol):
    def __call__(self, run_date: date, ctx: RunContext) -> StageResult: ...


def make_context(
    settings: Settings | None = None, models: str = "real", connect: bool = True
) -> RunContext:
    s = settings or get_settings()
    configure_logging(s.log_level)
    run_id = uuid.uuid4().hex
    ctx = RunContext(
        settings=s, log=get_logger("pipeline", run_id=run_id), models=models, run_id=run_id
    )
    if connect:
        from autolens.common.db import Database
        from autolens.common.store import ObjectStore

        ctx.db = Database.from_settings(s)
        ctx.store = ObjectStore(s)
    return ctx
