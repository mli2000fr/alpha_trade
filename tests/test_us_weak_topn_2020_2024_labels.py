"""Independent synthetic checks for the reconstructed offline label contracts."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from scripts.research import us_weak_topn_2020_2024_labels as labels


def prices(count=65,symbol='A'):
    calendar=pd.bdate_range('2020-01-02',periods=count)
    frame=pd.DataFrame(dict(date=calendar,symbol=symbol,open=100.,high=101.,low=99.,
        close=100.,adj_close=100.,volume=1000.,is_filled=0,
        instrument_id=1,data_source='SIP',data_adjustment='split'))
    return frame,calendar


def change_bar(frame,index,*,open=100.,high=101.,low=99.,close=100.):
    frame.loc[index,['open','high','low','close','adj_close']]=[open,high,low,close,close]


def row(frame,date):
    found=frame.loc[frame.date.eq(date)]
    assert len(found)==1
    return found.iloc[0]


def test_e2_is_close_to_close_at_three_sessions_not_next_open():
    bars,calendar=prices()
    signal=19
    change_bar(bars,signal+1,open=102.,high=104.,low=99.,close=100.)
    change_bar(bars,signal+3,open=100.,high=105.,low=99.,close=104.)
    result=row(labels.symbol_terminal(bars,calendar,3,{}),calendar[signal])
    assert result.terminal_return_h3==pytest.approx(.04)
    assert result.available_h3==calendar[signal+4]


def test_terminal_counts_calendar_sessions_instead_of_sparse_observations():
    bars,calendar=prices()
    bars=bars.drop(index=21)
    result=row(labels.symbol_terminal(bars,calendar,3,{}),calendar[19])
    assert pd.isna(result.terminal_return_h3)
    assert result.terminal_quality_h3=='INVALID_OR_MISSING_PATH'


@pytest.mark.parametrize('field,value,reason',[
    ('volume',0.,'INVALID_OR_MISSING_PATH'),
    ('is_filled',1,'INVALID_OR_MISSING_PATH'),
    ('instrument_id',2,'CHANGED_INSTRUMENT_ID'),
    ('data_source','EODHD','CHANGED_DATA_SOURCE'),
    ('data_adjustment','raw','CHANGED_DATA_ADJUSTMENT'),
])
def test_terminal_excludes_bad_path_and_changed_lineage(field,value,reason):
    bars,calendar=prices()
    bars.loc[21,field]=value
    result=row(labels.symbol_terminal(bars,calendar,3,{}),calendar[19])
    assert pd.isna(result.terminal_return_h3) and result.terminal_quality_h3==reason


def test_explicit_identity_registry_blocks_terminal_window_even_when_ids_match():
    bars,calendar=prices()
    registry={'A':[SimpleNamespace(last_predecessor_date=calendar[20],first_successor_date=calendar[21])]}
    result=row(labels.symbol_terminal(bars,calendar,3,registry),calendar[19])
    assert pd.isna(result.terminal_return_h3)
    assert result.terminal_quality_h3=='KNOWN_IDENTITY_BREAK'


def test_last_price_is_not_enough_without_later_label_availability_session():
    bars,calendar=prices()
    result=labels.symbol_terminal(bars,calendar,3,{}).iloc[-1]
    assert result.terminal_quality_h3=='IMMATURE_WINDOW'
    assert pd.isna(result.terminal_return_h3) and pd.isna(result.available_h3)


def test_price_adjustment_is_applied_once_consistently_to_ohlc():
    bars,calendar=prices()
    bars.loc[:,'adj_close']=bars.close*.5
    adjusted,good,_=labels.price_grid(bars,calendar)
    assert good.all()
    assert adjusted.iloc[0].to_dict()==dict(open=50.,high=50.5,low=49.5,close=50.)


def test_duplicate_price_keys_fail_instead_of_choosing_last_provider():
    bars,calendar=prices()
    with pytest.raises(ValueError,match='duplicate'):
        labels.symbol_terminal(pd.concat([bars,bars.iloc[[20]]]),calendar,3,{})


def test_h20_deciles_use_complete_feature_universe_not_top_subset():
    date=pd.Timestamp('2020-06-01')
    frame=pd.DataFrame(dict(date=date,symbol=[f'S{i:02}' for i in range(40)],
        terminal_return_h20=np.arange(40)/100))
    eligibility=frame[['date','symbol']]
    result=labels.global_deciles(frame,eligibility)
    assert result.oracle_decile.iloc[20]==6
    assert result.oracle_decile.iloc[-1]==10
    assert result.global_label_count_h20.eq(40).all()


@pytest.mark.parametrize('missing,known',[ (2,True),(3,False)])
def test_global_label_coverage_threshold_is_95_percent(missing,known):
    frame=pd.DataFrame(dict(date=pd.Timestamp('2020-06-01'),symbol=[f'S{i:02}' for i in range(40)],
        terminal_return_h20=np.arange(40,dtype=float)/100))
    frame.loc[:missing-1,'terminal_return_h20']=np.nan
    result=labels.global_deciles(frame,frame[['date','symbol']])
    assert result.oracle_decile.notna().any()==known
    assert result.global_label_coverage_h20.iloc[0]==pytest.approx((40-missing)/40)


def test_constant_global_returns_do_not_create_spurious_d10_labels():
    frame=pd.DataFrame(dict(date=pd.Timestamp('2020-06-01'),symbol=[f'S{i:02}' for i in range(40)],
        terminal_return_h20=0.))
    result=labels.global_deciles(frame,frame[['date','symbol']])
    assert result.oracle_decile.isna().all()


def test_e3_uses_atr_known_at_j_and_monitors_entry_candle():
    bars,calendar=prices()
    signal=19
    change_bar(bars,signal+1,open=100.,high=107.,low=99.,close=100.)
    result=row(labels.symbol_e3(bars,calendar,{}),calendar[signal])
    assert result.e3_atr_j==pytest.approx(2.)
    assert result.e3_stop_price==pytest.approx(95.)
    assert result.e3_tp_price==pytest.approx(106.)
    assert result.e3_long_target==1 and result.e3_exit_reason=='TP'
    assert result.e3_long_net_return==pytest.approx(.06-.0016)
    assert result.available_e3==calendar[signal+21]


def test_e3_same_entry_bar_stop_and_target_gives_stop_priority():
    bars,calendar=prices()
    change_bar(bars,20,open=100.,high=107.,low=94.,close=100.)
    result=row(labels.symbol_e3(bars,calendar,{}),calendar[19])
    assert result.e3_exit_reason=='SL' and result.e3_long_target==0
    assert result.e3_long_net_return==pytest.approx(-.05-.0016)


def test_e3_gap_below_stop_exits_at_open_not_at_stop_level():
    bars,calendar=prices()
    change_bar(bars,21,open=92.,high=93.,low=91.,close=92.)
    result=row(labels.symbol_e3(bars,calendar,{}),calendar[19])
    assert result.e3_exit_reason=='SL'
    assert result.e3_long_net_return==pytest.approx(-.08-.0016)


def test_e3_gap_above_target_uses_conservative_target_price():
    bars,calendar=prices()
    change_bar(bars,21,open=108.,high=109.,low=107.,close=108.)
    result=row(labels.symbol_e3(bars,calendar,{}),calendar[19])
    assert result.e3_exit_reason=='TP'
    assert result.e3_long_net_return==pytest.approx(.06-.0016)


def test_e3_exits_after_twenty_held_sessions_not_twenty_one():
    bars,calendar=prices()
    signal=19
    change_bar(bars,signal+20,open=100.,high=105.,low=99.,close=104.)
    change_bar(bars,signal+21,open=120.,high=121.,low=119.,close=120.)
    result=row(labels.symbol_e3(bars,calendar,{}),calendar[signal])
    assert result.e3_exit_reason=='TIME_EXIT'
    assert result.e3_long_net_return==pytest.approx(.04-.0016)


@pytest.mark.parametrize('entry,eligible',[(103.,True),(103.001,False)])
def test_e3_gap_boundary_accepts_exactly_three_percent(entry,eligible):
    bars,calendar=prices()
    change_bar(bars,20,open=entry,high=entry+1,low=entry-1,close=entry)
    result=row(labels.symbol_e3(bars,calendar,{}),calendar[19])
    assert pd.notna(result.e3_long_target)==eligible
    if not eligible:assert result.e3_quality=='ENTRY_GAP_OVER_3PCT'


def test_atr_is_prefix_invariant_and_restarts_after_price_hole():
    bars,calendar=prices()
    adjusted,good,codes=labels.price_grid(bars,calendar)
    original=labels.causal_wilder_atr(adjusted,good,codes)
    changed=adjusted.copy();changed.loc[calendar[40]:,'high']=150.
    assert np.allclose(original[:40],labels.causal_wilder_atr(changed,good,codes)[:40],equal_nan=True)
    good[20]=False
    result=labels.causal_wilder_atr(adjusted,good,codes)
    assert np.isnan(result[20:34]).all() and result[34]==pytest.approx(2.)


def test_e3_registry_break_resets_atr_when_instrument_codes_are_unchanged():
    bars,calendar=prices()
    registry={'A':[SimpleNamespace(last_predecessor_date=calendar[20],first_successor_date=calendar[21])]}
    result=row(labels.symbol_e3(bars,calendar,registry),calendar[25])
    assert pd.isna(result.e3_long_target) and result.e3_quality=='MISSING_J_ATR'


def test_e3_reserves_future_holes_even_if_tp_was_touched_earlier():
    bars,calendar=prices()
    change_bar(bars,20,open=100.,high=107.,low=99.,close=100.)
    bars=bars.drop(index=30)
    result=row(labels.symbol_e3(bars,calendar,{}),calendar[19])
    assert pd.isna(result.e3_long_target) and result.e3_quality=='INVALID_OR_MISSING_PATH'
