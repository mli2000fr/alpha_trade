import pandas as pd
import pytest

from scripts.research.us_a2_replay_inputs_20261109 import IndexedSchedule,FixedWait


def event_frame():
    return pd.DataFrame([dict(signal_date='2026-10-16',symbol='AAA',confirmed_at='2026-10-19T13:45Z',
        available_at='2026-10-19T14:00:30Z',execution_at='2026-10-19T14:05Z',setup='A2_RANGE_SUPPORT_LONG')])


def test_indexed_schedule_matches_original_and_refuses_duplicate_or_future_evidence():
    from backtesting.range_support_entry import ScheduledEntries
    a,b=IndexedSchedule(event_frame()),ScheduledEntries(event_frame())
    rows=pd.DataFrame({'symbol':['AAA','BBB']});signal=pd.Timestamp('2026-10-16').date();day=pd.Timestamp('2026-10-19').date()
    for stamp in ['2026-10-19T13:30Z','2026-10-19T14:00Z','2026-10-19T14:05Z']:
        assert a(signal,day,pd.Timestamp(stamp),rows)==b(signal,day,pd.Timestamp(stamp),rows)
    with pytest.raises(ValueError,match='consumed'):a(signal,day,pd.Timestamp('2026-10-19T14:05Z'),rows)
    f=event_frame();f['execution_at']='2026-10-19T13:50Z'
    with pytest.raises(ValueError,match='delayed'):IndexedSchedule(f)


@pytest.mark.usefixtures('isolated_winner_config')
def test_event_pruning_never_reserves_future_capital_or_changes_results():
    from tests.test_winner_intraday import fixture
    from backtesting.simulator import BacktestEngine
    from backtesting.winner_portfolio_budget import replay_protections
    cfg,args,_=fixture(symbols=('AAA','BBB'),confirmation_bars=0,initial_position_fraction=1.,stop_loss_pct=.05)
    cfg.winner_daily_entry_enabled=True
    args['signals_df']=pd.DataFrame([dict(trade_date=pd.Timestamp('2026-10-16').date(),symbol=s,rank=i+1,selected=True)
        for i,s in enumerate(['AAA','BBB'])])
    policy,_=replay_protections(args['close'],daily_entry=True,target=.2)
    full=BacktestEngine(cfg).run(**args,winner_entry_timing_source=IndexedSchedule(event_frame()),winner_entry_risk_policy=policy)
    args['signals_df']=args['signals_df'][args['signals_df'].symbol.eq('AAA')]
    policy,_=replay_protections(args['close'],daily_entry=True,target=.2)
    pruned=BacktestEngine(cfg).run(**args,winner_entry_timing_source=IndexedSchedule(event_frame()),winner_entry_risk_policy=policy)
    pd.testing.assert_series_equal(full.equity_curve,pruned.equity_curve,check_exact=True)
    pd.testing.assert_frame_equal(full.closed_trades_df,pruned.closed_trades_df,check_exact=True)
    assert full.trade_events_df.loc[full.trade_events_df.event.eq('BUY_FILL'),'symbol'].tolist()==['AAA']


def test_fixed_wait_is_only_a_clock_control_with_no_price_pattern_filter():
    s=FixedWait();rows=pd.DataFrame({'symbol':['AAA','BBB']})
    signal=pd.Timestamp('2026-10-16').date();day=pd.Timestamp('2026-10-19').date()
    assert not s(signal,day,pd.Timestamp('2026-10-19T14:05Z'),rows)
    result=s(signal,day,pd.Timestamp('2026-10-19T14:30Z'),rows)
    assert set(result)=={'AAA','BBB'} and result['AAA']['setup']=='FIXED_1030_NY_WAIT'
