from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from backtesting.research_intraday_native import IntradayNativeLedger, evidence_reasons, fingerprint
from common.trading_costs import TradingCostModel
from risk_management.config import RiskConfig
from risk_management.models import PriceInfo


def calendar():
    # Short synthetic sessions for component tests, not a historical NYSE claim.
    return pd.DataFrame([dict(date=pd.Timestamp(d), market_open=pd.Timestamp(d+' 14:30Z'),
        market_close=pd.Timestamp(d+' 14:45Z')) for d in ['2025-01-02', '2025-01-03', '2025-01-06']])


def risk(**overrides):
    return RiskConfig(account_equity=4000, risk_per_trade_pct=.02, max_positions=8,
        max_short_positions=8, max_position_weight=.25, max_sector_weight=.5,
        max_gross_exposure=1., min_position_notional=0., allow_fractional_shares=False,
        short_selling_enabled=True, **overrides)


def ledger(**kwargs):
    return IntradayNativeLedger(calendar(), risk=risk(), strict=False, **kwargs)


def info(day='2025-01-02', symbol='ABC', price=100):
    return PriceInfo(symbol, price, 2., price_asof_date=pd.Timestamp(day).date(),
        atr_asof_date=(pd.Timestamp(day)-pd.Timedelta(days=1)).date(), adv_usd=100_000_000.)


def start(l, day='2025-01-02', price=100.):
    l.begin_bar(pd.Timestamp(day+' 14:30Z'), {'ABC': price})


def buy(l, side='buy', day='2025-01-02', **kwargs):
    return l.enter('ABC', side, info(day), sector='Industrials', signal_time=l.now, **kwargs)


def finish(l, price=100.):
    for k in range(3):
        if k:
            l.begin_bar(pd.Timestamp(str(l.day.date())+' 14:30Z')+pd.Timedelta(minutes=5*k), {'ABC': price})
        l.observe_bar({'ABC': [price, price, price, price]})
    return l.finish_day()


@pytest.mark.parametrize('side,expected_cash', [('buy', 3499.6), ('sell', 4499.6)])
def test_native_directional_cash_and_mark(side, expected_cash):
    l = ledger()
    start(l)
    assert buy(l, side)
    assert l.state.positions['ABC'].quantity == 5
    assert l.state.settled_cash == pytest.approx(expected_cash)
    assert l.equity() == pytest.approx(3999.6)
    assert l.buying_power() == pytest.approx(3499.6)


@pytest.mark.parametrize('side,exit_price,pnl', [('buy', 110., 49.16), ('sell', 90., 49.24)])
def test_native_exit_cashflow_conservation(side, exit_price, pnl):
    l = ledger()
    start(l)
    assert buy(l, side)
    trade = l.close('ABC', exit_price, 'TEST_CLOSE')
    assert trade['pnl'] == pytest.approx(pnl)
    assert trade['exit_source'] == 'explicit_replay'
    assert l.equity() == pytest.approx(4000+pnl)
    assert abs(l.reconcile()) < 1e-7


def test_short_sale_credit_not_free_capital():
    l = ledger()
    start(l)
    buy(l, 'sell')
    assert l.state.settled_cash > 4000
    assert l.buying_power() < 3500
    assert l.gross() == 500


def test_strict_mode_blocks_unqualified_both_sides():
    for side in ['buy', 'sell']:
        l = IntradayNativeLedger(calendar(), risk=risk(), strict=True)
        start(l)
        assert not buy(l, side)
        assert not l.state.positions
        reasons = l.audit[-1]['reasons']
        assert 'MISSING_QUOTE' in reasons and 'MISSING_RISK' in reasons
        assert ('MISSING_BORROW' in reasons) == (side == 'sell')


def test_prior_session_atr_no_future_same_day():
    l = ledger()
    start(l)
    p = replace(info(), atr_asof_date=l.day.date())
    assert not l.enter('ABC', 'buy', p, sector='Industrials', signal_time=l.now)


def test_missing_sector_blocked_not_unknown_neutral():
    l = ledger()
    start(l)
    assert not l.enter('ABC', 'buy', info(), sector='Unknown', signal_time=l.now)


