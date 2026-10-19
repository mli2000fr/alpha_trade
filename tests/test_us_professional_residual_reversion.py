import numpy as np
import pandas as pd
import pytest

from scripts.research.us_professional_residual_reversion import (
    ou_signals,daily_exit,returns_for,valid_grid,window_reason,MAX_HOLD)


def sample_prices(n=240):
    rng=np.random.default_rng(71)
    m=rng.normal(.0001,.008,n-1)
    x=np.zeros(n)
    for i in range(1,n):x[i]=.80*x[i-1]+rng.normal(0,.004)
    r=1.2*m+np.diff(x)
    return 100*np.r_[1,np.cumprod(1+r)],100*np.r_[1,np.cumprod(1+m)]


def test_prefix_causality():
    c,m=sample_prices()
    a=ou_signals(c,m,np.ones(len(c),bool))
    c2=c.copy();m2=m.copy();c2[151:]*=1.5;m2[151:]*=.8
    b=ou_signals(c2,m2,np.ones(len(c),bool))
    pd.testing.assert_frame_equal(a.iloc[:151],b.iloc[:151])
    short=ou_signals(c[:151],m[:151],np.ones(151,bool))
    pd.testing.assert_frame_equal(a.iloc[:151],short)
    assert a.model_valid.sum()>0


def scalar_score(c,m,pos):
    r=c[pos-59:pos+1]/c[pos-60:pos]-1
    spy=m[pos-59:pos+1]/m[pos-60:pos]-1
    fit=np.linalg.lstsq(np.column_stack([np.ones(60),spy]),r,rcond=None)[0]
    x=np.cumsum(r-fit[0]-fit[1]*spy)
    ar=np.linalg.lstsq(np.column_stack([np.ones(59),x[:-1]]),x[1:],rcond=None)[0]
    variance=np.sum((x[1:]-ar[0]-ar[1]*x[:-1])**2)/57
    if not 0<ar[1]<1:return fit[1],ar[1],None
    score=(x[-1]-ar[0]/(1-ar[1]))/np.sqrt(variance/(1-ar[1]**2))
    return fit[1],ar[1],score


def test_vector_ols_ou_against_scalar():
    c,m=sample_prices();a=ou_signals(c,m,np.ones(len(c),bool))
    for pos in range(60,len(c),13):
        beta,b,s=scalar_score(c,m,pos)
        assert a.beta.iloc[pos]==pytest.approx(beta,abs=1e-10)
        assert a.ar_b.iloc[pos]==pytest.approx(b,abs=1e-10)
        if s is not None:assert a.s_score.iloc[pos]==pytest.approx(s,abs=1e-9)


def test_no_fill_missing_history_blocks_61_sessions():
    c,m=sample_prices();good=np.ones(len(c),bool);good[90]=False
    a=ou_signals(c,m,good)
    assert not a.model_valid.iloc[90:151].any()
    assert a.s_score.iloc[90:151].isna().all()


def test_constant_benchmark_or_stock_has_no_valid_model():
    c,m=sample_prices()
    assert not ou_signals(c,np.ones(len(c))*100,np.ones(len(c),bool)).model_valid.any()
    assert not ou_signals(np.ones(len(c))*100,m,np.ones(len(c),bool)).model_valid.any()


def exit_arrays():
    return [np.ones(25)*100 for _ in range(4)]+[np.ones(25)*-2,np.ones(25,bool)]


def test_reversion_executes_next_open_not_signal_close():
    so,sc,mo,mc,z,v=exit_arrays();z[1]=-.4;so[2]=80
    end,why,age=daily_exit(so,sc,mo,mc,z,v,pos=0,side='LONG',beta=1)
    assert (end,why,age)==(2,'REVERSION_NEXT_OPEN',1)
    r=returns_for(so[1],so[end],mo[1],mo[end],1,'LONG',1,'OU_DYNAMIC')
    assert r['net']<-.1


