import numpy as np
import pytest
from scripts.research import us_top10_failed_start_replay as s


def path():
    return np.tile([100.,101.,99.,100.],(10,1))


def test_first_close_low_mfe_sells_next_open_not_same_close():
    a=path(); a[1]=[102,103,101,102]
    r=s.simulate(a,'FAILED_START_FIRST_CLOSE',.022)
    assert r['exit_price']==102 and r['exit_session']==2 and r['outcome']=='DAILY_EXIT'


def test_entry_day_stop_cannot_be_reversed_by_close_decision():
    a=path(); a[0,2]=94
    r=s.simulate(a,'FAILED_START_FIRST_CLOSE',.022)
    assert r['outcome']=='SL' and r['exit_session']==1 and not r['exit_requested']


def test_entry_day_take_profit_keeps_priority():
    a=path(); a[0,1]=111
    r=s.simulate(a,'FAILED_START_FIRST_CLOSE',.022)
    assert r['outcome']=='TP' and r['exit_session']==1 and not r['exit_requested']


@pytest.mark.parametrize('op,high,low,outcome,price',[(80,81,79,'SL',80),(120,121,119,'TP',110)])
def test_pending_exit_cannot_improve_native_open_gap_protection(op,high,low,outcome,price):
    a=path(); a[1]=[op,high,low,op]
    r=s.simulate(a,'FAILED_START_FIRST_CLOSE',.022)
    assert r['exit_requested'] and r['native_open_priority'] and not r['daily_exit_executed']
    assert r['outcome']==outcome and r['exit_price']==pytest.approx(price)


def test_pending_open_exit_precedes_later_intraday_stop():
    a=path(); a[1]=[99,100,94,95]
    r=s.simulate(a,'FAILED_START_FIRST_CLOSE',.022)
    assert r['outcome']=='DAILY_EXIT' and r['exit_price']==99


def test_high_ever_reached_in_entry_day_not_closing_return_is_rule():
    a=path(); a[0]=[100,103,99,100]
    r=s.simulate(a,'FAILED_START_FIRST_CLOSE',.022)
    assert not r['exit_requested'] and r['outcome']=='TIMEOUT'


def test_no_second_chance_signal_on_later_closes():
    a=path(); a[0,1]=103; a[1:,1]=101
    r=s.simulate(a,'FAILED_START_FIRST_CLOSE',.022)
    assert r['outcome']=='TIMEOUT' and not r['exit_requested']


def test_threshold_is_strict_and_not_rounded():
    a=path(); a[0,1]=103
    exact=a[0,1]/a[0,0]-1
    r=s.simulate(a,'FAILED_START_FIRST_CLOSE',exact)
    assert not r['exit_requested']


def test_future_prices_do_not_change_decision():
    a=path(); b=a.copy(); b[3:]=[100,109,98,105]
    x=s.simulate(a,'FAILED_START_FIRST_CLOSE',.022); y=s.simulate(b,'FAILED_START_FIRST_CLOSE',.022)
    assert x==y


def test_temporal_control_sells_even_when_progress_was_good():
    a=path(); a[0,1]=103
    r=s.simulate(a,'EXIT_ALL_FIRST_CLOSE',.022)
    assert r['daily_exit_executed'] and r['exit_session']==2


def test_baseline_exact_scalar_parity_both_gaps_and_ohlc_collision():
    import pandas as pd
    for a in [path(),np.array([[100,111,94,100]]+[[100,101,99,100]]*9,dtype=float)]:
        old=s.independent_scalar.scalar(pd.DataFrame(a,columns=['open','high','low','close']),'LONG')
        new=s.simulate(a,'BASELINE',.022)
        for k in ['entry_price','exit_price','exit_session','outcome','gap_stop']: assert old[k]==new[k]