def test_same_bar_close_cannot_finance_earlier_open():
    l = ledger()
    start(l)
    buy(l)
    l.close('ABC', 95., 'STOP', phase='INTRABAR')
    with pytest.raises(ValueError, match='phase'):
        buy(l)


def test_native_costs_exact_once_per_leg():
    costs = TradingCostModel(spread_bps=10., commission_bps=2., slippage_bps=3., borrow_fee_annual=0.)
    l = ledger(costs=costs)
    start(l)
    buy(l)
    t = l.close('ABC', 100, 'CLOSE')
    assert t['quantity'] == 5
    assert t['pnl'] == pytest.approx(-1.5)
    assert l.reconcile() == pytest.approx(0)


def test_five_minute_bars_do_not_accrue_five_minute_borrow_days():
    l = ledger()
    start(l)
    buy(l, 'sell')
    finish(l)
    start(l, '2025-01-03')
    t = l.close('ABC', 100, 'NEXT_DAY')
    assert t['borrow_cost'] == pytest.approx(500*.003/252)
    assert t['holding_days'] == 1
    assert l.reconcile() == pytest.approx(0)


def test_skip_session_or_intraday_gap_rejected():
    l = ledger()
    start(l)
    l.observe_bar({'ABC': [100]*4})
    with pytest.raises(ValueError, match='Skipped intraday'):
        l.begin_bar(pd.Timestamp('2025-01-02 14:40Z'), {'ABC': 100})


def test_daily_close_only_once_and_no_reset_equity():
    l = ledger()
    start(l)
    buy(l)
    l.close('ABC', 110, 'TEST')
    end = finish(l)
    with pytest.raises(ValueError):
        l.finish_day()
    start(l, '2025-01-03')
    assert l.equity() == pytest.approx(end)


@pytest.mark.parametrize('side,bar,expected', [
    ('buy', [100, 140, 96, 110], 105.),
    ('sell', [100, 104, 60, 90], 69.)])
def test_trailing_uses_only_previously_completed_bar(side, bar, expected):
    l = ledger()
    start(l)
    buy(l, side)
    l.observe_bar({'ABC': bar})
    assert 'ABC' in l.state.positions
    l.begin_bar(pd.Timestamp('2025-01-02 14:35Z'), {'ABC': expected})
    l.resolve_open()
    assert not l.state.positions
    assert l.state.closed_trades[-1]['exit_price'] == expected


@pytest.mark.parametrize('side,bar,stop', [
    ('buy', [100, 130, 94, 110], 95.), ('sell', [100, 106, 70, 90], 105.)])
def test_tp_stop_collision_conservative(side, bar, stop):
    l = ledger(tp=.1)
    start(l)
    buy(l, side)
    l.observe_bar({'ABC': bar})
    assert l.state.closed_trades[-1]['exit_price'] == stop


def test_gap_stop_can_exceed_planned_loss():
    l = ledger()
    start(l)
    buy(l)
    l.observe_bar({'ABC': [100]*4})
    l.begin_bar(pd.Timestamp('2025-01-02 14:35Z'), {'ABC': 60})
    l.resolve_open()
    assert l.state.closed_trades[-1]['exit_price'] == 60
    assert l.state.closed_trades[-1]['pnl'] < -200


def test_future_entry_signal_rejected():
    l = ledger()
    start(l)
    with pytest.raises(ValueError):
        l.enter('ABC', 'buy', info(), sector='Industrials', signal_time=l.now+pd.Timedelta(minutes=5))


