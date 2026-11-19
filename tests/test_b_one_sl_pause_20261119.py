from datetime import date
import pandas as pd
import pytest
from scripts.research.us_b_one_sl_pause_policy_20261119 import StopPause


def calendar():
    return [d.date() for d in pd.bdate_range('2025-01-01',periods=300)]


def stamp(days,i,time='16:00'):
    return pd.Timestamp(str(days[i])+' '+time,tz='America/New_York')


def test_single_stop_blocks_immediately_then_100_following_sessions():
    days=calendar();p=StopPause(days)
    p.observe('A','STOP',stamp(days,3),'one')
    assert p.blocked(stamp(days,3,'15:59'))==set()
    assert p.blocked(stamp(days,3))=={'A'}
    assert p.blocked(stamp(days,103,'09:30'))=={'A'}
    assert p.blocked(stamp(days,104,'09:29'))==set()


def test_gap_is_available_at_open_and_other_exits_do_not_pause():
    days=calendar();p=StopPause(days)
    p.observe('A','STOP_GAP',stamp(days,3,'09:30'),'one')
    p.observe('B','HORIZON_OPEN',stamp(days,3,'09:30'),'two')
    assert p.blocked(stamp(days,3,'09:29:59'))==set()
    assert p.blocked(stamp(days,3,'09:30'))=={'A'}


def test_no_refill_or_priority_change_and_disabled_control_is_noop():
    days=calendar();rows=pd.DataFrame(dict(symbol=['A','B','C'],rank=[1,2,3]))
    for enabled in [False,True]:
        p=StopPause(days,enabled=enabled)
        p.observe('B','STOP',stamp(days,2),'one')
        result=p.select(days[2],rows,stamp(days,3,'09:29:59'))
        assert result['selected']==(['A','C'] if enabled else ['A','B','C'])
        assert rows.symbol.tolist()==['A','B','C']


def test_future_exits_do_not_affect_earlier_decision_and_reject_duplicate():
    days=calendar();p=StopPause(days)
    p.observe('A','STOP',stamp(days,10),'one')
    assert p.blocked(stamp(days,9))==set()
    assert p.triggers==[]
    with pytest.raises(ValueError,match='Duplicate'):
        p.observe('A','STOP',stamp(days,10),'one')


@pytest.mark.usefixtures('isolated_winner_config')
def test_no_pause_adapter_reproduces_native_fills_and_equity():
    from tests.test_winner_daily_entry import daily_fixture
    from backtesting.simulator import BacktestEngine
    cfg,args,_=daily_fixture(confirmation_bars=0,stop_loss_pct=.05)
    native=BacktestEngine(cfg).run(**args)
    # Use the fixture's market sessions, including its 2026 dates and expiry tail.
    from modelFactory.oracle.build_labels import nyse_sessions
    p=StopPause([d.date() for d in nyse_sessions(date(2026,1,1),date(2028,1,1))],enabled=False)
    with p.installed():
        actual=BacktestEngine(cfg).run(**args,winner_selection_source=p.select)
    pd.testing.assert_series_equal(actual.equity_curve,native.equity_curve)
    pd.testing.assert_frame_equal(actual.closed_trades_df,native.closed_trades_df)


@pytest.mark.usefixtures('isolated_winner_config')
def test_executed_stop_blocks_next_session_purchase_in_actual_engine():
    from tests.test_winner_daily_entry import daily_fixture
    from backtesting.simulator import BacktestEngine
    from modelFactory.oracle.build_labels import nyse_sessions
    cfg,args,raw=daily_fixture(confirmation_bars=0,stop_loss_pct=.05)
    second=args['signals_df'].copy();second['trade_date']=date(2026,10,19)
    args['signals_df']=pd.concat([args['signals_df'],second],ignore_index=True)
    raw[date(2026,10,19),'AAA'].loc[1,'low']=90.
    args['low']=args['low'].copy();args['low'].loc['2026-10-19','AAA']=90.
    native=BacktestEngine(cfg).run(**args)
    assert native.trade_events_df.event.eq('BUY_FILL').sum()==2
    p=StopPause([d.date() for d in nyse_sessions(date(2026,1,1),date(2028,1,1))])
    with p.installed():
        actual=BacktestEngine(cfg).run(**args,winner_selection_source=p.select)
    assert actual.trade_events_df.event.eq('BUY_FILL').sum()==1
    assert len(p.triggers)==1 and p.triggers[0]['trigger_session']=='2026-10-19'
    assert any(d['excluded']==['AAA'] for d in p.decisions)
