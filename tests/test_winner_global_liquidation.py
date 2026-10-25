"""Offline global DD liquidation: causal marks, fees, cancellation and residual holdings."""
from dataclasses import replace
from datetime import datetime,UTC,timedelta,date
from types import SimpleNamespace

import pandas as pd
import pytest

from backtesting.simulator import BacktestEngine,BacktestConfig
from backtesting.winner_global_liquidation import GlobalLiquidation,close_campaign
from execution_engine.config import ExecutionConfig
from risk_management.config import RiskConfig
from tests.test_winner_intraday import fixture
from tests.test_winner_runtime import setup,tick


def control(*,hard=.25,fraction=.5,halt=False,cycle=None,months=0):
    risk=RiskConfig(max_portfolio_drawdown_pct=.15,force_close_on_breaker=True,force_close_pct=fraction)
    cfg=BacktestConfig(start_date=date(2020,1,1),end_date=date(2026,10,21),initial_equity=4000.,
        winner_global_drawdown_halt=halt,winner_hard_drawdown_pct=hard,
        winner_cycle_drawdown_pct=cycle,winner_drawdown_cooldown_months=months)
    ex=ExecutionConfig(force_close_on_breaker=True,force_close_pct=fraction)
    return GlobalLiquidation(cfg,risk,ex)


class MarkBook:
    def __init__(self):
        self.marks={'AAA':80.,'BBB':90.,'CCC':100.}
        self.lots={s:dict(symbol=s,remaining=1,entry=100.) for s in self.marks}
        self.events=[]
    def positions(self):
        return [dict(symbol=s,qty=1,side='long') for s in self.marks]


def evaluation(tripped=False,peak=4000):
    return dict(reference_peak=peak,circuit_breaker=SimpleNamespace(just_tripped=lambda:tripped))


def test_soft_fifteen_selects_worst_half_not_total_or_repeated_on_each_bar():
    guard=control();book=MarkBook();stamp=datetime(2026,10,19,14,tzinfo=UTC)
    guard.observe(stamp,3400.,book,evaluation(True))
    assert guard.pending['symbols']==['AAA','BBB'] and not guard.halted
    assert guard.pending['threshold_pct']==.15 and guard.pending['force_close_pct']==.5
    guard.observe(stamp+timedelta(minutes=5),3350.,book,evaluation(True))
    assert guard.counter==1


def test_absolute_twenty_five_latches_and_upgrades_pending_soft_close():
    guard=control();book=MarkBook();stamp=datetime(2026,10,19,14,tzinfo=UTC)
    guard.observe(stamp,3400.,book,evaluation(True))
    guard.observe(stamp+timedelta(minutes=5),3000.,book,evaluation(False))
    assert guard.halted and guard.pending['symbols']==['AAA','BBB','CCC']
    assert guard.pending['force_close_pct']==1 and guard.pending['threshold_pct']==.25
    assert guard.pending['reason']=='HARD_DRAWDOWN'
    guard.observe(stamp+timedelta(minutes=10),5000.,book,evaluation(False))
    assert guard.halted  # Never silently reset/rearm historical loss limit.


@pytest.mark.parametrize('bad',[.10,.15,1.,float('nan'),True])
def test_invalid_hard_threshold_fails_closed(bad):
    with pytest.raises(ValueError):control(hard=bad)


def test_elevated_historical_peak_is_not_reset_to_initial_deposit():
    guard=control();book=MarkBook();stamp=datetime(2026,10,19,14,tzinfo=UTC)
    guard.observe(stamp,8000.,book,evaluation(False,8000))
    guard.observe(stamp+timedelta(days=400),6000.,book,evaluation(False,6500))
    assert guard.halted and guard.pending['peak_at_detection']==8000.


def test_empty_portfolio_at_hard_limit_still_blocks_future_buys():
    guard=control();book=MarkBook();book.marks={}
    guard.observe(datetime(2026,10,19,14,tzinfo=UTC),2900.,book,evaluation())
    assert guard.halted and guard.pending['symbols']==[]


def test_coordinator_exit_cancels_protection_and_closes_only_remaining_quantity():
    cfg,store,repo,broker=setup()
    tick(cfg,store,repo,broker)
    record=store.rows()[0];quantity=record['state']['lots'][0]['remaining']
    broker.marks={'TEST':broker.price}
    closed=close_campaign(record,store,repo,broker,cfg,datetime(2026,10,19,14,20,tzinfo=UTC),1)
    assert closed==quantity and broker.position_quantity==0
    state=store.get(record['state']['campaign_id'])['state']
    assert state['status']=='CLOSED' and state['lots'][0]['remaining']==0
    assert sum(c.intent_role=='exit' for c in broker.calls)==1
    assert not store.rows()


