from dataclasses import replace
from datetime import date

import pandas as pd
import pytest

from backtesting.oracle_portfolio_ledger import OraclePortfolioLedger
from backtesting.oracle_portfolio_session import OraclePortfolioSession
from scripts.research.us_concentrated_contract_audit import frozen_backtest_config, frozen_configs
from service.market.models import neutral_snapshot

D1, D2, D3 = map(pd.Timestamp, ['2025-01-02', '2025-01-03', '2025-01-06'])


def setup():
    days = pd.bdate_range(end=D3, periods=30)
    close = pd.DataFrame({'FIXTURE': 100.}, index=days)
    cfg = frozen_backtest_config(D1, D3)
    cfg.risk_config = cfg.risk_config.with_overrides(min_breakout_days=1, min_position_notional=0)
    ledger = OraclePortfolioLedger(cfg, opens=close.copy(), close=close.copy(),
        high=close+1, low=close-1, volume=close*10000, sector_map={'FIXTURE': 'Technology'})
    session = OraclePortfolioSession(cfg.risk_config, sector_map=ledger.sectors, account_long_only=False)
    return ledger, session


def decide(ledger, session, day):
    ledger.mark_close()
    return session.decide(day.date(), scores=pd.DataFrame([
        {'trade_date': day, 'symbol': 'FIXTURE', 'proba_extreme': .9}]),
        snapshot=ledger.snapshot(), regime=neutral_snapshot(day.date()),
        close=ledger.close, high=ledger.high, low=ledger.low, volume=ledger.volume)


def test_decision_fills_protections_exit_cash_and_next_snapshot_end_to_end():
    ledger, session = setup()
    ledger.begin_day(D1)
    approved = decide(ledger, session, D1)
    approved = [e for e in approved if e.approved_shares > 0]
    assert len(approved) == 1
    ledger.finish_day()
    ledger.begin_day(D2)
    protections, opened = ledger.execute_approved(approved, execution_config=ledger.config.exec_config)
    assert opened == ['FIXTURE']
    qty = approved[0].approved_shares
    session.record_fill('entry1', day=D2.date(), symbol='FIXTURE', entry=True)
    assert ledger.state.positions['FIXTURE'].quantity == pytest.approx(qty)
    assert ledger.state.settled_cash < 4000.-qty*100.
    # Next decision sees the ACTUAL held position, not a new empty account.
    ledger.mark_close()
    snapshot = ledger.snapshot()
    assert len(snapshot.positions) == 1
    assert snapshot.account.equity < 4000.
    ledger.finish_day()
    ledger.begin_day(D3)
    terminal = ledger.close_resolved([{'symbol': 'FIXTURE', 'exit_date': D3,
        'exit_price': 100., 'exit_reason': 'pre_scheduled_terminal_close'}], phase='close')
    session.record_fill('exit1', day=D3.date(), symbol='FIXTURE', entry=False, realized_pnl=terminal[0]['pnl'])
    assert terminal[0]['pnl'] < 0 # Same price still pays BOTH legs.
    ledger.mark_close()
    ledger.finish_day()
    assert not ledger.state.positions
    assert ledger.reconciliation_error() == pytest.approx(0., abs=1e-9)
    assert ledger.daily[-1]['equity'] == pytest.approx(4000.+terminal[0]['pnl'])


def test_future_close_cannot_change_opening_equity_or_quantity():
    a, sa = setup()
    b, sb = setup()
    for ledger, session in ((a, sa), (b, sb)):
        ledger.begin_day(D1)
        approved = decide(ledger, session, D1)
        ledger.finish_day()
        # An unobserved closing price on execution day is not an opening mark.
        if ledger is b:
            ledger.close.at[D2, 'FIXTURE'] = 200.
        ledger.begin_day(D2)
        ledger.execute_approved(approved, execution_config=ledger.config.exec_config)
    assert a.equity() == pytest.approx(b.equity())
    assert a.state.positions['FIXTURE'].quantity == b.state.positions['FIXTURE'].quantity


