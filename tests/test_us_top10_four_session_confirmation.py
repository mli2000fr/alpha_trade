import numpy as np
import pytest
from scripts.research import us_top10_four_session_confirmation as s
from tests.test_us_top10_three_session_confirmation import fixture


@pytest.mark.parametrize('values,expected',[
    ([99,100,101,102],'LONG'),([102,101,100,99],'SHORT'),([99,100,101,100],'NONE'),
    ([99,100,101,101],'NONE'),([99,101,100,102],'NONE'),([99,100,101,np.nan],'NONE')])
def test_four_strict_closes_including_j_plus_two(values,expected):
    assert s.directions(values,[1]).tolist()==[expected]


def test_signal_never_uses_entry_day_or_future_prices():
    prices=np.array([99,100,101,102,100,105.]); a=s.directions(prices,[1]); prices[4:]=1.
    np.testing.assert_array_equal(a,s.directions(prices,[1]))


def test_entry_j_plus_three_and_gap_loss_not_capped():
    f=fixture(); f.iloc[4,f.columns.get_indexer(['open','high','low','close'])]=[120,121,119,120]
    result=s.trades_for(f,[1],'LONG')
    assert result['entry_price'][0]==120 and result['exit_price'][0]==pytest.approx(100)
    assert result['gap_stop'][0] and result['exit_session'][0]==2


def test_expiry_j_plus_twelve_includes_ten_holding_sessions():
    f=fixture(); f.iloc[13,f.columns.get_indexer(['open','high','low','close'])]=[100,103,99,102]
    result=s.trades_for(f,[1],'LONG')
    assert result['exit_price'][0]==102 and result['exit_session'][0]==10


@pytest.mark.parametrize('bad_index',[0,13])
def test_both_ends_of_full_j_minus_one_to_j_plus_twelve_quality_window(bad_index):
    f=fixture(); raw=f.rename_axis('date').reset_index(); raw.loc[bad_index,'is_filled']=1
    _,_,reason=s.qualify(raw,f.index,[1]); assert reason[0]=='INVALID_OR_MISSING_CONFIRMATION_OR_PATH'


def test_event_crossing_whole_union_not_only_one_subwindow():
    f=fixture(); raw=f.rename_axis('date').reset_index()
    _,_,reason=s.qualify(raw,f.index,[1],identity_events=[dict(last_predecessor_date=f.index[0],first_successor_date=f.index[13])])
    assert reason[0]=='KNOWN_IDENTITY_BREAK'


def test_future_invalid_bar_does_not_change_observable_four_close_direction():
    f=fixture(); f.loc[f.index[:4],'adj_close']=[99,100,101,102]
    raw=f.rename_axis('date').reset_index()
    _,direction,reasons=s.qualify(raw,f.index,[1]); assert direction[0]=='LONG' and reasons[0]==''
    raw.loc[13,'is_filled']=1
    _,direction,reasons=s.qualify(raw,f.index,[1]); assert direction[0]=='LONG' and reasons[0]!=''
