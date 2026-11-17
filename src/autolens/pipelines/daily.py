from __future__ import annotations

from datetime import date

from prefect import flow, task
from prefect.cache_policies import NO_CACHE

from autolens.common.stage import RunContext, Stage, StageResult, make_context
from autolens.common.time import today_cairo, utcnow
from autolens.pipelines.gates import dq_gate
from autolens.pipelines.runlog import record_pipeline_run
from autolens.pipelines.stages import GATED_AFTER_DQ, STAGES


@task(retries=2, retry_delay_seconds=300, cache_policy=NO_CACHE)
def run_stage(name: str, fn: Stage, run_date: date, ctx: RunContext) -> StageResult:
    started = utcnow()
    try:
        result = fn(run_date, ctx)
    except Exception as exc:
        record_pipeline_run(ctx, name, run_date, None, "failed", started, error=str(exc))
        raise
    record_pipeline_run(ctx, name, run_date, result, "success", started)
    return result


def notify_gate_failed(ctx: RunContext, stage: str, run_date: date) -> None:
    ctx.log.error(
        "data-quality gate failed, downstream stages skipped", stage=stage, run_date=str(run_date)
    )
    record_pipeline_run(ctx, stage, run_date, None, "skipped", utcnow(), error="dq gate failed")


@flow(name="daily-pipeline")
def daily(run_date: date | None = None) -> list[StageResult]:
    run_date = run_date or today_cairo()
    ctx = make_context()
    results: list[StageResult] = []
    for name, fn in STAGES:
        if name in GATED_AFTER_DQ and not dq_gate(run_date, ctx):
            notify_gate_failed(ctx, name, run_date)
            break
        results.append(run_stage(name, fn, run_date, ctx))
    return results


if __name__ == "__main__":
    daily()
