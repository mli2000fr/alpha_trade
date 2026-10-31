"""LONG campaign replay using the SAME coordinator and native risk reapproval.

Shared cash, settled-cash/margin capacity, costs and native breaker/constraints.
Regular five-minute OHLC imply explicit execution assumptions: no claim of
historical quote/fill parity, guaranteed stops, borrow, or current-sector PIT.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import math

import pandas as pd

from common.market_calendar import get_market_calendar
from common.winner_pyramiding import aware, resolve_bar_exit, regular_bounds, WinnerPyramidingConfig
from common.winner_risk_state import CampaignRiskState
from execution_engine.models import ExecutionTarget
from execution_engine.winner_plans import stage_targets
from execution_engine.winner_risk import reapprove_campaign
from execution_engine.winner_runtime import WinnerCampaignRuntime
from risk_management.config import load_risk_config
from risk_management.live_pipeline_guards import evaluate_vol_target


class MemoryCampaignStore:
    """Run-local CAS store. No production DB write, even on a historical replay."""
    def __init__(self):
        self.records = {}

    def create(self, state, account, broker_mode, risk_run_id):
        if state['campaign_id'] in self.records or any(r['state']['symbol'] == state['symbol']
                for r in self.rows()):
            return False
        state.update(account_id=account, broker_mode=broker_mode, risk_run_id=risk_run_id)
        self.records[state['campaign_id']] = dict(state=deepcopy(state), version=0)
        return True

    def rows(self, *args, active_only=True):
        return [deepcopy(r) for r in self.records.values() if not active_only
            or r['state']['status'] not in ('CLOSED', 'EXPIRED', 'CANCELED')]

    def get(self, key):
        return deepcopy(self.records[key])

    def save(self, state, version):
        old = self.records[state['campaign_id']]
        if old['version'] != version:
            raise RuntimeError('Replay CAS version conflict')
        for k in ('policy', 'account_policy', 'entry_policy', 'risk_budget', 'full_quantity', 'initial_quantity', 'account_id', 'broker_mode'):
            if old['state'].get(k) != state.get(k):
                raise ValueError('Frozen replay campaign field changed')
        if old['state']['due_open'] is not None and state['due_open'] != old['state']['due_open']:
            raise ValueError('Replay reinforcement cannot reset horizon')
        self.records[state['campaign_id']] = dict(state=deepcopy(state), version=version+1)
        return version+1


class ReplayBroker:
    def __init__(self, engine, *, fee):
        self.engine, self.fee = engine, fee
        self.cash = float(engine.config.initial_equity)
        self.unsettled, self.orders, self.intents, self.lots, self.claims = [], {}, {}, {}, []
        self.trades, self.events, self.marks = [], [], {}
        self.now = None
        self.fees = self.interest = self.dividends = 0.
        self.constraints = engine.config.trading_constraints

    def equity(self):
        return (self.cash+sum(v for _, v in self.unsettled)+sum(c['amount'] for c in self.claims)
            +sum(l['remaining']*self.marks[l['symbol']] for l in self.lots.values()))

    def gross(self):
        return sum(l['remaining']*self.marks[l['symbol']] for l in self.lots.values())

    def pending_entries(self, exclude=None):
        return [dict(symbol=r['symbol'], side='buy',
            notional=float(r['qty'])*float(r['limit_price'])) for k, r in self.orders.items()
            if k != exclude and r.get('side') == 'buy' and r['status'] == 'new'
            and r.get('time_in_force') == 'day' and r.get('limit_price') is not None]

    def capacity(self, exclude=None):
        available = self.engine._resolve_available_entry_budget(constraints=self.constraints,
            settled_cash=self.cash, current_equity=self.equity(), current_gross_notional=self.gross())
        return max(available-sum(p['notional']*(1+self.fee) for p in self.pending_entries(exclude)), 0.)

    def settle(self, day):
        self.cash += sum(v for due, v in self.unsettled if due <= day)
        self.unsettled = [(due, v) for due, v in self.unsettled if due > day]
        self.cash += sum(c['amount'] for c in self.claims if c['payable_date'] <= day)
        self.claims = [c for c in self.claims if c['payable_date'] > day]

    def corporate_action(self, action, day):
        held = [l for l in self.lots.values() if l['symbol'] == action['symbol'] and l['remaining']]
        if not held:
            return
        if action['ca_type'] not in ('cash_dividend', 'special_dividend'):
            raise ValueError('Corporate action requires qualified share lifecycle before replay: '+str(action))
        from datetime import date
        payable = action.get('payable_date')
        amount = float(action.get('amount_per_share') or 0)
        if (not payable or str(payable) == 'NaT' or not math.isfinite(amount) or amount <= 0
                or action.get('currency') != 'USD' or date.fromisoformat(str(payable)[:10]) < day):
            raise ValueError('Cash dividend currency/amount/payment date unqualified')
        for lot in held:
            value = lot['remaining']*amount
            self.claims.append(dict(amount=value, payable_date=date.fromisoformat(str(payable)[:10])))
            lot['dividends_remaining'] = lot.get('dividends_remaining', 0.)+value
            self.dividends += value
        self.settle(day)

    def positions(self):
        grouped = {}
        for lot in self.lots.values():
            grouped[lot['symbol']] = grouped.get(lot['symbol'], 0)+lot['remaining']
        return [dict(symbol=s, side='long', qty=q, quantity=q, mark=self.marks[s]) for s, q in grouped.items() if q]

    def get(self, key):
        return deepcopy(self.orders[key])

    def lookup(self, intent):
        return self.get(intent.intent_id) if intent.intent_id in self.orders else None

    def persist(self, *args):
        pass

    def actual_fill_time(self, raw, state):
        return aware(raw['filled_at'])

    def submit(self, state, intent):
        if intent.intent_id in self.orders:
            raise ValueError('Duplicate replay broker POST')
        self.intents[intent.intent_id] = intent
        raw = dict(id=intent.intent_id, type=intent.order_type, status='new', filled_qty='0',
            filled_avg_price=None, client_order_id=intent.submission_key, qty=str(intent.qty),
            side=intent.side, symbol=intent.symbol, time_in_force=intent.time_in_force,
            stop_price=intent.stop_price, limit_price=intent.limit_price)
        self.orders[intent.intent_id] = raw
        price = self.marks[intent.symbol]
        if intent.side == 'buy':
            self.fill_buy(intent, raw, price, state['campaign_id'])
            if raw['status'] == 'new' and intent.time_in_force != 'day':
                raw['status'] = 'canceled'  # IOC: no deferred or retroactive fill.
        elif intent.intent_role == 'exit':
            if intent.time_in_force == 'opg':
                raw['queued_moo'] = True
            else:
                reason=next((o.get('exit_reason') for o in state['operations'] if o['key']==intent.intent_id),None)
                self.close(intent.symbol, intent.qty, price, intent.intent_id, reason or 'HORIZON_LATE_MARKET')
        elif intent.order_type != 'stop':
            raise ValueError('Unsupported replay order')
        return SimpleNamespace(broker_order_id=intent.intent_id)

    def fill_buy(self, intent, raw, price, campaign_id):
        if ((intent.limit_price is not None and price > intent.limit_price+1e-8)
                or intent.qty*price*(1+self.fee) > self.capacity(exclude=intent.intent_id)+1e-6):
            return
        self.cash -= intent.qty*price*(1+self.fee)
        self.fees += intent.qty*price*self.fee
        self.lots[intent.intent_id] = dict(symbol=intent.symbol, quantity=intent.qty,
            remaining=intent.qty, entry=price, entry_time=self.now, entry_fee=intent.qty*price*self.fee,
            campaign_id=campaign_id)
        self.events.append(dict(time=self.now, symbol=intent.symbol, event='BUY_FILL',
            quantity=intent.qty, price=price, costs=intent.qty*price*self.fee))
        self.filled(raw, intent.qty, price)

    def expire_day_entries(self):
        for raw in self.orders.values():
            if raw.get('side') == 'buy' and raw.get('time_in_force') == 'day' and raw['status'] == 'new':
                raw['status'] = 'expired'

    def filled(self, raw, qty, price):
        raw.update(status='filled', filled_qty=str(qty), filled_avg_price=str(price), filled_at=self.now.isoformat())

    def protect(self, state, lot, parent, *, tp_intent, stop_intent):
        for intent in (stop_intent, tp_intent):
            if intent:
                self.intents[intent.intent_id] = intent
                self.orders[intent.intent_id] = dict(id=intent.intent_id, status='new', type=intent.order_type,
                    side='sell', filled_qty='0', qty=str(intent.qty), stop_price=intent.stop_price,
                    limit_price=intent.limit_price, parent=parent.intent_id,
                    peer=tp_intent.intent_id if intent == stop_intent and tp_intent else stop_intent.intent_id)
        return (SimpleNamespace(broker_order_id=tp_intent.intent_id) if tp_intent else None,
            SimpleNamespace(broker_order_id=stop_intent.intent_id))

    def tighten(self, state, lot, intent):
        raw = self.orders[lot['stop_order_id']]
        if raw['status'] != 'new' or intent.stop_price < raw['stop_price']:
            raise ValueError('Unqualified replay stop replacement')
        updated = deepcopy(raw)
        updated.update(id=intent.intent_id, stop_price=intent.stop_price)
        self.orders[intent.intent_id], self.intents[intent.intent_id] = updated, intent
        raw['status'] = 'replaced'
        if updated.get('peer') in self.orders:
            self.orders[updated['peer']]['peer'] = intent.intent_id
        if self.marks[intent.symbol] <= intent.stop_price:
            self.close(intent.symbol, intent.qty, self.marks[intent.symbol], intent.intent_id,
                'TIGHTENED_STOP_GAP', parent=updated['parent'])
        return SimpleNamespace(broker_order_id=intent.intent_id)

    def cancel(self, key):
        if self.orders[key]['status'] in ('new', 'held', 'accepted'):
            self.orders[key]['status'] = 'canceled'
        return self.get(key)

    def close(self, symbol, quantity, price, order_id, reason, *, parent=None):
        remaining = quantity
        for key, lot in self.lots.items():
            if lot['symbol'] != symbol or parent and parent != key or not lot['remaining']:
                continue
            used = min(remaining, lot['remaining'])
            fee = used*price*self.fee
            proceeds = used*price-fee
            if self.constraints.use_settled_cash_only and self.constraints.cash_settlement_days:
                cal = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
                day = self.now.astimezone(__import__('zoneinfo').ZoneInfo('America/New_York')).date()
                for _ in range(self.constraints.cash_settlement_days):
                    day = cal.next_session(day)
                self.unsettled.append((day, proceeds))
            else:
                self.cash += proceeds
            self.fees += fee
            entry_fee = lot['entry_fee']*used/lot['quantity']
            dividends = lot.get('dividends_remaining', 0.)*used/lot['remaining']
            lot['dividends_remaining'] = lot.get('dividends_remaining', 0.)-dividends
            pnl = used*(price-lot['entry'])-entry_fee-fee+dividends
            self.trades.append(dict(symbol=symbol, quantity=used, entry_date=lot['entry_time'],
                exit_date=self.now, entry_price=lot['entry'], exit_price=price,
                pnl=pnl, return_pct=pnl/(used*lot['entry']), holding_days=(self.now-lot['entry_time']).total_seconds()/86400,
                exit_reason=reason, is_day_trade=self.now.date() == lot['entry_time'].date(),
                side='buy', entry_fees=entry_fee, exit_fees=fee, dividends=dividends, campaign_id=lot['campaign_id']))
            lot['remaining'] -= used
            remaining -= used
            if not remaining:
                break
        if remaining:
            raise ValueError('Replay attempted to oversell holdings')
        raw = self.orders[order_id]
        self.filled(raw, quantity, price)
        self.events.append(dict(time=self.now, symbol=symbol, event='SELL_FILL',
            quantity=quantity, price=price, costs=quantity*price*self.fee))
        if raw.get('peer') in self.orders:
            self.orders[raw['peer']]['status'] = 'canceled'

    def resolve(self, bars, *, opening):
        # Only previously standing orders; a completed bar's high cannot move
        # its own trailing stop before its low has been tested.
        for key, raw in list(self.orders.items()):
            if raw['status'] != 'new':
                continue
            intent = self.intents[key]
            if intent.symbol not in bars:
                continue
            bar = bars[intent.symbol]
            if opening and intent.side == 'buy' and intent.time_in_force == 'day':
                # Conservative 5m replay: resting DAY limits execute only at
                # observed opens, never using a future low to invent a fill.
                self.fill_buy(intent, raw, float(bar['open']), intent.winner_campaign_id)
                continue
            if opening and raw.get('queued_moo'):
                self.close(intent.symbol, intent.qty, float(bar['open']), key, 'HORIZON_OPEN')
                continue
            if not raw.get('parent') or raw['parent'] not in self.lots:
                continue
            parent = self.lots[raw['parent']]
            if not parent['remaining']:
                continue
            # Process an OCO once, from the stop leg, adverse collision first.
            if raw['type'] != 'stop':
                continue
            peer = self.orders.get(raw.get('peer'), {})
            levels = dict(stop=float(raw['stop_price']), tp=peer.get('limit_price'))
            result = resolve_bar_exit(levels, bar)
            if result is None or (result[2] == 'OPEN') != opening:
                continue
            price, reason, _ = result
            selected_id = raw['peer'] if reason.startswith('TP') else key
            self.close(intent.symbol, parent['remaining'], price, selected_id, reason, parent=raw['parent'])


def run_winner_replay(engine, *, open_df, close, high, low, signals_df, volume=None,
        sector_map=None, intraday_source=None, research_assumptions=False, progress=None, corporate_actions=None,
        factor_context_source=None,selection_source=None):
    from backtesting.simulator import BacktestResult
    if not research_assumptions:
        raise ValueError('Winner intraday: historical quotes/sector/CA are not certified. '
            'Explicit research_assumptions=True required for the OHLC replay.')
    cfg, exec_cfg = engine.config, engine.config.exec_config
    if exec_cfg is None:
        from execution_engine.config import ExecutionConfig
        exec_cfg = ExecutionConfig()
    policy = exec_cfg.winner_pyramiding
    if not policy.enabled:
        raise ValueError('Explicit enabled campaign replay policy required')
    if cfg.trading_constraints.swing_only:
        raise ValueError('Intraday protective exits require swing_only=False; no silent same-day exit suppression')
    if cfg.use_tiered_commission:
        raise ValueError('Tiered commissions not qualified in winner replay; select canonical costs')
    if intraday_source is None:
        raise ValueError('An explicit intraday data source is required')
    if corporate_actions is None:
        raise ValueError('Explicit corporate-action inventory required (unknown is not empty)')
    selected = signals_df.loc[signals_df.selected.fillna(False).astype(bool)].copy()
    if 'side' in selected and not selected.side.fillna('buy').isin(['buy', 'long']).all():
        raise ValueError('Winner replay is LONG-only; selected SHORT rows cannot be silently dropped')
    selected['trade_date'] = pd.to_datetime(selected.trade_date).dt.date
    if selected.duplicated(['trade_date', 'symbol']).any():
        raise ValueError('Duplicate daily selected signals')
    sectors = sector_map or {}
    calendar = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    sessions = [s for s in calendar.sessions(cfg.start_date, cfg.end_date) if s.is_open]
    if not sessions:
        raise ValueError('No US replay sessions')
    fee = (cfg.cost_round_trip_bps/20000 if cfg.cost_round_trip_bps else
        engine._cost_model.per_leg_cost_pct*cfg.cost_multiplier)
    book = ReplayBroker(engine, fee=fee)
    store = MemoryCampaignStore()
    repo = SimpleNamespace(acquire_execution_lock=lambda **kw: True, release_execution_lock=lambda **kw: None)
    base_risk = cfg.risk_config or load_risk_config(equity=cfg.initial_equity)
    if base_risk.enable_factor_model and factor_context_source is None:
        raise ValueError('Winner replay requires qualified factor tapes when factor model is enabled')
    if base_risk.enforce_net_exposure or (base_risk.correlation_check_enabled and base_risk.max_long_short_correlation is not None):
        raise ValueError('Winner replay does not qualify market-neutral / cross-leg overlays')
    # No fake calendar history: the initial equity is an explicit replay deposit.
    from backtesting.regime_trailing import compute_regime
    spy_regimes = compute_regime(close['SPY']).dropna() if 'SPY' in close else pd.Series(dtype=object)
    regimes = {pd.Timestamp(k).date(): str(v) for k, v in spy_regimes.items()}
    first_seed = [s.session_date for s in calendar.sessions(cfg.start_date-timedelta(days=14), cfg.start_date)
        if s.is_open and s.session_date < sessions[0].session_date][-1]
    if base_risk.policy != 'b0' and first_seed not in regimes:
        raise ValueError('Adaptive risk requires prior SPY SMA50/200 history')
    guard = CampaignRiskState(base_risk, observations=[(first_seed, cfg.initial_equity)], regimes=regimes)
    from backtesting.winner_global_liquidation import GlobalLiquidation
    liquidation=GlobalLiquidation(cfg,base_risk,exec_cfg)
    daily_equity, marks, audit, breaker_marks, coverage = [], [], [], [], set()
    returns = close.pct_change(fill_method=None)
    cache = {}

    def raw_groups(day, symbols):
        key = (day, tuple(sorted(symbols)))
        if key not in cache:
            session = next(s for s in calendar.sessions(day, day) if s.is_open)
            opening, closing = session.open_at_utc, session.close_at_utc
            frame = intraday_source(day, symbols) if symbols else pd.DataFrame()
            groups = {}
            if not frame.empty:
                frame = frame.copy()
                frame['timestamp'] = pd.to_datetime(frame['timestamp'], utc=True)
                if frame.duplicated(['symbol', 'timestamp']).any() or set(frame.symbol)-set(symbols):
                    raise ValueError('Ambiguous/unsolicited intraday rows')
                for row in frame.to_dict('records'):
                    stamp = row['timestamp'].to_pydatetime()
                    values = [float(row[k]) for k in ('open', 'high', 'low', 'close', 'volume')]
                    if (not opening <= stamp < closing or (stamp-opening).total_seconds() % 300
                            or not all(math.isfinite(x) and x > 0 for x in values)
                            or not values[2] <= min(values[0], values[3]) <= max(values[0], values[3]) <= values[1]):
                        raise ValueError('Unqualified regular-session OHLCV')
                groups = {s: g.set_index('timestamp').sort_index() for s, g in frame.groupby('symbol')}
            cache[key] = groups
        return cache[key]

    def full_session(group, day):
        opening, closing = regular_bounds(day)
        return group is not None and len(group) == int((closing-opening).total_seconds()/300)

    def admit(signal_day, stamp):
        rows = selected.loc[selected.trade_date.eq(signal_day)]
        if rows.empty:
            return
        if selection_source is not None:
            filtered=selection_source(signal_day,rows,stamp)
            if filtered['incomplete']:
                coverage.add((str(signal_day),'*','OPTIONS_COHORT_INCOMPLETE'))
            rows=rows.loc[rows.symbol.isin(filtered['selected'])]
            if rows.empty:
                return
        if liquidation.blocks_entries:
            return
        risk = replace(base_risk, account_equity=book.equity())
        targets = []
        raw = raw_groups(signal_day, sorted(rows.symbol.unique()))
        for row in rows.sort_values('rank' if 'rank' in rows else 'symbol').to_dict('records'):
            symbol = row['symbol']
            if symbol not in sectors or symbol not in close or pd.Timestamp(signal_day) not in close.index:
                raise ValueError('Signal daily price / current sector missing: '+symbol)
            if not full_session(raw.get(symbol), signal_day):
                coverage.add((str(signal_day), symbol, 'SIGNAL_RAW_5M_INCOMPLETE'))
                continue
            # Sizing and breakout levels share raw prices with actual fills;
            # never compare a split-adjusted daily level with raw five-minute bars.
            price = float(raw[symbol].iloc[-1]['close'])
            budget = risk.account_equity*risk.risk_per_trade_pct*risk.risk_multiplier
            full = min(math.floor(budget/(price*(policy.stop_loss_pct+2.05*max(policy.fee, fee)))),
                math.floor(risk.account_equity*risk.max_position_weight/price))
            if full < 1 or full*policy.initial_position_fraction*price < risk.effective_min_notional:
                audit.append(dict(time=stamp, symbol=symbol, reason='SIGNAL_BUDGET_TOO_SMALL'))
                continue
            targets.append(ExecutionTarget('replay-'+str(signal_day), signal_day, symbol, full, price,
                full*price/risk.account_equity, sectors[symbol], 1., 'native_campaign_budget', None,
                selection_rank=int(row.get('rank') or 1), risk_budget_dollars=budget, side='long'))
        stage_targets(store, targets, exec_cfg, 'winner-replay', now=stamp, calendar=calendar)

    # Signals dated before the requested start can be admitted only if their
    # next official session is the first replay session.
    previous = first_seed
    admit(previous, sessions[0].open_at_utc-timedelta(seconds=1))
    for index, session in enumerate(sessions):
        day, opening, closing = session.session_date, session.open_at_utc, session.close_at_utc
        book.settle(day)
        prior_day = previous if index == 0 else sessions[index-1].session_date
        resumed=liquidation.resume(opening,book)
        if resumed:
            # Only the cycle risk episode is reset. Global DD/peak never reset.
            guard=CampaignRiskState(base_risk,observations=[(prior_day,book.equity())],
                regimes={prior_day:regimes.get(prior_day)})
            # No stale pre-pause plans: only the latest prior-session signal.
            admit(prior_day,opening-timedelta(seconds=1))
        elif selection_source is not None and index>0:
            # Nightly options receipts are known before the next open, not
            # one second after the signal close. No future trade-day data.
            admit(prior_day,opening-timedelta(seconds=1))
        records = store.rows()
        symbols = sorted({r['state']['symbol'] for r in records})
        prior_day = previous if index == 0 else sessions[index-1].session_date
        daily_days = [pd.Timestamp(s.session_date) for s in calendar.sessions(
            prior_day-timedelta(days=150), prior_day) if s.is_open][-61:]
        groups, priors = raw_groups(day, symbols), raw_groups(prior_day, symbols)
        held_symbols = {p['symbol'] for p in book.positions()}
        for symbol in symbols:
            if not full_session(groups.get(symbol), day):
                coverage.add((str(day), symbol, 'CANDIDATE_RAW_5M_INCOMPLETE'))
            if not full_session(priors.get(symbol), prior_day):
                coverage.add((str(day), symbol, 'PRIOR_RAW_5M_INCOMPLETE'))
        actions = [a for a in corporate_actions if str(a['ex_date'])[:10] == day.isoformat() and a['symbol'] in symbols]
        for action in actions:
            book.corporate_action(action, day)
        if actions and any(a['symbol'] in held_symbols for a in actions):
            audit.append(dict(time=opening, reason='CASH_DIVIDEND_ENTITLEMENT'))
        # Never admit a pre-action raw breakout threshold after a same-day
        # split/dividend. Historical events affect accounting, not selection
        # based on their future returns.
        action_symbols = {a['symbol'] for a in actions}
        past_returns = returns.loc[returns.index <= pd.Timestamp(prior_day)].tail(base_risk.correlation_lookback_days)
        for offset in range(int((closing-opening).total_seconds()/300)):
            stamp = opening+timedelta(minutes=5*offset)
            book.now = stamp
            bars = {s: g.loc[pd.Timestamp(stamp)].to_dict() for s, g in groups.items() if pd.Timestamp(stamp) in g.index}
            held = {p['symbol'] for p in book.positions()}
            if held-set(bars):
                raise ValueError(f'Missing held-position 5m bar {day}/{stamp}: {sorted(held-set(bars))}')
            # Pre-open exit staging must not see the future opening print.
            records = store.rows()
            if offset == 0:
                due = [r for r in records if r['state']['due_open'] and aware(r['state']['due_open']) == opening]
                if due:
                    book.now = opening-timedelta(minutes=5)
                    preopen = WinnerCampaignRuntime(store, repo, book, exec_cfg, market=lambda *_: {},
                        risk=lambda *a: {}, now=book.now).run(due)
                    if preopen['winner_failures']:
                        raise ValueError('Pre-open exit reconciliation failed: '+str(preopen))
                    book.now = opening
            book.marks.update({s: float(b['open']) for s, b in bars.items()})
            book.resolve(bars, opening=True)
            risk = replace(base_risk, account_equity=book.equity())
            evaluated = guard.evaluate(day, book.equity(), regimes.get(prior_day), daily_pnl=book.equity()-
                (daily_equity[-1][1] if daily_equity else cfg.initial_equity))
            liquidation.observe(stamp,book.equity(),book,evaluated)
            liquidation.execute(stamp,store,repo,book,exec_cfg)
            records = store.rows()
            def source(state, now):
                symbol = state['symbol']
                if symbol in action_symbols:
                    raise ValueError('EX_DATE_ENTRY_BLOCKED_RAW_REFERENCE')
                if symbol not in bars:
                    raise ValueError('CANDIDATE_5M_BAR_MISSING')
                delay=timedelta(seconds=state['policy'].get('market_data_delay_seconds',0))
                tail = groups[symbol].loc[groups[symbol].index+pd.Timedelta(minutes=5) <= pd.Timestamp(now-delay)].tail(
                    max(state['policy']['confirmation_bars']+1, 3))
                if not full_session(priors.get(symbol), prior_day):
                    raise ValueError('Prior raw session high unavailable')
                evidence=[dict(row,timestamp=t.to_pydatetime(),session_tag='regular') for t,row in tail.iterrows()]
                from common.winner_delayed import delayed_entry
                if delayed_entry(state,'ADD' if state['lots'] else 'ENTRY'):
                    from common.winner_delayed import delayed_snapshot
                    return delayed_snapshot(evidence,WinnerPyramidingConfig(**state['policy']),now) | dict(
                        prior_session_high=float(priors[symbol]['high'].max()),prior_session=prior_day,
                        available_cash=book.capacity())
                if state['policy']['confirmation_bars']==0 and not state['lots'] and not state['policy']['standard_entry_quote_check_enabled']:
                    return dict(bars=[],prior_session=prior_day,prior_session_high=None,
                        ask=None,bid=None,feed='sip',standard_entry_quote_check_enabled=False)
                return dict(bars=evidence,
                    prior_session_high=float(priors[symbol]['high'].max()),
                    ask=book.marks[symbol], bid=book.marks[symbol], feed='sip', quote_time=now,
                    available_cash=book.capacity())

            def recheck(state, version, quantity, snapshot, now, kind):
                from execution_engine.winner_live_risk import concentration_allowed
                if liquidation.blocks_entries:
                    raise ValueError('Global drawdown emergency halt blocks all new entries and additions')
                vol = 1.
                if risk.target_annual_vol:
                    vol_decision = evaluate_vol_target(returns.loc[returns.index <= pd.Timestamp(prior_day)].get(
                        'SPY', pd.Series(dtype=float)), target_annual_vol=risk.target_annual_vol,
                        lookback_days=risk.vol_target_lookback_days, benchmark_symbol='SPY')
                    if not vol_decision.applied:
                        raise ValueError('Volatility target history unavailable')
                    vol = min(1., float(vol_decision.scaler))
                # Capacity is recalculated after each accepted entry, not frozen
                # at the day's or five-minute group's initial cash balance.
                current = replace(risk, account_equity=book.equity())
                leverage = engine._resolve_daily_leverage_state(book.equity())
                current = replace(current, max_gross_exposure=min(current.max_gross_exposure,
                    leverage.effective_leverage if leverage.active else 1.))
                positions = [dict(symbol=p['symbol'], side=p['side'], quantity=p['qty'], mark=p['mark']) for p in book.positions()]
                candidate = state['symbol']
                daily_ok = len(daily_days) == 61
                for field in (open_df, close, high, low, volume):
                    if field is None or candidate not in field:
                        daily_ok = False
                        break
                    values = field[candidate].reindex(daily_days)
                    if not values.map(lambda x: pd.notna(x) and math.isfinite(float(x)) and x > 0).all():
                        daily_ok = False
                        break
                hist = close.loc[close.index <= pd.Timestamp(prior_day), candidate].tail(20)
                adv = None
                if volume is not None and candidate in volume:
                    adv = float((hist*volume.loc[hist.index, candidate]).mean())
                fills = [dict(fill_timestamp=l['entry_time'], filled_qty=l['quantity'], avg_fill_price=l['entry'],
                    side='buy', intent_role='entry', request_id=k) for k, l in book.lots.items() if l['symbol'] == candidate]
                fills += [dict(fill_timestamp=t['exit_date'], filled_qty=t['quantity'], avg_fill_price=t['exit_price'],
                    side='sell', intent_role='exit') for t in book.trades if t['symbol'] == candidate]
                fills.sort(key=lambda f: f['fill_timestamp'])
                concentration = concentration_allowed(fills, current, candidate, day, kind)
                ctx = dict(account_id=state['account_id'], broker_mode=state['broker_mode'], captured_at=now,
                    equity=book.equity(), available_buying_power=book.capacity(), positions=positions,
                    pending_entries=book.pending_entries(), sector_map=sectors, risk_config=current,
                    circuit_breaker=evaluated['circuit_breaker'], breaker_qualified=True,
                    allocation_scale=evaluated['allocation_scale'], return_matrix=past_returns,
                    adv_usd=adv, cost_reserve_pct=fee, max_spread_bps=50., volatility_allocation_scale=vol,
                    entry_data_qualified=daily_ok, regime_qualified=True, concentration_qualified=True,
                    concentration_allowed=concentration, corporate_actions_qualified=True,
                    factor_qualified=True, entries_allowed=not exec_cfg.blocks_new_entries)
                from common.winner_delayed import delayed_entry
                if delayed_entry(state,kind):
                    ctx.update(delayed_sip_allowed=True,standard_entry_quote_check_enabled=False)
                elif snapshot.get('standard_entry_quote_check_enabled') is False:
                    ctx.update(standard_entry_quote_check_enabled=False,
                        reference_price=float(priors[candidate].iloc[-1]['close']),reference_price_asof=prior_day)
                if current.enable_factor_model:
                    required={candidate}|{p['symbol'] for p in positions}|{p['symbol'] for p in ctx['pending_entries']}
                    try:
                        context=factor_context_source(prior_day,required,now,current)
                    except ValueError as exc:
                        coverage.add((str(day),candidate,'FACTOR_CONTEXT_UNAVAILABLE: '+str(exc)[:300]))
                        raise
                    ctx.update(factor_context=context,factor_asof_date=prior_day,
                               factor_qualified=context.get('qualified') is True)
                return reapprove_campaign(state, version, quantity, snapshot, now, kind, context=ctx)

            if records:
                result = WinnerCampaignRuntime(store, repo, book, exec_cfg, market=source, risk=recheck, now=stamp).run(records)
                audit.extend(dict(time=stamp, **r) for r in result['winner_details'])
                if result['winner_failures']:
                    raise ValueError('Campaign replay requires reconciliation: '+str(result['winner_details']))
            # Intrabar touch time is unknowable from OHLC. Record the closing
            # bound, not an invented earlier timestamp usable by another buy.
            book.now = stamp+timedelta(minutes=5)
            book.resolve(bars, opening=False)
            book.marks.update({s: float(b['close']) for s, b in bars.items()})
            if liquidation.enabled:
                close_evaluation=guard.evaluate(day,book.equity(),regimes.get(prior_day),daily_pnl=book.equity()-
                    (daily_equity[-1][1] if daily_equity else cfg.initial_equity))
                liquidation.observe(stamp+timedelta(minutes=5),book.equity(),book,close_evaluation)
            marks.append((stamp+timedelta(minutes=5), book.equity(), book.gross()))
            breaker_marks.append(dict(timestamp=stamp, peak=evaluated['reference_peak'],
                allocation=evaluated['allocation_scale'], active=evaluated['active'],
                global_halted=liquidation.halted,cycle_stopped=liquidation.cycle_stopped,cycle=liquidation.cycle))
        # Reconcile last-bar fills and terminal campaigns before the next
        # signal is admitted; no buying at the just-closed session.
        book.expire_day_entries()
        closed_cfg = replace(exec_cfg, winner_pyramiding=replace(policy, enabled=False))
        final = WinnerCampaignRuntime(store, repo, book, closed_cfg, market=source, risk=recheck, now=closing).run(store.rows())
        if final['winner_failures']:
            raise ValueError('Closing reconciliation failed: '+str(final))
        # Financing convention mirrors BacktestEngine: annual /252 sessions.
        charge = max(-book.cash, 0.)*cfg.margin_interest_rate_annual/252
        book.cash -= charge
        book.interest += charge
        book.events.append(dict(time=closing, event='FINANCING', costs=charge))
        daily_equity.append((pd.Timestamp(day), book.equity()))
        if selection_source is None:
            admit(day, closing+timedelta(seconds=1))
        cache = {k: v for k, v in cache.items() if k[0] >= day}
        if progress:
            progress(index+1, len(sessions), str(day))
    result = BacktestResult(equity_curve=pd.Series(dict(daily_equity), name='equity'),
        closed_trades_df=pd.DataFrame(book.trades), trade_events_df=pd.DataFrame(audit+book.events),
        drawdown_breaker_df=pd.DataFrame(breaker_marks),
        intraday_equity_curve=pd.DataFrame(marks, columns=['timestamp', 'equity', 'gross']))
    result.tracker_snapshot = dict(winner_replay=dict(status='INCOMPLETE_COVERAGE' if coverage else 'COMPLETED_EXPLORATORY',
        coverage_gaps=[dict(date=d, symbol=s, reason=r) for d, s, r in sorted(coverage)], full_live_parity=False,
        costs=book.fees, margin_interest=book.interest, dividends_accrued=book.dividends,
        dividends_receivable=sum(c['amount'] for c in book.claims), settled_cash=book.cash,
        unsettled_cash=sum(v for _, v in book.unsettled), gross=book.gross(),
        open_positions=book.positions(), campaigns=len(store.records), policy=policy.__dict__))
    result.tracker_snapshot['winner_replay']['global_liquidation']=liquidation.summary()
    if policy.confirmation_bars == 0:
        result.tracker_snapshot['winner_replay']['standard_entry_assumptions'] = (
            'Regular-session observed 5m opens only; no historical pre-open SIP quotes; '
            'DAY limits expire at session close; no intrabar limit-fill inference.')
    return result
