"""SHORT-only daily research coordinator using the tested isolated SHORT ledger.

No shared Winner engine edits and no live routing. Daily close drawdown is
reported separately from the old five-minute drawdown. Borrow is an assumption.
"""
from dataclasses import replace
from datetime import date
import hashlib
import json
import logging
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import requests

from scripts.research.us_q051_b_short_20261118 import ROOT, read
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest


def config():
    from backtesting.simulator import BacktestConfig
    from backtesting.trading_constraints import TradingConstraintConfig
    from common.q051_paper import reference
    from execution_engine.config import ExecutionConfig, LeverageConfig
    from common.winner_pyramiding import WinnerPyramidingConfig
    from risk_management.config import RiskConfig
    p = reference('q051_b_witness_v1')
    # Mirror20 LONG slots with20 SHORT slots; no automatic bearish regime gate.
    risk = replace(RiskConfig(**p['risk']), max_short_positions=20)
    execution = ExecutionConfig(account_type='margin', dry_run=True, simulated_account_equity=4000.,
        simulated_margin_buying_power_multiplier=2., winner_pyramiding=WinnerPyramidingConfig(**p['winner']),
        leverage=LeverageConfig(**p['leverage']), account_id='research-short',
        entry_order_type='market', max_entry_gap_pct=0.)
    return BacktestConfig(start_date=date(2021,1,1), end_date=date(2026,10,1), initial_equity=4000.,
        risk_config=risk, exec_config=execution, winner_drawdown_controller_enabled=False,
        trading_constraints=TradingConstraintConfig(account_type='margin', swing_only=False))