def test_unconfirmed_protection_cancel_does_not_send_market_sale():
    cfg,store,repo,broker=setup();tick(cfg,store,repo,broker)
    record=store.rows()[0];broker.marks={'TEST':broker.price}
    broker.cancel=lambda key:dict(broker.get(key),status='pending_cancel')
    with pytest.raises(ValueError,match='cancellation unconfirmed'):
        close_campaign(record,store,repo,broker,cfg,datetime(2026,10,19,14,20,tzinfo=UTC),1)
    assert not any(c.intent_role=='exit' for c in broker.calls)


def data_with_global_drawdown(*,hard=.25,last=date(2026,10,21)):
    cfg,args,raw=fixture(last=last,symbols=('AAA','BBB','CCC'),initial_position_fraction=1.,stop_loss_pct=.5)
    # Large but bounded positions; local SL50 isolates the GLOBAL risk mechanism.
    cfg.risk_config=replace(cfg.risk_config,risk_per_trade_pct=.4,max_position_weight=.3,
        max_portfolio_drawdown_pct=.15,max_daily_loss_pct=.9,force_close_on_breaker=True,
        force_close_pct=.5,rolling_peak_window_days=0)
    cfg.exec_config=replace(cfg.exec_config,force_close_on_breaker=True,force_close_pct=.5)
    cfg.winner_hard_drawdown_pct=hard
    first=cfg.start_date
    # Establish a known high-water mark, then return part of the unrealized gain.
    # No look-ahead high/low is used by the global trigger.
    for symbol in ('AAA','BBB','CCC'):
        f=raw[first,symbol]
        f.loc[5:9,['open','close','high','low']]=[130.,130.,130.1,129.9]
        f.loc[10:,['open','close','high','low']]=[75.,75.,75.1,74.9]
    return cfg,args,raw


def test_replay_hard_exit_fees_flat_cash_and_no_later_reentry():
    cfg,args,raw=data_with_global_drawdown()
    # Keep explicit source closures referring to the same dict when extending paths.
    result=BacktestEngine(cfg).run(**args)
    info=result.tracker_snapshot['winner_replay']['global_liquidation']
    assert info['halted'] and info['hard_threshold_pct']==.25
    exits=result.closed_trades_df
    global_exits=exits[exits.exit_reason.eq('GLOBAL_DRAWDOWN')]
    assert len(global_exits)==3
    assert result.tracker_snapshot['winner_replay']['open_positions']==[]
    assert (global_exits.exit_fees>0).all()
    event=next(e for e in info['events'] if e['reason']=='HARD_DRAWDOWN')
    assert pd.Timestamp(event['executed_at'])>=pd.Timestamp(event['detected_at'])
    fills=result.trade_events_df
    buys=fills[fills.event.eq('BUY_FILL')]
    assert not (pd.to_datetime(buys.time,utc=True)>=pd.Timestamp(event['detected_at'])).any()
    assert result.intraday_equity_curve.iloc[-1].gross==0
    assert result.equity_curve.iloc[-1]==pytest.approx(result.tracker_snapshot['winner_replay']['settled_cash'])


def test_no_global_exit_when_disabled_and_legacy_path_remains_active():
    cfg,args,_=fixture()
    result=BacktestEngine(cfg).run(**args)
    assert not result.tracker_snapshot['winner_replay']['global_liquidation']['enabled']
    assert not result.trade_events_df.event.eq('GLOBAL_DD_TRIGGER').any()


def test_soft_exit_is_one_episode_not_repeated_five_minute_halving():
    cfg,args,raw=data_with_global_drawdown(last=date(2026,10,19))
    # Portfolio drawdown ~18%, below hard25. Retain native degraded B4.
    cfg.risk_config=replace(cfg.risk_config,policy='b4')
    args['close']['SPY']=100.+pd.Series(range(len(args['close'])),index=args['close'].index)*.01
    for symbol in ('AAA','BBB','CCC'):
        raw[cfg.start_date,symbol].loc[10:,['open','close','high','low']]=[105.,105.,105.1,104.9]
    result=BacktestEngine(cfg).run(**args)
    info=result.tracker_snapshot['winner_replay']['global_liquidation']
    assert not info['halted'] and len(info['events'])==1
    assert info['events'][0]['reason']=='SOFT_DRAWDOWN'
    assert len(info['events'][0]['symbols'])==2
    assert len(result.tracker_snapshot['winner_replay']['open_positions'])==1
    assert result.drawdown_breaker_df.allocation.min()<1.


def test_close_trigger_uses_next_open_with_gap_not_the_known_close():
    cfg,args,raw=data_with_global_drawdown(last=date(2026,10,19))
    for symbol in ('AAA','BBB','CCC'):
        f=raw[cfg.start_date,symbol]
        f.loc[9,['open','close','high','low']]=[130.,75.,130.1,74.9]
        f.loc[10:,['open','close','high','low']]=[70.,70.,70.1,69.9]
    result=BacktestEngine(cfg).run(**args)
    info=result.tracker_snapshot['winner_replay']['global_liquidation']
    event=info['events'][0]
    assert event['reason']=='HARD_DRAWDOWN'
    next_open=raw[cfg.start_date,'AAA'].loc[10,'timestamp']
    assert pd.Timestamp(event['detected_at'])==next_open
    assert pd.Timestamp(event['executed_at'])==next_open
    assert result.closed_trades_df.exit_price.eq(70.).all()
    assert info['max_observed_drawdown_pct'] < -25.