def test_gap_rejection_does_not_debit_cash_or_reserve_a_position():
    ledger, session = setup()
    ledger.begin_day(D1)
    approved = decide(ledger, session, D1)
    ledger.finish_day()
    ledger.opens.at[D2, 'FIXTURE'] = 104.
    ledger.begin_day(D2)
    _, opened = ledger.execute_approved(approved, execution_config=ledger.config.exec_config)
    assert not opened
    assert ledger.state.settled_cash == 4000.
    assert not ledger.state.positions
    assert len(ledger.execution_audits[-1]['phase3_diagnostics']['gap_rejections']) == 1


def test_orders_cannot_be_executed_on_the_decision_day():
    ledger, session = setup()
    ledger.begin_day(D1)
    approved = decide(ledger, session, D1)
    with pytest.raises(ValueError):
        ledger.execute_approved(approved, execution_config=ledger.config.exec_config)


def test_future_exit_cannot_be_consumed_early():
    ledger, session = setup()
    ledger.begin_day(D1)
    approved = decide(ledger, session, D1)
    ledger.finish_day()
    ledger.begin_day(D2)
    ledger.execute_approved(approved, execution_config=ledger.config.exec_config)
    with pytest.raises(ValueError, match='causal'):
        ledger.close_resolved([{'symbol': 'FIXTURE', 'exit_date': D3,
            'exit_price': 100., 'exit_reason': 'future'}], phase='intraday')


def test_cannot_skip_settlement_sessions_or_finish_twice():
    ledger, _ = setup()
    ledger.begin_day(D1)
    ledger.mark_close()
    ledger.finish_day()
    with pytest.raises(ValueError): ledger.finish_day()
    with pytest.raises(ValueError, match='consecutive'): ledger.begin_day(D3)


def test_margin_interest_is_charged_once_and_in_decision_snapshot():
    ledger, session = setup()
    ledger.begin_day(D1)
    approved = decide(ledger, session, D1)
    ledger.finish_day()
    ledger.begin_day(D2)
    ledger.execute_approved(approved, execution_config=ledger.config.exec_config)
    ledger.state.settled_cash = -100.
    ledger.mark_close()
    first = ledger.snapshot().account.settled_cash
    ledger.mark_close()
    assert ledger.snapshot().account.settled_cash == first
    assert first < -100.
    ledger.finish_day()
    assert ledger.interest == pytest.approx(-100.-first)


def test_cash_sale_proceeds_are_unsettled_until_next_session():
    from backtesting.trading_constraints import TradingConstraintConfig
    ledger, session = setup()
    ledger.config.trading_constraints = TradingConstraintConfig(account_type='cash')
    ledger.begin_day(D1)
    approved = decide(ledger, session, D1)
    ledger.finish_day()
    ledger.begin_day(D2)
    ledger.execute_approved(approved, execution_config=ledger.config.exec_config)
    before = ledger.state.settled_cash
    closed = ledger.close_resolved([{'symbol': 'FIXTURE', 'exit_date': D2,
        'exit_price': 100., 'exit_reason': 'resolved_protection'}], phase='intraday')
    assert ledger.state.settled_cash == before
    assert ledger.state.unsettled_cash == pytest.approx(closed[0]['proceeds'])
    ledger.mark_close()
    assert ledger.snapshot().account.buying_power == pytest.approx(before)
    ledger.finish_day()
    ledger.begin_day(D3)
    assert ledger.state.unsettled_cash == pytest.approx(0.)
    assert ledger.state.settled_cash == pytest.approx(before+closed[0]['proceeds'])


def test_after_intraday_exit_it_is_too_late_for_an_opening_entry():
    ledger, session = setup()
    ledger.begin_day(D1)
    approved = decide(ledger, session, D1)
    ledger.finish_day()
    ledger.begin_day(D2)
    ledger.close_resolved([], phase='intraday')
    with pytest.raises(ValueError, match='after close'):
        ledger.execute_approved(approved, execution_config=ledger.config.exec_config)


def open_fixture():
    ledger, session = setup()
    ledger.begin_day(D1)
    approved = decide(ledger, session, D1)
    ledger.finish_day()
    ledger.begin_day(D2)
    ledger.execute_approved(approved, execution_config=ledger.config.exec_config)
    return ledger


