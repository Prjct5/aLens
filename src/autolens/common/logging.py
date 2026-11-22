from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

_RESERVED = {"run_id", "stage", "run_date"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        fields: dict[str, Any] = getattr(record, "fields", {})
        payload.update(fields)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


class StructuredLogger:
    def __init__(self, logger: logging.Logger, **bound: Any) -> None:
        self._logger = logger
        self._bound = bound

    def bind(self, **more: Any) -> StructuredLogger:
        return StructuredLogger(self._logger, **{**self._bound, **more})

    def _log(
        self,
        level: int,
        msg: str,
        args: tuple[Any, ...],
        fields: dict[str, Any],
        exc_info: bool = False,
    ) -> None:
        self._logger.log(
            level,
            msg,
            *args,
            extra={"fields": {**self._bound, **fields}},
            exc_info=exc_info,
        )

    def debug(self, msg: str, *args: Any, **fields: Any) -> None:
        self._log(logging.DEBUG, msg, args, fields)

    def info(self, msg: str, *args: Any, **fields: Any) -> None:
        self._log(logging.INFO, msg, args, fields)

    def warning(self, msg: str, *args: Any, **fields: Any) -> None:
        self._log(logging.WARNING, msg, args, fields)

    def error(self, msg: str, *args: Any, **fields: Any) -> None:
        self._log(logging.ERROR, msg, args, fields)

    def exception(self, msg: str, *args: Any, **fields: Any) -> None:
        self._log(logging.ERROR, msg, args, fields, exc_info=True)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger("autolens")
    if any(getattr(h, "_autolens", False) for h in root.handlers):
        root.setLevel(level.upper())
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler._autolens = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(level.upper())
    root.propagate = False


def get_logger(
    name: str = "autolens",
    level: str | None = None,
    *,
    run_id: str | None = None,
    stage: str | None = None,
    run_date: Any = None,
) -> StructuredLogger:
    bound: dict[str, Any] = {}
    if run_id is not None:
        bound["run_id"] = run_id
    if stage is not None:
        bound["stage"] = stage
    if run_date is not None:
        bound["run_date"] = str(run_date)
    base = name if name.startswith("autolens") else f"autolens.{name}"
    logger = logging.getLogger(base)
    if level:
        logger.setLevel(level.upper())
    return StructuredLogger(logger, **bound)