def test_standing_stop_at_next_open_wins_race_and_no_double_sale():
    cfg,args,raw=data_with_global_drawdown(last=date(2026,10,19))
    for symbol in ('AAA','BBB','CCC'):
        f=raw[cfg.start_date,symbol]
        f.loc[9,['open','close','high','low']]=[130.,75.,130.1,74.9]
        f.loc[10:,['open','close','high','low']]=[40.,40.,40.1,39.9]
    result=BacktestEngine(cfg).run(**args)
    trades=result.closed_trades_df
    assert len(trades)==3 and trades.exit_reason.eq('STOP_GAP').all()
    sells=result.trade_events_df[result.trade_events_df.event.eq('SELL_FILL')]
    buys=result.trade_events_df[result.trade_events_df.event.eq('BUY_FILL')]
    assert sells.quantity.sum()==buys.quantity.sum()
    assert not result.tracker_snapshot['winner_replay']['open_positions']


@pytest.mark.parametrize('cycle,months',[(.15,3),(.25,3),(.20,0),(.20,-1),(.20,3.),(.20,True),(None,3)])
def test_cooldown_policy_fails_closed_on_invalid_values(cycle,months):
    with pytest.raises(ValueError):control(cycle=cycle,months=months)


def test_calendar_cooldown_clips_month_end_and_global_peak_never_resets():
    guard=control(cycle=.20,months=3);book=MarkBook();book.marks={}
    book.equity=lambda:3190.
    stamp=datetime(2027,1,31,15,tzinfo=UTC)
    guard.observe(stamp,3190.,book,evaluation(True))
    assert guard.blocks_entries and not guard.halted
    assert guard.pending['reason']=='CYCLE_DRAWDOWN'
    store=SimpleNamespace(rows=lambda:[])
    guard.execute(stamp,store,None,book,None)
    assert guard.paused_until==pd.Timestamp('2027-04-30T00:00:00-04:00')
    assert not guard.resume(datetime(2027,4,29,13,30,tzinfo=UTC),book)
    assert guard.resume(datetime(2027,4,30,13,30,tzinfo=UTC),book)
    assert not guard.blocks_entries and guard.cycle==2
    assert guard.cycle_peak==3190. and guard.peak==4000.
    # Only ~6% additional loss after reset reaches the unchanged global25 cap.
    guard.observe(datetime(2027,4,30,14,tzinfo=UTC),2990.,book,evaluation(False,3190.))
    assert guard.halted and guard.pending['reason']=='HARD_DRAWDOWN'
    assert guard.pending['peak_at_detection']==4000.


def test_actual_resume_rearms_cycle_risk_and_only_latest_signal_not_stale_plans():
    cfg,args,raw=data_with_global_drawdown(last=date(2027,1,21))
    cfg.winner_cycle_drawdown_pct=.20;cfg.winner_drawdown_cooldown_months=3
    cfg.risk_config=replace(cfg.risk_config,policy='b4')
    args['close']['SPY']=100.+pd.Series(range(len(args['close'])),index=args['close'].index)*.01
    names=('AAA','BBB','CCC')
    for symbol in names:
        raw[cfg.start_date,symbol].loc[10:,['open','close','high','low']]=[100.,100.,100.1,99.9]
        f=raw[date(2027,1,19),symbol]
        f.loc[1:,['open','close','high','low']]=[106.,106.,106.1,105.9]
    # Jan18 is a US holiday. Reopening Jan19 must use Jan15, not old October plans.
    fresh=pd.DataFrame([dict(trade_date=date(2027,1,15),symbol=s,rank=i+1,selected=True) for i,s in enumerate(names)])
    args['signals_df']=pd.concat([args['signals_df'],fresh],ignore_index=True)
    result=BacktestEngine(cfg).run(**args)
    info=result.tracker_snapshot['winner_replay']['global_liquidation']
    cycles=[e for e in info['events'] if e['reason']=='CYCLE_DRAWDOWN']
    assert len(cycles)==1 and len(info['resumes'])==1
    resume=pd.Timestamp(info['resumes'][0]['resumed_at'])
    assert resume==pd.Timestamp('2027-01-19T14:30Z')
    buys=result.trade_events_df[result.trade_events_df.event.eq('BUY_FILL')]
    during=(pd.to_datetime(buys.time,utc=True)>=pd.Timestamp(cycles[0]['detected_at'])) & (pd.to_datetime(buys.time,utc=True)<resume)
    assert not during.any() and (pd.to_datetime(buys.time,utc=True)>=resume).any()
    assert info['resumes'][0]['global_peak']==cycles[0]['peak_at_detection']
    assert info['resumes'][0]['equity']==pytest.approx(cycles[0]['equity_after'])
