from dataclasses import replace
from functools import partial

import pandas as pd
import pytest

from scripts.research.us_concentrated_live_portfolio import run_portfolio
from scripts.research.us_oracle_merger_ledger import MergerLedger, exchange_quantities
from service.market import parse_market_regimes
from tests.test_us_concentrated_live_portfolio import fixture_data


def test_exchange_ratio_is_applied_once_and_fraction_not_rounded_up():
    whole, fraction, total = exchange_quantities(10, '2.793', cash_fraction=True)
    assert whole == 27
    assert fraction == pytest.approx(.93)
    assert total == pytest.approx(27.93)
    assert exchange_quantities(10, '1', cash_fraction=False) == (10., 0., 10.)


@pytest.mark.parametrize('q,r', [(0, '2'), (1, '-1'), (1, 'NaN')])
def test_invalid_share_exchange_fails(q, r):
    with pytest.raises(ValueError):
        exchange_quantities(q, r, cash_fraction=True)


def converted_fixture():
    frames, scores, macro, days = fixture_data()
    for name, frame in frames.items():
        frame['NEW'] = frame.FIXTURE if name == 'volume' else frame.FIXTURE/2
    event = dict(source='FIXTURE', target='NEW', day=str(days[4].date()), ratio='2',
                 cash_fraction=False, trading_symbol='NEW')
    return frames, scores, macro, days, event


def test_native_conversion_preserves_cash_basis_stop_tp_and_expiry(tmp_path):
    frames, scores, macro, days, event = converted_fixture()
    result = run_portfolio(frames=frames, scores=scores, sectors={'FIXTURE': 'Technology', 'NEW': 'Technology'},
        macro=macro, market_config=parse_market_regimes({'enabled': False}), policy='ORACLE_TOP10',
        variant='CURRENT_NO_EXPIRY', output=tmp_path, expiry_open_sessions=20,
        decision_end_date=days[0], ledger_factory=partial(MergerLedger, events=(event,)),
        protection_options=dict(take_profit_enabled=True, trailing_enabled=False))
    trade = pd.read_parquet(tmp_path/'trades.parquet').iloc[0]
    assert trade.symbol == 'NEW'
    assert trade.entry_symbol == 'FIXTURE'
    assert trade.entry_price == 50.
    assert trade.replay_initial_stop_price == 46.5
    assert trade.replay_take_profit_price == 60.
    assert trade.exit_date == days[21]  # Not twenty sessions from conversion.
    assert result['account_wealth_complete']
    assert abs(result['cash_reconciliation_error']) < 1e-8


def test_strict_rejects_cash_fraction_instead_of_assuming_a_price(tmp_path):
    frames, scores, macro, days, event = converted_fixture()
    event = dict(event, ratio='2.793', cash_fraction=True)
    with pytest.raises(ValueError, match='Unqualified cash-in-lieu'):
        run_portfolio(frames=frames, scores=scores, sectors={'FIXTURE': 'Technology', 'NEW': 'Technology'},
            macro=macro, market_config=parse_market_regimes({'enabled': False}), policy='ORACLE_TOP10',
            variant='CURRENT_NO_EXPIRY', output=tmp_path, expiry_open_sessions=20,
            decision_end_date=days[0], ledger_factory=partial(MergerLedger, events=(event,)))


def test_unvalued_claim_is_unavailable_not_a_realised_zero_payment(tmp_path):
    frames, scores, macro, days, event = converted_fixture()
    event = dict(event, ratio='2.793', cash_fraction=True)
    for name, frame in frames.items():
        if name != 'volume':
            frame.NEW = frame.FIXTURE/2.793
    result = run_portfolio(frames=frames, scores=scores, sectors={'FIXTURE': 'Technology', 'NEW': 'Technology'},
        macro=macro, market_config=parse_market_regimes({'enabled': False}), policy='ORACLE_TOP10',
        variant='CURRENT_NO_EXPIRY', output=tmp_path, expiry_open_sessions=20,
        decision_end_date=days[0], ledger_factory=partial(MergerLedger, events=(event,), cash_policy='UNVALUED_RECEIVABLE'),
        protection_options=dict(take_profit_enabled=True, trailing_enabled=False))
    claim = result['unvalued_fractional_claims'][0]
    assert claim['value'] is None and claim['payment_date'] is None
    assert claim['usable_cash'] == 0.
    assert claim['entry_cash_flow'] < 0
    assert result['cash_in_lieu_pnl'] is None
    assert not result['account_wealth_complete']
    assert not result['full_broker_corporate_action_parity']
    assert abs(result['cash_reconciliation_error']) < 1e-8


