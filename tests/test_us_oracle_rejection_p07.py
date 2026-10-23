from types import SimpleNamespace

import pandas as pd
import pytest

from scripts.research import us_oracle_rejection_p07 as study
from scripts.research import us_oracle_rejection_p07_audit as review


def daily(high=102.,low=100.,close=101.,first_close=None):
    return pd.DataFrame(dict(high=[high,high],low=[low,low],close=[first_close if first_close is not None else close,close]))


def prior():
    return [daily() for _ in range(9)]+[daily(105.,99.,104.)]


def features(frames):
    a=study.daily_features(frames);b=review.features(frames)
    assert a==b
    return a


def calendar():
    days=pd.bdate_range('2026-03-02',periods=52)
    return pd.DataFrame(dict(date=days,market_open=days.tz_localize('UTC')+pd.Timedelta(hours=13,minutes=30),
                            market_close=days.tz_localize('UTC')+pd.Timedelta(hours=20)))


def session(day,closes,opens=None,lows=None):
    times=pd.date_range(day.tz_localize('UTC')+pd.Timedelta(hours=13,minutes=30),periods=len(closes),freq='5min')
    opens=opens if opens is not None else closes
    lows=lows if lows is not None else [min(o,c)-1 for o,c in zip(opens,closes)]
    return pd.DataFrame([dict(symbol='A',bar_timestamp=t,bar_end_timestamp=t+pd.Timedelta(minutes=5),
        open=float(o),high=float(max(o,c)+1),low=float(l),close=float(c)) for t,o,l,c in zip(times,opens,lows,closes)])


def inspect_entry(groups,schedule):
    day=schedule.date.iloc[9]
    a=study.scan_entry('A',day,105.,99.,groups,schedule)
    b=review.entry('A',day,105.,99.,groups,schedule,study.parent.END)
    assert a==b
    return a


def fixture():
    schedule=calendar();days=list(schedule.date)
    groups={('A',d):f for d,f in zip(days[:10],prior())}
    groups['A',days[10]]=session(days[10],[104,106,107])
    row=SimpleNamespace(pair_id=1,symbol='A',rank=1,oracle_date=days[9])
    return row,groups,schedule


def test_three_conditions_required():
    f=features(prior())
    assert f['pattern'] and f['new_low'] and f['widest_range'] and f['upper_quarter']


def test_low_equality_not_new_low():
    f=prior();f[-1]=daily(106,100,105)
    assert not features(f)['new_low'] and not features(f)['pattern']


def test_range_equality_not_largest_strict():
    f=prior();f[0]=daily(106,100,103)
    assert not features(f)['widest_range'] and not features(f)['pattern']


def test_upper_quartile_boundary_inclusive():
    f=prior();f[-1]=daily(105,99,103.5)
    assert features(f)['close_location']==.75 and features(f)['pattern']


def test_below_quartile_not_pattern():
    f=prior();f[-1]=daily(105,99,103.499)
    assert not features(f)['pattern']


def test_last_regular_close_not_earlier_intraday_close():
    f=prior();f[-1]=daily(105,99,104,99)
    assert features(f)['pattern']


def test_flat_j_known_absent_pattern_not_missing():
    f=prior();f[-1]=daily(100,100,100)
    result=features(f)
    assert not result['pattern'] and result['close_location'] is None


def test_nine_or_eleven_sessions_not_accepted():
    for fn in (study.daily_features,review.features):
        with pytest.raises(ValueError,match='TEN'):fn(prior()[:9])
        with pytest.raises(ValueError,match='TEN'):fn(prior()+[daily()])


def test_invalid_daily_observation_unknown_not_false_pattern():
    f=prior();f[-1]=daily(105,99,110)
    for fn in (study.daily_features,review.features):
        with pytest.raises(ValueError,match='INVALID'):fn(f)


