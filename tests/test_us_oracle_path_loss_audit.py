import numpy as np
import pandas as pd
import pytest

from scripts.research.us_oracle_path_loss_audit import (aggregate_positions, diagnose_path,
    first_contact, log_constraints, monthly_mtm)


def fixture():
    calendar = pd.bdate_range('2025-01-02', periods=25)
    bars = pd.DataFrame(dict(open=100., high=101., low=99., close=100., volume=1000.,
        is_filled=0,instrument_id='A'), index=calendar)
    row = dict(entry_identity='A',entry_date=calendar[0],exit_date=calendar[3],
        entry_price=100.,max_executed_exit_price=90.)
    return calendar,bars,row


def test_later_rise_is_not_preexit_opportunity_or_replacement_pnl():
    calendar,bars,row = fixture()
    bars.loc[calendar[3],'low'] = 85.
    bars.loc[calendar[9],'high'] = 125.
    result = diagnose_path(row,bars,calendar)
    assert result['first_contact'] == 'SL_FIRST'
    assert result['would_reach_tp20']
    assert result['mfe20_pct'] == pytest.approx(25)
    assert result['preexit_upside_lower_bound_pct'] == pytest.approx(1)
    assert result['dominant_direction'] == 'UP'
    assert 'pnl' not in result


def test_exit_day_high_cannot_be_assumed_before_stop():
    calendar,bars,row = fixture()
    bars.loc[calendar[3],['high','low']] = [125.,85.]
    result = diagnose_path(row,bars,calendar)
    assert result['first_contact'] == 'AMBIGUOUS_SAME_DAY'
    assert result['preexit_upside_lower_bound_pct'] == pytest.approx(1)


@pytest.mark.parametrize('opening,expected', [(100.,'AMBIGUOUS_SAME_DAY'),(85.,'SL_FIRST'),(125.,'TP_FIRST')])
def test_open_contact_precedes_ambiguous_high_low(opening,expected):
    path = pd.DataFrame([dict(date=pd.Timestamp('2025-01-03'),open=opening,high=130.,low=80.)])
    assert first_contact(path,100.)['first_contact'] == expected


def test_twenty_sessions_exclude_expiry_session_high_and_later_prices():
    calendar,bars,row = fixture()
    bars.loc[calendar[20:],'high'] = 1000.
    result = diagnose_path(row,bars,calendar)
    assert result['mfe20_pct'] == pytest.approx(1)
    assert result['first_contact'] == 'NO_CONTACT'
    assert not result['would_reach_tp20']


@pytest.mark.parametrize('problem,status', [('missing','MISSING_OR_INVALID_OHLCV'),
    ('filled','FILLED_OR_UNKNOWN_CHANGED_IDENTITY'),('identity','FILLED_OR_UNKNOWN_CHANGED_IDENTITY'),
    ('basis','ENTRY_PRICE_BASIS_MISMATCH'),('ca','CORPORATE_ACTION_WINDOW_REQUIRES_REBASING')])
def test_unqualified_future_is_unknown_not_losing_or_winning(problem,status):
    calendar,bars,row = fixture()
    events = ()
    if problem=='missing':bars.loc[calendar[8],'volume']=np.nan
    if problem=='filled':bars.loc[calendar[8],'is_filled']=1
    if problem=='identity':bars.loc[calendar[8],'instrument_id']='B'
    if problem=='basis':row['entry_price']=90.
    if problem=='ca':events=({'source':'A','day':str(calendar[8].date())},)
    result=diagnose_path(row,bars,calendar,events)
    assert result == dict(path_status=status)


def test_partial_legs_aggregate_to_one_position_and_keep_costs_and_gap_excess():
    legs = pd.DataFrame([dict(symbol='A',entry_date=pd.Timestamp('2025-01-02'),signal_date=pd.Timestamp('2025-01-01'),
        exit_date=pd.Timestamp('2025-01-03'),entry_price=100.,exit_price=85.,quantity=1.,pnl=-17.,
        sector='S',replay_initial_stop_price=90.,exit_reason='initial_stop_gap_open'),
        dict(symbol='A',entry_date=pd.Timestamp('2025-01-02'),signal_date=pd.Timestamp('2025-01-01'),
        exit_date=pd.Timestamp('2025-01-04'),entry_price=100.,exit_price=120.,quantity=1.,pnl=18.,
        sector='S',replay_initial_stop_price=90.,exit_reason='take_profit')])
    positions, derived = aggregate_positions(legs)
    assert len(positions)==1
    assert positions.pnl.iloc[0] == 1.
    assert positions.trading_cost_usd.iloc[0] == 4.
    assert positions.stop_gap_excess_usd.iloc[0] == 5.
    assert positions.gross_pnl_usd.iloc[0]-positions.trading_cost_usd.iloc[0] == positions.pnl.iloc[0]


def test_monthly_marks_chain_from_initial_capital_not_entry_cohort_pnl():
    daily = pd.DataFrame(dict(date=pd.to_datetime(['2025-01-02','2025-01-31','2025-02-28']),
        equity=[3990.,4050.,3990.],gross_notional=[1000.,2000.,0.],positions=[1,2,0]))
    result=monthly_mtm(daily)
    assert [r['mtm_pnl_usd'] for r in result] == [50.,-60.]
    assert sum(r['mtm_pnl_usd'] for r in result) == -10.


def test_constraint_log_counts_are_scoped_to_case(tmp_path):
    path=tmp_path/'stderr.log'
    path.write_text('INFO Starting 2024 TOP20\nPosition reduite pour A: 10 -> 0 (max_long_positions atteint)\n'
        'Concentration filters: blocked 2 (max trades) + 3 (blacklist) / 10 candidates\n'
        'INFO Starting 2024 TOP50\nPosition reduite pour B: 10 -> 0 (max_long_positions atteint)\n',encoding='utf-8')
    result=log_constraints(path)
    assert result['2024-TOP20']['max_long_positions atteint']==1
    assert result['2024-TOP20']['blacklist_logged_candidate_events']==3
    assert 'blacklist_logged_candidate_events' not in result['2024-TOP50']
