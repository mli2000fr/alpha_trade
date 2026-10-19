import numpy as np
import pandas as pd
import pytest

from scripts.research.us_top10_intraday_breakout import first_break, simulate, qualify_day, independent_ids


def bars(values, start='2025-01-02 14:30Z'):
    a = np.asarray(values, dtype=float)
    times = pd.date_range(start, periods=len(a), freq='5min')
    f = pd.DataFrame(a, columns=['open', 'high', 'low', 'close'])
    return f.assign(bar_timestamp=times, bar_end_timestamp=times+pd.Timedelta(minutes=5),
        is_filled=0, data_adjustment='raw', volume=100, provider='alpaca', data_source='alpaca_sip',
        market_code='US_EQ', interval_code='5m', session_tag='regular')


def test_next_bar_not_trigger_bar_and_no_reversal():
    f = bars([[100,120,80,106], [107,108,90,94], [95,105,93,104]])
    assert first_break(f, 105, 95) == (1, 'LONG')
    r = simulate(f.iloc[1:], 'LONG')
    assert r['entry_price'] == 107
    assert r['outcome'] == 'SL'


def test_last_bar_only_break_is_not_executable():
    assert first_break(bars([[100,102,99,101],[101,110,100,109]]),105,95) is None


def test_touch_is_not_close_break():
    assert first_break(bars([[100,110,90,105],[105,106,94,95],[95,96,93,94]]),105,95) is None


def test_first_short_wins():
    assert first_break(bars([[100,101,93,94],[95,108,94,107],[107,109,106,108]]),105,95) == (1,'SHORT')


@pytest.mark.parametrize('side,path', [
    ('LONG', [[100,101,99,100],[90,92,88,91]]),
    ('SHORT', [[100,101,99,100],[110,112,108,111]])])
def test_adverse_gaps_not_capped(side,path):
    r = simulate(bars(path),side)
    assert r['gross'] == pytest.approx(-.10)
    assert r['gap_stop']


@pytest.mark.parametrize('side,path', [
    ('LONG', [[100,101,99,100],[120,122,119,121]]),
    ('SHORT', [[100,101,99,100],[80,82,78,81]])])
def test_favourable_gap_limited(side,path):
    r = simulate(bars(path), side)
    assert r['gross'] == pytest.approx(.10)
    assert r['outcome'] == 'TP'


@pytest.mark.parametrize('side', ['LONG','SHORT'])
def test_collision_conservative(side):
    r = simulate(bars([[100,115,85,101]]),side)
    assert r['gross'] == pytest.approx(-.05)
    assert r['collision']


def test_grid_half_day_and_missing_or_duplicate_rejected():
    f = bars([[100,101,99,100]]*42)
    assert qualify_day(f,f.bar_timestamp.iloc[0],f.bar_end_timestamp.iloc[-1])[1]=='OK'
    assert qualify_day(f.iloc[1:],f.bar_timestamp.iloc[0],f.bar_end_timestamp.iloc[-1])[1]=='INCOMPLETE_5M_GRID'
    assert qualify_day(pd.concat([f,f.iloc[:1]]),f.bar_timestamp.iloc[0],f.bar_end_timestamp.iloc[-1])[1]=='DUPLICATE_BARS'


@pytest.mark.parametrize('column,value', [('is_filled',1),('volume',0),('data_source','alpaca_iex'),('data_adjustment','split')])
def test_invalid_metadata(column,value):
    f = bars([[100,101,99,100]])
    f[column] = value
    assert qualify_day(f,f.bar_timestamp.iloc[0],f.bar_end_timestamp.iloc[-1])[0] is None


def test_timeout_costs_and_short_borrow():
    f = bars([[100,101,99,100],[100,102,99,101]])
    r = simulate(f,'LONG')
    assert r['exit_time']==f.bar_end_timestamp.iloc[-1]
    assert r['net']==pytest.approx(.01-.0008*2.01)
    assert simulate(f,'SHORT')['borrow']>0


def test_independence_blocks_both_directions_entire_window():
    f = pd.DataFrame(dict(pair_id=[0,1,2],symbol=['A']*3,rank=[1]*3,
        date=pd.to_datetime(['2025-01-02','2025-01-03','2025-01-20']),
        entry_date=pd.to_datetime(['2025-01-03','2025-01-06','2025-01-21']),
        last_path_date=pd.to_datetime(['2025-01-17','2025-01-20','2025-02-03'])))
    assert independent_ids(f)=={0,2}


def test_bad_path_rejected():
    with pytest.raises(ValueError):
        simulate(bars([[100,99,101,100]]),'LONG')


@pytest.mark.parametrize('side,values,outcome', [
    ('LONG', [[100,110,99,105]], 'TP'), ('LONG', [[100,101,95,98]], 'SL'),
    ('SHORT', [[100,101,90,95]], 'TP'), ('SHORT', [[100,105,99,101]], 'SL')])
def test_exact_decimal_touch_and_interval_timestamp(side,values,outcome):
    f = bars(values)
    r = simulate(f,side)
    assert r['outcome'] == outcome
    assert r['exit_time_precision'] == '5M_INTERVAL'
    assert r['exit_time'] == f.bar_end_timestamp.iloc[0]
