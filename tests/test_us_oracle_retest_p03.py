from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from scripts.research import us_oracle_retest_p03 as study
from scripts.research import us_oracle_retest_p03_audit as review


def frame(n=20):
    times=pd.date_range('2026-01-05 14:30Z',periods=n,freq='5min')
    closes=[99.,101.,102.]+[104.]*(n-3)
    rows=[dict(symbol='A',bar_timestamp=t,bar_end_timestamp=t+pd.Timedelta(minutes=5),
        open=c,high=c+1,low=c-1,close=c) for t,c in zip(times,closes)]
    return pd.DataFrame(rows)


def anchor(f):
    return dict(timestamp=f.bar_timestamp.iloc[3],price=f.open.iloc[3],prior_high=100.,
        signal_close=f.close.iloc[2],signal_bar=f.bar_timestamp.iloc[2],cross_bar=f.bar_timestamp.iloc[1],
        date=pd.Timestamp('2026-01-05'),delay=1)


def evaluate(f):
    found,notes=study.timing_signals(f,anchor(f),1.)
    expected,reasons=review.timing(f,3,100.,1.)
    assert notes==reasons
    assert set(found)==set(expected)
    for arm,(index,touch) in expected.items():
        assert found[arm]['timestamp']==f.bar_timestamp.iloc[index]
        assert found[arm]['price']==f.open.iloc[index]
        assert found[arm]['signal_close']==f.close.iloc[index-1]
        if touch is not None: assert found[arm]['retest_bar']==f.bar_timestamp.iloc[touch]
    return found,notes


def test_no_retest_not_forced_into_trade():
    signals,notes=evaluate(frame())
    assert 'P03' not in signals and notes['P03']=='NO_RETEST_IN_WINDOW'
    assert signals['DELAY_CONTROL']['delay_bars']==6


def test_retest_then_two_distinct_later_closes():
    f=frame();f.loc[4,'low']=100.25
    signals,_=evaluate(f)
    assert signals['P03']['timestamp']==f.bar_timestamp.iloc[7]
    assert signals['P03']['delay_bars']==4


def test_touch_bar_cannot_count_its_own_recovery():
    f=frame();f.loc[3,'low']=100.;f.loc[3,'close']=103.
    signals,_=evaluate(f)
    assert signals['P03']['timestamp']==f.bar_timestamp.iloc[6]


def test_breakout_confirmation_low_not_a_retest():
    f=frame();f.loc[2,'low']=99.
    signals,_=evaluate(f)
    assert 'P03' not in signals


def test_upper_boundary_touch_inclusive():
    f=frame();f.loc[4,'low']=101.
    signals,_=evaluate(f)
    assert 'P03' in signals


def test_lower_boundary_not_invalidated():
    f=frame();f.loc[4,'low']=99.
    signals,_=evaluate(f)
    assert 'P03' in signals


def test_invalidation_strict_lower_boundary():
    f=frame();f.loc[4,'low']=98.999999
    signals,notes=evaluate(f)
    assert not signals
    assert notes['P03']=='INVALIDATED_BEFORE_RETEST_CONFIRMATION'


def test_same_bar_low_invalidation_before_high_recovery():
    f=frame();f.loc[4,['low','high','close']]=[98.,150.,140.]
    signals,_=evaluate(f)
    assert 'P03' not in signals


def test_invalidation_on_confirmation_bar_wins():
    f=frame();f.loc[4,'low']=100.;f.loc[6,['low','high','close']]=[98.,150.,140.]
    signals,_=evaluate(f)
    assert 'P03' not in signals


def test_counter_resets_on_at_level_close():
    f=frame();f.loc[4,'low']=100.;f.loc[5,'close']=100.;f.loc[7,'close']=100.
    signals,_=evaluate(f)
    assert signals['P03']['timestamp']==f.bar_timestamp.iloc[10]
    assert 'DELAY_CONTROL' not in signals


def test_first_touch_remains_first_after_later_touches():
    f=frame();f.loc[4,'low']=100.;f.loc[5,'close']=100.;f.loc[6,'low']=100.
    signals,_=evaluate(f)
    assert signals['P03']['retest_bar']==f.bar_timestamp.iloc[4]


def test_last_allowed_confirmation_can_fill():
    f=frame();f.loc[12,'low']=100.
    signals,_=evaluate(f)
    assert signals['P03']['timestamp']==f.bar_timestamp.iloc[15]
    assert signals['P03']['delay_bars']==12


def test_confirmation_beyond_hour_not_used():
    f=frame();f.loc[13,'low']=100.
    signals,notes=evaluate(f)
    assert 'P03' not in signals and notes['P03']=='RETEST_NOT_CONFIRMED_IN_WINDOW'


def test_last_session_bar_not_filled_tomorrow():
    f=frame(8);f.loc[5,'low']=100.
    signals,_=evaluate(f)
    assert not signals


def test_fixed_delay_not_matched_to_future_retest():
    a=frame();a.loc[4,'low']=100.;b=frame();b.loc[10,'low']=100.
    sa,_=evaluate(a);sb,_=evaluate(b)
    assert sa['DELAY_CONTROL']['timestamp']==sb['DELAY_CONTROL']['timestamp']
    assert sa['P03']['timestamp']!=sb['P03']['timestamp']


