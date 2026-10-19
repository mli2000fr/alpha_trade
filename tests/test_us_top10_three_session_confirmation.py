import numpy as np
import pandas as pd
import pytest
from scripts.research import us_top10_three_session_confirmation as s
from tests.test_us_tradable_symbol_reliability import bars


def fixture():
    f=bars(35); f[['open','close']]=100.; f.high=101.; f.low=99.
    f['adj_close']=f.close
    return f


@pytest.mark.parametrize('values,expected',[
    ([99,100,101],'LONG'),([101,100,99],'SHORT'),([99,101,100],'NONE'),
    ([100,100,101],'NONE'),([99,np.nan,101],'NONE'),([99,0,101],'NONE')])
def test_three_closes_strict_not_just_endpoint(values,expected):
    assert s.directions(values,[1]).tolist()==[expected]


def test_confirmation_never_reads_j_plus_two_or_later():
    prices=np.array([99,100,101,102,103.])
    old=s.directions(prices,[1]); prices[3:]=1.
    np.testing.assert_array_equal(old,s.directions(prices,[1]))


def test_entry_j_plus_two_not_confirmation_day():
    f=fixture(); f.iloc[3,f.columns.get_indexer(['open','high','low','close'])]=[120,121,119,120]
    trade=s.trades_for(f,[1],'LONG')
    assert trade['entry_price'][0]==120
    assert trade['exit_price'][0]==pytest.approx(100.)  # next-session adverse gap, not SL capped
    assert trade['exit_session'][0]==2


def test_ten_sessions_include_entry_expire_j_plus_eleven():
    f=fixture(); f.iloc[12,f.columns.get_indexer(['open','high','low','close'])]=[100,103,99,102]
    trade=s.trades_for(f,[1],'LONG')
    assert trade['exit_price'][0]==102 and trade['exit_session'][0]==10


def test_barrier_collision_conservative_and_sl5():
    f=fixture(); f.loc[f.index[3],'high']=111; f.loc[f.index[3],'low']=94
    trade=s.trades_for(f,[1],'LONG')
    assert trade['outcome'][0]=='SL' and trade['exit_price'][0]==95
    assert trade['ambiguity'][0]


def test_unknown_future_quality_does_not_change_frozen_signal():
    f=fixture(); f.loc[f.index[:3],'adj_close']=[99,100,101]
    raw=f.rename_axis('date').reset_index()
    _,direction,reasons=s.qualify(raw,f.index,[1])
    assert direction[0]=='LONG' and reasons[0]==''
    raw.loc[8,'is_filled']=1
    _,direction,reasons=s.qualify(raw,f.index,[1])
    assert direction[0]=='LONG' and reasons[0]=='INVALID_OR_MISSING_CONFIRMATION_OR_PATH'


def test_identity_and_price_reserves_cover_confirmation_and_delayed_window():
    f=fixture(); raw=f.rename_axis('date').reset_index()
    _,_,reason=s.qualify(raw,f.index,[1],identity_events=[dict(last_predecessor_date=f.index[5],first_successor_date=f.index[6])])
    assert reason[0]=='KNOWN_IDENTITY_BREAK'
    _,_,reason=s.qualify(raw,f.index,[1],price_reserve=dict(start=f.index[12]))
    assert reason[0]=='UNRESOLVED_PRICE_OR_DISTRIBUTION_BASIS'


def test_adjusted_confirmation_does_not_buy_mechanical_split():
    f=fixture(); f.loc[f.index[:2],['open','high','low','close']]*=2
    raw=f.rename_axis('date').reset_index()
    grid,direction,reasons=s.qualify(raw,f.index,[1])
    assert reasons[0]=='' and direction[0]=='NONE'
    assert grid.close.iloc[:3].eq(100).all()


def test_chosen_side_and_blind_controls_use_same_pairs():
    f=pd.DataFrame(dict(symbol=['A','A','B','B','C','C'],side=['LONG','SHORT']*3,
        direction=['LONG','LONG','SHORT','SHORT','NONE','NONE']))
    chosen=s.select_arm(f,'CONFIRMED_DIRECTION')
    assert chosen.symbol.tolist()==['A','B'] and chosen.side.tolist()==['LONG','SHORT']
    assert s.select_arm(f,'CONFIRMED_PAIRS_ALL_LONG').symbol.tolist()==['A','B']
    assert s.select_arm(f,'ALL_TOP10_LONG').symbol.tolist()==['A','B','C']
