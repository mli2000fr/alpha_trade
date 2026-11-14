"""Q051 native sizing and live account capture, without extra strategy overlays."""
from datetime import UTC, date, datetime
import hashlib
import json
import math

import pandas as pd
from sqlalchemy import text, bindparam

from common.q051_paper import reference, risk_config, validate_frozen, NoDrawdownController
from common.winner_pyramiding import aware
from risk_management.portfolio_volatility import portfolio_limit
from risk_management.constraints import PortfolioState
from risk_management.risk_checker import RiskCheckerImpl


def regime_allowed(close, signal_day):
    day = pd.Timestamp(signal_day)
    history = close.sort_index().loc[:day].tail(200)
    if (len(history) != 200 or history.index[-1] != day
            or not history.index.is_unique or not history.gt(0).all()
            or not all(math.isfinite(float(x)) for x in history)):
        raise ValueError('Q051 : 200 clôtures SPY qualifiées jusqu’à J requises')
    return bool(history.iloc[-1] > .98 * history.mean())


def quantity(*, symbol, price, proposed, context, risk_budget=None, full_quantity=None):
    """Same full-position SL5 sizing, native constraints, then covariance root."""
    cfg = risk_config(context['equity'])
    if (not math.isfinite(float(price)) or price <= 0 or not math.isfinite(float(proposed))
            or proposed < 0 or not math.isfinite(float(context['available_buying_power']))):
        raise ValueError('Q051 : prix, quantité ou capacité invalide')
    if not context['regime_allowed']:
        return dict(quantity=0, reason='Q051_SPY_BELOW_098_SMA200')
    if not context.get('concentration_allowed', True):
        return dict(quantity=0, reason='Q051_REFERENCE_SYMBOL_CONCENTRATION')
    book = PortfolioState()
    sectors = context['sector_map']
    for row in context['positions']:
        if row['symbol'] == symbol:
            return dict(quantity=0, reason='Q051_ALREADY_HELD')
        q, mark = float(row['quantity']), float(row['mark'])
        if row['side'] not in ('buy', 'long') or not all(math.isfinite(x) and x > 0 for x in (q, mark)):
            raise ValueError('Q051 : position détenue non qualifiée ou SHORT')
        book.add_position(notional=q*mark, sector=sectors.get(row['symbol'], 'UNKNOWN'),
                          side='buy', symbol=row['symbol'])
    for row in context['pending_entries']:
        if row['symbol'] == symbol:
            return dict(quantity=0, reason='Q051_ALREADY_PENDING')
        if (row['side'] not in ('buy', 'long') or not math.isfinite(float(row['notional']))
                or row['notional'] <= 0):
            raise ValueError('Q051 : réservation d’ordre en cours non qualifiée')
        book.add_position(notional=row['notional'], sector=sectors.get(row['symbol'], 'UNKNOWN'),
                          side='buy', symbol=row['symbol'])
    fee = reference()['winner']['cost_reserve_bps_per_leg']/10000
    budget = min(context['equity']*.0125, risk_budget if risk_budget is not None else math.inf)
    full = min(math.floor(budget/(price*(.05+2.05*fee))),
               int(full_quantity) if full_quantity is not None else math.floor(proposed))
    native = min(math.floor(proposed), full,
                 math.floor(max(context['available_buying_power'], 0)/(price*(1+fee))),
                 math.floor(context['equity']*.2/price))
    checker = RiskCheckerImpl(cfg, state=book, sector_map=sectors,
                              circuit_breaker=NoDrawdownController())
    native = int(checker.check_position_size(symbol, native, price, side='buy')) if native > 0 else 0
    if native <= 0:
        reason = checker.get_last_decision_reason()
        return dict(quantity=0, reason=reason if reason != 'OK' else 'Q051_BUDGET_OR_CAPACITY')
    decision = portfolio_limit(context['returns'], prior_day=context['signal_day'],
        positions=context['positions'], pending=context['pending_entries'], symbol=symbol,
        price=price, equity=context['equity'], proposed=native, target=.2, lookback=60)
    final = int(checker.check_position_size(symbol, decision['quantity'], price, side='buy')) if decision['quantity'] else 0
    return dict(quantity=final, reason=decision['reason'], covariance=decision,
                risk_budget=budget, config_hash=cfg.fingerprint)


