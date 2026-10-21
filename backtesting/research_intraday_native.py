"""Research-only intraday adapter to native accounting and risk primitives.

No DB, provider, broker, orders or production defaults. Five-minute events are
NOT inserted as fake trading days. This is a component-parity adapter, not a
certificate of complete live/PAPER parity or of historical borrow availability.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass, replace
import hashlib
import json
import math

import pandas as pd

from backtesting.simulator import BacktestConfig, BacktestDiagnostics, BacktestEngine, _RunState
from backtesting.microstructure import MicrostructureConfig, should_skip_entry_for_gap, resolve_intrabar_exit
from backtesting.trading_constraints import TradingConstraintConfig
from common.trading_costs import DEFAULT_COST_MODEL
from core.direction import compute_initial_stop_price, compute_take_profit_price, compute_trailing_stop_price
from risk_management.config import RiskConfig
from risk_management.constraints import ConstraintChecker, PortfolioState
from risk_management.liquidity import alpaca_borrow_status, BorrowStatus
from risk_management.models import PriceInfo
from risk_management.position_sizer import PositionSizer


def utc(value):
    t = pd.Timestamp(value)
    if pd.isna(t) or t.tzinfo is None:
        raise ValueError('An explicit timezone is required')
    return t.tz_convert('UTC')


def fingerprint(value):
    if is_dataclass(value):
        value = asdict(value)
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, allow_nan=False).encode()).hexdigest()


def evidence_reasons(symbol, side, decision_time, evidence, *, state_hash=None):
    """Fail closed. Receipt presence alone is not certification of its producer.

    A historical EOD quote or a present-day borrow snapshot cannot stand in for
    a contemporaneous decision. Unknown coverage is NOT an empty-event proof.
    The exporter must seal original receipts before this adapter is promoted.
    """
    now = utc(decision_time)
    reasons = []
    for kind in ['quote', 'risk', 'corporate_actions'] + (['borrow'] if side == 'sell' else []):
        r = evidence.get(kind)
        if not r:
            reasons.append('MISSING_'+kind.upper())
            continue
        if r.get('symbol') != symbol or not r.get('source_sha256') or len(str(r['source_sha256'])) != 64:
            reasons.append('INVALID_'+kind.upper()+'_PROVENANCE')
            continue
        try:
            available, valid_until = utc(r['available_at']), utc(r['valid_until'])
            if available > now or valid_until < now:
                reasons.append('NON_CAUSAL_OR_STALE_'+kind.upper())
                continue
        except (KeyError, ValueError, TypeError):
            reasons.append('INVALID_'+kind.upper()+'_TIME')
            continue
        if kind == 'quote':
            try:
                stamp = utc(r['source_timestamp'])
                bid, ask = float(r['bid']), float(r['ask'])
                if not (0 <= (now-stamp).total_seconds() <= 300 and stamp <= available
                        and r.get('feed') == 'sip' and math.isfinite(bid) and math.isfinite(ask)
                        and 0 < bid <= ask and float(r['bid_size']) > 0 and float(r['ask_size']) > 0):
                    raise ValueError('Invalid quote')
            except (KeyError, ValueError, TypeError):
                reasons.append('INVALID_QUOTE')
        elif kind == 'risk':
            if (r.get('side') != side or r.get('producer') != 'PortfolioBuilder'
                    or not r.get('config_hash') or state_hash is not None and r.get('state_hash') != state_hash
                    or r.get('regime_qualified') is not True or r.get('sector_pit') is not True
                    or r.get('correlation_qualified') is not True):
                reasons.append('UNQUALIFIED_RISK_CONTEXT')
        elif kind == 'corporate_actions':
            if r.get('coverage_complete') is not True:
                reasons.append('UNKNOWN_CORPORATE_ACTION_COVERAGE')
        else:
            status = alpaca_borrow_status(r)
            if status == BorrowStatus.NOT_SHORTABLE:
                reasons.append('NOT_SHORTABLE')
            elif status == BorrowStatus.HARD_TO_BORROW and r.get('locate_confirmed') is not True:
                reasons.append('MISSING_CONFIRMED_LOCATE')
            rate = r.get('annual_fee')
            if (r.get('marginable') is not True or not isinstance(rate, (int, float))
                    or not math.isfinite(rate) or rate < 0 or r.get('holding_cost_coverage') is not True):
                reasons.append('UNQUALIFIED_BORROW_COST_OR_MARGIN')
    return reasons


class IntradayNativeLedger:
    """Book time-bounded fills through the native BacktestEngine.

    Native sizing/constraints/costs/entry/exit/cash, daily settlements/borrow
    duration and trade trackers are reused. Intraday events and protections are
    explicit adapter policies, not the native daily watcher. No reinforcement.
    """

    def __init__(self, calendar, *, risk: RiskConfig, costs=DEFAULT_COST_MODEL,
                 strict=True, sl=.05, trailing=.15, tp=None, max_gap=.03):
        if type(strict) is not bool or not 0 < sl < 1:
            raise ValueError('Explicit strict boolean and valid stop required')
        if trailing is not None and not 0 < trailing < 1 or tp is not None and not 0 < tp < 1:
            raise ValueError('Invalid trailing/TP')
        if costs.per_leg_cost_bps < 0 or costs.borrow_fee_annual < 0:
            raise ValueError('Invalid costs')
        self.calendar = calendar.set_index('date').copy()
        self.days = pd.DatetimeIndex(self.calendar.index)
        if not self.days.is_unique or not self.days.is_monotonic_increasing:
            raise ValueError('Invalid daily calendar')
        self.risk, self.strict, self.sl, self.trailing, self.tp, self.max_gap = risk, strict, sl, trailing, tp, max_gap
        cfg = BacktestConfig(start_date=self.days[0].date(), end_date=self.days[-1].date(),
            initial_equity=risk.account_equity, risk_config=risk, trading_cost_model=costs,
            use_canonical_costs=True, execution_replay_mode='execution_replay',
            exit_lifecycle_replay_mode='exit_lifecycle_replay',
            require_replay_quantities=True, reject_constrained_replay_entries=True,
            min_score_threshold=0., trading_constraints=TradingConstraintConfig(account_type='margin'),
            concentration_max_trades_per_symbol=risk.concentration_max_trades_per_symbol,
            concentration_window_calendar_days=risk.concentration_window_calendar_days,
            concentration_max_consecutive_losses=risk.concentration_max_consecutive_losses,
            concentration_blacklist_duration_days=risk.concentration_blacklist_duration_days,
            # Native day-open gap rule must not mistake a5m signal for yesterday.
            microstructure=MicrostructureConfig(max_entry_gap_pct=0., initial_stop_pct=sl))
        self.engine = BacktestEngine(cfg)
        self.state = _RunState(settled_cash=risk.account_equity, peak_equity=risk.account_equity)
        self.diagnostics = BacktestDiagnostics()
        self.now = self.day = None
        self.phase = 'IDLE'
        self.prices = {}
        self.audit = []
        self.claims = {}
        self.actions = {}
        self.dividends_accrued = 0.
        self.interest = 0.
        self.last_finished = None
        self.last_bar_end = None
        self.failed = False
        self.expiry_symbols = set()
        self.spreads = {}
        self.borrow_rates = {}

    def _healthy(self):
        if self.failed:
            raise ValueError('Native mutation failed; restart from a validated checkpoint')

    def _account_state(self):
        return dict(cash=self.state.settled_cash, unsettled=self.state.unsettled_cash,
            positions={s: dict(side=p.side, quantity=p.quantity, entry=p.entry_price)
                for s, p in sorted(self.state.positions.items())}, claims=self.claims)

    def _frame(self):
        return pd.DataFrame([self.prices], index=pd.DatetimeIndex([self.day]))

    def equity(self):
        if self.day is None:
            return self.state.settled_cash+self.state.unsettled_cash+sum(c['amount'] for c in self.claims.values())
        native = self.engine._mark_to_market(self.state.positions, self._frame(), self.day)
        return self.state.settled_cash+self.state.unsettled_cash+native+sum(c['amount'] for c in self.claims.values())

    def gross(self):
        return self.engine._compute_gross_notional(self.state.positions, self._frame(), self.day)

    def buying_power(self):
        return self.engine._resolve_available_entry_budget(constraints=self.engine.config.trading_constraints,
            settled_cash=self.state.settled_cash, current_equity=self.equity(), current_gross_notional=self.gross())

    def begin_bar(self, timestamp, opening_marks, *, expiry_symbols=()):
        self._healthy()
        now = utc(timestamp)
        day = pd.Timestamp(now.tz_convert('America/New_York').date())
        if self.now is not None and now <= self.now or self.day is not None and day != self.day and self.phase != 'FINISHED':
            raise ValueError('Out-of-order bar or unfinished daily session')
        if day not in self.calendar.index:
            raise ValueError('Not a trading session')
        op, cl = self.calendar.loc[day, ['market_open', 'market_close']]
        if not op <= now < cl or (now-op).total_seconds() % 300:
            raise ValueError('Outside regular5m calendar')
        marks = {s: float(p) for s, p in opening_marks.items()}
        if not set(self.state.positions).issubset(marks) or any(not math.isfinite(p) or p <= 0 for p in marks.values()):
            raise ValueError('Missing/invalid held opening mark')
        if self.day != day:
            if now != op:
                raise ValueError('First event of a session must be its real open')
            if self.last_finished is not None and self.days.get_loc(day) != self.days.get_loc(self.last_finished)+1:
                raise ValueError('Skipped daily session')
            self.engine._apply_settlements(self.state, self.days.get_loc(day))
            for key, claim in list(self.claims.items()):
                if pd.Timestamp(claim['payable_date']) <= day:
                    self.state.settled_cash += claim['amount']
                    del self.claims[key]
        elif self.last_bar_end != now:
            raise ValueError('Skipped intraday bar')
        self.now, self.day, self.prices, self.phase = now, day, marks, 'OPEN'
        self.expiry_symbols = set(expiry_symbols)
        self.spreads = {}

    def enter(self, symbol, side, price_info: PriceInfo, *, sector, signal_time,
              quantity_fraction=.5, evidence=None, selection_rank=1):
        self._healthy()
        if self.phase != 'OPEN' or side not in ('buy', 'sell') or not 0 < quantity_fraction <= 1:
            raise ValueError('Invalid entry phase/side/fraction')
        signal_time = utc(signal_time)
        if signal_time != self.now or symbol not in self.prices:
            # A5m close and the next open share a boundary; caller proves the
            # signal uses the COMPLETED preceding bar, not this bar's values.
            raise ValueError('A contiguous completed-bar decision is required')
        self.resolve_open()  # Known stops/expiry release capital before orders.
        reasons = []
        if symbol in self.expiry_symbols:
            reasons.append('EXPIRED_CAMPAIGN')
        if self.strict:
            reasons = evidence_reasons(symbol, side, signal_time, evidence or {},
                state_hash=fingerprint(self._account_state()))
            if evidence and evidence.get('risk', {}).get('config_hash') != fingerprint(self.risk):
                reasons.append('RISK_CONFIG_MISMATCH')
            if side == 'sell' and (evidence or {}).get('borrow', {}).get('fee_basis') != 'ANNUAL_252_ENTRY_NOTIONAL':
                # The native engine uses a constant annual rate on entry
                # notional/session count. Never pass calendar360/variable fees
                # off as this convention. Such schedules need another adapter.
                reasons.append('UNSUPPORTED_HISTORICAL_BORROW_FEE_BASIS')
        if symbol in self.state.positions:
            reasons.append('DUPLICATE_HELD_SYMBOL')
        if not sector or sector == 'Unknown':
            reasons.append('MISSING_SECTOR')
        if side == 'sell' and (not self.risk.short_selling_enabled or self.equity() < 2000):
            reasons.append('SHORT_POLICY_OR_MINIMUM_EQUITY')
        if (price_info.symbol != symbol or price_info.price_asof_date != self.day.date()
                or price_info.atr_asof_date is None or price_info.atr_asof_date >= self.day.date()
                or price_info.atr_20 is None or not math.isfinite(price_info.atr_20) or price_info.atr_20 <= 0
                or not math.isfinite(price_info.last_close) or price_info.last_close <= 0):
            reasons.append('UNQUALIFIED_PRICE_OR_PRIOR_SESSION_ATR')
        price = self.prices[symbol]
        if should_skip_entry_for_gap(price_info.last_close, price, max_gap_pct=self.max_gap):
            reasons.append('SIGNAL_TO_FILL_GAP')
        if reasons:
            self.audit.append(dict(time=self.now, symbol=symbol, side=side, status='BLOCKED', reasons=reasons))
            return False
        eq = self.equity()
        cfg = self.risk.with_overrides(account_equity=eq, fixed_stop_pct=self.sl)
        sized = PositionSizer(cfg).compute(price_info).proposed_shares
        # Freeze full target before half sizing, as in the parent experiment.
        fee = self.engine._cost_model.per_leg_cost_pct
        if self.strict:
            quote = evidence['quote']
            midpoint = (quote['bid']+quote['ask'])/2
            spread = 10000*(quote['ask']-quote['bid'])/midpoint
            if spread > 300:
                self.audit.append(dict(time=self.now, symbol=symbol, side=side,
                    status='BLOCKED', reasons=['INVALID_OR_EXTREME_SPREAD']))
                return False
            self.spreads[symbol] = spread
            fee = (self.engine._cost_model.commission_bps+self.engine._cost_model.slippage_bps+spread/2)/10000
        full = min(math.floor(sized), math.floor(eq*cfg.max_position_weight/price),
            math.floor(self.buying_power()/(price*(1+fee))))
        quantity = math.floor(full*quantity_fraction)
        ps = PortfolioState()
        for s, p in self.state.positions.items():
            ps.add_position(notional=p.quantity*self.prices[s], sector=p.sector,
                side=p.side, symbol=s)
        quantity, constraint = ConstraintChecker(cfg).check(symbol, sector, quantity, price, ps,
            side=side, adv_usd=price_info.adv_usd, selection_rank=selection_rank)
        if quantity <= 0:
            self.audit.append(dict(time=self.now, symbol=symbol, side=side,
                status='BLOCKED', reasons=[constraint], full_quantity=full))
            return False
        if self.strict:
            approval = evidence['risk']
            if int(approval.get('approved_shares', -1)) != quantity:
                self.audit.append(dict(time=self.now, symbol=symbol, side=side,
                    status='BLOCKED', reasons=['RISK_QUANTITY_MISMATCH']))
                return False
        row = pd.Series(dict(symbol=symbol, side=side, sector=sector, signal_date=self.day,
            filled_qty=quantity, target_weight=quantity*price/eq, score=1.,
            stop_price_initial=compute_initial_stop_price(side, price, stop_pct=self.sl)))
        frame = self._frame()
        self.failed = True
        self.engine._try_open_entries(state=self.state, candidate_rows=[row], open_df=frame,
            high_df=frame, low_df=frame, close=frame, trade_day=self.day,
            day_idx=self.days.get_loc(self.day), trading_days=self.days, adv_usd_df=None,
            sector_map={symbol: sector}, current_equity=eq, drawdown_allocation_scale=1., diagnostics=self.diagnostics,
            spread_df=pd.DataFrame([self.spreads], index=[self.day]) if self.spreads else None)
        self.failed = False
        opened = symbol in self.state.positions
        if opened:
            p = self.state.positions[symbol]
            p.trailing_stop_pct = self.trailing
            if self.strict and side == 'sell':
                self.borrow_rates[symbol] = float(evidence['borrow']['annual_fee'])
        self.audit.append(dict(time=self.now, symbol=symbol, side=side,
            status='NATIVE_OPENED' if opened else 'NATIVE_REJECTED', quantity=quantity,
            mode='QUALIFIED_COMPONENT_REPLAY' if self.strict else 'RESEARCH_ASSUMPTIONS',
            full_quantity=full, constraint=constraint))
        return opened

    def known_stop(self, symbol):
        p = self.state.positions[symbol]
        initial = p.initial_stop_price
        if self.trailing is None:
            return initial
        trailing = compute_trailing_stop_price(p.side, p.trough_low if p.side == 'sell' else p.peak_high, self.trailing)
        return min(initial, trailing) if p.side == 'sell' else max(initial, trailing)

    def close(self, symbol, price, reason, *, phase='OPEN'):
        self._healthy()
        if self.phase not in ('OPEN', 'INTRABAR') or phase not in ('OPEN', 'INTRABAR'):
            raise ValueError('Invalid close phase')
        if self.phase == 'INTRABAR' and phase == 'OPEN':
            raise ValueError('Intrabar proceeds cannot fund an earlier opening order')
        if symbol not in self.state.positions or not math.isfinite(price) or price <= 0:
            raise ValueError('Invalid closed position/price')
        p = self.state.positions[symbol]
        p.explicit_exit_date, p.explicit_exit_price = self.day, float(price)
        p.explicit_exit_reason, p.explicit_exit_intent_role = reason, reason
        p.explicit_oco_sibling_canceled = True
        equity = self.equity()
        others = {s: pos for s, pos in self.state.positions.items() if s != symbol}
        self.state.positions = {symbol: p}
        frame = self._frame()
        self.failed = True
        saved_cost_model = self.engine._cost_model
        if symbol in self.borrow_rates:
            self.engine._cost_model = replace(saved_cost_model, borrow_fee_annual=self.borrow_rates[symbol])
        try:
            self.engine._try_close_positions(state=self.state, close=frame, high=frame, low=frame,
                trade_day=self.day, day_idx=self.days.get_loc(self.day), trading_days=self.days,
                adv_usd_df=None, rng=None, diagnostics=self.diagnostics, current_equity=equity)
            if symbol in self.state.positions:
                raise ValueError('Native engine refused exit')
            trade = self.state.closed_trades[-1]
            # Both trackers are mutated by native entry/exit, never twice here.
        finally:
            self.state.positions.update(others)
            self.engine._cost_model = saved_cost_model
        self.failed = False
        self.borrow_rates.pop(symbol, None)
        self.phase = phase
        self.audit.append(dict(time=self.now if phase == 'OPEN' else self.now+pd.Timedelta(minutes=5),
            symbol=symbol, status='NATIVE_CLOSED', phase=phase, reason=reason, price=price,
            cost_evidence='HYPOTHETICAL_CANONICAL_EXIT_COSTS', full_parity=False))
        return trade

    def observe_bar(self, bars, *, expiry_symbols=()):
        """Open guards first, then conservative intrabar exits, then extrema.

        Caller sends orders between begin_bar and observe_bar. A native opening
        gap/expiry pass may be invoked BEFORE those entries via resolve_open.
        """
        self._healthy()
        if self.phase != 'OPEN' or set(self.state.positions)-set(bars):
            raise ValueError('Missing bars or wrong observed phase')
        for s, a in bars.items():
            if len(a) != 4 or not all(math.isfinite(x) and x > 0 for x in a) or a[1] < max(a) or a[2] > min(a):
                raise ValueError('Invalid OHLC')
            if s in self.prices and a[0] != self.prices[s]:
                raise ValueError('Opening price changed after sizing')
        self.resolve_open(expiry_symbols=self.expiry_symbols | set(expiry_symbols))
        for s, p in list(self.state.positions.items()):
            op, hi, lo, close = bars[s]
            stop = self.known_stop(s)
            target = compute_take_profit_price(p.side, p.entry_price, self.tp) if self.tp is not None else (0. if p.side == 'sell' else float('inf'))
            resolution = resolve_intrabar_exit(day_high=hi, day_low=lo, take_profit_price=target,
                trailing_stop_price=float('inf') if p.side == 'sell' else float('-inf'),
                initial_stop_price=stop, priority='conservative', side=p.side)
            if resolution.triggered:
                self.close(s, float(resolution.exit_price), resolution.exit_reason, phase='INTRABAR')
            else:
                p.peak_high, p.trough_low = max(p.peak_high, hi), min(p.trough_low, lo)
        self.prices = {s: float(a[3]) for s, a in bars.items()}
        self.phase = 'INTRABAR'
        self.last_bar_end = self.now+pd.Timedelta(minutes=5)
        return self.equity()

    def resolve_open(self, *, expiry_symbols=None):
        self._healthy()
        expiry_symbols = self.expiry_symbols if expiry_symbols is None else expiry_symbols
        if self.phase != 'OPEN':
            raise ValueError('Opening guards already passed')
        for s, p in list(self.state.positions.items()):
            op, stop = self.prices[s], self.known_stop(s)
            if (op >= stop if p.side == 'sell' else op <= stop):
                self.close(s, op, 'GAP_STOP')
            elif s in expiry_symbols:
                self.close(s, op, 'EXPIRY')
            elif self.tp is not None:
                target = compute_take_profit_price(p.side, p.entry_price, self.tp)
                if (op <= target if p.side == 'sell' else op >= target):
                    self.close(s, target, 'TP_GAP_LIMIT')

    def finish_day(self):
        self._healthy()
        if self.phase != 'INTRABAR' or self.last_bar_end != self.calendar.at[self.day, 'market_close']:
            raise ValueError('Daily close not fully observed')
        charge = self.engine._accrue_margin_interest(self.state,
            annual_rate=self.engine.config.margin_interest_rate_annual)
        self.interest += charge
        value = self.equity()
        self.state.equity_points.append(value)
        self.state.peak_equity = max(self.state.peak_equity, value)
        self.last_finished, self.phase = self.day, 'FINISHED'
        return value

    def corporate_action(self, event):
        """Apply qualified effective events before the first bar's trading.

        Cash dividends accrue an entitlement/liability on ex date and settle
        only on payable date. No fake cash-in-lieu or identity-merger handling.
        """
        self._healthy()
        if self.phase != 'OPEN' or self.now != self.calendar.at[self.day, 'market_open']:
            raise ValueError('Corporate action must precede session trading')
        key = event['event_id']
        stamp = fingerprint(event)
        if key in self.actions:
            if self.actions[key] != stamp:
                raise ValueError('Conflicting corporate action identity')
            return
        if pd.Timestamp(event['ex_date']) != self.day or event.get('currency') != 'USD' or not event.get('source_sha256'):
            raise ValueError('Unqualified corporate action')
        s = event['symbol']
        p = self.state.positions.get(s)
        if p is not None and p.entry_date >= self.day:
            raise ValueError('Ex-date buyer is not a prior holder')
        if p is not None:
            if event['kind'] == 'split':
                ratio = float(event['ratio'])
                if not math.isfinite(ratio) or ratio <= 0 or not math.isclose(p.quantity*ratio, round(p.quantity*ratio)):
                    raise ValueError('Unsupported split/fractional cash-in-lieu')
                updates = dict(quantity=p.quantity*ratio, entry_price=p.entry_price/ratio,
                    peak_high=p.peak_high/ratio, trough_low=p.trough_low/ratio)
                for field in ['initial_stop_price', 'risk_per_share', 'replay_take_profit_price', 'replay_initial_stop_price']:
                    value = getattr(p, field)
                    updates[field] = value/ratio if value is not None else None
                self.state.positions[s] = replace(p, **updates)
            elif event['kind'] == 'cash_dividend':
                amount = float(event['amount_per_share'])
                payable = pd.Timestamp(event['payable_date'])
                if not math.isfinite(amount) or amount < 0 or pd.isna(payable) or payable < self.day:
                    raise ValueError('Invalid dividend terms')
                cash = p.quantity*amount*(-1 if p.side == 'sell' else 1)
                self.dividends_accrued += cash
                if payable == self.day:
                    self.state.settled_cash += cash
                else:
                    self.claims[key] = dict(amount=cash, payable_date=str(payable.date()))
            else:
                raise ValueError('Unsupported corporate action; do not continue an identity discontinuity')
        self.actions[key] = stamp

    def reconcile(self):
        self._healthy()
        if self.state.positions:
            raise ValueError('Positions still open')
        expected = self.risk.account_equity+sum(t['pnl'] for t in self.state.closed_trades)+self.dividends_accrued-self.interest
        error = self.equity()-expected
        if abs(error) > 1e-6:
            raise AssertionError(f'Native cash conservation failed: {error}')
        return error
