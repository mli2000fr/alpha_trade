"""Isolated full SHORT lifecycle with real native risk; no production routing."""
from dataclasses import replace
from datetime import date,timedelta
from types import SimpleNamespace

import pandas as pd
import pytest

from backtesting.simulator import BacktestEngine
from backtesting.winner_intraday import MemoryCampaignStore
from backtesting.winner_short_broker import ShortReplayBroker
from backtesting.winner_short import short_plan,ShortReplayCoordinator,reapprove_short
from common.market_calendar import get_market_calendar
from common.winner_pyramiding import WinnerPyramidingConfig
from execution_engine.models import ExecutionTarget
from risk_management.circuit_breaker import CircuitBreaker
from tests.test_winner_intraday import fixture

pytestmark=pytest.mark.usefixtures('isolated_winner_config')


def lifecycle(*,confirmation=2,stop=.05,tp=None,trailing=None,reinforce=False,last=date(2026,10,20),
              target_side='short',price_path=None,delay=0,risk_override=None):
    cfg,args,raw=fixture(last=last,confirmation_bars=confirmation,stop_loss_pct=stop,reinforcement_enabled=reinforce)
    policy=replace(cfg.exec_config.winner_pyramiding,trailing_stop_pct=trailing,take_profit_pct=tp,
        market_data_delay_seconds=delay,standard_entry_quote_check_enabled=confirmation!=0)
    exec_cfg=replace(cfg.exec_config,winner_pyramiding=policy)
    risk=replace(cfg.risk_config,short_selling_enabled=True,**(risk_override or {}))
    engine=BacktestEngine(cfg);book=ShortReplayBroker(engine,fee=.0008,borrow_fee_annual=.003)
    store=MemoryCampaignStore();cal=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    target=ExecutionTarget('risk',date(2026,10,16),'AAA',20,100.,.5,'Technology',1.,'test',None,
        risk_budget_dollars=400.,side=target_side)
    plan=short_plan(target,exec_cfg,now=pd.Timestamp('2026-10-19T13:29:59Z').to_pydatetime(),calendar=cal)
    store.create(plan,'default','paper','risk');decisions=[]
    breaker=CircuitBreaker(risk)
    def recheck(state,version,quantity,snapshot,now,kind):
        context=dict(account_id='default',broker_mode='paper',captured_at=now,equity=book.equity(),risk_config=replace(risk,account_equity=book.equity()),
            available_buying_power=book.capacity(),positions=[dict(p,quantity=p['qty']) for p in book.positions()],
            pending_entries=book.pending_entries(),sector_map={'AAA':'Technology'},circuit_breaker=breaker,
            allocation_scale=1.,volatility_allocation_scale=1.,cost_reserve_pct=.0008,return_matrix=pd.DataFrame(),
            adv_usd=1e9,entry_data_qualified=True,regime_qualified=True,concentration_qualified=True,
            concentration_allowed=True,corporate_actions_qualified=True,breaker_qualified=True,entries_allowed=True,
            replay_observed_price=book.marks['AAA'])
        result=reapprove_short(state,version,quantity,snapshot,now,kind,context=context)
        decisions.append((now,kind,result));return result
    for session in [s for s in cal.sessions(cfg.start_date,last) if s.is_open]:
        frame=raw[(session.session_date,'AAA')].copy()
        frame.loc[1:,['open','close','high','low']]=[98.,98.,98.1,97.9]
        if price_path is not None:price_path(session.session_date,frame)
        for index,row in frame.iterrows():
            stamp=row.timestamp.to_pydatetime();book.now=stamp;book.marks['AAA']=float(row.open)
            bar={'AAA':row.to_dict()}
            book.resolve(bar,opening=True)
            def source(state,now):
                tail=frame.loc[frame.timestamp+pd.Timedelta(minutes=5)<=pd.Timestamp(now)-pd.Timedelta(seconds=delay)].tail(max(confirmation+1,3))
                bars=[dict(r,timestamp=r['timestamp'].to_pydatetime(),session_tag='regular') for r in tail.to_dict('records')]
                if delay and (confirmation or state['lots']):
                    from common.winner_delayed import delayed_snapshot
                    return delayed_snapshot(bars,policy,now)|dict(prior_session_low=99.9,prior_session_high=100.1)
                return dict(bars=bars,prior_session_low=99.9,prior_session_high=100.1,
                    bid=float(row.open),ask=float(row.open),standard_entry_quote_check_enabled=confirmation!=0)
            result=ShortReplayCoordinator(store,book,exec_cfg,market=source,risk=recheck,now=stamp,
                lifecycle_only=bool(delay and confirmation)).run(store.rows())
            assert result['winner_failures']==0
            if delay:
                # Use a non-grid delay just like the observed-clock adapter.
                observed=stamp+timedelta(seconds=delay%300 or 0)
                book.now=observed
                ShortReplayCoordinator(store,book,exec_cfg,market=source,risk=recheck,now=observed).run(store.rows())
            book.now=stamp+timedelta(minutes=5)
            book.resolve(bar,opening=False);book.marks['AAA']=float(row.close)
        book.expire_day_entries();book.charge_borrow(session.session_date)
        ShortReplayCoordinator(store,book,replace(exec_cfg,winner_pyramiding=replace(policy,enabled=False)),
            market=lambda *a:{},risk=recheck,now=session.close_at_utc,lifecycle_only=True).run(store.rows())
    return book,store,decisions


