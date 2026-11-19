"""DAY is explicit and frozen; old OPG plans never become late purchases."""
from dataclasses import replace
from datetime import UTC,datetime,timedelta
from unittest.mock import MagicMock

import pandas as pd
import pytest

from common.q051_paper import entry_window,entry_tif,entry_price_basis,execution_config,settings
from execution_engine.winner_runtime import WinnerCampaignRuntime
from execution_engine.winner_plans import stage_targets
from execution_engine.order_intents import intent_to_alpaca_payload
from execution_engine.broker_adapter import BrokerAdapter
from execution_engine.winner_broker import NativeWinnerBroker,make_intent


def setup_day():
    from tests.test_q051_paper_profile import setup,NOW
    cfg,_,repo,broker,_=setup()
    from sqlalchemy import create_engine
    from execution_engine.winner_campaign_store import WinnerCampaignStore
    from execution_engine.models import ExecutionTarget
    from datetime import date
    store=WinnerCampaignStore(create_engine('sqlite://'))
    cfg=replace(cfg,paper_entry_time_in_force='day',paper_exit_time_in_force='day')
    target=ExecutionTarget('q-risk',date(2026,10,16),'TEST',8,100.,.2,'Technology',
        .7,'q051_sl5_cov60_vol20',None,risk_budget_dollars=50.,side='long')
    stage_targets(store,[target],cfg,'q-exec',now=NOW)
    return cfg,store,repo,broker


@pytest.mark.parametrize('stamp,allowed',[
    ('2026-10-16T19:59Z',False),('2026-10-16T23:05Z',True),
    ('2026-10-19T13:28Z',True),('2026-10-19T13:31Z',True),
    ('2026-10-19T19:59Z',True),('2026-10-19T20:00Z',False),
    ('2026-10-20T13:00Z',False)])
def test_day_is_valid_for_jplus1_only(stamp,allowed):
    cfg,store,*_=setup_day()
    state=store.rows()[0]['state']
    assert state['q051_entry_time_in_force']=='day'
    assert entry_window(state,pd.Timestamp(stamp).to_pydatetime()) is allowed
    old=dict(state);old.pop('q051_entry_time_in_force')
    assert entry_tif(old)=='opg'
    assert not entry_window(old,datetime(2026,10,19,14,tzinfo=UTC))


def test_day_runtime_sends_once_during_session_and_keeps_sl5_h10(monkeypatch):
    from tests.test_q051_paper_profile import approval
    monkeypatch.setattr('common.q051_paper.settings',lambda:dict(enabled=True))
    cfg,store,repo,broker=setup_day()
    when=datetime(2026,10,19,15,tzinfo=UTC)
    source=lambda *_:dict(bars=[],prior_session=datetime(2026,10,16).date(),ask=None,bid=None)
    def approve(state,*args):
        return dict(approval(state,*args),price_basis=entry_price_basis(state))
    run=lambda t:WinnerCampaignRuntime(store,repo,broker,cfg,market=source,risk=approve,now=t).run(store.rows())
    result=run(when);assert result['winner_buys_submitted']==1
    intent=broker.calls[0]
    assert intent.time_in_force=='day' and intent.winner_entry_mode=='q051_day'
    assert intent_to_alpaca_payload(intent,cfg)['time_in_force']=='day'
    for invalid in [replace(cfg,paper_strategy_profile=None),replace(cfg,paper_entry_time_in_force='opg')]:
        with pytest.raises(ValueError):intent_to_alpaca_payload(intent,invalid)
    broker.fill(3,101.,stamp=when,status='expired')
    run(when+timedelta(seconds=5));state=store.rows()[0]['state']
    assert state['lots'][0]['quantity']==3 and state['lots'][0]['stop']==95.95
    assert state['lots'][0]['stop_order_id'] and state['due_open']
    assert run(when+timedelta(seconds=10))['winner_buys_submitted']==0


