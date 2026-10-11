"""Fail-closed limits for the explicitly requested prospective analyst trial."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


def trial_skip_reason(config, *, now=None):
    trial = str(config.get("status", "")).startswith("ACTIVE_RESEARCH_TRIAL")
    start_raw = config.get("trial_start_date")
    end_raw = config.get("trial_end_date_exclusive")
    if not trial and start_raw is None and end_raw is None:
        return None
    try:
        start = date.fromisoformat(str(start_raw))
        end = date.fromisoformat(str(end_raw))
        if start >= end:
            return "INVALID_TRIAL_WINDOW"
        instant = now or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=timezone.utc)
        today = instant.astimezone(ZoneInfo(config.get("timezone") or "Europe/Paris")).date()
    except (ValueError, TypeError, KeyError):
        return "INVALID_TRIAL_WINDOW"
    if today < start:
        return "TRIAL_NOT_STARTED"
    if today >= end:
        return "TRIAL_EXPIRED"
    return None
