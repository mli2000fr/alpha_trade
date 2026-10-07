from datetime import date, datetime, timezone
from dataclasses import replace

import pandas as pd
import pytest

from backtesting.oracle_portfolio_session import OraclePortfolioSession
from risk_management.config import RiskConfig
from risk_management.operational_data import BacktestOperationalDataAdapter
from service.market.models import neutral_snapshot

D1, D2 = date(2025, 1, 2), date(2025, 1, 3)


def session(**overrides):
    return OraclePortfolioSession(RiskConfig(account_equity=4000,
        min_position_notional=0, min_breakout_days=overrides.pop('min_breakout_days', 1),
        max_positions=overrides.pop('max_positions', 8), **overrides),
        sector_map={'NEW': 'Tech', 'HELD': 'Tech'}, account_long_only=False)


def inputs(day, *, equity=4000., positions=(), **kwargs):
    days = pd.bdate_range(end=day, periods=30)
    close = pd.DataFrame({'NEW': 100.}, index=days)
    snapshot = BacktestOperationalDataAdapter.build(account_id='stateful',
        account={'equity': equity, 'cash': equity, 'settled_cash': equity, 'buying_power': equity},
        positions=positions, orders=[], as_of=datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc),
        source='test_ledger')
    return dict(scores=pd.DataFrame([{'symbol': 'NEW', 'trade_date': day, 'proba_extreme': .9}]),
        snapshot=snapshot, regime=neutral_snapshot(day), close=close, high=close+1,
        low=close-1, **kwargs)


def test_breakout_state_survives_between_decisions():
    s = session(min_breakout_days=2)
    first = s.decide(D1, **inputs(D1))
    assert not any(e.approved_shares > 0 for e in first)
    second = s.decide(D2, **inputs(D2))
    assert any(e.approved_shares > 0 for e in second)


def test_actual_held_positions_reserve_slots_next_day():
    s = session(max_positions=1)
    assert any(e.approved_shares > 0 for e in s.decide(D1, **inputs(D1)))
    held = [{'symbol': 'HELD', 'qty': 10., 'side': 'long',
             'avg_entry_price': 100., 'current_price': 100.}]
    assert not any(e.approved_shares > 0 for e in s.decide(D2, **inputs(D2, positions=held)))


def test_approval_is_not_counted_as_a_fill_and_retries_are_idempotent():
    s = session(concentration_max_trades_per_symbol=1)
    s.decide(D1, **inputs(D1))
    assert s.trades.to_summary()['total_entries'] == 0
    s.record_fill('fill1', day=D2, symbol='NEW', entry=True)
    s.record_fill('fill1', day=D2, symbol='NEW', entry=True)
    assert s.trades.to_summary()['total_entries'] == 1
    assert not any(e.approved_shares > 0 for e in s.decide(D2, **inputs(D2)))


def test_losses_survive_between_decisions():
    s = session(concentration_max_consecutive_losses=1)
    s.decide(D1, **inputs(D1))
    s.record_fill('closed1', day=D2, symbol='NEW', entry=False, realized_pnl=-50.)
    assert s.losses.is_blacklisted('NEW', D2, side='buy')
    assert not any(e.approved_shares > 0 for e in s.decide(D2, **inputs(D2)))


def test_future_prices_cannot_change_decision():
    base = inputs(D1)
    future = inputs(D1)
    for col in ('close', 'high', 'low'):
        future[col].loc[pd.Timestamp(D2)] = 1000000.
    a = session().decide(D1, **base)
    b = session().decide(D1, **future)
    assert [(e.approved_shares, e.stop_price_initial, e.take_profit_price) for e in a] == [
        (e.approved_shares, e.stop_price_initial, e.take_profit_price) for e in b]


def test_regime_permissions_reach_shared_builder():
    kwargs = inputs(D1)
    kwargs['regime'] = replace(kwargs['regime'], allowed_long_entries=False)
    assert session().decide(D1, **kwargs) == []


def test_ledger_equity_is_not_reset_to_starting_capital():
    s = session()
    s.decide(D1, **inputs(D1))
    s.decide(D2, **inputs(D2, equity=3100.))
    assert s.resolved_config.account_equity == 3100.


@pytest.mark.parametrize('problem', ['repeat', 'regime', 'snapshot', 'candidate', 'stale'])
def test_bad_chronology_and_dates_fail_closed(problem):
    s = session()
    kwargs = inputs(D2)
    if problem == 'repeat': s.decide(D2, **kwargs)
    if problem == 'regime': kwargs['regime'] = neutral_snapshot(D1)
    if problem == 'snapshot': kwargs['snapshot'] = inputs(D1)['snapshot']
    if problem == 'candidate': kwargs['scores']['trade_date'] = D1
    if problem == 'stale':
        for col in ('close', 'high', 'low'):
            kwargs[col] = kwargs[col].iloc[:-1]
    with pytest.raises(ValueError): s.decide(D2, **kwargs)


def test_conflicting_fill_identity_is_rejected():
    s = session()
    s.decide(D1, **inputs(D1))
    s.record_fill('a', day=D2, symbol='NEW', entry=True)
    with pytest.raises(ValueError, match='Conflicting'):
        s.record_fill('a', day=D2, symbol='HELD', entry=True)


def test_incomplete_atr_cannot_silently_use_a_fallback():
    kwargs = inputs(D1)
    for col in ('close', 'high', 'low'):
        kwargs[col] = kwargs[col].iloc[-10:]
    with pytest.raises(ValueError, match='ATR'):
        session().decide(D1, **kwargs)


def test_failed_builder_cannot_double_count_mutated_trackers(monkeypatch):
    from risk_management.portfolio_builder import PortfolioBuilder
    def broken(*args, **kwargs):
        raise RuntimeError('fixture failure after entering build')
    monkeypatch.setattr(PortfolioBuilder, 'build', broken)
    s = session()
    with pytest.raises(RuntimeError): s.decide(D1, **inputs(D1))
    with pytest.raises(ValueError, match='checkpoint'): s.decide(D1, **inputs(D1))
