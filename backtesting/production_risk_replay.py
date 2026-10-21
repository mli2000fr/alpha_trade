"""Calendar adapter to production risk components; offline RESEARCH, not live.

No broker/DB/alerts or new B4 rules. Clock/next-open ordering is explicit.
Only the global portfolio protection layer is overlaid on frozen entry targets;
this is NOT all PortfolioBuilder or certification of historical live execution.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, replace
import math

from risk_management.circuit_breaker import CircuitBreaker, PnLSnapshot
from risk_management.config import RiskConfig


GUARD_FIELDS=('max_portfolio_drawdown_pct','max_daily_loss_pct','policy',
    'rolling_peak_window_days','degraded_entry_allocation_pct','recovery_pct',
    'regime_ramp_up_enabled','regime_ramp_up_pct_per_day','regime_ramp_up_max_pct',
    'regime_ramp_up_peak_window_days')


def force_close_selection(held, fraction):
    """Same count/worst-unrealized-PnL convention as Executor.run; not capital%.

    Inputs are observed simultaneous OPEN marks, never today's future close.
    Stable ties retain held-position order, as the production broker loop.
    """
    if not 0<fraction<=1:raise ValueError('Invalid forced-close fraction')
    if not held:return []
    ordered=sorted(held,key=lambda p:(-1 if p['side']=='sell' else 1)*p['quantity']*(p['mark']-p['entry_price']))
    n=max(1,int(len(ordered)*fraction+.5))
    return [p['symbol'] for p in ordered[:n]]


class ProductionRiskController:
    """Persistent production CircuitBreaker, one evaluation per real session.

    Input equity is today's observed open AFTER standing gap/expiry guards.
    Window252 counts daily closes, not five-minute bars or calls to status().
    Allocation affects this session's entries; streak advances once/session.
    B4's production is_active() does NOT turn the daily-loss status into a hard
    halt. This adapter records that fact; it does not invent a3% guaranteed stop.
    """
    def __init__(self,fields,*,initial_equity=4000.):
        self.fields=dict(fields)
        if set(self.fields)!=set(GUARD_FIELDS):raise ValueError('Complete frozen production guard fields required')
        template=replace(RiskConfig(),**fields)
        self.window=int(template.rolling_peak_window_days)
        # External DAILY window preserves252sessions. Never append a fake day
        # for each extra status()/checker call within a five-minute replay.
        self.template=replace(template,rolling_peak_window_days=0)
        self.pnl=PnLSnapshot(initial_equity,initial_equity,0.)
        self.breaker=CircuitBreaker(self.template,self.pnl)
        self.closes=deque([float(initial_equity)],maxlen=self.window if self.window>0 else None)
        self.previous_close=float(initial_equity)
        self.last_day=None
        self.last_closed_day=None

    def evaluate(self,day,equity,regime):
        if self.last_day is not None and day<=self.last_day:raise ValueError('Risk clock must advance by session')
        if self.last_day is not None and self.last_closed_day!=self.last_day:raise ValueError('Prior risk session not closed')
        if not math.isfinite(equity) or equity<=0:raise ValueError('Non-positive risk equity')
        peak=max(max(self.closes),float(equity))
        self.pnl.portfolio_high_watermark=peak
        self.pnl.portfolio_current_value=float(equity)
        self.pnl.daily_pnl=float(equity)-self.previous_close
        self.breaker._cfg=replace(self.template,account_equity=float(equity))
        self.breaker._regime_today=regime  # Same input as set_spy_regime, frozen prior-session map.
        before=asdict(self.breaker._episode) if self.breaker._episode is not None else None
        self.breaker.update_adaptive(equity,peak)
        active=self.breaker.is_active()
        trip=self.breaker.just_tripped()
        self.breaker.update_regime_streak('normal',equity)
        scale=self.breaker.allocation_scale(entry_mode='normal')
        daily=self.breaker._evaluate_daily_loss()
        self.last_day=day
        return dict(date=day,equity_before=float(equity),reference_peak=float(peak),
            drawdown_pct=100*(1-equity/peak),previous_close=self.previous_close,
            daily_pnl=float(equity)-self.previous_close,daily_loss_status=bool(daily.active),
            active=bool(active),just_tripped=bool(trip),allocation_scale=float(scale),
            regime=regime,episode_before=before,
            episode_after=asdict(self.breaker._episode) if self.breaker._episode is not None else None)

    def finish(self,day,equity):
        if self.last_day!=day or self.last_closed_day==day:raise ValueError('Risk daily-close ordering')
        if not math.isfinite(equity) or equity<=0:raise ValueError('Invalid risk daily close')
        self.closes.append(float(equity));self.previous_close=float(equity)
        self.last_closed_day=day