def capture(repo, broker, account, signal_day, now, *, clock=None):
    """Actual broker state, source-selected daily history, no fallback capital."""
    from common.daily_bar_sources import load_daily_close_series
    from common.market_calendar import get_market_calendar
    from risk_management.db_io import RiskRepository
    now = aware(now)
    if repo.engine.dialect.name != 'mysql' or repo.engine.url.database != 'alpha_trade':
        raise ValueError('Q051 : contexte compte réservé à alpha_trade US')
    clock = clock or (lambda: datetime.now(UTC))
    cal = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    local_day = now.astimezone(ZoneInfo('America/New_York')).date()
    completed = [s for s in cal.sessions(local_day-timedelta(days=14), local_day)
                 if s.is_open and s.close_at_utc < now]
    if not completed or completed[-1].session_date != signal_day:
        raise ValueError('Q051 : décision sur une ancienne séance refusée')
    raw = broker.get_account_snapshot()
    observed = aware(clock())
    if any(raw.get(k) is True for k in ('trading_blocked','account_blocked','trade_suspended_by_user')):
        raise ValueError('Q051 : compte bloqué par le broker')
    if raw.get('status') != 'ACTIVE':
        raise ValueError('Q051 : compte broker non actif')
    equity = float(raw.get('equity') or 0)
    power = raw.get('regt_buying_power')
    if power in (None, ''):
        power = raw.get('buying_power')
    if power in (None, ''):
        raise ValueError('Q051 : capacité broker absente')
    buying_power = float(power)
    if not math.isfinite(equity) or equity <= 0 or not math.isfinite(buying_power):
        raise ValueError('Q051 : equity/capacité broker absente, aucun capital de secours')
    buying_power = max(buying_power, 0.)
    positions = [dict(symbol=p['symbol'], side=p['side'], quantity=abs(float(p['qty'])),
                      mark=float(p['current_price'])) for p in broker.get_all_positions()]
    if len({p['symbol'] for p in positions}) != len(positions):
        raise ValueError('Q051 : positions broker dupliquées')
    orders = broker.list_recent_orders(status='open', limit=500)
    if len(orders) >= 500:
        raise ValueError('Q051 : liste des ordres potentiellement tronquée')
    pending = []
    longs = {p['symbol'] for p in positions if p['side'] == 'long'}
    rr = RiskRepository(repo.engine)
    for o in orders:
        if o['side'] == 'sell' and o['symbol'] in longs:
            continue
        remaining = float(o['qty'])-float(o.get('filled_qty') or 0)
        if remaining <= 0:
            continue
        price = o.get('limit_price') or o.get('stop_price')
        if price is None:
            # A pending MOO has no current fill price. Its journaled decision
            # notional is an explicit reservation, not a fabricated quote.
            with repo.engine.connect() as c:
                row = c.execute(text('SELECT decision_price FROM execution_order_requests '
                    'WHERE account_id=:account AND submission_key=:key'),
                    dict(account=account, key=o.get('client_order_id'))).scalar_one_or_none()
            price = row
        if price is None or not math.isfinite(float(price)) or float(price) <= 0:
            raise ValueError('Q051 : ordre en cours sans réservation de capital vérifiable')
        pending.append(dict(symbol=o['symbol'], side=o['side'], notional=remaining*float(price)))
    names = sorted({p['symbol'] for p in positions} | {p['symbol'] for p in pending})
    spy = load_daily_close_series(repo.engine, 'SPY', signal_day)
    official = [s.session_date for s in cal.sessions(signal_day-timedelta(days=500),signal_day) if s.is_open][-200:]
    spy = spy.reindex(pd.DatetimeIndex(official))
    return dict(account_id=account, broker_mode='paper', captured_at=observed,
        equity=equity, available_buying_power=min(buying_power, 2*equity),
        positions=positions, pending_entries=pending, signal_day=signal_day,
        regime_allowed=regime_allowed(spy, signal_day), sector_map={}, returns=pd.DataFrame(),
        raw_account=raw, base_symbols=names)


def complete_context(context, engine, symbols):
    names = sorted(set(symbols) | set(context['base_symbols']))
    # Reindex the official grid to expose gaps rather than silently joining
    # two nonconsecutive trading sessions into one covariance observation.
    from common.market_calendar import get_market_calendar
    from datetime import timedelta
    day = context['signal_day']
    sessions = [s.session_date for s in get_market_calendar('US_EQ', allow_us_weekday_fallback=False).sessions(
        day-timedelta(days=150), day) if s.is_open][-61:]
    if len(sessions) != 61 or sessions[-1] != day:
        raise ValueError('Q051 : calendrier de covariance incomplet')
    from common.daily_bar_sources import select_daily_bars, SOURCES
    price_stmt = text('SELECT symbol,date,close,data_source FROM stock_bars_daily '
        'WHERE symbol IN :symbols AND date BETWEEN :start AND :end').bindparams(bindparam('symbols', expanding=True))
    with engine.connect() as c:
        raw = pd.DataFrame(c.execute(price_stmt, dict(symbols=names, start=sessions[0], end=day)).mappings().all())
    if raw.empty:
        raise ValueError('Q051 : cours quotidiens absents')
    if not raw.data_source.isin(SOURCES.values()).all():
        raise ValueError('Q051 : fournisseur daily non qualifié')
    raw['date'] = pd.to_datetime(raw['date'])
    raw = select_daily_bars(raw)
    closes = raw.pivot(index='date', columns='symbol', values='close').astype(float).reindex(
        index=pd.DatetimeIndex(sessions), columns=names)
    closes = closes.where(closes.gt(0))
    returns = closes.pct_change(fill_method=None).iloc[1:]
    stmt = text('SELECT symbol,sector FROM stock_metadata WHERE symbol IN :symbols').bindparams(bindparam('symbols', expanding=True))
    with engine.connect() as c:
        sectors = {r.symbol: str(r.sector or 'UNKNOWN') for r in c.execute(stmt, dict(symbols=names))}
    return context | dict(returns=returns, sector_map=sectors, reference_closes=closes.iloc[-1].to_dict())


