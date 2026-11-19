"""A generic watcher must reconcile frozen Q051 auction orders and actual fills."""
from dataclasses import replace
from datetime import UTC,datetime,timedelta
from copy import deepcopy
from unittest.mock import MagicMock

import pytest

from common.q051_paper import execution_config,reference
from common.winner_pyramiding import due_open
from execution_engine.broker_adapter import BrokerAdapter
from execution_engine.winner_broker import NativeWinnerBroker,make_intent
from execution_engine.winner_runtime import WinnerCampaignRuntime


def state():
    return dict(campaign_id='wp-real-campaign',risk_run_id='risk',exec_run_id='exec',
        account_id='default',broker_mode='paper',symbol='TEST',
        paper_strategy_profile=reference('q051_b_witness_v1'))


def test_generic_watcher_journals_opg_with_frozen_profile_before_any_sql_mutation():
    frozen=state();cfg=replace(execution_config('default'),paper_strategy_profile=None)
    repo=MagicMock();adapter=BrokerAdapter(MagicMock(),cfg)
    bridge=NativeWinnerBroker(repo,adapter,cfg)
    intent=make_intent(frozen,'buy',quantity=8,price=100,tif='opg',entry_mode='q051_moo',order_type='market')
    observed=MagicMock()
    bridge.persist_order(frozen,intent,observed)
    assert repo.upsert_execution_broker_order.call_args.kwargs['raw_payload']['time_in_force']=='opg'
    repo.reset_mock();bad=deepcopy(frozen);bad['account_id']='test1'
    with pytest.raises(ValueError,match='compte/mode'):bridge.persist_order(bad,intent,observed)
    repo.upsert_execution_order_request_from_intent.assert_not_called()
    repo.upsert_execution_broker_order.assert_not_called()


@pytest.mark.parametrize('quantity,status',[(3,'expired'),(8,'filled')])
def test_actual_fill_recognized_once_under_generic_watcher_with_stop_and_open11(monkeypatch,quantity,status):
    from tests.test_q051_paper_profile import setup,approval,NOW
    monkeypatch.setattr('common.q051_paper.settings',lambda:dict(enabled=True))
    cfg,store,repo,broker,_=setup()
    market=lambda *_:dict(bars=[],prior_session=NOW.date(),ask=None,bid=None)
    first=WinnerCampaignRuntime(store,repo,broker,cfg,market=market,risk=approval,now=NOW).run(store.rows())
    assert first['winner_buys_submitted']==1
    generic=replace(cfg,paper_strategy_profile=None)
    bridge=NativeWinnerBroker(repo,BrokerAdapter(MagicMock(),generic),generic)
    booked={}
    repo.load_cumulative_filled_qty.side_effect=lambda request_id:booked.get(request_id,0)
    repo.load_entry_fill_price.return_value=100.
    def insert(fill,**kw):booked[fill.intent_id]=booked.get(fill.intent_id,0)+fill.filled_qty
    repo.insert_execution_broker_fill.side_effect=insert
    broker.persist=bridge.persist
    stamp=datetime(2026,10,19,13,30,tzinfo=UTC)
    broker.fill(quantity,100.,stamp=stamp,status=status)
    run=lambda now:WinnerCampaignRuntime(store,repo,broker,generic,market=market,risk=approval,now=now).run(store.rows())
    result=run(stamp+timedelta(seconds=5))
    assert result['winner_fills_reconciled']==1 and result['winner_protections_submitted']==1
    saved=store.rows()[0]['state']
    assert saved['lots'][0]['quantity']==quantity and saved['lots'][0]['stop']==95.
    assert saved['lots'][0]['stop_order_id'] and saved['first_fill_at']==stamp.isoformat()
    assert saved['due_open']==due_open(stamp,cfg.winner_pyramiding).isoformat()
    assert all(o['status']=='DONE' for o in saved['operations'])
    calls=len(broker.calls);fills=repo.insert_execution_broker_fill.call_count
    again=run(stamp+timedelta(seconds=10))
    assert again['winner_buys_submitted']==0 and again['winner_protections_submitted']==0
    assert len(broker.calls)==calls and repo.insert_execution_broker_fill.call_count==fills


@pytest.mark.parametrize('definitive',[True,False])
def test_protection_rejection_is_visible_and_ambiguous_post_is_never_repeated(monkeypatch,definitive):
    from tests.test_q051_paper_profile import setup,approval,NOW
    from service.alpaca.trading_client import BrokerApiError
    monkeypatch.setattr('common.q051_paper.settings',lambda:dict(enabled=True))
    cfg,store,repo,broker,_=setup()
    source=lambda *_:dict(bars=[],prior_session=NOW.date(),ask=None,bid=None)
    run=lambda t:WinnerCampaignRuntime(store,repo,broker,cfg,market=source,risk=approval,now=t).run(store.rows())
    run(NOW);stamp=datetime(2026,10,19,13,30,tzinfo=UTC);broker.fill(8,100.,stamp=stamp)
    failed=MagicMock(side_effect=BrokerApiError(422,'Rejected','{}') if definitive else TimeoutError('unknown POST'))
    broker.protect=failed
    assert run(stamp+timedelta(seconds=5))['winner_failures']==1
    saved=store.rows()[0]['state'];op=[o for o in saved['operations'] if o['action']=='PROTECT'][0]
    assert op['status']==('MANUAL_REVIEW' if definitive else 'RESERVED')
    if definitive:assert 'Protective order definitively rejected' in saved['manual_review']
    run(stamp+timedelta(seconds=10))
    assert failed.call_count==1
