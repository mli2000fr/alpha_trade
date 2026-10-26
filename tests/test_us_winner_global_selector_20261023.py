from datetime import date
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from scripts.research import us_winner_global_selector_20261023 as s


def bars(values):
    f=pd.DataFrame(values,columns=['open','high','low','close'])
    f['bar_timestamp']=pd.date_range('2026-01-02 14:30Z',periods=len(f),freq='5min')
    f['bar_end_timestamp']=f.bar_timestamp+pd.Timedelta(minutes=5)
    f['session_close']=pd.Timestamp('2026-01-02 21:00Z')
    return f


@pytest.mark.parametrize('p',s.PROFILES)
def test_vector_scalar_equivalence_and_rounding(p):
    paths=[[[100,108,92,104],[104,109,100,105]],
           [[100,106,98,105],[101,103,100,102]],
           [[100,101,99,100],[125,130,124,128]],
           [[30.5,30.5,30.4,30.5],[30.5,31,30.4,30.6],[29,30,28,29]]]
    for values in paths:
        f=bars(values);due=pd.Timestamp('2026-02-01Z'.replace('Z',''),tz='UTC')
        # Ensure all paths have a terminal due bar even if no price barrier touches.
        due=f.bar_timestamp.iloc[-1]
        a=s.vector_exit(f,float(f.open.iloc[0]),due,p)
        b=s.scalar_exit(f,f.bar_timestamp.iloc[0],float(f.open.iloc[0]),due,sl=p['sl'],tp=p['tp'],trail=p['tr'])
        assert a==b


def test_maturity_not_early_exit_decides_split():
    assert not s.maturity_ok('2024-12-01','2025-01-31')
    assert s.maturity_ok('2024-10-01','2024-12-31')
    assert not s.maturity_ok('2026-09-01','2026-11-01')


def test_anchors_are_spaced_before_any_price_quality_or_outcome():
    days=pd.bdate_range('2024-01-01',periods=140)
    sessions=[SimpleNamespace(session_date=d.date()) for d in days]
    f=pd.DataFrame(dict(date=days[:70],symbol=['AA']*70,rank=[50]*70))
    p=s.sample_plan(f,sessions)
    assert list(p[p.anchor].date)==[days[0],days[42]]


def test_eval_is_top10_not_top100():
    days=pd.bdate_range('2025-01-01',periods=150)
    sessions=[SimpleNamespace(session_date=d.date()) for d in days]
    f=pd.DataFrame(dict(date=[days[0],days[0]],symbol=['AA','BB'],rank=[10,11]))
    p=s.sample_plan(f,sessions)
    assert dict(zip(p.symbol,p.anchor))=={'AA':True,'BB':False}


def test_features_prefix_invariant_no_symbol_year_or_future_price():
    days=pd.bdate_range('2020-01-01',periods=250);n=len(days)
    p=50+np.arange(n)*.1+np.sin(np.arange(n))
    f=pd.DataFrame(dict(date=days,open=p,high=p+1,low=p-1,close=p,volume=100000+np.arange(n)*10,
        data_adjustment='split',is_filled=0,data_source='alpaca_sip'))
    full=s.price_features(f,days);prefix=s.price_features(f.iloc[:220],days[:220])
    a=s.features_at(full,full,days[219],10);b=s.features_at(prefix,prefix,days[219],10)
    assert a==b and a is not None
    assert not {'symbol','year','sector','future_return'}.intersection(s.FEATURES)


def test_iex_and_missing_j_not_imputed():
    days=pd.bdate_range('2020-01-01',periods=220)
    f=pd.DataFrame(dict(date=days,open=50.,high=51.,low=49.,close=50.,volume=100.,
        data_adjustment='split',is_filled=0,data_source='alpaca_iex'))
    out=s.price_features(f,days)
    assert out.ret20.isna().all()


def test_profile_fallback_has_frozen_cost_margin():
    class Model:
        def predict(self,x):return np.zeros(len(x))
    rows=[]
    for p in s.PROFILES:
        rows.append(dict(date=pd.Timestamp('2025-01-02'),symbol='AA',profile=p['name'],**{k:0 for k in s.FEATURES}))
    d=s.decisions(Model(),pd.DataFrame(rows))
    assert list(d.profile)==['REFERENCE']
