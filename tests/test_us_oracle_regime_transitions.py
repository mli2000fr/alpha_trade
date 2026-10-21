import numpy as np
import pandas as pd
import pytest

from scripts.research.us_oracle_regime_transitions import annotate_history, lot_daily_attribution, phase_summary


def regimes(states):
    days = pd.bdate_range('2025-01-01', periods=len(states)+1)
    return pd.DataFrame(dict(date=days[1:], source_date=days[:-1], regime=states))


def test_last_change_defines_disjoint_causal_five_session_window():
    g = annotate_history(regimes(['BULL']*7+['CORRECTION']*7))
    assert g.phase.iloc[0] == 'LEFT_CENSORED'
    assert g.phase.iloc[5] == 'STABLE'
    assert g.phase.iloc[7] == 'CHANGE_DAY'
    assert g.primary_phase.iloc[7:12].eq('RECENT_0_4').all()
    assert g.phase.iloc[12] == 'STABLE'
    assert g.sessions_since_change.iloc[12] == 5


def test_future_changes_do_not_relabel_prior_decisions():
    base = regimes(['BULL']*12+['CORRECTION']*8)
    changed = base.copy(); changed.loc[15:, 'regime'] = 'SLIDE'
    pd.testing.assert_frame_equal(annotate_history(base).iloc[:15], annotate_history(changed).iloc[:15])


def test_rapid_changes_reset_age_not_overlap_primary_counts():
    g = annotate_history(regimes(['BULL']*7+['SLIDE', 'REBOUND', 'BULL']+['BULL']*5))
    assert g.phase.iloc[7:10].eq('CHANGE_DAY').all()
    assert g.sessions_since_change.iloc[10] == 1
    assert g.changes_in_last20.iloc[10] == 3


def test_current_session_source_is_rejected():
    g = regimes(['BULL']*10)
    g.loc[5, 'source_date'] = g.loc[5, 'date']
    with pytest.raises(ValueError, match='noncausal'):
        annotate_history(g)


def toy_prices():
    days = pd.bdate_range('2025-01-06', periods=3)
    return days, {days[0]: dict(open=99., close=102.), days[1]: dict(open=101., close=103.),
                  days[2]: dict(open=104., close=106.)}


@pytest.mark.parametrize('side', ['buy', 'sell'])
def test_decomposition_distinguishes_new_entry_overnight_and_actual_exit(side):
    days, prices = toy_prices()
    r = dict(symbol='A', pair_id=1, qty=2., entry_price=100., exit_price=105., borrow_cost=.1 if side == 'sell' else 0.,
        entry_timestamp=days[0].tz_localize('America/New_York')+pd.Timedelta(hours=10),
        exit_timestamp=days[2].tz_localize('America/New_York')+pd.Timedelta(hours=10))
    table = pd.DataFrame(lot_daily_attribution(r, days, prices, side))
    sign = 1 if side == 'buy' else -1
    expected = sign*2*(105-100)-.0008*2*(100+105)-r['borrow_cost']
    assert np.isclose(table.net_pnl_usd.sum(), expected)
    assert table.cohort.tolist() == ['NEW_ENTRY', 'HELD_OVERNIGHT', 'HELD_OVERNIGHT']
    assert table.overnight_price_pnl_usd.tolist() == [0., sign*(-2.), sign*2.]
    assert table.borrow_posted_usd.iloc[:2].sum() == 0


def test_open_mtm_cost_recognized_at_account_end_not_invented_daily():
    days, prices = toy_prices()
    r = dict(symbol='A', pair_id=1, qty=2., entry_price=100., borrow_accrued_usd=.3,
             entry_timestamp=days[0].tz_localize('America/New_York')+pd.Timedelta(hours=10))
    table = pd.DataFrame(lot_daily_attribution(r, days, prices, 'sell'))
    assert np.isclose(table.net_pnl_usd.sum(), -12-.16-.3)
    assert table.borrow_posted_usd.tolist() == [0., 0., .3]


def test_same_day_roundtrip_has_no_overnight_and_both_fees():
    days, prices = toy_prices()
    r = dict(symbol='A', pair_id=1, qty=1., entry_price=100., exit_price=102., borrow_cost=0.,
        entry_timestamp=days[0].tz_localize('America/New_York')+pd.Timedelta(hours=10),
        exit_timestamp=days[0].tz_localize('America/New_York')+pd.Timedelta(hours=11))
    table = pd.DataFrame(lot_daily_attribution(r, days, prices, 'buy'))
    assert len(table) == 1 and table.overnight_price_pnl_usd.iloc[0] == 0
    assert np.isclose(table.net_pnl_usd.iloc[0], 2-.0008*202)


def test_missing_held_session_price_is_not_forward_filled():
    days, prices = toy_prices(); del prices[days[1]]
    r = dict(symbol='A', pair_id=1, qty=1., entry_price=100., borrow_accrued_usd=0.,
             entry_timestamp=days[0].tz_localize('America/New_York')+pd.Timedelta(hours=10))
    with pytest.raises(ValueError, match='Missing actual held'):
        lot_daily_attribution(r, days, prices, 'buy')
