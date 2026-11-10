from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from backtesting.range_support_entry import aggregate_m15,first_rebound,freeze_range,RangeSupportSettings,ScheduledEntries
from backtesting.simulator import BacktestEngine


def tape():
    stamps=pd.date_range('2026-10-19T13:30Z',periods=12,freq='5min')
    return pd.DataFrame(dict(timestamp=stamps,open=100.,high=101.,low=99.,close=100.5,volume=100.))


def schedule():
    return ScheduledEntries(pd.DataFrame([dict(signal_date='2026-10-16',symbol='AAA',
        confirmed_at='2026-10-19T13:45:00Z',available_at='2026-10-19T14:00:30Z',
        execution_at='2026-10-19T14:05:00Z',setup='A2_RANGE_SUPPORT_LONG')]))


def test_frozen_range_requires_impulse_before_base_and_spaced_contacts():
    frame=pd.DataFrame(dict(timestamp=pd.date_range('2026-10-15T13:30Z',periods=46,freq='15min'),
        open=100.,close=100.,high=101.,low=99.,volume=100.))
    for i in range(14,26):
        frame.loc[i,['open','close','high','low']]=[100+(i-14)*.5,100+(i-13)*.5,100+(i-13)*.5+.2,100+(i-14)*.5-.2]
    for i in range(26,46):
        value=106.+(.6 if i%2 else 0.)
        frame.loc[i,['open','close','high','low']]=[value+.1,value+.2,value+.4,value]
    frame['end']=frame.timestamp+pd.Timedelta(minutes=15)
    zone,reason=freeze_range(frame)
    assert reason=='RANGE_READY' and zone['impulse_atr']>=2 and min(zone['low_touches'],zone['high_touches'])>=2
    assert zone['frozen_at']==frame.end.iloc[-1].isoformat()
    assert freeze_range(frame.iloc[:30])[1]=='MISSING_PRE_SIGNAL_M15_CONTEXT'
    frame.loc[14:25,'close']=100.
    assert freeze_range(frame)[1]=='NO_BULLISH_PRE_RANGE_IMPULSE'


def test_m15_requires_three_closed_contiguous_bars_and_is_future_invariant():
    f=tape();a=aggregate_m15(f,date(2026,10,19),known_at=pd.Timestamp('2026-10-19T13:45Z'))
    assert len(a)==1 and a.iloc[0].volume==300
    f.loc[3:,'high']=np.nan;f=pd.concat([f,f.iloc[[6]]],ignore_index=True)
    pd.testing.assert_frame_equal(a,aggregate_m15(f,date(2026,10,19),known_at=pd.Timestamp('2026-10-19T13:45Z')))
    assert aggregate_m15(f.iloc[[0,2]],date(2026,10,19),known_at=pd.Timestamp('2026-10-19T13:45Z')).empty


def test_rebound_is_available_after_delay_and_does_not_trade_at_observed_past_open():
    c=aggregate_m15(tape(),date(2026,10,19),known_at=pd.Timestamp('2026-10-19T14:30Z'))
    zone=dict(low=100.,tolerance=.2,high=103.,frozen_at='2026-10-16T20:00Z')
    event,reason=first_rebound(c,zone,date(2026,10,19))
    assert reason=='A2_CONFIRMED' and pd.Timestamp(event['execution_at'])==pd.Timestamp('2026-10-19T14:05Z')
    mutated=c.copy();mutated.loc[1:,'close']=1.
    assert first_rebound(mutated,zone,date(2026,10,19))==(event,reason)
    c.loc[0,'close']=99.
    assert first_rebound(c,zone,date(2026,10,19))[1]=='RANGE_INVALIDATED_BEFORE_REBOUND'