def test_expired_zero_fill_does_not_stay_pending_or_resubmit(monkeypatch):
    from tests.test_q051_paper_profile import approval,NOW
    monkeypatch.setattr('common.q051_paper.settings',lambda:dict(enabled=True))
    cfg,store,repo,broker=setup_day()
    def approve(state,*args):return dict(approval(state,*args),price_basis=entry_price_basis(state))
    source=lambda *_:dict(bars=[],prior_session=NOW.date(),ask=None,bid=None)
    run=lambda t:WinnerCampaignRuntime(store,repo,broker,cfg,market=source,risk=approve,now=t).run(store.rows())
    run(NOW);broker.orders[broker.calls[0].intent_id]['status']='expired'
    run(NOW+timedelta(seconds=10))
    row=store.get(store.rows(active_only=False)[0]['state']['campaign_id'])
    assert row['state']['status']=='EXPIRED' and not row['state']['lots']
    assert len(broker.calls)==1 and run(NOW+timedelta(seconds=20))['winner_buys_submitted']==0


def test_native_bridge_keeps_frozen_day_when_watcher_config_is_generic():
    cfg,store,repo,_=setup_day();state=store.rows()[0]['state']
    generic=replace(cfg,paper_strategy_profile=None,paper_entry_time_in_force='opg')
    bridge=NativeWinnerBroker(repo,BrokerAdapter(MagicMock(),generic),generic)
    intent=make_intent(state,'buy',quantity=8,price=100.,tif='day',entry_mode='q051_day',order_type='market')
    bridge.persist_order(state,intent,MagicMock())
    assert repo.upsert_execution_broker_order.call_args.kwargs['raw_payload']['time_in_force']=='day'


def test_settings_require_explicit_supported_duration():
    raw={'us_pipeline':{'b_anti_sl_reference':{'enabled':True,'entry_time_in_force':'day'}}}
    assert settings(raw)['entry_time_in_force']=='day'
    raw['us_pipeline']['b_anti_sl_reference']['entry_time_in_force']='gtc'
    with pytest.raises(ValueError,match='entry_time_in_force'):settings(raw)


def test_h10_exit_day_keeps_open11_date_and_can_reconcile_in_generic_watcher(monkeypatch):
    from tests.test_q051_paper_profile import approval
    from common.winner_pyramiding import aware
    from common.q051_paper import exit_tif
    monkeypatch.setattr('common.q051_paper.settings',lambda:dict(enabled=True))
    cfg,store,repo,broker=setup_day()
    when=datetime(2026,10,19,15,tzinfo=UTC)
    source=lambda *_:dict(bars=[],prior_session=datetime(2026,10,16).date(),ask=None,bid=None)
    def approve(state,*args):return dict(approval(state,*args),price_basis=entry_price_basis(state))
    run=lambda t:WinnerCampaignRuntime(store,repo,broker,cfg,market=source,risk=approve,now=t).run(store.rows())
    run(when);broker.fill(8,100.,stamp=when);run(when+timedelta(seconds=5))
    state=store.rows()[0]['state'];due=aware(state['due_open'])
    assert exit_tif(state)=='day'
    result=run(due-timedelta(minutes=5))
    assert result['winner_exits_submitted']==1
    intent=broker.calls[-1]
    assert intent.side=='sell' and intent.qty==8 and intent.time_in_force=='day'
    assert intent_to_alpaca_payload(intent,cfg)['time_in_force']=='day'
    generic=replace(cfg,paper_strategy_profile=None,paper_exit_time_in_force='opg')
    bridge=NativeWinnerBroker(repo,BrokerAdapter(MagicMock(),generic),generic)
    bridge.persist_order(state,intent,MagicMock())
    assert repo.upsert_execution_broker_order.call_args.kwargs['raw_payload']['time_in_force']=='day'
    for invalid in [generic,replace(cfg,paper_exit_time_in_force='opg')]:
        with pytest.raises(ValueError):intent_to_alpaca_payload(intent,invalid)
    old=dict(state);old.pop('q051_exit_time_in_force')
    assert exit_tif(old)=='opg'
