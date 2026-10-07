"""Chronological Oracle-only risk decisions using the shared live builder.

This is the risk side of a replay, not a broker/fill simulator. Callers must
advance their real simulated ledger before submitting the next snapshot.
No implicit neutral regime, cash reset or synthetic direction is permitted.
"""
from __future__ import annotations

from datetime import date
import math

import pandas as pd

from backtesting.risk_bridge import _build_prices, _build_return_matrix
from risk_management.config import RiskConfig
from risk_management.concentration import (
    BreakoutConfirmationTracker, ConsecutiveLossTracker, SymbolTradeTracker,
)
from risk_management.models import SelectionScore
from risk_management.operational_data import OperationalDataSnapshot
from risk_management.portfolio_builder import PortfolioBuilder
from risk_management.regime_apply import (
    apply_account_cp_policy, apply_snapshot, apply_structural_market_guards,
    apply_transition,
)
from selector.regime_scoring import MomentumRotationState
from service.market.models import MarketRegimeSnapshot
from risk_management.live_pipeline_guards import evaluate_vol_target, apply_vol_target_to_risk_config


class OraclePortfolioSession:
    """One persistent risk session per portfolio, never one per trade date."""

    def __init__(self, config: RiskConfig, *, sector_map: dict[str, str],
                 market_regimes_config=None, account_long_only: bool):
        self.config = config
        self.sectors = dict(sector_map)
        self.market_config = market_regimes_config
        self.account_long_only = account_long_only
        self.breakout = BreakoutConfirmationTracker(min_breakout_days=config.min_breakout_days)
        self.trades = SymbolTradeTracker(max_trades=config.concentration_max_trades_per_symbol,
            window_days=config.concentration_window_calendar_days)
        self.losses = ConsecutiveLossTracker(
            max_consecutive_losses=config.concentration_max_consecutive_losses,
            blacklist_duration_days=config.concentration_blacklist_duration_days)
        self.rotation = MomentumRotationState(lookback_weeks=4, threshold=-.03)
        self.last_decision = None
        self.last_event = None
        self.previous_equity = None
        self.events = set()
        self._event_payloads = {}
        self.resolved_config = None
        self.failed = False

    def decide(self, day: date, *, scores: pd.DataFrame,
               snapshot: OperationalDataSnapshot, regime: MarketRegimeSnapshot,
               close: pd.DataFrame, high: pd.DataFrame, low: pd.DataFrame,
               volume: pd.DataFrame | None = None, transition=None,
               pnl=None, circuit_breaker=None):
        """Decide at J close; the returned orders may execute only AFTER J.

        ``scores`` contains the already frozen Oracle membership for J. Future
        prices are discarded BEFORE computing ATR, ADV and correlation.
        Account-long-only describes account policy, not simply strategy side.
        """
        if self.failed:
            raise ValueError('Risk session failed after state mutation; restart from a validated checkpoint')
        if self.last_decision is not None and day <= self.last_decision:
            raise ValueError('Decisions must be strictly chronological')
        if self.last_event is not None and day < self.last_event:
            raise ValueError('Decision precedes an already processed fill')
        if not isinstance(snapshot, OperationalDataSnapshot) or snapshot.account.as_of.date() != day:
            raise ValueError('Real ledger snapshot required for this decision date')
        if not isinstance(regime, MarketRegimeSnapshot) or regime.trade_date != day:
            raise ValueError('Explicit same-date regime required')
        equity = float(snapshot.account.equity)
        if not math.isfinite(equity) or equity <= 0:
            raise ValueError('Invalid ledger equity')
        if scores.duplicated('symbol').any():
            raise ValueError('Duplicate candidate')
        if not scores.empty and not pd.to_datetime(scores.trade_date).dt.date.eq(day).all():
            raise ValueError('Candidate date mismatch')
        candidates = [SelectionScore(str(r.symbol), self.sectors.get(str(r.symbol), 'Unknown'),
            float(r.proba_extreme), score_source='oracle_amplitude', snapshot_date=day)
            for r in scores.itertuples(index=False)]
        cutoff = pd.Timestamp(day)
        def history(frame):
            if frame is None:
                return None
            if not isinstance(frame.index, pd.DatetimeIndex) or not frame.index.is_unique:
                raise ValueError('Unique datetime market index required')
            if not frame.index.is_monotonic_increasing:
                raise ValueError('Market index must be chronological')
            return frame.loc[frame.index <= cutoff]
        closes, highs, lows, volumes = map(history, (close, high, low, volume))
        symbols = [c.symbol for c in candidates]
        for frame in (closes, highs, lows):
            if symbols and (cutoff not in frame.index or any(s not in frame.columns for s in symbols)):
                raise ValueError('Missing same-date market bar')
            if symbols and not frame.loc[cutoff, symbols].map(
                    lambda value: pd.notna(value) and math.isfinite(float(value)) and float(value) > 0).all():
                raise ValueError('Invalid same-date market bar')
        prices = _build_prices(close_df=closes, high_df=highs, low_df=lows,
            volume_df=volumes, snapshot_date=day, symbols=symbols)
        for symbol in symbols:
            price = prices.get(symbol)
            if price is None or price.price_asof_date != day or price.atr_asof_date != day:
                raise ValueError(f'Missing same-date price/ATR: {symbol}/{day}')
            if price.atr_20 is None or not math.isfinite(price.atr_20) or price.atr_20 <= 0:
                raise ValueError(f'Incomplete ATR20: {symbol}/{day}')
        cfg = self.config.with_overrides(account_equity=equity)
        cfg = apply_structural_market_guards(cfg, market_regimes_config=self.market_config, equity=equity)
        cfg = apply_snapshot(cfg, regime)
        cfg = apply_account_cp_policy(cfg, account_long_only=self.account_long_only)
        cfg = apply_transition(cfg, transition)
        if 'SPY' in closes and cfg.target_annual_vol:
            self.vol_target = evaluate_vol_target(closes.SPY.pct_change(fill_method=None).dropna(),
                target_annual_vol=cfg.target_annual_vol, lookback_days=cfg.vol_target_lookback_days)
            cfg = apply_vol_target_to_risk_config(cfg, self.vol_target)
        if circuit_breaker is not None:
            circuit_breaker.is_active()
            scale = circuit_breaker.allocation_scale(entry_mode=regime.mode, side='buy')
            cfg = cfg.with_overrides(risk_multiplier=cfg.risk_multiplier * scale)
        # Trackers may mutate during build. A failed build cannot be replayed
        # into this same in-memory session and counted a second time.
        self.failed = True
        if self.previous_equity is not None:
            self.rotation.record(equity / self.previous_equity - 1.)
        builder = PortfolioBuilder(cfg, pnl=pnl, circuit_breaker=circuit_breaker,
            regime_snapshot=regime, regime_transition=transition, rotation_state=self.rotation,
            breakout_tracker=self.breakout, sector_map=self.sectors,
            concentration_trade_tracker=self.trades, concentration_loss_tracker=self.losses)
        builder.set_operational_snapshot(snapshot)
        entries = builder.build(candidates, prices, trade_date=day,
            return_matrix=_build_return_matrix(closes, day, symbols, cfg.correlation_lookback_days),
            selection_policy='oracle_pure_long')
        self.last_decision, self.previous_equity = day, equity
        self.resolved_config = cfg
        self.failed = False
        return entries

    def record_fill(self, event_id: str, *, day: date, symbol: str,
                    entry: bool, realized_pnl: float | None = None):
        """Record actual fills, not approvals/rejections; retries are idempotent.

        Call once for each opened position (not every partial entry fill), and
        once for each closed position with its net realized PnL.
        """
        if self.failed:
            raise ValueError('Cannot record fill into a failed risk session')
        if not event_id or not symbol:
            raise ValueError('Fill identity required')
        payload = (day, symbol, entry, realized_pnl)
        if event_id in self.events:
            if self._event_payloads[event_id] != payload:
                raise ValueError('Conflicting fill identity')
            return
        if self.last_decision is None or day <= self.last_decision:
            raise ValueError('Fill must follow the latest decision')
        if self.last_event is not None and day < self.last_event:
            raise ValueError('Out-of-order fill')
        if not entry and (realized_pnl is None or not math.isfinite(realized_pnl)):
            raise ValueError('Closed-position net PnL required')
        if entry:
            self.trades.record(symbol, day, side='buy')
        else:
            self.losses.record(symbol, realized_pnl, day, side='buy')
        self.events.add(event_id)
        self._event_payloads[event_id] = payload
        self.last_event = day
