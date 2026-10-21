import numpy as np
import pandas as pd
import pytest
from scripts.research.us_activist_13d_replay import price_path,marks


def data():
    days=pd.bdate_range('2024-01-01',periods=80)
    rows=pd.DataFrame(dict(date=days,open=100.,high=110.,low=90.,close=105.,adj_close=105.,volume=1000.,is_filled=0,
        instrument_id=1,data_source='eodhd_eod',data_adjustment='split'))
    return days,rows


def test_horizon_includes_entry_not_extra_session():
    d,r=data();path,why=price_path(r,d,d[3],20)
    assert why=='OK' and len(path)==20 and path.index[0]==d[3] and path.index[-1]==d[22]
    assert marks(path)['gross_return']==pytest.approx(.05)


def test_normalize_entire_ohlc_and_fixed_exit_friction():
    d,r=data();r.loc[:9,['open','high','low','close']]*=2
    path,why=price_path(r,d,d[0],20)
    assert why=='OK' and path.open.eq(100).all()
    x=marks(path)
    assert x['net_return']==pytest.approx(.05-.002-.00205)
    assert x['hypothetical_net_usd']==pytest.approx(45.95)
    assert marks(path,bps=25)['net_return']<x['net_return']


@pytest.mark.parametrize('field,value',[('volume',0),('is_filled',1),('adj_close',np.nan),('data_source','alpaca_iex')])
def test_invalid_future_is_unknown_not_replaced(field,value):
    d,r=data();r.loc[10,field]=value
    path,why=price_path(r,d,d[3],20)
    assert path is None and why!='OK'


def test_no_forward_fill_and_no_global_reserve_deletion():
    d,r=data();assert price_path(r.drop(index=10),d,d[3],20)[0] is None
    assert price_path(r,d,d[3],20,{'start':str(d[30])})[1]=='OK'
    assert price_path(r,d,d[3],60,{'start':str(d[30])})[0] is None


def test_class_identity_change_blocks_whole_path():
    d,r=data();r.loc[15:,'instrument_id']=2
    assert price_path(r,d,d[3],20)[0] is None


def test_drawdown_uses_closes_and_not_invented_highlow_order():
    d,r=data();r.loc[4,['close','adj_close']]=90
    path,why=price_path(r,d,d[3],5);x=marks(path)
    assert x['max_close_drawdown']==pytest.approx(90/105-1)
    assert x['mae']==pytest.approx(-.1)
