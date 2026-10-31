"""Regression: valid 930s SIP evidence must not be lost on a 5m price grid."""
from dataclasses import replace
from datetime import date, timedelta
from unittest.mock import Mock

import pandas as pd
import pytest

from backtesting.simulator import BacktestEngine
from backtesting.winner_clock import next_observed_open, observation_offset
from common.winner_pyramiding import WinnerPyramidingConfig
from tests.test_winner_intraday import fixture

pytestmark=pytest.mark.usefixtures('isolated_winner_config')
FIRST=date(2026,10,19)


def test_930_evidence_is_evaluated_at_availability_then_filled_at_next_open(monkeypatch):
    from backtesting import winner_intraday
    cfg,args,raw=fixture(last=FIRST,market_data_delay_seconds=930)
    frame=raw[(FIRST,'AAA')]
    frame.loc[frame.timestamp.eq(pd.Timestamp('2026-10-19T14:00Z')),
        ['open','close','high','low']]=[101.,101.,101.1,100.9]
    frame.loc[frame.timestamp.ge(pd.Timestamp('2026-10-19T14:05Z')),
        ['open','close','high','low']]=[103.,103.,103.1,102.9]
    observed=[]
    real=winner_intraday.reapprove_campaign
    def check(state,version,quantity,snapshot,now,kind,**kw):
        observed.append((now,snapshot.copy()))
        return real(state,version,quantity,snapshot,now,kind,**kw)
    monkeypatch.setattr(winner_intraday,'reapprove_campaign',check)
    result=BacktestEngine(cfg).run(**args)
    buys=result.trade_events_df.query("event == 'BUY_FILL'")
    assert len(buys)==1
    assert observed[0][0]==pd.Timestamp('2026-10-19T14:00:30Z')
    assert pd.Timestamp(observed[0][1]['data_cutoff'])==pd.Timestamp('2026-10-19T13:45Z')
    assert observed[0][1]['ask'] is None
    assert buys.iloc[0].time==pd.Timestamp('2026-10-19T14:05Z')
    assert buys.iloc[0].price==103.  # Neither the old 102 close nor the 14:00 open of 101.
    assert buys.iloc[0].execution_proxy=='NEXT_OBSERVED_5M_OPEN'
    meta=result.tracker_snapshot['winner_replay']
    assert meta['status']=='COMPLETED_EXPLORATORY' and not meta['full_live_parity']
    assert meta['replay_clock']['observation_offset_seconds']==30
    assert meta['costs']>0


@pytest.mark.parametrize('missing',[False,True])
def test_deferred_buy_cancels_at_exact_next_open_without_using_future_low(missing):
    cfg,args,raw=fixture(last=FIRST,market_data_delay_seconds=930)
    frame=raw[(FIRST,'AAA')]
    frame.loc[frame.timestamp.ge(pd.Timestamp('2026-10-19T14:05Z')),
        ['open','close','high','low']]=[110.,110.,110.1,90.]
    if missing:
        raw[(FIRST,'AAA')]=frame.loc[~frame.timestamp.eq(pd.Timestamp('2026-10-19T14:05Z'))]
    result=BacktestEngine(cfg).run(**args)
    events=result.trade_events_df
    assert not events.event.eq('BUY_FILL').any()
    canceled=events.loc[events.event.eq('DELAYED_ENTRY_CANCELED')].iloc[0]
    assert canceled.time==pd.Timestamp('2026-10-19T14:05Z')
    assert canceled.reason==('NEXT_OPEN_MISSING' if missing else 'LIMIT_OR_CAPACITY')
    assert canceled.decision_time=='2026-10-19T14:00:30+00:00'
    assert result.tracker_snapshot['winner_replay']['status']==(
        'INCOMPLETE_COVERAGE' if missing else 'COMPLETED_EXPLORATORY')