def test_common_watcher_lifecycle_resolves_tp_and_native_ledger_books_it():
    ledger = open_fixture()
    tp = ledger.state.positions['FIXTURE'].replay_take_profit_price
    ledger.high.at[D2, 'FIXTURE'] = tp+1.
    assert ledger.apply_observed_protections(phase='open') == []
    closed = ledger.apply_observed_protections(phase='intraday')
    assert len(closed) == 1
    assert closed[0]['exit_reason'] == 'take_profit'
    assert closed[0]['exit_price'] == tp
    assert not ledger.state.positions
    ledger.mark_close()
    ledger.finish_day()
    assert ledger.reconciliation_error() == pytest.approx(0., abs=1e-9)


@pytest.mark.parametrize('opening,expected', [(90., 'stop_gap_open'), (110., 'take_profit_gap_limit')])
def test_held_open_gap_precedes_intraday_ambiguity(opening, expected):
    ledger = open_fixture()
    ledger.apply_observed_protections(phase='intraday')
    ledger.mark_close()
    ledger.finish_day()
    ledger.opens.at[D3, 'FIXTURE'] = opening
    ledger.high.at[D3, 'FIXTURE'] = 115.
    ledger.low.at[D3, 'FIXTURE'] = 85.
    ledger.begin_day(D3)
    closed = ledger.apply_observed_protections(phase='open')
    assert len(closed) == 1
    assert closed[0]['exit_reason'].endswith(expected)
    if opening == 90.:
        assert closed[0]['exit_price'] == 90. # No optimistic fill at the stop.
    else:
        assert closed[0]['exit_price'] < opening # Conservative TP limit.


def test_unknown_future_high_cannot_trigger_today_watcher_or_exit():
    ledger = open_fixture()
    ledger.high.at[D3, 'FIXTURE'] = 10000.
    assert ledger.apply_observed_protections(phase='open') == []
    assert ledger.apply_observed_protections(phase='intraday') == []
    assert 'FIXTURE' in ledger.state.positions


def test_partial_regime_reduction_keeps_protection_and_reconciles_cash():
    ledger = open_fixture()
    initial = ledger.state.positions['FIXTURE'].quantity
    partial = ledger.close_resolved([dict(symbol='FIXTURE', exit_date=D2,
        exit_price=100., exit_reason='regime_reduce', quantity=initial/2)], phase='open')
    assert len(partial) == 1
    assert ledger.state.positions['FIXTURE'].quantity == pytest.approx(initial/2)
    assert ledger.protections['FIXTURE'].signals_df.filled_qty.iloc[0] == pytest.approx(initial/2)
    ledger.mark_close()
    assert len(ledger.snapshot().open_orders) == 2
    ledger.finish_day()
    ledger.begin_day(D3)
    ledger.close_resolved([dict(symbol='FIXTURE', exit_date=D3,
        exit_price=100., exit_reason='terminal')], phase='close')
    ledger.mark_close()
    ledger.finish_day()
    assert ledger.reconciliation_error() == pytest.approx(0., abs=1e-9)
    assert all(t['pnl'] < 0 for t in ledger.state.closed_trades)


def test_no_tp_fixed_stop_neither_takes_profit_nor_activates_trailing():
    ledger = open_fixture()
    ledger.high.at[D2, 'FIXTURE'] = 150.
    assert ledger.apply_observed_protections(phase='intraday', take_profit_enabled=False,
        trailing_enabled=False) == []
    ledger.mark_close()
    assert len(ledger.snapshot(take_profit_enabled=False).open_orders) == 1
    ledger.finish_day()
    ledger.begin_day(D3)
    assert ledger.apply_observed_protections(phase='open', take_profit_enabled=False,
        trailing_enabled=False) == []
    assert ledger.apply_observed_protections(phase='intraday', take_profit_enabled=False,
        trailing_enabled=False) == []


def test_no_tp_keeps_initial_stop():
    ledger = open_fixture()
    stop = ledger.state.positions['FIXTURE'].replay_initial_stop_price
    ledger.low.at[D2, 'FIXTURE'] = stop-1
    trades = ledger.apply_observed_protections(phase='intraday', take_profit_enabled=False,
        trailing_enabled=False)
    assert trades[0]['exit_reason'] == 'initial_stop'
    assert trades[0]['exit_price'] == stop