class DailyShortReplay:
    """One marked account, whole shares, causal J+1 plans, fixed SL/open11."""
    def __init__(self, pivots, sectors, actions, signals, sessions, cfg, borrow=.03):
        from backtesting.simulator import BacktestEngine
        from backtesting.winner_short_broker import ShortReplayBroker
        from risk_management.concentration import SymbolTradeTracker, ConsecutiveLossTracker
        self.pivots, self.sectors, self.actions, self.signals = pivots, sectors, actions, signals
        self.sessions = sessions;self.calendar = pd.DatetimeIndex([s.session_date for s in sessions])
        self.cfg = cfg;self.book = ShortReplayBroker(BacktestEngine(cfg), fee=.0008, borrow_fee_annual=borrow)
        self.plans = [];self.states = {};self.curve = [];self.refusals = [];self.reserves = [];self.entries = []
        self.counter = SymbolTradeTracker(10, 90);self.losses = ConsecutiveLossTracker(3, 90)
        self.recorded_exits = 0;self.peak = cfg.initial_equity;self.insolvent = False

    def update_exits(self):
        for trade in self.book.trades[self.recorded_exits:]:
            self.losses.record(trade['symbol'], trade['pnl'], self.book.now.date(), side='sell')
        self.recorded_exits = len(self.book.trades)

    def _bar(self, day, symbol, *, completed=True):
        bar = {k: float(f.at[pd.Timestamp(day), symbol]) for k, f in self.pivots.items()}
        if not completed:
            if not np.isfinite(bar['open']) or bar['open'] <= 0:
                raise ValueError(f'Unqualified opening price {day}/{symbol}')
            return bar
        if (not all(np.isfinite(v) and v > 0 for v in bar.values())
                or bar['high'] < max(bar['open'], bar['low'], bar['close'])
                or bar['low'] > min(bar['open'], bar['high'], bar['close'])):
            raise ValueError(f'Unqualified held/entry daily price {day}/{symbol}')
        return bar

    def _native_quantity(self, symbol, price, proposed, budget):
        from risk_management.constraints import PortfolioState
        from risk_management.risk_checker import RiskCheckerImpl
        from common.q051_paper import NoDrawdownController
        equity = self.book.equity()
        cfg = replace(self.cfg.risk_config, account_equity=equity)
        state = PortfolioState()
        for position in self.book.positions():
            state.add_position(notional=position['quantity']*position['mark'],
                sector=self.sectors.get(position['symbol'], 'UNKNOWN'), side='sell', symbol=position['symbol'])
        # Same full-position reserve formula as the B witness. Never add size
        # because a favourable opening moved below the signal price.
        maximum = min(int(proposed), int(budget/(price*(.05+2.05*.0025))),
            int(equity*.2/price), int(self.book.capacity()/(price*1.0025)))
        if maximum <= 0:
            return 0, 'BUDGET_OR_CAPACITY'
        checker = RiskCheckerImpl(cfg, state=state, sector_map=self.sectors,
            circuit_breaker=NoDrawdownController())
        qty = int(checker.check_position_size(symbol, maximum, price, side='sell'))
        return qty, checker.get_last_decision_reason()

    def _cover(self, state, quantity, reason):
        from execution_engine.winner_broker import make_intent
        from execution_engine.models import IntentRole
        key = state['campaign_id']+'-cover-'+reason
        intent = make_intent(state, key, quantity=quantity, side='buy', role=IntentRole.EXIT, order_type='market')
        state['operations'].append(dict(key=intent.intent_id, exit_reason=reason))
        self.book.submit(state, intent)

    def _open(self, plan, session, offset, bar):
        from execution_engine.winner_broker import make_intent
        from execution_engine.models import IntentRole
        symbol = plan['symbol'];day = session.session_date
        if symbol in {p['symbol'] for p in self.book.positions()}:
            self.refusals.append(dict(date=str(day), symbol=symbol, reason='ALREADY_HELD'));return
        if not self.counter.allow_entry(symbol, day, side='sell') or self.losses.is_blacklisted(symbol, day, side='sell'):
            self.refusals.append(dict(date=str(day), symbol=symbol, reason='SYMBOL_CONCENTRATION'));return
        qty, reason = self._native_quantity(symbol, bar['open'], plan['quantity'], plan['risk_budget'])
        if not qty:
            self.refusals.append(dict(date=str(day), symbol=symbol, reason=reason));return
        key = 'research-short-'+hashlib.sha256((str(plan['signal_date'])+'|'+symbol).encode()).hexdigest()[:24]
        from dataclasses import asdict
        state = dict(campaign_id=key, symbol=symbol, side='short', risk_run_id='isolated-short',
            exec_run_id='isolated-short', broker_mode='paper', policy=asdict(self.cfg.exec_config.winner_pyramiding),
            lots=[], operations=[], due_index=offset+10)
        parent = make_intent(state, key+'-entry', quantity=qty, side='sell', price=bar['open'], order_type='market', tif='day')
        equity_before, gross_before = self.book.equity(), self.book.gross()
        self.book.short_reservations[parent.intent_id] = bar['open']
        self.book.submit(state, parent)
        if parent.intent_id not in self.book.lots:
            raise ValueError('Approved SHORT daily fill unexpectedly rejected')
        stop = make_intent(state, key+'-stop', quantity=qty, side='buy', role=IntentRole.INITIAL_STOP,
            order_type='stop', stop=round(bar['open']*1.05, 2), parent=parent.intent_id)
        self.book.protect(state, {}, parent, tp_intent=None, stop_intent=stop)
        # No take-profit sibling exists for this fixed-stop-only experiment.
        self.book.orders[stop.intent_id]['peer'] = None
        state.update(parent_id=parent.intent_id, stop=stop.stop_price)
        self.states[key] = state
        self.counter.record(symbol, day, side='sell')
        self.entries.append(dict(signal_date=plan['signal_date'], entry_date=str(day), symbol=symbol,
            quantity=qty, entry_price=bar['open'], risk_budget=plan['risk_budget'],
            full_quantity=plan['quantity'], short_probability=plan['short_probability'], rank=plan['rank'],
            campaign_id=key, due_index=offset+10, equity_before=equity_before, gross_before=gross_before))

    def _plan(self, day):
        self.plans = []
        if self.insolvent:
            return
        rows = self.signals[self.signals.date.eq(pd.Timestamp(day))].sort_values(['rank', 'symbol'])
        held = {p['symbol'] for p in self.book.positions()}
        equity = self.book.equity()
        for row in rows.itertuples():
            if row.symbol in held:
                continue
            price = float(self.pivots['close'].at[pd.Timestamp(day), row.symbol])
            if not np.isfinite(price) or price <= 0:
                self.refusals.append(dict(date=str(day), symbol=row.symbol, reason='MISSING_SIGNAL_CLOSE'));continue
            budget = equity*.0125
            qty = min(int(budget/(price*(.05+2.05*.0025))), int(equity*.2/price))
            self.plans.append(dict(symbol=row.symbol, signal_date=str(day), quantity=qty,
                risk_budget=budget, short_probability=float(row.short_probability), rank=int(row.rank)))

    def run(self, progress=None):
        days = [s for s in self.sessions if self.cfg.start_date <= s.session_date <= self.cfg.end_date]
        seed = max(s for s in self.calendar if s.date() < days[0].session_date)
        self.book.now = self.sessions[self.calendar.get_loc(seed)].close_at_utc
        self._plan(seed.date())
        for n, session in enumerate(days):
            day = session.session_date;offset = self.calendar.get_loc(pd.Timestamp(day))
            self.book.now = session.open_at_utc;self.book.settle(day)
            held = {p['symbol'] for p in self.book.positions()}
            needed = held | {p['symbol'] for p in self.plans}
            bars = {}
            for symbol in needed:
                try:
                    bars[symbol] = self._bar(day, symbol, completed=False)
                except (KeyError, ValueError):
                    if symbol in held:
                        raise
                    self.refusals.append(dict(date=str(day), symbol=symbol, reason='MISSING_ENTRY_PRICE'))
            self.book.marks.update({s: b['open'] for s, b in bars.items()})
            # Existing SHORTs pay borrow for the exit session too, once only.
            self.book.charge_borrow(day)
            actions = self.actions[pd.to_datetime(self.actions.ex_date).eq(pd.Timestamp(day))]
            for action in actions.to_dict('records'):
                self.book.corporate_action(action, day)
            observed_open = {s: dict(open=b['open'], high=b['open'], low=b['open']) for s,b in bars.items()}
            self.book.resolve(observed_open, opening=True)
            for key, state in self.states.items():
                lot = self.book.lots[state['parent_id']]
                if lot['remaining'] and offset >= state['due_index']:
                    self._cover(state, lot['remaining'], 'HORIZON_OPEN')
            self.update_exits()
            if self.book.equity() <= 0:
                self.insolvent = True
                for state in self.states.values():
                    lot = self.book.lots[state['parent_id']]
                    if lot['remaining']:
                        self._cover(state, lot['remaining'], 'INSOLVENCY_AT_OPEN')
                self.update_exits()
            if not self.insolvent:
                for plan in self.plans:
                    if plan['symbol'] in bars:
                        self._open(plan, session, offset, bars[plan['symbol']])
            # Only stop orders can trigger inside the daily bar; no TP/trailing
            # or same-bar observation is used to authorize an opening entry.
            open_equity = self.book.equity()
            stress = open_equity
            # The completed range is observed only after all opening decisions.
            # Unknown future ranges must never veto an otherwise known opening.
            for position in self.book.positions():
                bars[position['symbol']] = self._bar(day, position['symbol'], completed=True)
            for state in self.states.values():
                lot = self.book.lots[state['parent_id']]
                if lot['remaining']:
                    bar = bars[state['symbol']]
                    stress -= lot['remaining']*(min(bar['high'], state['stop'])-bar['open'])
            self.book.now = session.close_at_utc
            self.book.resolve(bars, opening=False)
            self.update_exits()
            self.book.marks.update({s: b['close'] for s, b in bars.items()})
            equity = self.book.equity();self.peak = max(self.peak, equity)
            self.curve.append(dict(date=str(day), equity=equity, gross=self.book.gross(),
                cash=self.book.cash, borrow=self.book.borrow_fees, fees=self.book.fees,
                close_drawdown_pct=100*(equity/self.peak-1), simultaneous_adverse_stress_equity=stress))
            self._ledger_check()
            if equity <= 0:self.insolvent = True
            self._plan(day)
            if progress:
                progress(n+1, len(days), str(day))
        return self

    def _ledger_check(self):
        realized = sum(t['pnl'] for t in self.book.trades)
        unrealized = sum(l['remaining']*(l['entry']-self.book.marks[l['symbol']])
            - l['entry_fee']*l['remaining']/l['quantity'] - l['borrow_remaining'] + l.get('dividends_remaining',0)
            for l in self.book.lots.values() if l['remaining'])
        if abs(self.cfg.initial_equity + realized + unrealized - self.book.equity()) > 1e-6:
            raise ValueError('SHORT ledger cash/PnL/dividend/borrow reconciliation failed')


