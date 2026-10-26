from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from scripts.research import us_winner_context_headroom as study


def path(rows,stamps=None):
    stamps=stamps if stamps is not None else pd.date_range('2026-01-05 14:30Z',periods=len(rows),freq='5min')
    return pd.DataFrame([dict(bar_timestamp=t,bar_end_timestamp=t+pd.Timedelta(minutes=5),
        open=a,high=b,low=c,close=d) for t,(a,b,c,d) in zip(stamps,rows)])


def unit(frame,**params):
    policy=replace(study.BASE,**params)
    schedule=study.calendar_frame();cal=study.ArchiveCalendar(schedule)
    due=next(s.open_at_utc for s in cal.sessions(pd.Timestamp('2026-01-06').date(),pd.Timestamp('2026-01-07').date()))
    extra=path([(103,104,102,103)],[pd.Timestamp(due)])
    g=pd.concat([frame,extra],ignore_index=True)
    entry=dict(timestamp=frame.bar_timestamp.iloc[0],price=float(frame.open.iloc[0]))
    return study.unit_outcome(g,entry,policy,cal)


def test_stop_before_tp_on_ambiguous_bar():
    result=unit(path([(100,120,90,105)]),horizon_sessions=1,take_profit_pct=.10)
    assert result['reason']=='STOP' and result['exit_price']==93


def test_stop_gap_is_not_guaranteed_loss_cap():
    result=unit(path([(100,101,99,100),(80,82,79,81)]),horizon_sessions=1)
    assert result['reason']=='STOP_GAP' and result['net_pct']< -20


def test_trailing_uses_previous_completed_bar_and_cents():
    result=unit(path([(100,120,99,110),(110,112,100,105)]),horizon_sessions=1,trailing_stop_pct=.15)
    assert result['exit_price']==102 and result['reason']=='STOP'


def test_same_bar_peak_cannot_tighten_stop_retroactively():
    result=unit(path([(100,120,99,110)]),horizon_sessions=1,trailing_stop_pct=.15)
    assert result['reason']=='HORIZON_OPEN'


def test_favorable_gap_tp_capped():
    result=unit(path([(100,105,99,103),(130,132,129,131)]),horizon_sessions=1,take_profit_pct=.10)
    assert result['reason']=='TP_GAP_CAPPED' and result['exit_price']==110


def test_horizon_from_entry_not_oracle_and_no_early_maturity():
    frame=path([(100,101,99,100)])
    result=unit(frame,horizon_sessions=1)
    assert result['exit_time']==pd.Timestamp('2026-01-06 14:30Z')
    cal=study.ArchiveCalendar(study.calendar_frame())
    with pytest.raises(ValueError,match='immature'):
        study.unit_outcome(frame,dict(timestamp=frame.bar_timestamp.iloc[0],price=100),study.BASE,cal)


def test_future_prices_after_exit_not_used():
    a=path([(100,101,90,95),(80,90,75,85)])
    b=a.copy();b.loc[1,['open','high','low','close']]=[300,400,250,350]
    assert unit(a,horizon_sessions=1)==unit(b,horizon_sessions=1)


def test_unit_cost_stress_includes_actual_exit_notional():
    frame=path([(100,101,90,95)]);cal=study.ArchiveCalendar(study.calendar_frame())
    due=path([(100,101,99,100)],[pd.Timestamp('2026-01-06 14:30Z')])
    frame=pd.concat([frame,due],ignore_index=True);entry=dict(timestamp=frame.bar_timestamp.iloc[0],price=100.)
    p=replace(study.BASE,horizon_sessions=1)
    a=study.unit_outcome(frame,entry,p,cal);b=study.unit_outcome(frame,entry,p,cal,.0025)
    assert a['exit_price']==b['exit_price']==93
    assert a['net_pct']-b['net_pct']==pytest.approx(100*(.0025-.0008)*1.93)


