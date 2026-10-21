import numpy as np
import pandas as pd
import pytest

from scripts.research import us_top10_liquidity_gap_audit as s


def bars(n=50):
    return pd.DataFrame(dict(date=pd.bdate_range('2024-01-01',periods=n),open=100.,high=101.,low=99.,close=100.,
        volume=300000.,is_filled=0,data_source='eodhd_eod',data_adjustment='split',instrument_id=1))


def test_feature_no_future_leak():
    b=bars();days=pd.DatetimeIndex(b.date)
    _,before=s.past_features(b,days)
    b.loc[31:,['open','high','low','close','volume']]*=100
    _,after=s.past_features(b,days)
    pd.testing.assert_frame_equal(before.iloc[:31],after.iloc[:31])
    assert before.adv20.iloc[30]==30e6
    assert before.past_gap20.iloc[30]==0


@pytest.mark.parametrize('fault',['missing','filled','zero_volume','identity'])
def test_feature_complete_calendar_required(fault):
    b=bars();days=pd.DatetimeIndex(b.date)
    if fault=='missing':b=b.drop(index=20)
    if fault=='filled':b.loc[20,'is_filled']=1
    if fault=='zero_volume':b.loc[20,'volume']=0
    if fault=='identity':b.loc[20:,'instrument_id']=2
    _,f=s.past_features(b,days)
    assert f.iloc[30].isna().any()


@pytest.mark.parametrize('side',['LONG','SHORT'])
def test_tp_sl_collision_not_win(side):
    b=bars(20);b.loc[0,['high','low']]=[125.,75.]
    r=s.barrier_path(b,side)
    assert r['outcome']=='SL' and r['ambiguity']
    assert r['path_return']==pytest.approx(-.07)


@pytest.mark.parametrize('side',['LONG','SHORT'])
def test_gap_stop_worse_than_fixed_sl(side):
    b=bars(20)
    b.loc[1,['open','high','low','close']]=[85.,86.,84.,85.] if side=='LONG' else [115.,116.,114.,115.]
    r=s.barrier_path(b,side)
    assert r['outcome']=='SL' and r['gap_stop'] and not r['ambiguity']
    assert r['path_return']==pytest.approx(-.15)


def test_open_resolves_collision_before_intraday_low():
    b=bars(20);b.loc[1,['open','high','low','close']]=[125.,130.,90.,100.]
    r=s.barrier_path(b,'LONG')
    assert r['outcome']=='TP' and not r['ambiguity']
    assert r['exit_price']==120.


def test_good_final_direction_can_lose_first():
    b=bars(20);b.loc[1,'low']=92.;b.loc[8,['high','close']]=[130.,125.];b.loc[19,['high','close']]=[125.,120.]
    r=s.barrier_path(b,'LONG')
    assert r['right_terminal_but_stopped'] and r['favorable20_but_stopped']
    assert r['first_sl_session']==2 and r['first_tp_session']==9
    assert r['max_adverse_before_best_prior_bars']==pytest.approx(.08)


def test_unqualified_or_incomplete_path_not_filled():
    b=bars(20);b.loc[5,'is_filled']=1
    assert s.barrier_path(b,'LONG')['path_status']=='UNQUALIFIED_PATH'
    with pytest.raises(ValueError):s.barrier_path(b.iloc[:19],'LONG')


def test_filters_strict_gap_and_no_outcome_inputs():
    f=pd.DataFrame(dict(adv20=[20e6,19e6,25e6],past_gap20=[.069,.01,.07],tp_first=[False,True,True]))
    assert s.filter_mask(f,'BOTH').tolist()==[True,False,False]
    a=s.filter_mask(f,'BOTH');f.tp_first=~f.tp_first
    pd.testing.assert_series_equal(a,s.filter_mask(f,'BOTH'))
