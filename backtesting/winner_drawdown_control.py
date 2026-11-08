"""Explicit replay-only drawdown switch. Production breaker is never changed."""
from dataclasses import replace
from datetime import date
import math


class InactiveReplayBreaker:
    """Native risk still sizes/limits entries; only the replay breaker is off."""
    def is_active(self):return False
    def just_tripped(self):return False
    def allocation_scale(self,*args,**kwargs):return 1.


class InactiveReplayDrawdown:
    def __init__(self,day,equity):
        self.peak=float(equity);self.last_day=None;self.breaker=InactiveReplayBreaker()
        self.evaluate(day,equity,None,daily_pnl=0.)

    def evaluate(self,day,equity,regime,*,daily_pnl):
        day=date.fromisoformat(day) if isinstance(day,str) else day
        if (not math.isfinite(equity) or equity<=0 or not math.isfinite(daily_pnl)
                or self.last_day is not None and day<self.last_day):
            raise ValueError('Invalid or backward replay equity observation')
        self.peak=max(self.peak,equity);self.last_day=day
        return dict(reference_peak=self.peak,allocation_scale=1.,circuit_breaker=self.breaker,active=False,day=day.isoformat())


def effective_drawdown_settings(risk,execution,enabled):
    if type(enabled) is not bool:raise ValueError('Replay drawdown controller: boolean required')
    if enabled:return risk,execution
    return replace(risk,force_close_on_breaker=False),replace(execution,force_close_on_breaker=False)


def create_drawdown_state(risk,day,equity,regimes,enabled):
    if type(enabled) is not bool:raise ValueError('Replay drawdown controller: boolean required')
    if enabled:
        from common.winner_risk_state import CampaignRiskState
        return CampaignRiskState(risk,observations=[(day,equity)],regimes=regimes)
    return InactiveReplayDrawdown(day,equity)


def controller_snapshot(enabled,risk,execution=None):
    components=['DRAWDOWN','DAILY_LOSS'] if enabled else []
    if enabled and risk.policy!='b0':components.append('ADAPTIVE_ALLOCATION_'+risk.policy.upper())
    liquidates=bool(enabled and (risk.force_close_on_breaker or execution is not None and execution.force_close_on_breaker))
    if liquidates:components.append('ASSOCIATED_LIQUIDATION')
    return dict(enabled=enabled,scope='WINNER_BACKTEST_ONLY',configured_policy=risk.policy,
        drawdown_limit=risk.max_portfolio_drawdown_pct,daily_loss_limit=risk.max_daily_loss_pct,
        active_components=components,liquidation_enabled=liquidates,
        position_protections_and_sizing_unchanged=True,drawdown_still_measured=True)