@pytest.mark.parametrize('side,sign', [('buy', 1), ('sell', -1)])
def test_dividend_ex_entitlement_payable_cash_and_conservation(side, sign):
    l = ledger()
    start(l)
    buy(l, side)
    finish(l)
    start(l, '2025-01-03', 99)
    cash = l.state.settled_cash
    event = dict(event_id='D1', symbol='ABC', kind='cash_dividend', ex_date='2025-01-03',
        payable_date='2025-01-06', amount_per_share=1., currency='USD', source_sha256='a'*64)
    l.corporate_action(event)
    l.corporate_action(event)  # Idempotent, never double pay/accrue.
    assert l.state.settled_cash == cash
    assert l.claims['D1']['amount'] == 5*sign
    l.close('ABC', 99, 'CLOSE')
    l.reconcile()
    finish(l, 99)
    cash = l.state.settled_cash
    start(l, '2025-01-06', 99)
    assert not l.claims
    assert l.state.settled_cash == pytest.approx(cash+5*sign)
    l.reconcile()


def test_split_updates_qty_price_protections_not_cashflow():
    l = ledger()
    start(l)
    buy(l)
    finish(l)
    start(l, '2025-01-03', 50)
    cash = l.state.settled_cash
    l.corporate_action(dict(event_id='S1', symbol='ABC', kind='split', ratio=2.,
        ex_date='2025-01-03', currency='USD', source_sha256='a'*64))
    p = l.state.positions['ABC']
    assert p.quantity == 10 and p.entry_price == 50 and p.initial_stop_price == 47.5
    assert l.state.settled_cash == cash
    l.close('ABC', 50, 'CLOSE')
    assert l.reconcile() == pytest.approx(0)


def test_unsupported_fractional_split_fails_before_mutation():
    l = ledger()
    start(l)
    buy(l)
    finish(l)
    start(l, '2025-01-03')
    with pytest.raises(ValueError, match='Unsupported split'):
        l.corporate_action(dict(event_id='S', symbol='ABC', kind='split', ratio=.5,
            ex_date='2025-01-03', currency='USD', source_sha256='a'*64))
    assert l.state.positions['ABC'].quantity == 5


def test_quote_future_or_stale_not_usable():
    now = pd.Timestamp('2025-01-02 14:40Z')
    base = dict(symbol='ABC', source_sha256='a'*64, available_at=now+pd.Timedelta(days=1),
        valid_until=now+pd.Timedelta(days=2), source_timestamp=now, bid=99., ask=101.,
        feed='sip', bid_size=10, ask_size=10)
    reasons = evidence_reasons('ABC', 'buy', now, {'quote': base})
    assert 'NON_CAUSAL_OR_STALE_QUOTE' in reasons
    base['available_at'] = now-pd.Timedelta(minutes=10)
    base['source_timestamp'] = base['available_at']
    assert 'INVALID_QUOTE' in evidence_reasons('ABC', 'buy', now, {'quote': base})


def test_unknown_borrow_not_assumed_free_easy_to_borrow():
    now = pd.Timestamp('2025-01-02 14:40Z')
    r = dict(symbol='ABC', source_sha256='a'*64, available_at=now,
        valid_until=now+pd.Timedelta(hours=1), shortable=True, marginable=True,
        annual_fee=0., holding_cost_coverage=False)
    reasons = evidence_reasons('ABC', 'sell', now, {'borrow': r})
    assert 'MISSING_CONFIRMED_LOCATE' in reasons
    assert 'UNQUALIFIED_BORROW_COST_OR_MARGIN' in reasons


def test_readiness_unknown_corporate_events_not_zero_events():
    now = pd.Timestamp('2025-01-02 14:40Z')
    r = dict(symbol='ABC', source_sha256='a'*64, available_at=now,
        valid_until=now+pd.Timedelta(hours=1), coverage_complete=False)
    assert 'UNKNOWN_CORPORATE_ACTION_COVERAGE' in evidence_reasons('ABC', 'buy', now, {'corporate_actions': r})


def test_margin_low_equity_blocks_new_short_only():
    l = IntradayNativeLedger(calendar(), risk=replace(risk(), account_equity=1900), strict=False)
    start(l)
    assert not buy(l, 'sell')
    assert buy(l, 'buy')


def test_native_mutation_failure_cannot_be_retried_in_place(monkeypatch):
    l = ledger()
    start(l)
    def broken(**kwargs):
        raise RuntimeError('Injected native mutation failure')
    monkeypatch.setattr(l.engine, '_try_open_entries', broken)
    with pytest.raises(RuntimeError):
        buy(l)
    with pytest.raises(ValueError, match='checkpoint'):
        buy(l)


