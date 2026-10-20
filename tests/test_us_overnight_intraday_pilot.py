import numpy as np
import pandas as pd
import pytest

from scripts.research.us_overnight_intraday_pilot import (
    window_all, stable, sign, decompose, directions, grid, outcomes, independent, net_return, blocked_interval,
)


def bars(n=85):
    days=pd.bdate_range('2024-01-01',periods=n)
    b=pd.DataFrame(dict(date=days,open=100.,high=110.,low=90.,close=101.,adj_close=101.,
        volume=1000.,is_filled=0,instrument_id=1,data_source='eodhd_eod',data_adjustment='split'))
    return days,b


def test_decomposition_exact_compound_identity_and_first_day():
    o=np.arange(100,160,dtype=float);c=o*1.01
    f=decompose(o,c,np.ones(60,bool))
    assert f.intraday20.iloc[:20].isna().all()
    assert f.intraday20.iloc[20]==pytest.approx(20*np.log(1.01))
    for j in range(20,60): assert f.close20.iloc[j]==pytest.approx(np.log(c[j]/c[j-20]))


def test_feature_prefix_does_not_see_future():
    rng=np.random.default_rng(1);o=np.exp(rng.normal(0,.01,80).cumsum())*100;c=o*np.exp(rng.normal(0,.01,80))
    a=decompose(o,c,np.ones(80,bool));o[51:]*=2;c[51:]*=.5
    b=decompose(o,c,np.ones(80,bool));pd.testing.assert_frame_equal(a.iloc[:51],b.iloc[:51])
    pd.testing.assert_frame_equal(b.iloc[:51],decompose(o[:51],c[:51],np.ones(51,bool)))


def test_invalid_history_not_forward_filled_or_zeroed():
    o=np.ones(80)*100;c=np.ones(80)*101;q=np.ones(80,bool);q[30]=False
    f=decompose(o,c,q)
    assert not f.history_good.iloc[30:51].any()
    assert f.intraday20.iloc[30:51].isna().all()
    assert f.history_good.iloc[51]


def test_signs_and_agreement_abstention():
    d=directions([.1,-.1,.1,0,np.nan],[.1,-.1,-.2,.1,.2])
    assert d['AGREEMENT20'].tolist()==[1,-1,0,0,0]
    assert d['CLOSE20'].tolist()[:4]==[1,-1,-1,1]
    assert sign([1e-15,-1e-15,0]).tolist()==[0,0,0]


def test_inclusive_window_no_negative_wrapping():
    q=[True,True,False,True]
    assert window_all(q,[-1,0,1,3],[1,1,3,4]).tolist()==[False,True,False,False]


def test_metadata_stability_and_nan_block():
    assert stable(['a','a','b',None],[0,0,1],[1,2,3]).tolist()==[True,False,False]


def test_adjust_all_ohlc_not_just_close_and_split_cancellation():
    days,b=bars();b.loc[:39,['open','high','low','close']]*=2
    g,f=grid(b,days)
    assert g.open.eq(100).all() and g.close.eq(101).all()
    assert f.history_good.iloc[50]
    assert f.overnight20.iloc[50]==pytest.approx(-20*np.log(1.01))


@pytest.mark.parametrize('field,value',[('adj_close',np.nan),('volume',0),('is_filled',1),('data_source','alpaca_iex'),('data_adjustment',None)])
def test_bad_bar_blocks_history_and_outcomes(field,value):
    days,b=bars();b.loc[35,field]=value;g,f=grid(b,days)
    assert not f.history_good.iloc[40]
    ret,valid=outcomes(g,10)
    assert not valid[30] and np.isnan(ret[30])


def test_outcome_entry_next_open_and_includes_entry_session():
    days,b=bars();b.loc[21,['open','low']]=80;b.loc[25,['close','adj_close','high']]=120
    g,_=grid(b,days);r,v=outcomes(g,5)
    assert v[20] and r[20]==pytest.approx(.5)
    assert np.isnan(r[-5:]).all()


def test_future_missing_does_not_modify_history_or_membership():
    days,b=bars();g,f=grid(b,days);b.loc[50,'volume']=0;g2,f2=grid(b,days)
    pd.testing.assert_frame_equal(f.iloc[:50],f2.iloc[:50])
    assert outcomes(g,20)[1][40] and not outcomes(g2,20)[1][40]


def test_no_overlap_unknown_members_block_and_year_not_reset():
    f=pd.DataFrame(dict(symbol=['A']*5,pos=[0,1,19,20,21],rank=1,history_good=[False]*5))
    assert independent(f).tolist()==[True,False,False,True,False]


def test_costs_on_exit_notional_and_short_borrow():
    r=net_return([.2,-.1],[1,-1],[20,20])
    assert r[0]==pytest.approx(.2-.0022)
    assert r[1]==pytest.approx(.1-.0019-.003*20/365)
    assert net_return([0],[1],[1])[0]<0
    with pytest.raises(ValueError):net_return([.1],[0],[1])


def test_block_interval_deterministic_and_paired_zero():
    days=pd.bdate_range('2024-01-01',periods=70)
    rows=pd.DataFrame(dict(date=days,value=np.zeros(70)))
    assert blocked_interval(rows,days,'value',draws=39)==[0,0]
    rows['value']=.01
    assert blocked_interval(rows,days,'value',draws=39)==pytest.approx([.01,.01])
    assert blocked_interval(rows.iloc[:2],days,'value',draws=39) is None


def test_metadata_change_not_bridged():
    days,b=bars();b.loc[35:,'instrument_id']=2;g,f=grid(b,days)
    assert not f.history_good.iloc[35:55].any() and f.history_good.iloc[55]
    assert not outcomes(g,10)[1][30]


def test_identity_events_cut_history_and_future():
    days,b=bars();ev=[dict(last_predecessor_date=str(days[30]),first_successor_date=str(days[31]))]
    g,f=grid(b,days,identities=ev)
    assert not f.history_good.iloc[31:51].any()
    assert not outcomes(g,10,ev)[1][25]


def test_price_reservation_no_global_symbol_deletion():
    days,b=bars();g,f=grid(b,days,reserve={'start':str(days[60])})
    assert f.history_good.iloc[59] and not f.history_good.iloc[60:].any()
    assert outcomes(g,5)[1][50] and not outcomes(g,5)[1][56]