@pytest.mark.usefixtures('isolated_winner_config')
def test_engine_scheduled_entry_prices_budget_and_open_horizon_are_native():
    from tests.test_winner_daily_entry import daily_fixture
    cfg,args,_=daily_fixture(confirmation_bars=0,horizon_sessions=1)
    result=BacktestEngine(cfg).run(**args,winner_entry_timing_source=schedule())
    buy=result.trade_events_df.loc[result.trade_events_df.event.eq('BUY_FILL')].iloc[0]
    assert buy.time==pd.Timestamp('2026-10-19T14:05Z') and buy.price==102.
    assert buy.price_source=='OBSERVED_5M_OPEN' and buy.execution_proxy=='SCHEDULED_5M_OPEN'
    trade=result.closed_trades_df.iloc[0]
    assert trade.exit_date==pd.Timestamp('2026-10-20T13:30Z') and trade.exit_reason=='HORIZON_OPEN'
    assert result.tracker_snapshot['winner_replay']['initial_entry']['mode']=='SCHEDULED_5M_OPEN_AFTER_SIGNAL'


@pytest.mark.usefixtures('isolated_winner_config')
def test_scheduled_volatility_budget_uses_actual_execution_price_and_can_veto(monkeypatch):
    from tests.test_winner_daily_entry import daily_fixture
    from backtesting.winner_portfolio_budget import replay_protections
    import backtesting.winner_portfolio_budget as module
    cfg,args,_=daily_fixture(confirmation_bars=0)
    dates=pd.bdate_range('2026-01-01','2026-10-16')
    close=pd.DataFrame({'AAA':100.*np.cumprod(np.resize([1.25,.8],len(dates)))},index=dates)
    policy,_=replay_protections(close,daily_entry=True,target=.01)
    prices=[];native=module.portfolio_limit
    def wrapped(*a,**kw):prices.append(kw['price']);return native(*a,**kw)
    monkeypatch.setattr(module,'portfolio_limit',wrapped)
    result=BacktestEngine(cfg).run(**args,winner_entry_timing_source=schedule(),winner_entry_risk_policy=policy)
    assert prices==[102.] and policy.receipts[0]['final_quantity']==0
    assert not result.trade_events_df.get('event',pd.Series(dtype=str)).eq('BUY_FILL').any()


@pytest.mark.usefixtures('isolated_winner_config')
def test_missing_future_bar_never_retroactively_removes_the_entry():
    from tests.test_winner_daily_entry import daily_fixture
    cfg,args,raw=daily_fixture(confirmation_bars=0)
    a=BacktestEngine(cfg).run(**args,winner_entry_timing_source=schedule())
    raw[cfg.start_date,'AAA']=raw[cfg.start_date,'AAA'].drop(index=40)
    b=BacktestEngine(cfg).run(**args,winner_entry_timing_source=schedule())
    for result in [a,b]:
        buy=result.trade_events_df.loc[result.trade_events_df.event.eq('BUY_FILL')].iloc[0]
        assert buy.time==pd.Timestamp('2026-10-19T14:05Z') and buy.price==102.
    buy=b.trade_events_df.loc[b.trade_events_df.event.eq('BUY_FILL')].iloc[0]
    mark=b.intraday_equity_curve.loc[b.intraday_equity_curve.timestamp.eq(pd.Timestamp('2026-10-19T14:10Z'))].iloc[0]
    assert mark.gross==buy.quantity*buy.price
    assert mark.equity==pytest.approx(cfg.initial_equity-buy.costs)


def test_schedule_rejects_future_evidence_and_is_one_attempt_only():
    s=schedule();rows=pd.DataFrame({'symbol':['AAA']})
    assert s(date(2026,10,16),date(2026,10,19),pd.Timestamp('2026-10-19T13:45Z'),rows)=={}
    assert list(s(date(2026,10,16),date(2026,10,19),pd.Timestamp('2026-10-19T14:05Z'),rows))==['AAA']
    with pytest.raises(ValueError,match='already consumed'):
        s(date(2026,10,16),date(2026,10,19),pd.Timestamp('2026-10-19T14:05Z'),rows)
