from types import SimpleNamespace

import pandas as pd
import pytest

from scripts.research import us_oracle_dual_thrust_p04 as study
from scripts.research import us_oracle_dual_thrust_p04_audit as review


def frame(closes=None):
    closes=closes if closes is not None else [100.]*10
    times=pd.date_range('2026-01-08 14:30Z',periods=len(closes),freq='5min')
    return pd.DataFrame([dict(symbol='A',bar_timestamp=t,bar_end_timestamp=t+pd.Timedelta(minutes=5),
        open=100.,close=float(c),high=max(100.,c)+.5,low=min(100.,c)-.5) for t,c in zip(times,closes)])


def evaluate(f,prior_high=106.,span=10.):
    observed,notes,event=study.session_entries(f,prior_high,span)
    expected,reasons,metadata=review.scalar_session(f,prior_high,span)
    assert notes==reasons and set(observed)==set(expected)
    for key,value in metadata.items():
        if pd.isna(value):assert pd.isna(event[key])
        else:assert event[key]==value
    for arm,values in expected.items():
        assert observed[arm]==values
    return observed,notes,event


def daily(high,low,close,firstclose=None):
    return pd.DataFrame(dict(high=[high,high],low=[low,low],close=[firstclose or close,close]))


def test_range_not_simply_max_high_minus_min_low():
    prior=[daily(110,90,105),daily(115,95,100),daily(112,91,110),daily(113,94,108)]
    assert study.range_from_prior(prior)==20.
    assert review.scalar_range(prior)==20.


def test_range_uses_last_regular_close_not_all_intraday_closes():
    prior=[daily(110,90,101,109),daily(110,90,102),daily(110,90,103),daily(110,90,104)]
    assert study.range_from_prior(prior)==review.scalar_range(prior)==14.


def test_exactly_four_sessions_required():
    for fn in (study.range_from_prior,review.scalar_range):
        with pytest.raises(ValueError,match='FOUR'):fn([daily(10,9,9.5)]*3)


def test_zero_range_rejected():
    for fn in (study.range_from_prior,review.scalar_range):
        with pytest.raises(ValueError,match='NONPOSITIVE'):fn([daily(10,10,10)]*4)


def test_first_up_buys_both_p04_and_timing_control():
    f=frame([100,106,107,108,100])
    signals,_,event=evaluate(f)
    assert signals['P04']['timestamp']==f.bar_timestamp.iloc[2]
    assert signals['P04']==signals['TIME_LONG']
    assert event['first_direction']=='UP'


def test_first_down_abstains_even_if_up_later():
    f=frame([100,94,100,106,108,109,100])
    signals,notes,event=evaluate(f)
    assert 'P04' not in signals and notes['P04']=='DOWN_FIRST_ABSTAIN'
    assert signals['TIME_LONG']['timestamp']==f.bar_timestamp.iloc[2]
    assert signals['TIME_LONG']['trigger_direction']=='DOWN'
    assert 'HIGH_J' in signals and event['first_direction']=='DOWN'


def test_no_intra_bar_high_low_touch_signal():
    f=frame();f.loc[0,['high','low']]=[200,1]
    signals,notes,_=evaluate(f)
    assert 'P04' not in signals and notes['P04']=='NO_DUAL_TRIGGER'


def test_exact_band_equality_not_crossing():
    signals,_,event=evaluate(frame([100,105,95,105,100]))
    assert 'TIME_LONG' not in signals and event['first_direction']=='NONE'


def test_first_bar_can_confirm_but_not_fill_at_same_open():
    f=frame([106,107,108])
    signals,_,_=evaluate(f)
    assert signals['P04']['signal_bar']==f.bar_timestamp.iloc[0]
    assert signals['P04']['timestamp']==f.bar_timestamp.iloc[1]


def test_last_bar_first_trigger_not_filled_tomorrow():
    signals,notes,event=evaluate(frame([100,100,106]))
    assert 'P04' not in signals and 'TIME_LONG' not in signals
    assert notes['P04']=='LAST_BAR_NO_FILL' and event['first_direction']=='UP'


def test_one_bar_session_never_invents_next_open():
    signals,notes,_=evaluate(frame([106]))
    assert signals=={} and notes['P04']=='LAST_BAR_NO_FILL'


def test_future_reversal_does_not_cancel_first_up():
    a=frame([100,106,107,108,109]);b=frame([100,106,107,90,80])
    left,_,_=evaluate(a);right,_,_=evaluate(b)
    assert left['P04']==right['P04']


def test_actual_next_open_not_threshold_price():
    f=frame([100,106,107,108]);f.loc[2,'open']=112.
    signals,_,_=evaluate(f)
    assert signals['P04']['price']==112 and signals['P04']['entry_threshold']==105


def test_opening_gap_alone_not_signal():
    f=frame([120,120,120,120]);f['open']=120.;f['high']=121.;f['low']=119.
    signals,notes,event=evaluate(f)
    assert 'HIGH_J' in signals and 'P04' not in signals
    assert event['upper']==125. and notes['P04']=='NO_DUAL_TRIGGER'


