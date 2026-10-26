import numpy as np
import pandas as pd
import pytest
from types import SimpleNamespace
from scripts.research.us_winner_loss_diagnostics_20261023 import (
    path_signatures,loss_category,entry_features,mark_nonoverlap,feature_statistics,FEATURES,campaign_key,
)


def bars(values,start='2026-01-02 15:00Z'):
    f=pd.DataFrame(values,columns=['open','high','low','close'])
    f['bar_timestamp']=pd.date_range(start,periods=len(f),freq='5min')
    f['bar_end_timestamp']=f.bar_timestamp+pd.Timedelta(minutes=5)
    f['volume']=100
    return f


def signatures(held,future=None,reason='STOP',complete=True):
    return path_signatures(held,held.iloc[:0] if future is None else future,
        entry_time=held.bar_timestamp.iloc[0],exit_time=held.bar_timestamp.iloc[-1],
        entry=100,exit_price=93,reason=reason,threshold=99,fee=.0008,complete=complete)


def test_exit_bar_high_not_assumed_before_stop():
    f=bars([[100,103,99,102],[102,112,92,95]])
    r=signatures(f)
    assert r['mfe_lower_pct']==pytest.approx(3)
    assert r['mfe_upper_pct']==pytest.approx(12)
    assert not r['gain_1R_certain'] and r['exit_bar_1R_ambiguous']
    assert loss_category(dict(pnl=-7,**r))=='AMBIGUOUS_EXIT_BAR_1R'


def test_open_exit_has_no_look_through_bar():
    r=signatures(bars([[100,103,99,102],[90,112,80,95]]),reason='STOP_GAP')
    assert r['mfe_upper_pct']==pytest.approx(3)
    assert r['mae_upper_pct']==pytest.approx(7)


def test_rebound_requires_future_close_not_wick():
    held=bars([[100,102,98,99],[99,100,93,93]])
    future=bars([[93,115,90,106],[106,108,95,107]],start='2026-01-02 15:10Z')
    r=signatures(held,future)
    assert r['post_stop_close_1R'] is True
    assert r['post_stop_1R_time']==pd.Timestamp('2026-01-02 15:20Z')
    assert r['post_stop_mae_until_1R_pct']==pytest.approx(10)
    assert loss_category(dict(pnl=-7,**r))=='POST_STOP_REBOUND_1R'
    future.loc[1,'close']=106
    assert signatures(held,future)['post_stop_close_1R'] is False


def test_censoring_is_not_negative_rebound_label():
    r=signatures(bars([[100,101,92,93]]),complete=False)
    assert r['post_stop_close_1R'] is None
    assert loss_category(dict(pnl=-7,**r))=='UNKNOWN_CENSORED_WINDOW'


def test_immediate_failure_requires_two_known_closes():
    f=bars([[100,101,97,98],[98,100,97,98],[98,100,92,93]])
    r=signatures(f)
    assert r['immediate_observed'] and r['immediate_failed_breakout']
    assert loss_category(dict(pnl=-7,**r))=='IMMEDIATE_FAILED_BREAKOUT'
    assert signatures(f.iloc[:1])['immediate_failed_breakout'] is None


def test_primary_category_is_not_exclusive_flags_claim():
    r=signatures(bars([[100,110,99,108],[108,110,98,98],[98,100,92,93]]))
    assert r['gain_1R_certain']
    assert loss_category(dict(pnl=-7,**r))=='GAIN_RESTITUTED_1R'
    assert loss_category(dict(pnl=1,**r))=='WIN_OR_FLAT'


def test_feature_prefix_never_sees_rest_of_entry_day():
    days=pd.bdate_range('2025-11-20',periods=32)
    schedule=[SimpleNamespace(session_date=d.date(),open_at_utc=d.tz_localize('UTC')+pd.Timedelta(hours=14,minutes=30)) for d in days]
    idx=days[-1];entry=idx.tz_localize('UTC')+pd.Timedelta(hours=14,minutes=45)
    history=pd.DataFrame({'open':100+np.arange(32),'high':102+np.arange(32),
        'low':99+np.arange(32),'close':101+np.arange(32)},index=days)
    today=bars([[130,131,129,130],[130,132,130,131],[131,133,130,132],[132,1000,1,500]],start=str(idx.date())+' 14:30Z')
    previous=bars([[128,130,127,129],[129,130,128,129],[129,130,128,130]],start=str(days[-2].date())+' 14:30Z')
    spy=pd.Series(400+np.arange(32),index=days)
    kwargs=dict(entry_time=entry,signal_day=days[-3],oracle_rank=2,schedule=schedule)
    a=entry_features(history,today,previous,spy,**kwargs)
    b=entry_features(history.iloc[:-1],today.iloc[:3],previous,spy.iloc[:-1],**kwargs)
    assert a==b
    assert a['entry_minutes_from_open']==15
    assert a['signal_age_sessions']==2
    assert a['pre_entry_extension_atr14']==pytest.approx(2/3)
    assert a['confirmation_volume_ratio']==1


def test_nonoverlap_selection_ignores_profit():
    f=pd.DataFrame(dict(year=[2026]*3,symbol=['A']*3,
        entry_date=pd.to_datetime(['2026-01-02Z'.replace('Z',''),'2026-01-10','2026-02-10'],utc=True),
        theoretical_due_open=pd.to_datetime(['2026-02-02','2026-02-10','2026-03-10'],utc=True),pnl=[-1,100,-1]))
    assert mark_nonoverlap(f).tolist()==[True,False,True]
    f.pnl=-f.pnl
    assert mark_nonoverlap(f).tolist()==[True,False,True]


def test_statistics_missing_values_not_imputed():
    f=pd.DataFrame([dict(year=2026,closed=True,nonoverlap20=True,pnl=1 if i<5 else -1,
        symbol=str(i),entry_day='2026-01-02',**{k:float(i) for k in FEATURES}) for i in range(10)])
    f.loc[0,'prior_atr14_pct']=np.nan
    out=feature_statistics(f)
    r=out[(out.feature=='prior_atr14_pct')&(out['sample']=='ALL')].iloc[0]
    assert r.covered==9 and pd.isna(r.auc_hypothesis)
    r=out[(out.feature=='oracle_rank')&(out['sample']=='ALL')].iloc[0]
    assert r.auc_hypothesis==1


def test_campaign_lineage_is_date_and_symbol_specific():
    assert campaign_key('2026-01-02','ABC')==campaign_key(pd.Timestamp('2026-01-02'),'ABC')
    assert campaign_key('2026-01-02','ABC')!=campaign_key('2026-01-05','ABC')
