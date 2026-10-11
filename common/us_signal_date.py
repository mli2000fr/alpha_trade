"""US end-of-session signal dates, independent of the Paris calendar day."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from common.market_calendar import get_market_calendar


def resolve_us_signal_date(requested=None, *, now=None, calendar=None) -> date:
    """Roll holidays/weekends and today's pre-open to the preceding session.

    An explicit older session stays fixed. This is not authorization for Web
    research: callers still validate close <= now < the next session open.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Horodatage timezone-aware requis")
    today = now.astimezone(ZoneInfo("America/New_York")).date()
    day = date.fromisoformat(requested) if isinstance(requested, str) else requested or today
    calendar = calendar or get_market_calendar("US_EQ", allow_us_weekday_fallback=False)
    if day > today:
        paris_today = now.astimezone(ZoneInfo("Europe/Paris")).date()
        if day == paris_today and (day - today).days == 1:
            # Paris is already tomorrow while NY is still in its evening.
            # This is today's IHM default, not a future US signal selection.
            day = today
        else:
            return day  # Never silently rewrite a genuinely future selection.
    if day not in calendar.session_dates(day, day):
        return calendar.previous_session(day)
    if day == today:
        opened, _ = calendar.session_bounds(day)
        if now < opened:
            return calendar.previous_session(day)
    return day


def pin_command_date(command, phase: str, day: str) -> list[str]:
    """Replace all copies of the date flag with exactly one frozen value."""
    flag = {"predict": "--universe-date", "risk": "--trade-date", "execute": "--date"}[phase]
    result = []
    index = 0
    while index < len(command):
        item = command[index]
        if item == flag:
            if index + 1 >= len(command) or command[index + 1].startswith("--"):
                raise ValueError(f"Valeur manquante pour {flag}")
            index += 2
        elif item.startswith(flag + "="):
            index += 1
        else:
            result.append(item)
            index += 1
    return [*result, flag, day]
