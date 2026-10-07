"""Incremental ledger adapter for Oracle replay; native accounting, no SQL.

Execution/protection inputs must be resolved causally by the caller. This
adapter does not certify a complete live-parity strategy or invent exits.
"""
from __future__ import annotations

from datetime import datetime, time
from dataclasses import replace
from zoneinfo import ZoneInfo
import math

import pandas as pd

from backtesting.simulator import BacktestEngine, BacktestDiagnostics, _RunState
from backtesting.execution_replay import simulate_phase3_execution_replay
from backtesting.execution_lifecycle_replay import build_phase4_protection_replay
from backtesting.protection_watcher_replay import build_phase5_watcher_replay
from backtesting.exit_lifecycle_replay import build_phase7_exit_lifecycle_replay
from risk_management.operational_data import BacktestOperationalDataAdapter


class OraclePortfolioLedger(BacktestEngine):
    """Own ONE native cash/positions ledger throughout all daily decisions."""

    def __init__(self, config, *, opens, close, high, low, volume, sector_map):
        super().__init__(config)
        if (not config.require_replay_quantities or not config.require_replay_protections
                or not config.use_canonical_costs or config.exposure_multiplier != 1
                or config.entry_limit_offset_pct != 0
                or config.microstructure.execution_model.model != 'next_open'):
            raise ValueError('Explicit next-open quantities/protections/canonical costs required')
        self.days = pd.DatetimeIndex(close.index)
        if not self.days.is_unique or not self.days.is_monotonic_increasing:
            raise ValueError('Invalid ledger calendar')
        for frame in (opens, high, low, volume):
            if not frame.index.equals(close.index) or not frame.columns.equals(close.columns):
                raise ValueError('Market frames must be identically aligned')
        self.opens, self.close, self.high, self.low, self.volume = opens, close, high, low, volume
        self.sectors = dict(sector_map)
        self.adv = (close * volume).rolling(20, min_periods=20).mean().shift(1)
        self.state = _RunState(settled_cash=float(config.initial_equity), peak_equity=float(config.initial_equity))
        self.diagnostics = BacktestDiagnostics()
        self.current_day = None
        self.last_finished = None
        self.at_close = False
        self.phase = 'open'
        self.interest_charged = False
        self.failed = False
        self.daily = []
        self.execution_audits = []
        self.interest = 0.
        self.protections = {}
        self.protection_audits = []

    def _require_day(self):
        if self.current_day is None or self.failed:
            raise ValueError('No usable active ledger day')

    def _marks(self):
        frame = self.close.loc[:self.current_day].copy()
        if not self.at_close:
            frame.loc[self.current_day] = self.opens.loc[self.current_day]
        for symbol in self.state.positions:
            value = frame.at[self.current_day, symbol]
            if not pd.notna(value) or not math.isfinite(float(value)) or value <= 0:
                raise ValueError(f'Missing held-position mark {symbol}/{self.current_day}')
        return frame

    def equity(self):
        self._require_day()
        return self.state.settled_cash + self.state.unsettled_cash + self._mark_to_market(
            self.state.positions, self._marks(), self.current_day)

    def begin_day(self, day):
        day = pd.Timestamp(day).normalize()
        if self.failed or self.current_day is not None:
            raise ValueError('Previous ledger day not finished or ledger failed')
        idx = self.days.get_indexer([day])[0]
        if idx < 0:
            raise ValueError('Day absent from ledger calendar')
        if self.last_finished is not None:
            previous = self.days.get_indexer([self.last_finished])[0]
            if idx != previous + 1:
                raise ValueError('Ledger sessions must be consecutive')
        self.current_day, self.at_close = day, False
        self.phase, self.interest_charged = 'open', False
        self._apply_settlements(self.state, idx)
        self._marks()

    def execute_approved(self, entries, *, execution_config):
        """Consume J decisions at the following session's open, without resize.

        Returns phase 4 protections for the caller's chronological watcher.
        Broker-like retries remain synthetic. No close/high/low of today is
        supplied to entry sizing or opening valuation.
        """
        self._require_day()
        if self.phase != 'open':
            raise ValueError('Cannot execute opening orders after close')
        approved = [e for e in entries if e.approved_shares > 0]
        for entry in approved:
            decision = entry.score_snapshot_date or entry.price_asof_date
            idx = self.days.searchsorted(pd.Timestamp(decision), side='right')
            if idx >= len(self.days) or self.days[idx] != self.current_day:
                raise ValueError('Approved order is not for this next session')
            if entry.side != 'buy':
                raise ValueError('Oracle ledger policy is LONG-only')
        phase3 = simulate_phase3_execution_replay(approved, execution_config=execution_config,
            open_df=self.opens.loc[:self.current_day], risk_run_id_prefix='chronological_oracle',
            enforce_live_gap_filter=True)
        phase4 = self._build_entry_protections(phase3, execution_config=execution_config)
        signals = phase4.signals_df.copy()
        if not signals.empty:
            # Entry protections exist; no high/low of J+1 has yet triggered a watcher.
            signals['watcher_transition_state'] = 'pending'
            signals['watcher_transition_effective_date'] = pd.NaT
            signals['signal_date'] = pd.to_datetime(signals.trade_date)
            signals['sector'] = signals.symbol.map(self.sectors)
            if signals.sector.isna().any():
                raise ValueError('Missing execution sector')
            self._validate_replay_protections(signals, self.opens.loc[:self.current_day])
        opened, rejected = [], []
        self.failed = True
        try:
            for _, row in signals.iterrows():
                symbol = row.symbol
                if symbol in self.state.positions:
                    raise ValueError('Duplicate held symbol submitted for entry')
                if len(self.state.positions) >= self.config.max_positions:
                    raise ValueError('Approved portfolio exceeds position capacity')
                event_start = len(self.state.trade_events)
                self._try_open_entries(state=self.state, candidate_rows=[row],
                    open_df=self.opens.loc[:self.current_day], high_df=self.opens.loc[:self.current_day],
                    low_df=self.opens.loc[:self.current_day], close=self._marks(),
                    trade_day=self.current_day, day_idx=self.days.get_loc(self.current_day),
                    trading_days=self.days, adv_usd_df=self.adv.loc[:self.current_day],
                    sector_map=self.sectors, current_equity=self.equity_unchecked(),
                    drawdown_allocation_scale=1., diagnostics=self.diagnostics)
                if symbol in self.state.positions:
                    if abs(self.state.positions[symbol].quantity-float(row.filled_qty)) > 1e-6:
                        raise AssertionError('Approved quantity changed')
                    opened.append(symbol)
                    self.protections[symbol] = replace(phase4,
                        signals_df=phase4.signals_df.loc[phase4.signals_df.symbol.eq(symbol)].copy())
                else:
                    reasons = [e for e in self.state.trade_events[event_start:]
                        if e.get('event_type') == 'entry_rejected' and e.get('symbol') == symbol]
                    if reasons:
                        rejected.append(reasons[-1])
            self.execution_audits.append({'date': self.current_day,
                'approved': len(approved), 'opened': opened,
                'explicit_entry_rejections': rejected,
                'phase3_diagnostics': phase3.diagnostics,
                'phase3_attempts_rejected_at_portfolio_commit': [r['symbol'] for r in rejected],
                'hypothetical_fills_not_committed': sorted(set(signals.get('symbol', []))-set(opened)
                    -{r['symbol'] for r in rejected})})
        except Exception:
            # Never continue a potentially partially mutated accounting state.
            raise
        else:
            self.failed = False
        if rejected:
            phase4 = replace(phase4,
                signals_df=phase4.signals_df.loc[phase4.signals_df.symbol.isin(opened)].copy(),
                protection_frame=phase4.protection_frame.loc[
                    phase4.protection_frame.symbol.isin(opened)].copy(),
                diagnostics=dict(phase4.diagnostics, portfolio_commit_rejections=rejected,
                    phase3_fills_scope='synthetic attempts, committed signals only returned'))
        return phase4, opened

    def _build_entry_protections(self, phase3, *, execution_config):
        """Default native protections; research subclasses can isolate an experiment."""
        return build_phase4_protection_replay(phase3, execution_config=execution_config)

    def apply_observed_protections(self, *, phase, take_profit_enabled=True, trailing_enabled=True):
        """Replay common watcher/lifecycle only through the observed boundary.

        At the open, today's high/low are masked. Gap stops fill at the open;
        favourable TP gaps conservatively fill at their limit. At intraday
        resolution, daily OHLC ambiguity uses the common conservative rule.
        The known session calendar may schedule tomorrow's watcher activation,
        but no tomorrow price is exposed to these modules.
        """
        self._require_day()
        if phase not in {'open', 'intraday'} or self.at_close:
            raise ValueError('Invalid protection observation phase')
        if self.phase != 'open' and phase == 'open':
            raise ValueError('Opening protection phase already passed')
        exits = []
        for symbol, position in list(self.state.positions.items()):
            protection = self.protections.get(symbol)
            if protection is None:
                raise ValueError(f'Missing native protections: {symbol}')
            # Include exactly one known next session for scheduled activation,
            # with every unobserved price masked out.
            idx = self.days.get_loc(self.current_day)
            until = self.days[min(idx+1, len(self.days)-1)]
            highs = self.high.loc[position.entry_date:until, [symbol]].copy()
            lows = self.low.loc[position.entry_date:until, [symbol]].copy()
            mask = highs.index >= self.current_day if phase == 'open' else highs.index > self.current_day
            highs.loc[mask] = float('nan')
            lows.loc[mask] = float('nan')
            watcher = build_phase5_watcher_replay(protection, high_df=highs, low_df=lows)
            row = watcher.signals_df.iloc[0]
            if phase == 'open':
                opening = float(self.opens.at[self.current_day, symbol])
                effective = row.get('watcher_transition_effective_date')
                active = trailing_enabled and pd.notna(effective) and pd.Timestamp(effective) <= self.current_day
                prior_high = highs.loc[highs.index < self.current_day, symbol].dropna()
                peak = max(position.entry_price, float(prior_high.max())) if len(prior_high) else position.entry_price
                stop = peak * (1-float(row.replay_trailing_stop_pct)) if active else float(row.replay_initial_stop_price)
                if opening <= stop:
                    exits.append({'symbol': symbol, 'exit_date': self.current_day, 'exit_price': opening,
                        'exit_reason': 'trailing_stop_gap_open' if active else 'initial_stop_gap_open'})
                elif take_profit_enabled and opening >= float(row.replay_take_profit_price):
                    exits.append({'symbol': symbol, 'exit_date': self.current_day,
                        'exit_price': float(row.replay_take_profit_price), 'exit_reason': 'take_profit_gap_limit'})
            else:
                for frame in (highs, lows):
                    observed = frame.loc[frame.index <= self.current_day, symbol]
                    if observed.isna().any() or not observed.map(lambda v: math.isfinite(float(v)) and v > 0).all():
                        raise ValueError(f'Incomplete held protection path: {symbol}')
                lifecycle = build_phase7_exit_lifecycle_replay(watcher, high_df=highs, low_df=lows,
                    intrabar_priority='conservative', swing_only=self.config.trading_constraints.swing_only,
                    take_profit_enabled=take_profit_enabled, trailing_enabled=trailing_enabled)
                for resolved in lifecycle.exit_frame.to_dict('records'):
                    exit_day = pd.Timestamp(resolved['replay_exit_date'])
                    if exit_day < self.current_day:
                        raise ValueError(f'Unconsumed earlier lifecycle exit: {symbol}/{exit_day}')
                    if exit_day == self.current_day:
                        exits.append({'symbol': symbol, 'exit_date': exit_day,
                            'exit_price': float(resolved['replay_exit_price']),
                            'exit_reason': str(resolved['replay_exit_reason']),
                            'exit_intent_role': resolved['replay_exit_intent_role']})
            self.protection_audits.append({'date': self.current_day, 'symbol': symbol, 'phase': phase,
                'watcher_state': row.get('watcher_transition_state'),
                'watcher_effective_date': row.get('watcher_transition_effective_date')})
        return self.close_resolved(exits, phase=phase)

    def equity_unchecked(self):
        """Internal valuation while a native mutation is guarded as in-flight."""
        return self.state.settled_cash + self.state.unsettled_cash + self._mark_to_market(
            self.state.positions, self._marks(), self.current_day)

    def close_resolved(self, exits, *, phase):
        """Book ONLY exits resolved by the caller for today, with native fees.

        ``phase`` is 'open' for gaps/queued transition orders, 'close' for
        pre-scheduled terminal orders, or 'intraday' for resolved protections.
        No future scheduled exit may be consumed here.
        """
        self._require_day()
        if (phase not in {'open', 'intraday', 'close'}
                or (self.phase != 'open' and phase == 'open')
                or (self.at_close and phase != 'close')):
            raise ValueError('Invalid exit chronology')
        seen = set()
        for row in exits:
            symbol = row['symbol']
            if symbol in seen or symbol not in self.state.positions:
                raise ValueError('Unknown/duplicate closed position')
            seen.add(symbol)
            price = float(row['exit_price'])
            quantity = float(row.get('quantity', self.state.positions[symbol].quantity))
            if not math.isfinite(quantity) or not 0 < quantity <= self.state.positions[symbol].quantity:
                raise ValueError('Invalid partial exit quantity')
            if pd.Timestamp(row['exit_date']).normalize() != self.current_day or not math.isfinite(price) or price <= 0:
                raise ValueError('Invalid causal exit')
            if not row.get('exit_reason'):
                raise ValueError('Exit reason required')
        self.phase = phase
        if phase == 'close':
            self.at_close = True
        completed = []
        for row in exits:
            symbol = row['symbol']
            position = self.state.positions[symbol]
            full_equity = self.equity_unchecked()
            quantity = float(row.get('quantity', position.quantity))
            remaining = None
            if quantity < position.quantity:
                fraction = quantity / position.quantity
                remaining = replace(position, quantity=position.quantity-quantity,
                    entry_cost=position.entry_cost*(1-fraction),
                    entry_cash_flow=position.entry_cash_flow*(1-fraction))
                position = replace(position, quantity=quantity, entry_cost=position.entry_cost*fraction,
                    entry_cash_flow=position.entry_cash_flow*fraction)
            position.explicit_exit_date = self.current_day
            position.explicit_exit_price = float(row['exit_price'])
            position.explicit_exit_reason = str(row['exit_reason'])
            position.explicit_exit_intent_role = str(row.get('exit_intent_role', row['exit_reason']))
            position.explicit_oco_sibling_canceled = True
            others = {s: p for s, p in self.state.positions.items() if s != symbol}
            self.state.positions = {symbol: position}
            self.failed = True
            try:
                self._try_close_positions(state=self.state, close=self.close.loc[:self.current_day],
                    high=self.high.loc[:self.current_day], low=self.low.loc[:self.current_day],
                    trade_day=self.current_day, day_idx=self.days.get_loc(self.current_day), trading_days=self.days,
                    adv_usd_df=self.adv.loc[:self.current_day], rng=None, diagnostics=self.diagnostics,
                    current_equity=full_equity)
                if symbol in self.state.positions:
                    raise ValueError('Native ledger refused resolved exit')
                completed.append(self.state.closed_trades[-1])
                if remaining is None:
                    self.protections.pop(symbol, None)
                else:
                    others[symbol] = remaining
                    self.protections[symbol].signals_df.loc[:, 'filled_qty'] = remaining.quantity
            finally:
                self.state.positions.update(others)
            self.failed = False
        return completed

    def mark_close(self):
        self._require_day()
        self.at_close = True
        self.phase = 'close'
        if not self.interest_charged:
            charge = self._accrue_margin_interest(self.state, annual_rate=self.config.margin_interest_rate_annual)
            self.interest += charge
            self.interest_charged = True
            self._today_interest = charge
        return self.equity()

    def snapshot(self, *, take_profit_enabled=True, trailing_enabled=True):
        """Current ledger normalized exactly as for the risk session."""
        self._require_day()
        if not self.at_close or not self.interest_charged:
            raise ValueError('Decision snapshot requires the observed close')
        equity = self.equity()
        gross = self._compute_gross_notional(self.state.positions, self._marks(), self.current_day)
        budget = self._resolve_available_entry_budget(constraints=self.config.trading_constraints,
            settled_cash=self.state.settled_cash, current_equity=equity, current_gross_notional=gross)
        orders = []
        for symbol, position in self.state.positions.items():
            roles = ['stop'] + (['limit'] if take_profit_enabled else [])
            for role in roles:
                orders.append({'id': f'{symbol}-{position.entry_date}-{role}', 'symbol': symbol,
                    'side': 'sell', 'type': role, 'qty': position.quantity, 'status': 'new'})
        return BacktestOperationalDataAdapter.build(account_id='chronological_oracle',
            account={'equity': equity, 'cash': self.state.settled_cash+self.state.unsettled_cash,
                'settled_cash': self.state.settled_cash, 'buying_power': max(budget, 0.)},
            positions=[{'symbol': s, 'qty': p.quantity, 'side': 'long',
                'avg_entry_price': p.entry_price, 'current_price': float(self.close.at[self.current_day, s])}
                for s, p in self.state.positions.items()], orders=orders,
            as_of=datetime.combine(self.current_day.date(), time(16), tzinfo=ZoneInfo('America/New_York')),
            source='native_backtest_ledger')

    def finish_day(self):
        self._require_day()
        if not self.at_close or not self.interest_charged:
            raise ValueError('Close must be observed before finishing session')
        charge = self._today_interest
        equity = self.equity()
        self.state.peak_equity = max(self.state.peak_equity, equity)
        self.state.equity_points.append(equity)
        self.daily.append({'date': self.current_day, 'equity': equity,
            'settled_cash': self.state.settled_cash, 'unsettled_cash': self.state.unsettled_cash,
            'positions': len(self.state.positions), 'margin_interest': charge})
        self.last_finished, self.current_day = self.current_day, None
        return equity

    def reconciliation_error(self):
        if self.state.positions:
            raise ValueError('Cash reconciliation requires no remaining positions')
        cash = self.state.settled_cash + self.state.unsettled_cash
        expected = self.config.initial_equity + sum(t['pnl'] for t in self.state.closed_trades) - self.interest
        return cash - expected