def test_bands_ignore_current_session_final_high_low():
    f=frame([100,106,107,108]);before=evaluate(f)[2]
    f.loc[3,['high','low']]=[1000,1]
    after=evaluate(f)[2]
    assert before==after


def test_j1_winner_requires_fresh_cross_and_two_closes():
    f=frame([100,107,108,109,100]);signals,_,_=evaluate(f)
    assert signals['J1_WINNER']['timestamp']==f.bar_timestamp.iloc[3]
    assert signals['HIGH_J']['timestamp']==f.bar_timestamp.iloc[2]


def test_gap_above_high_j_not_fresh_winner_cross():
    f=frame([108,108,108,108]);signals,_,_=evaluate(f)
    assert 'HIGH_J' in signals and 'J1_WINNER' not in signals


def test_j1_winner_last_bar_confirmation_has_no_fill():
    signals,_,_=evaluate(frame([100,107,108]))
    assert 'J1_WINNER' not in signals


def test_high_j_first_last_bar_has_no_fill():
    signals,notes,_=evaluate(frame([100,100,107]))
    assert 'HIGH_J' not in signals and notes['HIGH_J']=='NO_SAME_SESSION_HIGH_J_FILL'


def test_nonpositive_lower_band_reserved():
    for fn in (study.session_entries,review.scalar_session):
        with pytest.raises(ValueError,match='INVALID_OPENING'):fn(frame(),106.,300.)


def test_noncontiguous_session_rejected():
    f=frame().drop(index=3).reset_index(drop=True)
    with pytest.raises(ValueError,match='NONCONTIGUOUS'):study.session_entries(f,106,10)


def test_mixed_sessions_rejected():
    f=frame();f.loc[4:,'bar_timestamp']+=pd.Timedelta(days=1);f.loc[4:,'bar_end_timestamp']+=pd.Timedelta(days=1)
    with pytest.raises(ValueError):study.session_entries(f,106,10)


def selection_fixture():
    days=pd.bdate_range('2026-01-02',periods=45)
    schedule=pd.DataFrame(dict(date=days,market_open=days.tz_localize('UTC')+pd.Timedelta(hours=14,minutes=30),
                               market_close=days.tz_localize('UTC')+pd.Timedelta(hours=21)))
    # Oracle at Jan7, first session Jan8. Four complete prior data fixtures.
    f=frame([100,107,108,109,100]);groups={('A',d):daily(106,96,100) for d in days[:4]}
    groups['A',days[4]]=f
    return SimpleNamespace(pair_id=1,symbol='A',oracle_date=days[3]),groups,schedule


def test_full_selector_independent_match(monkeypatch):
    row,groups,schedule=selection_fixture()
    observed,notes,event,why=study.select_entries(row,groups,schedule)
    expected,reasons,metadata,reserved=review.selection(row,groups,schedule,study.parent.END)
    assert why==reserved is None and notes==reasons and event==metadata
    assert observed==expected
    monkeypatch.setattr(study,'range_from_prior',lambda *a:(_ for _ in ()).throw(RuntimeError('primary forbidden')))
    assert review.selection(row,groups,schedule,study.parent.END)[1]==reasons


def test_missing_oldest_prior_session_reserves_all():
    row,groups,schedule=selection_fixture();del groups['A',schedule.date.iloc[0]]
    assert study.select_entries(row,groups,schedule)[-1]=='MISSING_FOUR_PRIOR_SESSIONS'
    assert review.selection(row,groups,schedule,study.parent.END)[-1]=='MISSING_FOUR_PRIOR_SESSIONS'


def test_missing_j1_session_not_skipped_to_later_day():
    row,groups,schedule=selection_fixture();del groups['A',schedule.date.iloc[4]]
    assert study.select_entries(row,groups,schedule)[-1]=='MISSING_J1_SESSION'


def test_source_availability_strictly_before_entry():
    row,groups,schedule=selection_fixture();signals,_,_,_=study.select_entries(row,groups,schedule)
    for signal in signals.values():
        assert signal['range_available_at']<signal['band_known_at']<signal['timestamp']
        assert signal['range_source_end']==row.oracle_date


def test_known_lookback_action_reserves_even_without_hold_entry():
    row,groups,schedule=selection_fixture()
    actions=pd.DataFrame([dict(symbol='A',ex_date=schedule.date.iloc[1])])
    assert study.common_reservation(row,{},groups,schedule,actions)=='KNOWN_LOOKBACK_CORPORATE_ACTION'
    assert review.reservation(row,{},groups,schedule,actions,study.parent.END)=='KNOWN_LOOKBACK_CORPORATE_ACTION'


def test_missing_future_day_reserved_not_removed_after_short_stop():
    row,groups,schedule=selection_fixture();entries,_,_,_=study.select_entries(row,groups,schedule)
    assert review.reservation(row,entries,groups,schedule,pd.DataFrame(),study.parent.END)=='COMMON_H20_MISSING_SESSION'


def test_single_predeclared_configuration_not_grid():
    assert study.RULE['prior_sessions']==4 and study.RULE['range_multiplier']==.5
    assert study.RULE['trigger_confirmation_bars']==1