def test_confirmation_uses_downward_break_not_upward_and_stop_above_entry():
    book,store,decisions=lifecycle()
    fills=[e for e in book.events if e['event']=='SHORT_FILL']
    assert len(fills)==1 and fills[0]['price']==98 and fills[0]['time']>=pd.Timestamp('2026-10-19T13:45Z')
    state=next(iter(store.records.values()))['state'];lot=state['lots'][0]
    assert lot['stop']==102.9 and lot['tp'] is None
    assert decisions[0][2]['side']=='sell'
    def rising(day,frame):frame.loc[1:,['open','close','high','low']]=[102.,102.,102.1,101.9]
    other,_,_=lifecycle(price_path=rising)
    assert not any(e['event']=='SHORT_FILL' for e in other.events)


def test_zero_confirmation_and_horizon_cover_with_cost_reconciliation():
    book,store,_=lifecycle(confirmation=0,last=date(2026,11,18))
    first=next(e for e in book.events if e['event']=='SHORT_FILL')
    assert first['time']==pd.Timestamp('2026-10-19T13:30Z')
    trade=book.trades[0]
    assert trade['side']=='sell' and trade['exit_reason']=='HORIZON_LATE_MARKET'
    assert trade['exit_date']==pd.Timestamp('2026-11-16T14:30Z')
    assert trade['borrow_fees']>0 and book.equity()-4000==pytest.approx(trade['pnl'])


def test_native_short_cap_and_risk_veto_are_respected():
    book,_,_=lifecycle(risk_override={'max_short_exposure':.0001})
    assert not any(e['event']=='SHORT_FILL' for e in book.events)


def test_stop_tp_and_trailing_are_real_short_protections():
    def stop(day,frame):frame.loc[5:,['open','close','high','low']]=[110.,110.,111.,109.]
    book,_,_=lifecycle(price_path=stop)
    assert book.trades[0]['exit_reason']=='STOP_GAP' and book.trades[0]['pnl']<0
    def gain(day,frame):frame.loc[5:,['open','close','high','low']]=[85.,85.,86.,84.]
    book,_,_=lifecycle(tp=.1,price_path=gain)
    assert book.trades[0]['exit_reason']=='TP_GAP_CAPPED' and book.trades[0]['exit_price']==88.2
    def reversal(day,frame):
        frame.loc[5:9,['open','close','high','low']]=[85.,85.,85.1,84.9]
        frame.loc[10:,['open','close','high','low']]=[95.,95.,95.1,94.9]
    book,_,_=lifecycle(trailing=.1,price_path=reversal)
    assert book.trades[0]['pnl']>0 and book.trades[0]['exit_price']<98


def test_one_add_on_winning_short_never_on_a_losing_short():
    def gain(day,frame):frame.loc[8:,['open','close','high','low']]=[90.,90.,90.1,89.9]
    book,store,_=lifecycle(reinforce=True,price_path=gain)
    fills=[e for e in book.events if e['event']=='SHORT_FILL']
    assert len(fills)==2 and fills[1]['price']<fills[0]['price']
    assert next(iter(store.records.values()))['state']['add_attempted']


def test_delayed_short_has_no_retroactive_fill():
    book,_,_=lifecycle(delay=930)
    fills=[e for e in book.events if e['event']=='SHORT_FILL']
    assert fills and fills[0]['time']>pd.Timestamp('2026-10-19T14:00Z')
    assert fills[0]['execution_proxy']=='NEXT_OBSERVED_5M_OPEN'