def test_future_invalidations_do_not_cancel_earlier_entries():
    f=frame();f.loc[4,'low']=100.;before,_=evaluate(f)
    f.loc[9:,'low']=1.
    after,_=evaluate(f)
    assert before==after


def test_next_open_is_actual_price_not_touch_level():
    f=frame();f.loc[4,'low']=100.;f.loc[7,'open']=112.
    signals,_=evaluate(f)
    assert signals['P03']['price']==112


def test_fixed_delay_invalidation_during_wait():
    f=frame();f.loc[8,'low']=98.
    signals,notes=evaluate(f)
    assert 'DELAY_CONTROL' not in signals
    assert notes['DELAY_CONTROL']=='INVALIDATED_DURING_FIXED_WAIT'


def test_noncontiguous_frame_rejected():
    f=frame().drop(index=8).reset_index(drop=True)
    with pytest.raises(ValueError,match='Noncontiguous'): study.timing_signals(f,anchor(f),1.)


def test_mixed_sessions_rejected():
    f=frame();f.loc[10:,'bar_timestamp']+=pd.Timedelta(days=1);f.loc[10:,'bar_end_timestamp']+=pd.Timedelta(days=1)
    with pytest.raises(ValueError): study.timing_signals(f,anchor(f),1.)


def test_wrong_anchor_confirmation_rejected():
    f=frame();f.loc[2,'close']=100.
    with pytest.raises(ValueError,match='Winner anchor'): study.timing_signals(f,anchor(f),1.)


def test_atr_constant_ranges_and_sma_seed():
    f=frame(25);f[['open','close']]=100.;f['high']=101.;f['low']=99.
    assert study.previous_atr(f)==2.
    assert review.scalar_atr(f)==2.


def test_atr_wilder_tail_independent_calculation():
    f=frame(25);f[['open','close']]=100.;f['high']=101.;f['low']=99.
    f.loc[24,'high']=103.
    assert study.previous_atr(f)==2.1
    assert review.scalar_atr(f)==2.1


def test_atr_missing_warmup_rejected():
    for fn in (study.previous_atr,review.scalar_atr):
        with pytest.raises(ValueError,match='WARMUP'): fn(frame(19))


def test_first_atr_range_uses_high_low_not_previous_session_gap():
    f=frame(20);f[['open','close']]=200.;f['high']=201.;f['low']=199.
    assert study.previous_atr(f)==review.scalar_atr(f)==2.


def test_invalid_atr_rejected_before_signals():
    with pytest.raises(ValueError): study.timing_signals(frame(),anchor(frame()),np.nan)


def test_selector_agrees_with_independent_enumeration(monkeypatch):
    days=pd.bdate_range('2026-01-02',periods=42)
    schedule=pd.DataFrame(dict(date=days,market_open=days.tz_localize('UTC')+pd.Timedelta(hours=14,minutes=30),
                               market_close=days.tz_localize('UTC')+pd.Timedelta(hours=21)))
    f=frame();f.loc[4,'low']=100.
    prev=f.copy();prev.bar_timestamp-=pd.Timedelta(days=3);prev.bar_end_timestamp-=pd.Timedelta(days=3)
    prev[['open','close']]=99.5;prev['high']=100.;prev['low']=99.
    groups={('A',days[0]):prev,('A',days[1]):f}
    row=SimpleNamespace(symbol='A',oracle_date=days[0])
    observed,notes,why=study.select_entries(row,groups,schedule)
    expected,reasons,reserved=review.selection(row,groups,schedule,study.parent.END)
    assert why==reserved is None and notes==reasons
    for arm,e in expected.items():
        for name,value in e.items():
            if pd.isna(value): assert pd.isna(observed[arm][name])
            else: assert observed[arm][name]==value
    monkeypatch.setattr(study,'select_entries',lambda *a:(_ for _ in ()).throw(RuntimeError('primary forbidden')))
    assert review.selection(row,groups,schedule,study.parent.END)[1]==reasons


def test_missing_path_reserves_all_emitted_arms():
    days=pd.bdate_range('2026-01-02',periods=42);schedule=pd.DataFrame(dict(date=days))
    groups={('A',d):frame() for d in days[1:22]};del groups['A',days[8]]
    row=SimpleNamespace(symbol='A');entries={a:dict(date=days[1]) for a in study.TEST_ARMS}
    assert review.reservation(row,entries,groups,schedule,pd.DataFrame(),study.parent.END)=='COMMON_H20_MISSING_SESSION'


def test_known_action_reserves_before_economic_outcomes():
    days=pd.bdate_range('2026-01-02',periods=42);schedule=pd.DataFrame(dict(date=days))
    groups={('A',d):frame() for d in days[1:22]}; row=SimpleNamespace(symbol='A')
    actions=pd.DataFrame([dict(symbol='A',ex_date=days[8])])
    assert review.reservation(row,dict(P03=dict(date=days[1])),groups,schedule,actions,study.parent.END)=='KNOWN_CORPORATE_ACTION'
