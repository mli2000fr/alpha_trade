"""Shared opt-in LONG campaign contract, independent of broker and storage.

No future bars, averaging down, new budget from profits or horizon reset.
Percentages are fractions. Safety constraints are NOT overridden by this policy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
import math
from functools import lru_cache
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class WinnerPyramidingConfig:
    enabled: bool = False
    initial_position_fraction: float = .5
    reinforcement_enabled: bool = False
    reinforcement_trigger_pct: float = .05
    confirmation_bars: int = 2
    standard_entry_quote_check_enabled: bool = True
    stop_loss_pct: float = .05
    take_profit_pct: float | None = None
    trailing_stop_pct: float | None = .15
    horizon_sessions: int | None = 20
    entry_valid_sessions: int = 20
    max_quote_age_seconds: int = 60
    max_bar_delay_seconds: int = 60
    cost_reserve_bps_per_leg: float = 25.

    def __post_init__(self):
        for key in ('enabled', 'reinforcement_enabled', 'standard_entry_quote_check_enabled'):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f'winner_pyramiding.{key}: boolean required')
        if type(self.initial_position_fraction) not in (int, float) or self.initial_position_fraction not in (.5, 1.):
            raise ValueError('initial_position_fraction must be0.5 or1.0')
        for key in ('stop_loss_pct', 'reinforcement_trigger_pct', 'take_profit_pct', 'trailing_stop_pct'):
            value = getattr(self, key)
            if value is None and key in ('take_profit_pct', 'trailing_stop_pct'):
                continue
            if type(value) not in (float, int) or not math.isfinite(value) or not 0 < value < 1:
                raise ValueError(f'winner_pyramiding.{key}: fraction in(0,1) required')
        for key, lo, hi in [('confirmation_bars', 0, 12), ('max_quote_age_seconds', 1, 300),
                ('max_bar_delay_seconds', 1, 300), ('entry_valid_sessions', 1, 60)]:
            if type(getattr(self, key)) is not int or not lo <= getattr(self, key) <= hi:
                raise ValueError(f'winner_pyramiding.{key}: integer in[{lo},{hi}] required')
        if self.horizon_sessions is not None and (type(self.horizon_sessions) is not int or not 1 <= self.horizon_sessions <= 252):
            raise ValueError('horizon_sessions must be1..252or null')
        if (type(self.cost_reserve_bps_per_leg) not in (float, int)
                or not math.isfinite(self.cost_reserve_bps_per_leg) or not 0 <= self.cost_reserve_bps_per_leg <= 500):
            raise ValueError('cost_reserve_bps_per_leg must be0..500')

    @property
    def fee(self):
        return self.cost_reserve_bps_per_leg / 10000.


def load_winner_pyramiding_config(raw=None):
    if raw is None:
        from common.config_loader import load_config
        raw = load_config()
    section = raw.get('winner_pyramiding', {})
    if not isinstance(section, dict):
        raise ValueError('winner_pyramiding must be a mapping')
    return WinnerPyramidingConfig(**section)


def aware(value):
    value = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError('Explicit aware market time required')
    return value.astimezone(UTC)


def due_open(opened_at, policy, calendar=None):
    if policy.horizon_sessions is None:
        return None
    from common.market_calendar import get_market_calendar
    opened_at = aware(opened_at)
    day = opened_at.astimezone(ZoneInfo('America/New_York')).date()
    calendar = calendar or get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    sessions = [s for s in calendar.sessions(day, day+timedelta(days=policy.horizon_sessions*3+40)) if s.is_open]
    if not sessions or sessions[0].session_date != day or len(sessions) <= policy.horizon_sessions:
        raise ValueError('Complete official session calendar required')
    due = sessions[policy.horizon_sessions].open_at_utc
    if due is None:
        raise ValueError('Official opening time missing')
    return aware(due)


def initial_quantities(approved_full, price, risk_budget, policy):
    if not policy.enabled:
        return int(approved_full), int(approved_full)
    if not all(type(v) in (int, float) and math.isfinite(float(v)) and float(v) > 0
            for v in (approved_full, price, risk_budget)):
        raise ValueError('Qualified approved quantity, price and campaign risk budget required')
    unit = price * (policy.stop_loss_pct+2.05*policy.fee)
    full = min(math.floor(approved_full), math.floor(risk_budget/unit))
    return full, math.floor(full*policy.initial_position_fraction)


def new_campaign(key, symbol, full_quantity, initial_quantity, risk_budget, policy):
    if not policy.enabled or not symbol or not 0 < initial_quantity <= full_quantity or risk_budget <= 0:
        raise ValueError('Enabled policy and positive bounded campaign quantities required')
    return dict(campaign_id=key, symbol=symbol, policy=asdict(policy), full_quantity=int(full_quantity),
        initial_quantity=int(initial_quantity), risk_budget=float(risk_budget), realized_losses=0.,
        added_quantity=0, add_attempted=False, first_fill_at=None, due_open=None, lots=[], status='PENDING')


def confirmed_breakout(bars, prior_session_high, policy, *, now):
    """A fresh cross, followed by N consecutive completed regular-session closes.

    Timestamps are bar START times. A currently forming/future bar is not
    evidence and is ignored. No next-bar open is known or assumed in live.
    The previous session's high must be supplied from qualified daily data.
    """
    # Zero is a separate standard-order path, never a vacuous breakout.
    if policy.confirmation_bars == 0:
        return False
    if not math.isfinite(float(prior_session_high)) or prior_session_high <= 0:
        return False
    count = policy.confirmation_bars
    tail = fresh_completed_bars(bars, policy, now=now, count=count+1)
    if not tail:
        return False
    return tail[0]['close'] <= prior_session_high and all(b['close'] > prior_session_high for b in tail[1:])


@lru_cache(maxsize=512)
def regular_bounds(day):
    from common.market_calendar import get_market_calendar
    sessions = [s for s in get_market_calendar('US_EQ', allow_us_weekday_fallback=False).sessions(day, day) if s.is_open]
    return (aware(sessions[0].open_at_utc), aware(sessions[0].close_at_utc)) if sessions else None


def fresh_completed_bars(bars, policy, *, now, count):
    """Fresh same-session 5m tail; explicit regular tag, official clock/grid."""
    from common.market_calendar import get_market_calendar
    now = aware(now)
    day = now.astimezone(ZoneInfo('America/New_York')).date()
    bounds = regular_bounds(day)
    if bounds is None:
        return []
    opening, closing = bounds
    if not opening <= now < closing:
        return []
    completed = sorted((b for b in bars if aware(b['timestamp'])+timedelta(minutes=5) <= now),
        key=lambda b: aware(b['timestamp']))
    if len(completed) < count:
        return []
    tail = completed[-count:]
    end = aware(tail[-1]['timestamp'])+timedelta(minutes=5)
    if not 0 <= (now-end).total_seconds() <= policy.max_bar_delay_seconds:
        return []
    for i, bar in enumerate(tail):
        stamp, close = aware(bar['timestamp']), float(bar['close'])
        if (not opening <= stamp < closing or stamp+timedelta(minutes=5) > closing
                or (stamp-opening).total_seconds() % 300
                or bar.get('session_tag') != 'regular' or not math.isfinite(close) or close <= 0
                or i and stamp-aware(tail[i-1]['timestamp']) != timedelta(minutes=5)):
            return []
    return tail


def add_fill(state, *, parent_id, quantity, price, filled_at, calendar=None, is_add=False,
        initial_fragment=False):
    p = WinnerPyramidingConfig(**state['policy'])
    if not math.isfinite(price) or price <= 0 or quantity <= 0 or not float(quantity).is_integer():
        raise ValueError('Whole positive actual fill required')
    if any(l['parent_id'] == parent_id for l in state['lots']):
        raise ValueError('Duplicate fill: reconcile cumulative partial fills before protection')
    first = state['first_fill_at'] is None
    if first and is_add or not first and not is_add and not initial_fragment:
        raise ValueError('Unexpected campaign fill lineage')
    if first:
        state['first_fill_at'] = aware(filled_at).isoformat()
        due = due_open(filled_at, p, calendar)
        state['due_open'] = due.isoformat() if due else None
    if is_add:
        state['added_quantity'] += quantity
    else:
        state['initial_filled_quantity'] = state.get('initial_filled_quantity', 0)+quantity
        state['initial_filled_notional'] = state.get('initial_filled_notional', 0.)+quantity*price
    state['lots'].append(dict(parent_id=parent_id, quantity=int(quantity), remaining=int(quantity),
        entry=float(price), peak=float(price), stop=round(price*(1-p.stop_loss_pct), 2),
        tp=round(price*(1+p.take_profit_pct), 2) if p.take_profit_pct else None,
        filled_at=aware(filled_at).isoformat(), stop_order_id=None, tp_order_id=None,
        entry_kind='ADD' if is_add else 'ENTRY'))
    state['status'] = 'OPEN'


def known_risk(state, fee):
    return state['realized_losses'] + sum(l['remaining']*(max(l['entry']-l['stop'], 0.)
        + fee*(l['entry']+l['stop'])) for l in state['lots'] if l['remaining'] > 0)


def reinforcement_quantity(state, price, available_cash, capacity_quantity):
    p = WinnerPyramidingConfig(**state['policy'])
    if (not p.enabled or not p.reinforcement_enabled or state['add_attempted']
            or p.initial_position_fraction == 1 or state['status'] != 'OPEN'
            or not state['lots'] or state['lots'][0]['remaining'] <= 0
            or any(l['remaining'] != l['quantity'] for l in state['lots'])):
        return 0
    initial_entry = (state['initial_filled_notional']/state['initial_filled_quantity']
        if state.get('initial_filled_quantity') else state['lots'][0]['entry'])
    if price < initial_entry*(1+p.reinforcement_trigger_pct):
        return 0
    remaining = max(state['risk_budget']-known_risk(state, p.fee), 0.)
    return max(0, min(state['full_quantity']-sum(l['quantity'] for l in state['lots']),
        math.floor(remaining/(price*(p.stop_loss_pct+2.05*p.fee))),
        math.floor(max(available_cash, 0.)/(price*(1+p.fee))), math.floor(capacity_quantity)))


def confirmed_winner(state, bars, *, now):
    """Completed consecutive regular5m bars after actual first fill; no gap replay."""
    p = WinnerPyramidingConfig(**state['policy'])
    if not state['lots']:
        return False
    # Zero disables initial confirmation only. An add still needs at least
    # one completed regular-session bar above its own winning threshold.
    tail = fresh_completed_bars(bars, p, now=now, count=max(1, p.confirmation_bars))
    if not tail:
        return False
    first_fill = aware(state['first_fill_at'])
    initial_entry = (state['initial_filled_notional']/state['initial_filled_quantity']
        if state.get('initial_filled_quantity') else state['lots'][0]['entry'])
    for b in tail:
        stamp = aware(b['timestamp'])
        if stamp < first_fill or b['close'] < initial_entry*(1+p.reinforcement_trigger_pct):
            return False
    return True


def observe_completed_bar(lot, high, policy):
    if not math.isfinite(high) or high <= 0:
        raise ValueError('Qualified completed high required')
    lot['peak'] = max(lot['peak'], high)
    if policy.trailing_stop_pct:
        lot['stop'] = max(lot['stop'], round(lot['peak']*(1-policy.trailing_stop_pct), 2))


def resolve_bar_exit(lot, bar, *, at_deadline=False):
    """Known prior stop wins gaps; adverse collision wins; TP gap capped."""
    op, hi, lo = (float(bar[k]) for k in ('open', 'high', 'low'))
    if not all(math.isfinite(v) and v > 0 for v in (op, hi, lo)) or not lo <= op <= hi:
        raise ValueError('Qualified regular OHLC required before resolving a lot')
    if op <= lot['stop']:
        return op, 'STOP_GAP', 'OPEN'
    if lot['tp'] is not None and op >= lot['tp']:
        return lot['tp'], 'TP_GAP_CAPPED', 'OPEN'
    if at_deadline:
        return op, 'HORIZON_OPEN', 'OPEN'
    if lo <= lot['stop']:
        return lot['stop'], 'STOP', 'INTRABAR'
    if lot['tp'] is not None and hi >= lot['tp']:
        return lot['tp'], 'TP', 'INTRABAR'
    return None
