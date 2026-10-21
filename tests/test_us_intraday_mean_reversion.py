import numpy as np
import pandas as pd
import pytest

from scripts.research.us_intraday_mean_reversion import bar_grid, trigger, execute, liquidity_pool


def bars(values, start='2025-01-02 14:30Z'):
    f=pd.DataFrame(values,columns=['open','high','low','close'],dtype=float)
    t=pd.date_range(start,periods=len(f),freq='5min')
    return f.assign(bar_timestamp=t,bar_end_timestamp=t+pd.Timedelta(minutes=5),volume=100,
        provider='alpaca',data_source='alpaca_sip',interval_code='5m',market_code='US_EQ',
        session_tag='regular',data_adjustment='raw',is_filled=0)


def grid(values):
    f=bars(values)
    return bar_grid(f,f.bar_timestamp.iloc[0],f.bar_end_timestamp.iloc[-1])


def test_vwap_uses_prefix_not_future():
    f=bars([[100,101,99,100]]*10)
    op=f.bar_timestamp.iloc[0]; cl=f.bar_end_timestamp.iloc[-1]
    a=bar_grid(f,op,cl)
    f.loc[8:,['open','high','low','close']]*=2
    b=bar_grid(f,op,cl)
    np.testing.assert_equal(a.vwap_proxy[:8].to_numpy(),b.vwap_proxy[:8].to_numpy())


def test_future_missing_does_not_remove_prefix():
    f=bars([[100,101,99,100]]*10)
    op=f.bar_timestamp.iloc[0]; cl=f.bar_end_timestamp.iloc[-1]
    a=bar_grid(f.iloc[:-1],op,cl)
    assert a.prefix_good[:9].all() and not a.prefix_good.iloc[-1]
    assert a.session_return[:9].notna().all()
    assert a.session_return.iloc[-1]!=a.session_return.iloc[-1]


@pytest.mark.parametrize('column,value',[('data_source','alpaca_iex'),('is_filled',1),
    ('data_adjustment','split'),('volume',0),('close',np.nan)])
def test_invalid_metadata_poison_prefix(column,value):
    f=bars([[100,101,99,100]]*10); f.loc[3,column]=value
    q=bar_grid(f,f.bar_timestamp.iloc[0],f.bar_end_timestamp.iloc[-1])
    assert q.prefix_good[:3].all() and not q.prefix_good[3:].any()


def test_duplicates_rejected():
    f=bars([[100,101,99,100]]*10)
    assert bar_grid(pd.concat([f,f.iloc[:1]]),f.bar_timestamp.iloc[0],f.bar_end_timestamp.iloc[-1]) is None


def test_trigger_completed_bar_next_open_and_future_invariance():
    f=grid([[100,101,99,100]]*6+[[97,98,96,96.5],[96.5,98,96.1,97.5]]+[[98,99,97,98]]*70)
    op=f.bar_timestamp.iloc[0]; cl=f.bar_end_timestamp.iloc[-1]; benchmark=np.zeros(len(f))
    r=trigger(f,benchmark,op,cl)
    assert r[:2]==(7,'LONG')
    assert f.bar_timestamp.iloc[r[0]+1]==f.bar_end_timestamp.iloc[r[0]]
    changed=f.copy(); changed.loc[8:,'close']=1000
    assert trigger(changed,benchmark,op,cl)==r
    rshort=trigger(f.assign(session_return=-f.session_return,close=-f.close,
        high=-f.low,low=-f.high,vwap_proxy=-f.vwap_proxy),benchmark,op,cl)
    assert rshort[:2]==(7,'SHORT')


def test_no_signal_without_market_reference():
    f=grid([[100,101,99,100]]*78)
    assert trigger(f,np.full(78,np.nan),f.bar_timestamp.iloc[0],f.bar_end_timestamp.iloc[-1]) is None


@pytest.mark.parametrize('side,values,target',[
    ('LONG',[[100,102,98,100],[100,101,99.5,100]],101),
    ('SHORT',[[100,102,98,100],[100,100.5,99,100]],99)])
def test_collision_stop_first(side,values,target):
    r=execute(grid(values),side,target)
    assert r['gross']==pytest.approx(-.01) and r['collision']


@pytest.mark.parametrize('side,values,target,loss',[
    ('LONG',[[100,100.5,99.5,100],[95,96,94,95],[96,97,95,96]],102,-.05),
    ('SHORT',[[100,100.5,99.5,100],[105,106,104,105],[104,105,103,104]],98,-.05)])
def test_gap_not_capped(side,values,target,loss):
    r=execute(grid(values),side,target)
    assert r['gross']==pytest.approx(loss) and r['gap_stop']


def test_forced_last_open_does_not_use_later_high_low():
    r=execute(grid([[100,100.1,99.9,100],[100.2,120,80,100]]),'LONG',101)
    assert r['outcome']=='TIME' and r['gross']==pytest.approx(.002)
    assert r['net']==pytest.approx(.002-.001*2.002-.002)
    assert r['stress_net']<r['net']


def test_abstain_entry_beyond_target():
    assert execute(grid([[102,103,101,102],[102,103,101,102]]),'LONG',101) is None


def test_unknown_path_not_zero_outcome():
    f=grid([[100,101,99,100]]*3); f.loc[2,'valid']=False
    with pytest.raises(ValueError): execute(f,'LONG',102)


def test_half_day_grid():
    assert len(grid([[100,101,99,100]]*42))==42


def test_liquidity_excludes_current_bar():
    days=pd.bdate_range('2024-01-01',periods=25)
    f=pd.DataFrame(dict(date=days,symbol='A',open=100.,high=101.,low=99.,close=100.,
        volume=1e6,is_filled=0,instrument_id=1,data_source='eodhd_eod',data_adjustment='split'))
    a=liquidity_pool(f,pd.DataFrame(dict(date=days)),{'A'})
    f.loc[24,'volume']=0
    b=liquidity_pool(f,pd.DataFrame(dict(date=days)),{'A'})
    pd.testing.assert_frame_equal(a,b)
    assert a.date.min()==days[20]
