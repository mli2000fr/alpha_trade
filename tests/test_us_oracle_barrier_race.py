import numpy as np
import pandas as pd
import pytest

from scripts.research.us_oracle_barrier_race import race


def window():
    return pd.DataFrame(dict(open=100.,high=100.,low=100.,close=100.),index=pd.bdate_range('2025-01-02',periods=20))


def test_long_target_first():
    frame=window()
    frame.iloc[3,frame.columns.get_loc('high')]=120.
    frame.iloc[5,frame.columns.get_loc('low')]=90.
    result=race(frame,'LONG')
    assert result['outcome']=='TARGET_FIRST'
    assert result['touch_session']==4


def test_long_stop_before_later_gain():
    frame=window()
    frame.iloc[2,frame.columns.get_loc('low')]=93.
    frame.iloc[5,frame.columns.get_loc('high')]=130.
    result=race(frame,'LONG')
    assert result['outcome']=='STOP_FIRST'
    assert result['target_touched_ever']


def test_short_target_and_stop_inverted():
    frame=window()
    frame.iloc[0,frame.columns.get_loc('low')]=80.
    assert race(frame,'SHORT')['outcome']=='TARGET_FIRST'
    frame=window()
    frame.iloc[0,frame.columns.get_loc('high')]=107.
    assert race(frame,'SHORT')['outcome']=='STOP_FIRST'


def test_ambiguous_bounds_and_gap_order():
    frame=window()
    frame.iloc[1,frame.columns.get_loc('high')]=125.
    frame.iloc[1,frame.columns.get_loc('low')]=90.
    result=race(frame,'LONG')
    assert result['outcome']=='AMBIGUOUS'
    assert result['conservative_outcome']=='STOP_FIRST'
    assert result['optimistic_outcome']=='TARGET_FIRST'
    frame.iloc[1,frame.columns.get_loc('open')]=121.
    assert race(frame,'LONG')['outcome']=='TARGET_FIRST'
    frame.iloc[1,frame.columns.get_loc('open')]=90.
    result=race(frame,'LONG')
    assert result['outcome']=='STOP_FIRST' and result['gap_stop']
    assert np.isclose(result['opening_side_return'],-.1)


def test_entry_bar_counts_and_exact_20_sessions():
    frame=window()
    frame.iloc[-1,frame.columns.get_loc('high')]=120.
    assert race(frame,'LONG')['touch_session']==20
    with pytest.raises(ValueError): race(frame.iloc[:-1],'LONG')


def test_neither_and_not_short_inverse_ratio():
    frame=window()
    frame.iloc[-1,frame.columns.get_loc('close')]=95.
    frame.iloc[-1,frame.columns.get_loc('low')]=95.
    result=race(frame,'SHORT')
    assert result['outcome']=='NEITHER'
    assert np.isclose(result['terminal_side_return'],.05)
