from dataclasses import replace

import numpy as np
import pandas as pd

from scripts.research.us_winner_anticipation_audit_20261025 import (
    FLAGS,price_features,closed_health,choose_on_development,aggregate,month_bootstrap,
)


def fixture():
    days=pd.bdate_range('2019-01-01',periods=320)
    names=['SPY']+[f'S{i}' for i in range(20)]
    close=pd.DataFrame({s:100+np.arange(len(days))*.1+np.sin(np.arange(len(days))) for s in names},index=days)
    pivots={'close':close,'high':close+2,'low':close-2}
    cohort=pd.DataFrame([dict(date=d,symbol=s,rank=i+1,selected=True)
        for d in days for i,s in enumerate(names[1:])])
    return pivots,cohort


def test_price_features_invariant_to_future_prices_and_future_coverage_flags():
    p,c=fixture();first=price_features(p,c)
    changed={k:v.copy() for k,v in p.items()}
    for frame in changed.values():frame.iloc[250:]*=3
    c['selected']=False
    other=price_features(changed,c)
    for a,b in zip(first,other):pd.testing.assert_frame_equal(a.iloc[:250],b.iloc[:250])


def test_missing_basket_cannot_become_favorable_or_adverse():
    p,c=fixture()
    for frame in p.values():frame.loc[:,[f'S{i}' for i in range(5)]]=np.nan
    market,_,_=price_features(p,c)
    assert market.ORACLE_BREADTH20_WEAK.isna().all()


def test_health_cannot_see_unrealized_or_later_exits():
    t=pd.DataFrame(dict(exit_date=pd.date_range('2020-01-01',periods=30,tz='UTC'),pnl=[-1.]*30))
    cutoff=pd.Timestamp('2020-01-22',tz='UTC')
    assert closed_health(t,cutoff)[0] is True
    altered=t.copy();altered.loc[altered.exit_date>cutoff,'pnl']=10000.
    assert closed_health(t,cutoff)==closed_health(altered,cutoff)
    assert closed_health(t,pd.Timestamp('2020-01-10',tz='UTC'))==(None,None)


def test_selection_never_uses_validation_or_unmatured_development_outcomes():
    rows=[]
    for year in [2020,2021,2022,2023,2024]:
        for i in range(120):
            stamp=pd.Timestamp(f'{year}-01-01',tz='UTC')+pd.Timedelta(days=i)
            flag=i%2==0
            rows.append(dict(entry_at=stamp,entry_year=year,common_maturity_at=stamp+pd.Timedelta(days=30),
                exit_at=stamp+pd.Timedelta(days=20),symbol='S'+str(i),entry_notional=100.,net_pnl_usd=-2. if flag else 2.,
                net_return_pct=-2. if flag else 2.,**{n:flag for n in FLAGS}))
    f=pd.DataFrame(rows);before=choose_on_development(f)
    altered=f.copy();altered.loc[altered.entry_year>=2023,['net_return_pct','net_pnl_usd']]=10000.
    assert choose_on_development(altered)==before
    later=f[f.entry_year==2022].copy();later['common_maturity_at']=pd.Timestamp('2023-01-02',tz='UTC')
    later['net_pnl_usd']=100000.;later['net_return_pct']=100000.
    assert choose_on_development(pd.concat([f,later],ignore_index=True))==before


def test_missing_not_counted_good_and_month_bootstrap_deterministic():
    rows=[]
    for month in range(1,13):
        for bad in [False,True]:
            rows.append(dict(entry_month=f'2024-{month:02}',entry_at=pd.Timestamp(f'2024-{month:02}-01',tz='UTC'),
                symbol='S',net_pnl_usd=-2. if bad else 2.,net_return_pct=-2. if bad else 2.,entry_notional=100.,X=bad))
    f=pd.DataFrame(rows);missing=f.iloc[:1].copy();missing['X']=None
    got=aggregate(pd.concat([f,missing],ignore_index=True),'X')
    assert got['missing']==1 and got['qualified']==24
    a=month_bootstrap(f,'X');b=month_bootstrap(f,'X')
    assert a==b and a['upper95_pct']==-4.
