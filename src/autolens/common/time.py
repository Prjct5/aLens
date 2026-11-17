from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

CAIRO = ZoneInfo("Africa/Cairo")


def utcnow() -> datetime:
    return datetime.now(UTC)


def today_cairo() -> date:
    return utcnow().astimezone(CAIRO).date()


def to_cairo_date(moment: datetime) -> date:
    if moment.tzinfo is None:
        raise ValueError("naive datetime: timestamps must be timezone-aware (UTC)")
    return moment.astimezone(CAIRO).date()
