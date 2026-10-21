"""Serializable native breaker state shared by campaign live/replay adapters.

Five-minute checks never become five-minute 'days'. B4's favorable streak and
allocation are advanced once per real session. Current equity remains visible
to the native checks; reference peaks are actual observations, never invented.
"""
from dataclasses import asdict, replace
from datetime import date
import hashlib
import json
import math

from backtesting.adaptive_breaker import BreakerEpisode
from risk_management.circuit_breaker import CircuitBreaker, PnLSnapshot

GUARD_FIELDS = ('max_portfolio_drawdown_pct', 'max_daily_loss_pct', 'policy',
    'rolling_peak_window_days', 'degraded_entry_allocation_pct', 'recovery_pct',
    'regime_ramp_up_enabled', 'regime_ramp_up_pct_per_day', 'regime_ramp_up_max_pct',
    'regime_ramp_up_peak_window_days')


class CampaignRiskState:
    def __init__(self, cfg, *, saved=None, observations=(), regimes=None):
        self.cfg = cfg
        self.fields = {k: getattr(cfg, k) for k in GUARD_FIELDS}
        self.fingerprint = hashlib.sha256(json.dumps(self.fields, sort_keys=True).encode()).hexdigest()
        if saved and saved['fingerprint'] != self.fingerprint:
            raise ValueError('Campaign global risk policy changed: explicit requalification required; state not reset')
        self.data = saved or dict(fingerprint=self.fingerprint, peaks={}, last_day=None,
            episode=None, tripped=False, allocation=1., normal_streak=0,
            equity_prev=0., equity_peak_window=[])
        self.breaker = CircuitBreaker(replace(cfg, rolling_peak_window_days=0), PnLSnapshot())
        if saved:
            # New real broker observations may have been recorded while the
            # watcher was down. Recover peaks without counting fictitious
            # favorable sessions or replaying the same day multiple times.
            for day, equity in observations:
                if not math.isfinite(equity) or equity <= 0:
                    raise ValueError('Invalid observed account equity')
                key = day.isoformat()
                self.data['peaks'][key] = max(self.data['peaks'].get(key, 0.), equity)
        if not saved:
            if not observations:
                raise ValueError('At least one real account equity observation is required; no synthetic high-watermark')
            for day, equity in sorted(observations):
                self.evaluate(day, equity, (regimes or {}).get(day), daily_pnl=0.)

    def evaluate(self, day, equity, regime, *, daily_pnl):
        day = date.fromisoformat(day) if isinstance(day, str) else day
        if not math.isfinite(equity) or equity <= 0 or not math.isfinite(daily_pnl):
            raise ValueError('Qualified account equity / daily PnL required')
        key = day.isoformat()
        previous = self.data['last_day']
        if previous is not None and key < previous:
            raise ValueError('Risk state cannot move backwards')
        if str(self.cfg.policy).lower() != 'b0' and regime not in ('BULL', 'REBOUND', 'CORRECTION', 'SLIDE'):
            raise ValueError('Qualified prior-session SPY regime required for adaptive risk')
        self.data['peaks'][key] = max(self.data['peaks'].get(key, 0.), equity)
        keys = sorted(self.data['peaks'])
        window = self.cfg.rolling_peak_window_days
        reference = keys[-window:] if window else keys
        peak = max(self.data['peaks'][d] for d in reference)
        cb = self.breaker
        cb._cfg = replace(self.cfg, account_equity=equity, rolling_peak_window_days=0)
        cb._pnl = PnLSnapshot(peak, equity, daily_pnl)
        cb._episode = BreakerEpisode(**self.data['episode']) if self.data['episode'] else None
        cb._tripped, cb._alloc_today = self.data['tripped'], self.data['allocation']
        cb._normal_streak = self.data['normal_streak']
        cb._equity_prev, cb._equity_peak_window = self.data['equity_prev'], list(self.data['equity_peak_window'])
        cb._regime_today = regime
        if key != previous:
            if cb.is_adaptive:
                cb.update_adaptive(equity, peak)
            else:
                cb.is_active()
            cb.update_regime_streak('normal', equity)
            self.data['session_allocation_ceiling'] = cb.allocation_scale(entry_mode='normal')
        elif cb.is_adaptive:
            # React to a new adverse equity observation without advancing the
            # daily favorable streak or promoting allocation intraday.
            cb.update_adaptive(equity, peak)
            cb._alloc_today = min(cb._alloc_today, self.data.get('session_allocation_ceiling', 1.))
        active = cb.is_active()
        self.data.update(last_day=key, episode=asdict(cb._episode) if cb._episode is not None else None,
            tripped=cb._tripped, allocation=cb._alloc_today, normal_streak=cb._normal_streak,
            equity_prev=cb._equity_prev, equity_peak_window=list(cb._equity_peak_window))
        return dict(reference_peak=peak, allocation_scale=cb.allocation_scale(entry_mode='normal'),
            circuit_breaker=cb, active=active, day=key)

