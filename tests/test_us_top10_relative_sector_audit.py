import numpy as np
import pandas as pd
from scripts.research.us_top10_relative_sector_audit import trailing_returns, peer_context


def test_no_forward_fill_and_no_future_in_trailing_return():
    prices=pd.DataFrame({'A':[10.,np.nan,12.,13.]})
    result=trailing_returns(prices,1)
    assert pd.isna(result.loc[2,'A'])
    assert np.isclose(result.loc[3,'A'],13/12-1)
    prices.loc[3,'A']=100
    assert pd.isna(trailing_returns(prices,1).loc[2,'A'])


def test_leave_one_out_and_unknown_not_veto():
    data=pd.DataFrame(dict(date=['2023-01-01']*3,sector=['S','S',None],ret20=[-.2,.1,-.5]))
    result=peer_context(data,minimum_peers=1)
    assert result.loc[0,'peer_ret20']==.1
    assert result.loc[0,'peer_breadth20']==1
    assert not result.loc[2,'context_known']
    assert not result.loc[2,'weakness_flag']


def test_strict_breadth_and_peer_minimum():
    data=pd.DataFrame(dict(date=['2023-01-01']*3,sector=['S']*3,ret20=[-.3,-.2,.1]))
    half=peer_context(data,minimum_peers=2)
    assert half.loc[0,'peer_breadth20']==.5
    assert not half.loc[0,'weakness_flag']
    assert not peer_context(data,minimum_peers=3).context_known.any()