def test_one_closed_bar_suffices_next_open_only():
    row,g,sch=fixture();result=inspect_entry(g,sch)
    frame=g['A',sch.date.iloc[10]]
    assert result['status']=='SIGNAL' and result['timestamp']==frame.bar_timestamp.iloc[2]


def test_high_touch_without_close_not_confirmation():
    sch=calendar();d=sch.date.iloc[10];e=sch.date.iloc[11]
    f=session(d,[104,104,104]);f['high']=110
    result=inspect_entry({('A',d):f,('A',e):session(e,[104,104])},sch)
    assert result['status']=='NO_BREAKOUT_TWO_SESSIONS'


def test_high_equality_not_confirmation():
    sch=calendar();d=sch.date.iloc[10];e=sch.date.iloc[11]
    result=inspect_entry({('A',d):session(d,[105,105]),('A',e):session(e,[105,105])},sch)
    assert result['status']=='NO_BREAKOUT_TWO_SESSIONS'


def test_low_equality_not_invalidation():
    sch=calendar();d=sch.date.iloc[10]
    result=inspect_entry({('A',d):session(d,[104,106,107],lows=[99,99,100])},sch)
    assert result['status']=='SIGNAL'


def test_low_break_invalidation_before_same_bar_recovery():
    sch=calendar();d=sch.date.iloc[10]
    result=inspect_entry({('A',d):session(d,[106,107],lows=[98,100])},sch)
    assert result['status']=='LOW_J_INVALIDATED'


def test_no_reentry_after_invalidation():
    sch=calendar();d=sch.date.iloc[10];e=sch.date.iloc[11]
    result=inspect_entry({('A',d):session(d,[100,104],lows=[98,100]),('A',e):session(e,[106,107])},sch)
    assert result['status']=='LOW_J_INVALIDATED'


def test_pending_fill_gap_below_low_cancels_before_entry():
    sch=calendar();d=sch.date.iloc[10]
    result=inspect_entry({('A',d):session(d,[106,107],opens=[106,98],lows=[100,97])},sch)
    assert result['status']=='GAP_BELOW_LOW_J_BEFORE_FILL'


def test_next_open_equal_low_not_cancelled_by_future_low():
    sch=calendar();d=sch.date.iloc[10]
    result=inspect_entry({('A',d):session(d,[106,107],opens=[106,99],lows=[100,80])},sch)
    assert result['status']=='SIGNAL' and result['price']==99


def test_next_bar_future_low_cannot_cancel_entry():
    sch=calendar();d=sch.date.iloc[10]
    result=inspect_entry({('A',d):session(d,[106,107],opens=[106,107],lows=[100,80])},sch)
    assert result['status']=='SIGNAL' and result['price']==107


def test_no_signal_j1_can_continue_to_j2():
    sch=calendar();d=sch.date.iloc[10];e=sch.date.iloc[11]
    result=inspect_entry({('A',d):session(d,[104,104]),('A',e):session(e,[106,107])},sch)
    assert result['status']=='SIGNAL' and result['delay']==2


def test_first_last_bar_signal_not_filled_overnight_or_retried():
    sch=calendar();d=sch.date.iloc[10];e=sch.date.iloc[11]
    result=inspect_entry({('A',d):session(d,[104,106]),('A',e):session(e,[106,107])},sch)
    assert result['status']=='FIRST_CONFIRMATION_LAST_BAR_NO_FILL'


def test_missing_j2_does_not_erase_valid_j1_entry():
    row,g,sch=fixture()
    assert ('A',sch.date.iloc[11]) not in g
    assert inspect_entry(g,sch)['status']=='SIGNAL'


def test_missing_j1_not_skipped_to_j2():
    sch=calendar();e=sch.date.iloc[11]
    result=inspect_entry({('A',e):session(e,[106,107])},sch)
    assert result['status']=='MISSING_ENTRY_SESSION' and result['missing_date']==sch.date.iloc[10]