def test_930_still_requires_native_factor_inputs():
    cfg,args,_=fixture(last=FIRST,market_data_delay_seconds=930)
    cfg.risk_config=replace(cfg.risk_config,enable_factor_model=True)
    source=Mock(side_effect=ValueError('No causal factor observations'))
    result=BacktestEngine(cfg).run(**args,winner_factor_source=source)
    assert source.called and source.call_args.args[2].second==30
    assert not result.trade_events_df.event.eq('BUY_FILL').any()
    meta=result.tracker_snapshot['winner_replay']
    assert meta['status']=='INCOMPLETE_COVERAGE'
    assert any('FACTOR_CONTEXT_UNAVAILABLE' in str(g) for g in meta['coverage_gaps'])


def test_930_reserves_shared_budget_between_decision_and_fill(monkeypatch):
    from backtesting import winner_intraday
    cfg,args,_=fixture(last=FIRST,market_data_delay_seconds=930,
        symbols=('AAA','BBB','CCC'),initial_position_fraction=1.)
    seen=[]
    real=winner_intraday.reapprove_campaign
    def check(*a,**kw):
        seen.append(kw['context']['pending_entries'])
        return real(*a,**kw)
    monkeypatch.setattr(winner_intraday,'reapprove_campaign',check)
    result=BacktestEngine(cfg).run(**args)
    assert any(p for p in seen)
    buys=result.trade_events_df.query("event == 'BUY_FILL'")
    assert len(buys)>=1 and (buys.price*buys.quantity+buys.costs).sum()<=4000
    assert result.intraday_equity_curve.gross.max()<=4000


def test_zero_confirmation_930_keeps_standard_open_and_real_holding_deadline():
    cfg,args,_=fixture(last=date(2026,11,18),market_data_delay_seconds=930,confirmation_bars=0)
    result=BacktestEngine(cfg).run(**args)
    trade=result.closed_trades_df.iloc[0]
    assert trade.entry_date==pd.Timestamp('2026-10-19T13:30Z')
    assert trade.exit_date==pd.Timestamp('2026-11-16T14:30Z')
    assert result.tracker_snapshot['winner_replay']['replay_clock']['observation_offset_seconds']==0


def test_delayed_fill_is_protected_and_exits_on_real_holding_deadline():
    cfg,args,_=fixture(last=date(2026,11,4),market_data_delay_seconds=930,horizon_sessions=10)
    result=BacktestEngine(cfg).run(**args)
    trade=result.closed_trades_df.iloc[0]
    assert trade.entry_date==pd.Timestamp('2026-10-19T14:05Z')
    assert trade.exit_date==pd.Timestamp('2026-11-02T14:30Z')
    assert trade.exit_reason=='HORIZON_OPEN'


def test_clock_respects_early_close_and_cannot_defer_to_tomorrow():
    assert next_observed_open(pd.Timestamp('2026-11-27T17:55:30Z')) is None
    assert next_observed_open(pd.Timestamp('2026-11-27T17:50:30Z'))==pd.Timestamp('2026-11-27T17:55Z')
    assert observation_offset(WinnerPyramidingConfig(market_data_delay_seconds=930))==30


def test_lifecycle_clock_reconciles_and_protects_without_new_market_or_risk_call():
    from execution_engine.winner_runtime import WinnerCampaignRuntime
    from tests.test_winner_runtime import setup,tick,NOW
    cfg,store,repo,broker=setup(trailing_stop_pct=None)
    broker.fail_post=True  # Filled at broker; response lost before local reconciliation.
    tick(cfg,store,repo,broker)
    assert not store.rows()[0]['state']['lots']
    source=Mock(side_effect=AssertionError('No evidence clock'))
    risk=Mock(side_effect=AssertionError('No entry decision'))
    report=WinnerCampaignRuntime(store,repo,broker,cfg,market=source,risk=risk,
        now=NOW+timedelta(minutes=5),lifecycle_only=True).run(store.rows())
    assert report['winner_failures']==0 and report['winner_protections_submitted']==1
    assert len(broker.calls)==1
    source.assert_not_called();risk.assert_not_called()


