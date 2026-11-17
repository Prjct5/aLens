from __future__ import annotations

import json
from datetime import date, datetime

from autolens.common.stage import RunContext, StageResult
from autolens.common.time import utcnow

COLUMNS = (
    "run_id",
    "run_date",
    "stage",
    "status",
    "rows_in",
    "rows_out",
    "warnings",
    "error",
    "started_at",
    "finished_at",
)


def record_pipeline_run(
    ctx: RunContext,
    stage: str,
    run_date: date,
    result: StageResult | None,
    status: str,
    started_at: datetime,
    error: str | None = None,
) -> None:
    ctx.log.info(
        "stage finished",
        stage=stage,
        run_date=str(run_date),
        status=status,
        rows_in=result.rows_in if result else None,
        rows_out=result.rows_out if result else None,
        warnings=result.warnings if result else [],
    )
    if ctx.db is None:
        return
    ctx.db.bulk_insert(
        "ops.pipeline_run",
        COLUMNS,
        [
            (
                ctx.run_id,
                run_date,
                stage,
                status,
                result.rows_in if result else None,
                result.rows_out if result else None,
                json.dumps(result.warnings if result else []),
                error,
                started_at,
                utcnow(),
            )
        ],
    )