@pytest.mark.parametrize('side,score',[('LONG',-.5),('SHORT',.5)])
def test_exact_symmetric_exit(side,score):
    a=exit_arrays();a[4][:]=score
    assert daily_exit(*a,pos=0,side=side,beta=1)[0]==2


def test_risk_is_daily_next_open_not_capped_stop():
    a=exit_arrays();a[1][1]=89;a[0][2]=70
    end,why,age=daily_exit(*a,pos=0,side='LONG',beta=1)
    assert (end,why)==(2,'DAILY_RISK_NEXT_OPEN')
    r=returns_for(100,70,100,100,1,'LONG',1,'OU_DYNAMIC')
    assert r['net']<-.15


def test_invalid_model_closes_next_open():
    a=exit_arrays();a[5][1]=False
    assert daily_exit(*a,pos=0,side='LONG',beta=1)[1]=='INVALID_MODEL_NEXT_OPEN'


def test_full_timeout_and_no_future_leak_into_exit_decision():
    a=exit_arrays()
    assert daily_exit(*a,pos=0,side='LONG',beta=1)==(11,'TIMEOUT_NEXT_OPEN',MAX_HOLD)
    a[4][4]=0
    original=daily_exit(*a,pos=0,side='LONG',beta=1)
    a[4][5:]=200;a[0][6:]*=3
    assert daily_exit(*a,pos=0,side='LONG',beta=1)==original


def test_exact_costs_two_legs_and_stress():
    r=returns_for(100,110,100,102,1,'LONG',1,'OU_DYNAMIC')
    assert r['gross']==pytest.approx(.04)
    assert r['costs']==pytest.approx(.001648)
    assert r['borrow']==pytest.approx(.003/365*.5)
    assert r['net_stress']<r['net']


def test_identical_asset_beta_one_hedge_has_zero_gross():
    for side in ['LONG','SHORT']:
        assert returns_for(100,130,100,130,1,side,10,'OU_DYNAMIC')['gross']==pytest.approx(0)


def test_reverse_same_exit_negates_gross_not_costs():
    a=returns_for(100,110,100,102,1,'LONG',3,'OU_DYNAMIC')
    b=returns_for(100,110,100,102,1,'LONG',3,'REVERSE_SAME_EXIT')
    assert a['gross']==pytest.approx(-b['gross'])
    assert a['costs']==pytest.approx(b['costs'])
    assert a['net']+b['net']<0


@pytest.mark.parametrize('kwargs',[{'beta':0},{'side':'X'},{'entry_stock':np.nan},{'policy':'X'}])
def test_invalid_return_inputs(kwargs):
    params=dict(entry_stock=100,exit_stock=110,entry_market=100,exit_market=102,beta=1,side='LONG',calendar_days=1,policy='OU_DYNAMIC')
    params.update(kwargs)
    with pytest.raises(ValueError):returns_for(**params)


def grid_data():
    days=pd.bdate_range('2024-01-01',periods=100)
    b=pd.DataFrame(dict(date=days,open=100.,high=101.,low=99.,close=100.,adj_close=100.,
        volume=100000.,is_filled=0,instrument_id=1,data_source='TEST',data_adjustment='split'))
    return days,b


def test_metadata_change_history_and_future_reserve():
    days,b=grid_data();b.loc[80:,'instrument_id']=2
    g=valid_grid(b,days)
    assert not g.stable_history.iloc[80:].any()
    assert window_reason(g,75)=='CHANGED_OR_UNKNOWN_INSTRUMENT_ID'
    reserve={'start':str(days[90].date())}
    assert window_reason(g,85,reserve)=='RESERVED_PRICE_BASIS'


def test_missing_future_not_imputed():
    days,b=grid_data();b=b.drop(index=74)
    g=valid_grid(b,days)
    assert window_reason(g,70)=='INVALID_OR_MISSING_FUTURE_PRICE'
