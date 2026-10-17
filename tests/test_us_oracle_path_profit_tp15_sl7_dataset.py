"""Native entry/exit cash, event ordering, standard financing, unknown labels."""
import numpy as np
import pandas as pd
import pytest

from scripts.research import us_oracle_path_profit_tp15_sl7_dataset as study


def fixture(case='expiry', price=100.):
    days=pd.bdate_range('2020-01-01','2021-03-01');j=days.get_loc(pd.Timestamp('2021-01-04'))
    raw=pd.DataFrame(dict(date=days,symbol='TEST',open=price,high=price*1.01,
        low=price*.99,close=price,adj_close=price,volume=1e7,is_filled=0,
        instrument_id=1,data_source='frozen',data_adjustment='split'))
    if case in ('tp','collision'):raw.loc[j+1,'high']=price*1.16
    if case in ('stop','collision'):raw.loc[j+1,'low']=price*.92
    if case in ('stop_gap','tp_gap'):
        value=price*(.90 if case=='stop_gap' else 1.20)
        raw.loc[j+2,['open','high','low','close']]=[value,value*1.01,value*.99,value]
    if case=='positive_expiry':
        raw.loc[j+21,['open','high','low','close']]=[price*1.05,price*1.06,price*1.04,price*1.05]
    grid,frames=study.market_frames(raw,days)
    return days,j,raw,grid,frames


@pytest.mark.parametrize('case,reason,multiplier,positive',[
    ('tp','take_profit',1.15,True),('stop','initial_stop',.93,False),
    ('collision','initial_stop',.93,False),('stop_gap','initial_stop_gap_open',.9,False),
    ('tp_gap','take_profit_gap_limit',1.15,True),('expiry','expiry_open',1.,False),
    ('positive_expiry','expiry_open',1.05,True)])
def test_real_native_parity(case,reason,multiplier,positive):
    days,j,raw,grid,frames=fixture(case)
    cfg=study.unit_config(days[0],days[-1])
    result=study.resolve_path(grid[['open','high','low','close']].iloc[j+1:j+22])
    assert result[1]==pytest.approx(100*multiplier) and result[2]==reason
    unit=study.native_unit(frames,j,result,cfg)
    assert bool(unit['label']) is positive
    assert study.assert_native_parity(frames,j,cfg)['native_parity']
    if case=='collision':assert unit['intrabar_ambiguous']
    if case=='positive_expiry':assert unit['exit_date']==days[j+21] and unit['holding_sessions']==20
    expected=.5*unit['entry_notional']*.065*(unit['exit_date']-unit['entry_date']).days/360
    assert unit['reference_financing']==pytest.approx(expected)
    assert unit['native_pnl']==pytest.approx(unit['exit_proceeds']-unit['entry_outlay'])
    assert unit['net_return']==pytest.approx((unit['native_pnl']-expected)/unit['entry_notional'])


def test_fractional_fill_no_cent_rounding_or_double_cost():
    days,j,raw,grid,frames=fixture('positive_expiry',20.0134)
    result=study.resolve_path(grid[['open','high','low','close']].iloc[j+1:j+22])
    unit=study.native_unit(frames,j,result,study.unit_config(days[0],days[-1]))
    assert unit['entry_price']==20.0134
    assert study.assert_native_parity(frames,j,study.unit_config(days[0],days[-1]))['native_parity']
    assert unit['native_pnl']<unit['quantity']*(unit['exit_price']-unit['entry_price'])


@pytest.mark.parametrize('fault,reason',[
    ('volume','MISSING_NONPOSITIVE_PATH'),('is_filled','FILLED_PATH'),
    ('instrument_id','UNKNOWN_CHANGED_INSTRUMENT_ID'),('data_source','UNKNOWN_CHANGED_DATA_SOURCE'),
    ('gap','NO_FILL_ENTRY_GAP')])
def test_unqualified_paths_stay_unknown_not_losses(fault,reason):
    days,j,raw,grid,frames=fixture()
    if fault=='volume':grid.loc[days[j+5],'volume']=0
    elif fault=='gap':grid.loc[days[j+1],['open','high','low','close']]=[104,105,103,104]
    elif fault=='is_filled':grid.loc[days[j+5],fault]=1
    elif fault=='instrument_id':grid.loc[days[j+5],fault]=2
    else:grid.loc[days[j+5],fault]='other'
    assert study.qualify_path(grid,j,days,'TEST',{})==reason


def test_early_profit_does_not_advance_label_availability():
    days,j,raw,grid,frames=fixture('tp')
    assert study.qualify_path(grid,j,days[:j+22],'TEST',{})=='IMMATURE_J22'
    assert days[j+22]>days[j+1]


def test_wrong_path_or_calendar_never_silently_truncated():
    with pytest.raises(ValueError):study.resolve_path(np.ones((20,4)))
    bad=np.ones((21,4));bad[0,1]=.5
    with pytest.raises(ValueError):study.resolve_path(bad)