class NativeQ051Risk:
    def __init__(self, repo, broker, config, clock=None):
        self.repo, self.broker, self.config = repo, broker, config
        self.clock = clock or (lambda: datetime.now(UTC))

    def __call__(self, state, version, proposed, snapshot, now, kind):
        from common.q051_paper import settings, entry_window, require_paper
        from execution_engine.winner_live_risk import concentration_allowed
        validate_frozen(state['paper_strategy_profile'])
        require_paper(state['account_id'], state['broker_mode'])
        if (not settings()['enabled'] or kind != 'ENTRY' or state['lots']
                or self.config.resolved_account_id != state['account_id']
                or self.config.broker_mode != 'paper' or not entry_window(state, now)):
            raise ValueError('Q051 : admission désactivée, mauvais compte ou ouverture J+1 manquée')
        signal = date.fromisoformat(state['signal_date'])
        if snapshot.get('prior_session') != signal:
            raise ValueError('Q051 : contexte prix différent de la séance J')
        context = complete_context(capture(self.repo, self.broker, state['account_id'], signal, now,
                                           clock=self.clock), self.repo.engine, [state['symbol']])
        asset = self.broker._client.get_asset(state['symbol'])
        if asset.get('tradable') is not True or asset.get('status') != 'active':
            raise ValueError('Q051 : titre non négociable chez Alpaca')
        if asset.get('marginable') is not True:
            cash = float(context['raw_account'].get('non_marginable_buying_power') or 0)
            context['available_buying_power'] = min(context['available_buying_power'], cash)
        with self.repo.engine.connect() as c:
            fills = c.execute(text('SELECT f.symbol,r.request_id,r.side,r.intent_role,f.filled_qty,'
                'f.avg_fill_price,f.fill_timestamp FROM execution_broker_fills f '
                'JOIN execution_order_requests r ON r.request_id=f.request_id '
                'JOIN execution_runs e ON e.exec_run_id=r.exec_run_id '
                'WHERE f.account_id=:account AND e.broker_mode=\'paper\' AND f.symbol=:symbol '
                'AND f.fill_timestamp<=:now ORDER BY f.fill_timestamp,f.fill_id'),
                dict(account=state['account_id'], symbol=state['symbol'], now=aware(now))).mappings().all()
        cfg = risk_config(context['equity'])
        context['concentration_allowed'] = concentration_allowed(fills, cfg, state['symbol'], signal, kind)
        price = float(state['target']['entry_price'])
        decision = quantity(symbol=state['symbol'], price=price, proposed=proposed, context=context,
                            risk_budget=state['risk_budget'], full_quantity=state['full_quantity'])
        decision_time = aware(self.clock())
        if not 0 <= (decision_time-context['captured_at']).total_seconds() <= 60 or not entry_window(state, decision_time):
            raise ValueError('Q051 : snapshot de compte périmé ou limite MOO dépassée')
        evidence = hashlib.sha256(json.dumps(context, default=str, sort_keys=True).encode()).hexdigest()
        from datetime import timedelta
        return dict(producer='native_intraday_risk', campaign_id=state['campaign_id'],
            account_id=state['account_id'], broker_mode='paper', state_version=version,
            side='buy', qualified=True, max_quantity=decision['quantity'], limit_price=price,
            available_at=decision_time.isoformat(), valid_until=(decision_time+timedelta(seconds=30)).isoformat(),
            config_hash=cfg.fingerprint, portfolio_hash=evidence, entry_data_qualified=True,
            realtime_sip_qualified=False, regime_qualified=True, standard_entry_quote_check_enabled=False,
            price_basis='q051_paper_moo_prior_close', reference_price_asof=str(signal),
            order_type='market', order_limit_price=None, q051_profile_sha256=state['paper_strategy_profile']['sha256'],
            q051_covariance=decision.get('covariance'), reason=decision['reason'])