def test_future_window_censored_not_assumed_no_signal(monkeypatch):
    sch=calendar();d=sch.date.iloc[10]
    monkeypatch.setattr(study.parent,'END',d)
    assert inspect_entry({('A',d):session(d,[104,104])},sch)['status']=='ENTRY_SCREEN_CENSORED'


def test_feature_and_entry_inspect_independent(monkeypatch):
    row,g,sch=fixture();actions=pd.DataFrame()
    actual=study.inspect_candidate(row,g,sch,actions)
    expected=review.inspect(row,g,sch,actions,study.parent.END)
    assert actual==expected and actual['P07_signal'] is True
    monkeypatch.setattr(study,'daily_features',lambda *a:(_ for _ in ()).throw(RuntimeError('primary forbidden')))
    assert review.inspect(row,g,sch,actions,study.parent.END)==expected


def test_missing_lookback_unknown_not_false():
    row,g,sch=fixture();del g['A',sch.date.iloc[0]]
    result=study.inspect_candidate(row,g,sch,pd.DataFrame())
    assert result['pattern'] is None and result['P07_signal'] is None
    assert result['feature_status']=='MISSING_TEN_SESSION_LOOKBACK'


def test_missing_entry_window_does_not_make_valid_pattern_false():
    row,g,sch=fixture();del g['A',sch.date.iloc[10]]
    result=study.inspect_candidate(row,g,sch,pd.DataFrame())
    assert result['pattern'] is True and result['P07_signal'] is None
    assert not result['entry_evaluable']


def test_pattern_false_does_not_suppress_break_control():
    row,g,sch=fixture();g['A',row.oracle_date]=daily(105,100,104)
    result=study.inspect_candidate(row,g,sch,pd.DataFrame())
    assert result['pattern'] is False and result['break_control_signal'] is True
    assert result['P07_signal'] is False


def test_known_lookback_action_reserved():
    row,g,sch=fixture();actions=pd.DataFrame([dict(symbol='A',ex_date=sch.date.iloc[4])])
    result=study.inspect_candidate(row,g,sch,actions)
    assert result['feature_status']=='KNOWN_LOOKBACK_CORPORATE_ACTION' and result['pattern'] is None


def test_no_pattern_opportunity_still_blocks_later_same_symbol():
    now=pd.Timestamp('2026-03-16 13:30Z');end=pd.Timestamp('2026-05-12 13:30Z')
    frame=pd.DataFrame([dict(pair_id=i,symbol='A',rank=1,entry_time=now+pd.Timedelta(days=i),
        label_available=end,P07_signal=i==1) for i in range(2)])
    assert list(study.parent.history.spaced(frame).pair_id)==[0]


def test_all_missing_coverage_screen_finishes_without_economics(tmp_path,monkeypatch):
    from scripts.research.us_concentrated_historical_tapes import atomic_json
    root=tmp_path/'screen';source=tmp_path/'archive';root.mkdir();source.mkdir()
    atomic_json(root/'protocol.json',dict(sources={}))
    atomic_json(source/'report.json',dict(files={}))
    sch=calendar();day=sch.date.iloc[9]
    pd.DataFrame([dict(pair_id=i,symbol='A',rank=1,oracle_date=day,year=day.year) for i in range(213)]).to_parquet(source/'campaigns.parquet')
    pd.DataFrame(columns=['symbol','ca_type','ex_date']).to_parquet(source/'corporate-actions.parquet')
    monkeypatch.setattr(study.parent,'PARENT',source)
    monkeypatch.setattr(study.parent,'load_groups',lambda:({},[],sch))
    forbidden=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('economic call forbidden'))
    monkeypatch.setattr(study.parent,'portfolio',forbidden)
    monkeypatch.setattr(study.parent.history,'unit_outcome',forbidden)
    report=study.screen(root)
    assert report['status']=='INSUFFICIENT_P07_FREQUENCY_NO_BACKTEST'
    assert report['feature_qualified']==0 and report['p07_signals']==0
    assert not report['performance_calculated'] and not report['economic_backtest_launched']
    assert not (root/'annual-summary.csv').exists()