def test_nonoverlap_uses_common_maturity_not_favorable_early_exit():
    f=pd.DataFrame([dict(pair_id=i,symbol='A',rank=1,entry_time=pd.Timestamp(d,tz='UTC'),
        label_available=pd.Timestamp(e,tz='UTC')) for i,d,e in [(1,'2025-01-01','2025-02-01'),
        (2,'2025-01-10','2025-02-10'),(3,'2025-02-02','2025-03-01')]])
    assert study.spaced(f).pair_id.tolist()==[1,3]


def test_equal_profiles_no_artificial_headroom():
    f=pd.DataFrame(dict(symbol=['A','B'],REFERENCE=[1,-2],SL5=[1,-2]))
    result=study.summary(f,['REFERENCE','SL5'])
    assert result['hindsight_headroom_pp']==0 and result['profiles_differ_pct']==0


def sample():
    rows=[]
    for year in [2025,2026]:
        for i in range(40):
            row=dict(year=year,entry_time=pd.Timestamp(f'{year}-01-01',tz='UTC')+pd.Timedelta(days=i*5),
                label_available=pd.Timestamp(f'{year}-02-01',tz='UTC')+pd.Timedelta(days=i*5))
            row.update({k:'A' for k in study.GROUPS})
            for name in study.PROFILES:row[name]=row[name+'_cost25']=float(name=='TRAIL20')
            rows.append(row)
    return pd.DataFrame(rows)


def test_choices_do_not_change_when_test_outcomes_change():
    a=sample();_,frozen=study.contextual_checks(a)
    b=a.copy();b.loc[b.year==2026,'TRAIL10']=1000
    _,other=study.contextual_checks(b)
    assert frozen==other
    assert frozen['baseline']=='TRAIL20'


def test_immature_train_labels_excluded():
    f=sample();f.loc[f.year==2025,'label_available']=pd.Timestamp('2026-02-01',tz='UTC')
    rows,result=study.contextual_checks(f)
    assert not rows and result['status']=='INSUFFICIENT_TEMPORAL_SAMPLE'


def test_rare_states_cannot_pass():
    f=sample().iloc[[0,1,40,41]].copy()
    checks,_=study.contextual_checks(f)
    assert not any(x['passes_context_gate'] for x in checks)


def test_constant_choice_is_not_personalization():
    checks,_=study.contextual_checks(sample())
    assert all(x['distinct_profiles']==1 and not x['passes_context_gate'] for x in checks)


def test_cluster_interval_zero_gain_and_reproducible():
    dates=pd.Series(pd.date_range('2026-01-01',periods=80,freq='3D',tz='UTC'))
    a=study.monthly_interval(dates,np.zeros(80));b=study.monthly_interval(dates,np.zeros(80))
    assert a==b and a['lower95']==a['upper95']==0


def test_daily_features_are_prefix_invariant():
    days=pd.bdate_range('2024-01-01',periods=240)
    frames=[]
    for symbol in ['A','SPY']:
        price=100+np.arange(len(days))*.1+np.sin(np.arange(len(days)))
        frames.append(pd.DataFrame(dict(symbol=symbol,date=days,open=price,high=price+1,low=price-1,
            close=price,volume=10000,is_filled=0,data_adjustment='split')))
    f=pd.concat(frames);a=study.daily_features(f,days)
    cutoff=days[210];p=f[f.date<=cutoff];b=study.daily_features(p,days[:211])
    assert study.context(a,'A',cutoff,3)==study.context(b,'A',cutoff,3)


def test_missing_daily_not_forward_filled():
    days=pd.bdate_range('2024-01-01',periods=240)
    f=pd.DataFrame(dict(symbol='A',date=days,open=100,high=101,low=99,close=100,
        volume=1000,is_filled=0,data_adjustment='split'))
    f.loc[230,'volume']=0
    out=study.daily_features(f,days)['A']
    assert pd.isna(out.loc[days[230],'close']) and pd.isna(out.loc[days[231],'atr_pct'])