def main():
    plan = read(ROOT/'protocol.json')
    if not (ROOT/'signals.parquet').exists():
        raise ValueError('Annual SHORT training/selection not finished')
    source = Path('artifacts/research/us_q051_sl_pause/20261116-30sessions-pause100-v1/inputs')
    pivots = {k: pd.read_parquet(source/(k+'.parquet')) for k in ['open','high','low','close','volume']}
    sectors = pd.read_parquet(source/'sectors.parquet').set_index('symbol').sector.to_dict()
    actions = pd.read_parquet(source/'actions.parquet')
    signals = pd.read_parquet(ROOT/'signals.parquet')
    from common.market_calendar import get_market_calendar
    from common.config_loader import replay_market_registry
    from scripts.research.us_q051_feature_groups_20261116 import shared, no_http
    with replay_market_registry(shared.restore_registry(shared.ROOT)), patch.object(requests.Session, 'request', no_http):
        sessions = [s for s in get_market_calendar('US_EQ', allow_us_weekday_fallback=False).sessions(
            date(2020,12,20), date(2026,10,1)) if s.is_open]
        cfg = config()
        atomic_json(ROOT/'replay-protocol.json', dict(source_sha256=digest(Path(__file__)),
            daily_prices={str(source/(k+'.parquet')):digest(source/(k+'.parquet')) for k in pivots},
            accounting='Existing isolated ShortReplayBroker, independent coordinator',
            drawdown='Daily close only; synchronous adverse stress NAV is a diagnostic, not exact intradayDD or mathematical bound',
            borrow_annual=.03, availability='Assumed, not historical locates',
            max_short_positions=20, no_long=True, no_anti_SL=True, corpus='Same frozen1790 universe and prices as B reference'))
        def progress(done, total, day):
            atomic_json(ROOT/'replay-progress.json', dict(status='REPLAYING', completed=done, total=total, day=day))
        logging.getLogger('risk_management.risk_checker').setLevel(logging.WARNING)
        replay = DailyShortReplay(pivots, sectors, actions, signals, sessions, cfg, borrow=.03).run(progress)
    curve = pd.DataFrame(replay.curve);trades = pd.DataFrame(replay.book.trades)
    curve.to_csv(ROOT/'equity-daily.csv', index=False);trades.to_csv(ROOT/'trades.csv', index=False)
    pd.DataFrame(replay.refusals).to_csv(ROOT/'refusals.csv', index=False)
    pd.DataFrame(replay.entries).to_csv(ROOT/'entries.csv', index=False)
    pd.DataFrame(replay.book.events).to_parquet(ROOT/'events.parquet', index=False)
    result = dict(status='COMPLETED_EXPLORATORY_DAILY_SHORT', final_equity=float(curve.equity.iloc[-1]),
        return_pct=float(100*(curve.equity.iloc[-1]/4000-1)), daily_close_max_drawdown_pct=float(curve.close_drawdown_pct.min()),
        closed_trades=len(trades), win_pct=float(100*trades.pnl.gt(0).mean()) if len(trades) else None,
        fees=replay.book.fees, assumed_borrow_cost=replay.book.borrow_fees,
        average_gross_capital=float(curve.gross.mean()), average_gross_equity_pct=float(100*(curve.gross/curve.equity).mean()),
        open_positions=len(replay.book.positions()), insolvent=replay.insolvent,
        no_production_changes=True, SQL_writes=0, provider_calls=0, broker_orders=0,
        historical_borrow_not_certified=True, intraday_drawdown_not_available=True)
    atomic_json(ROOT/'report.json', result)
    atomic_json(ROOT/'replay-progress.json', dict(status='COMPLETED', result=result))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
