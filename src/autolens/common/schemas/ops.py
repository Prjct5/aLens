from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from autolens.common.schemas._base import ContractModel


class PipelineRunRow(ContractModel):
    pipeline_run_id: int | None = None
    run_id: str
    run_date: date
    stage: str
    status: Literal["success", "failed", "skipped"]
    rows_in: int | None = None
    rows_out: int | None = None
    warnings: list[str] = []
    error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class ModelMonitorRow(ContractModel):
    monitor_id: int | None = None
    run_date: date
    model_name: str
    metric: str
    value: float | None = None
    threshold: float | None = None
    status: Literal["ok", "watch", "alert"]
    details: dict[str, Any] = {}
    created_at: datetime | None = None


class ApiRequestRow(ContractModel):
    hour: datetime
    endpoint: str
    n_requests: int
    n_5xx: int
    p50_ms: float | None = None
    p95_ms: float | None = None