def test_protection_after_conversion_uses_original_lot_history(tmp_path):
    frames, scores, macro, days, event = converted_fixture()
    # The predecessor of NEW had an unrelated high before we acquired it.
    # This must never be replayed as a retrospective TP for the acquired lot.
    frames['high'].loc[days[1:4], 'NEW'] = 999.
    frames['high'].loc[days[5], 'NEW'] = 65.
    run_portfolio(frames=frames, scores=scores, sectors={'FIXTURE': 'Technology', 'NEW': 'Technology'},
        macro=macro, market_config=parse_market_regimes({'enabled': False}), policy='ORACLE_TOP10',
        variant='CURRENT_NO_EXPIRY', output=tmp_path, expiry_open_sessions=20,
        decision_end_date=days[0], ledger_factory=partial(MergerLedger, events=(event,)),
        protection_options=dict(take_profit_enabled=True, trailing_enabled=False))
    trade = pd.read_parquet(tmp_path/'trades.parquet').iloc[0]
    assert trade.exit_date == days[5]
    assert trade.exit_price == 60.


def test_successor_missing_volume_is_not_imputed(tmp_path):
    frames, scores, macro, days, event = converted_fixture()
    frames['volume'].loc[days[4], 'NEW'] = 0.
    with pytest.raises(ValueError, match='Unqualified successor bar'):
        run_portfolio(frames=frames, scores=scores, sectors={'FIXTURE': 'Technology', 'NEW': 'Technology'},
            macro=macro, market_config=parse_market_regimes({'enabled': False}), policy='ORACLE_TOP10',
            variant='CURRENT_NO_EXPIRY', output=tmp_path, expiry_open_sessions=20,
            decision_end_date=days[0], ledger_factory=partial(MergerLedger, events=(event,)))


def test_conversion_gap_stop_executes_at_open_not_at_old_stop(tmp_path):
    frames, scores, macro, days, event = converted_fixture()
    for name, price in [('opens', 40.), ('close', 40.), ('high', 41.), ('low', 39.)]:
        frames[name].loc[days[4], 'NEW'] = price
    run_portfolio(frames=frames, scores=scores, sectors={'FIXTURE': 'Technology', 'NEW': 'Technology'},
        macro=macro, market_config=parse_market_regimes({'enabled': False}), policy='ORACLE_TOP10',
        variant='CURRENT_NO_EXPIRY', output=tmp_path, expiry_open_sessions=20,
        decision_end_date=days[0], ledger_factory=partial(MergerLedger, events=(event,)),
        protection_options=dict(take_profit_enabled=True, trailing_enabled=False))
    trade = pd.read_parquet(tmp_path/'trades.parquet').iloc[0]
    assert trade.exit_date == days[4]
    assert trade.exit_price == 40.
    assert trade.replay_initial_stop_price == 46.5


def test_ratio_one_ticker_change_preserves_original_expiry(tmp_path):
    frames, scores, macro, days, event = converted_fixture()
    for name, frame in frames.items():
        frame['NEW'] = frame.FIXTURE
    event = dict(event, ratio='1')
    result = run_portfolio(frames=frames, scores=scores, sectors={'FIXTURE': 'Technology', 'NEW': 'Technology'},
        macro=macro, market_config=parse_market_regimes({'enabled': False}), policy='ORACLE_TOP10',
        variant='CURRENT_NO_EXPIRY', output=tmp_path, expiry_open_sessions=20,
        decision_end_date=days[0], ledger_factory=partial(MergerLedger, events=(event,)),
        protection_options=dict(take_profit_enabled=True, trailing_enabled=False))
    trade = pd.read_parquet(tmp_path/'trades.parquet').iloc[0]
    assert trade.entry_price == 100.
    assert trade.replay_initial_stop_price == 93.
    assert trade.exit_date == days[21]
    assert result['unvalued_fractional_claims'] == []