def test_expired_campaign_cannot_reenter_at_expiry_open():
    l = ledger()
    l.begin_bar(pd.Timestamp('2025-01-02 14:30Z'), {'ABC': 100}, expiry_symbols=['ABC'])
    assert not buy(l)
    assert 'EXPIRED_CAMPAIGN' in l.audit[-1]['reasons']


def test_native_trade_trackers_count_once():
    l = ledger()
    start(l)
    buy(l)
    tracker = l.engine._concentration_trade_tracker
    assert tracker.to_summary()['total_entries'] == 1
    l.close('ABC', 95., 'CLOSE')
    losses = l.engine._concentration_loss_tracker.to_dict()
    assert max(losses['streak'].values()) == 1


def test_native_random_side_cash_formula_without_borrow():
    rng = np.random.default_rng(20261021)
    for side in ['buy', 'sell']:
        for price in rng.uniform(60, 140, 30):
            l = ledger(costs=TradingCostModel(borrow_fee_annual=0.))
            start(l)
            assert buy(l, side)
            quantity = l.state.positions['ABC'].quantity
            expected = quantity*(float(price)-100)*(1 if side == 'buy' else -1)-quantity*(100+price)*.0008
            t = l.close('ABC', float(price), 'TEST')
            assert t['pnl'] == pytest.approx(expected)
            assert l.equity() == pytest.approx(4000+expected)
            l.reconcile()


def strict_receipts(l, side):
    base = dict(symbol='ABC', available_at=l.now, valid_until=l.now+pd.Timedelta(minutes=5), source_sha256='a'*64)
    return dict(quote=dict(base, source_timestamp=l.now, bid=99.98, ask=100.02, bid_size=100., ask_size=100., feed='sip'),
        risk=dict(base, side=side, producer='PortfolioBuilder', config_hash=fingerprint(l.risk),
            state_hash=fingerprint(l._account_state()), regime_qualified=True, sector_pit=True,
            correlation_qualified=True, approved_shares=5),
        corporate_actions=dict(base, coverage_complete=True),
        borrow=dict(base, shortable=True, marginable=True, borrow_status='easy_to_borrow',
            annual_fee=.06, fee_basis='ANNUAL_252_ENTRY_NOTIONAL', holding_cost_coverage=True))


def test_strict_component_uses_fresh_quote_spread_not_default_twice():
    l = IntradayNativeLedger(calendar(), risk=risk(), strict=True)
    start(l)
    assert buy(l, evidence=strict_receipts(l, 'buy'))
    #4bps full spread /2 +1bps commission +2bps slippage =5bps entry.
    assert l.state.positions['ABC'].entry_cash_flow == pytest.approx(-500.25)
    assert l.engine._concentration_trade_tracker.to_summary()['total_entries'] == 1


def test_strict_short_uses_qualified_constant_native_rate_not_default():
    l = IntradayNativeLedger(calendar(), risk=risk(), strict=True)
    start(l)
    assert buy(l, 'sell', evidence=strict_receipts(l, 'sell'))
    finish(l)
    start(l, '2025-01-03')
    t = l.close('ABC', 100, 'CLOSE')
    assert t['borrow_cost'] == pytest.approx(500*.06/252)
    assert l.engine._cost_model.borrow_fee_annual == .003  # Restored, no cross-symbol leakage.
    l.reconcile()


def test_strict_short_rejects_unimplemented_calendar_rate_convention():
    l = IntradayNativeLedger(calendar(), risk=risk(), strict=True)
    start(l)
    evidence = strict_receipts(l, 'sell')
    evidence['borrow']['fee_basis'] = 'ACTUAL_CALENDAR_360_VARIABLE_MARKET_NOTIONAL'
    assert not buy(l, 'sell', evidence=evidence)
    assert 'UNSUPPORTED_HISTORICAL_BORROW_FEE_BASIS' in l.audit[-1]['reasons']
