import pandas as pd
import pytest

from scripts.research.us_oracle_grid_robustness_audit import cost_identity, verify_admissions


@pytest.mark.parametrize('side,exit_price', [('buy', 110.), ('sell', 90.)])
def test_stress_fees_charged_on_both_legs_and_wrong_rate_rejected(side, exit_price):
    sign = 1 if side == 'buy' else -1
    fee = .0025
    borrow = 0. if side == 'buy' else .1
    pnl = sign*2*(exit_price-100)-fee*2*(100+exit_price)-borrow
    t = pd.DataFrame([dict(quantity=2., entry_price=100., exit_price=exit_price, pnl=pnl, borrow_cost=borrow)])
    c = dict(side=side, fee_bps=25., financing_usd=0., net_pnl_usd=pnl)
    assert cost_identity(t, [], c)['max_error_usd'] < 1e-9
    with pytest.raises(ValueError, match='identity failed'):
        cost_identity(t, [], dict(c, fee_bps=8.))


def test_open_position_fees_and_borrow_are_not_lost_from_mtm():
    opened = [dict(qty=2, entry_price=100., mark=110., borrow_accrued_usd=.2, unrealized_pnl_usd=-20.7)]
    c = dict(side='sell', fee_bps=25., financing_usd=0., net_pnl_usd=-20.7)
    assert cost_identity(pd.DataFrame(), opened, c)['max_error_usd'] < 1e-9
    with pytest.raises(ValueError, match='identity failed'):
        cost_identity(pd.DataFrame(), opened, dict(c, net_pnl_usd=-20.5))


def test_stressed_entry_must_follow_declared_signal_and_actual_open():
    ts = pd.Timestamp('2025-01-03T15:05:00Z')
    eligibility = [dict(pair_id=1, reason='KEEP', decision_time=ts, original_time=ts-pd.Timedelta(minutes=5))]
    t = pd.DataFrame([dict(pair_id=1, symbol='A', side='buy', entry_timestamp=ts, entry_price=100.)])
    paths = {1: pd.DataFrame([dict(bar_timestamp=ts, open=100.)])}
    c = dict(side='buy', delay_bars=1, excluded_symbols=[], excluded_quarter=None)
    assert verify_admissions(t, [], eligibility, c, paths) == 1
    with pytest.raises(ValueError, match='Excluded symbol'):
        verify_admissions(t, [], eligibility, dict(c, excluded_symbols=['A']), paths)
    with pytest.raises(ValueError, match='delay'):
        verify_admissions(t, [], eligibility, dict(c, delay_bars=0), paths)