def test_off_grid_stop_amendment_preserves_old_stop_until_next_observed_open():
    from types import SimpleNamespace
    from backtesting.winner_intraday import ReplayBroker
    cfg,_,_=fixture(last=FIRST,market_data_delay_seconds=930)
    book=ReplayBroker(BacktestEngine(cfg),fee=.0008)
    book.now=pd.Timestamp('2026-10-19T14:00:30Z')
    book.cash=3900.;book.marks={'AAA':102.}
    book.lots['parent']=dict(symbol='AAA',quantity=1,remaining=1,entry=100.,campaign_id='test',
        entry_time=pd.Timestamp('2026-10-19T13:30Z'),entry_fee=.08)
    book.orders['old']=dict(id='old',status='new',type='stop',side='sell',
        stop_price=95.,parent='parent',filled_qty='0',qty='1')
    intent=SimpleNamespace(intent_id='new',symbol='AAA',side='sell',qty=1,stop_price=103.)
    book.tighten({},dict(stop_order_id='old'),intent)
    book.now=pd.Timestamp('2026-10-19T14:05Z')
    book.resolve({'AAA':dict(open=102.,close=105.,high=106.,low=101.)},opening=False)
    assert not book.trades  # No retroactive sale at the 14:00 open or earlier low.
    book.resolve({'AAA':dict(open=102.,close=102.,high=102.,low=102.)},opening=True)
    assert len(book.trades)==1 and book.trades[0]['exit_price']==102.
    assert book.trades[0]['exit_date']==book.now


def test_last_interval_delayed_decision_is_canceled_without_overnight_order():
    from dataclasses import asdict
    from types import SimpleNamespace
    from backtesting.winner_intraday import ReplayBroker
    cfg,_,_=fixture(last=FIRST,market_data_delay_seconds=930)
    book=ReplayBroker(BacktestEngine(cfg),fee=.0008)
    book.now=pd.Timestamp('2026-10-19T19:55:30Z')
    intent=SimpleNamespace(intent_id='last',order_type='limit',qty=1,side='buy',
        submission_key='last',symbol='AAA',time_in_force='ioc',stop_price=None,limit_price=103.)
    book.submit(dict(policy=asdict(cfg.exec_config.winner_pyramiding),lots=[],campaign_id='last'),intent)
    assert book.orders['last']['status']=='canceled'
    assert book.pending_entries()==[] and book.lots=={}


def test_known_global_halt_cancels_deferred_buy_before_next_open(monkeypatch):
    from backtesting.winner_global_liquidation import GlobalLiquidation
    cfg,args,_=fixture(last=FIRST,market_data_delay_seconds=930)
    original=GlobalLiquidation.observe
    def halt_after_decision(self,stamp,equity,book,evaluated):
        original(self,stamp,equity,book,evaluated)
        if book.pending_entries():
            self.halted=True
    monkeypatch.setattr(GlobalLiquidation,'observe',halt_after_decision)
    cfg.risk_config=replace(cfg.risk_config,force_close_on_breaker=True)
    result=BacktestEngine(cfg).run(**args)
    assert not result.trade_events_df.event.eq('BUY_FILL').any()
    assert result.trade_events_df.reason.eq('GLOBAL_DRAWDOWN_BEFORE_EXECUTION').any()


def test_same_open_gap_liquidation_sees_just_filled_deferred_lot(monkeypatch):
    from backtesting.winner_global_liquidation import GlobalLiquidation
    cfg,args,_=fixture(last=FIRST,market_data_delay_seconds=930)
    original=GlobalLiquidation.observe
    def gap_at_fill(self,stamp,equity,book,evaluated):
        original(self,stamp,equity,book,evaluated)
        if not self.halted and book.positions():
            self.halted=True
            self.pending=dict(event_id=1,detected_at=stamp.isoformat(),
                symbols=['AAA'],reason='HARD_DRAWDOWN')
    monkeypatch.setattr(GlobalLiquidation,'observe',gap_at_fill)
    result=BacktestEngine(cfg).run(**args)
    assert result.trade_events_df.event.eq('BUY_FILL').sum()==1
    assert result.trade_events_df.event.eq('SELL_FILL').sum()==1
    assert result.tracker_snapshot['winner_replay']['gross']==0
    assert result.closed_trades_df.iloc[0].exit_reason=='GLOBAL_DRAWDOWN'
