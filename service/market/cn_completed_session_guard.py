"""Guard for completed CN sessions, with an explicit after-close exception."""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")


def require_completed_session_end(end: date, *, allow_same_day_after_close: bool = False,
                                  now: datetime | None = None) -> None:
    local = (now or datetime.now(SHANGHAI)).astimezone(SHANGHAI)
    if end > local.date():
        raise ValueError("Future CN session cannot be canonicalized")
    if end == local.date() and not (allow_same_day_after_close and local.time() >= time(18, 0)):
        raise ValueError("Only completed CN sessions are accepted; current session requires explicit after-close approval from 18:00 Shanghai")
