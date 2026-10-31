"""Distinct evidence-availability and observed-price clocks for the 5m replay."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from common.winner_pyramiding import aware, regular_bounds


def observation_offset(policy):
    """Phase shift of evidence availability, without rounding the frozen delay."""
    market_needed = (policy.confirmation_bars > 0 or policy.reinforcement_enabled
                     or policy.trailing_stop_pct is not None)
    return policy.market_data_delay_seconds % 300 if market_needed else 0


def next_observed_open(now):
    """Return next SAME-session 5m open, never an already observed past open."""
    now = aware(now)
    day = now.astimezone(ZoneInfo('America/New_York')).date()
    bounds = regular_bounds(day)
    if bounds is None:
        return None
    opening, closing = bounds
    if not opening <= now < closing:
        return None
    seconds = (now-opening).total_seconds()
    if seconds % 300 == 0:
        return now
    following = opening+timedelta(seconds=(int(seconds)//300+1)*300)
    return following if following < closing else None


def at_observed_open(now):
    return next_observed_open(now) == aware(now)
