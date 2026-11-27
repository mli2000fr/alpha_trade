from datetime import timedelta
import json

import pytest

from execution_engine.winner_runtime import WinnerCampaignRuntime
from execution_engine.winner_protection_recovery import recover_rejected,rejection_detail
from service.alpaca.trading_client import BrokerApiError
from tests.test_winner_runtime import setup,tick,NOW,market,approve


def rejected(*,price=100.):
    cfg,store,repo,broker=setup(stop_loss_pct=.05)
    tick(cfg,store,repo,broker)
    row=store.rows()[0];state=row['state']
    op=next(o for o in state['operations'] if o['action']=='PROTECT')
    broker.orders.pop(op['broker_id']);op.pop('broker_id')
    op.update(status='MANUAL_REVIEW',definitive_rejection='[403] Forbidden')
    state['lots'][0]['stop_order_id']=None
    state['manual_review']='Protective order definitively rejected; held position requires immediate reconciliation: [403] Forbidden'
    store.save(state,row['version'])
    broker.price=price
    broker.positions=lambda:[dict(symbol='TEST',side='long',qty=broker.position_quantity,
        qty_available=broker.position_quantity,current_price=broker.price)] if broker.position_quantity else []
    broker.open_orders=lambda symbol:[]
    broker.market_open=lambda:True
    return cfg,store,repo,broker


def recovery_runtime(values):
    cfg,store,repo,broker=values
    rt=WinnerCampaignRuntime(store,repo,broker,cfg,market=market,risk=approve,now=NOW+timedelta(minutes=1))
    row=store.rows()[0];rt.state,rt.version=row['state'],row['version']
    return rt


def test_partial_buy_cancel_is_confirmed_and_raced_fills_are_protected():
    cfg,store,repo,broker=setup(stop_loss_pct=.05)
    original=broker.submit;events=[]
    def submit(state,intent):
        result=original(state,intent)
        if intent.side=='buy':
            broker.orders[intent.intent_id].update(status='partially_filled',filled_qty='5')
            broker.position_quantity=5
        return result
    def cancel(identifier):
        events.append('cancel')
        broker.orders[identifier].update(status='canceled',filled_qty='7')
        broker.position_quantity=7
        return broker.orders[identifier]
    protect=broker.protect
    def protect_after_cancel(*args,**kwargs):
        assert any(o['status']=='canceled' for o in broker.orders.values())
        events.append('protect');return protect(*args,**kwargs)
    broker.submit=submit;broker.cancel=cancel;broker.protect=protect_after_cancel
    result=tick(cfg,store,repo,broker)
    state=store.rows()[0]['state']
    assert events==['cancel','protect','protect']
    assert sum(l['remaining'] for l in state['lots'])==7
    assert all(l['stop_order_id'] for l in state['lots']) and result['winner_failures']==0


def test_legacy_generic403_needs_explicit_reconciliation_and_reinstalls_original_stop():
    values=rejected();rt=recovery_runtime(values)
    old=rt.state['operations'][-1]['intent'].copy();stop=rt.state['lots'][0]['stop']
    with pytest.raises(ValueError,match='explicit review'):recover_rejected(rt)
    assert recover_rejected(rt,operator_authorized=True)
    rt.tick()
    assert rt.state['lots'][0]['stop']==stop and rt.state['lots'][0]['stop_order_id']
    assert rt.state['operations'][-2]['intent']==old
    assert rt.state['operations'][-1]['intent']['submission_key']!=old['submission_key']
    assert not rt.state['manual_review']


def test_breached_stop_sells_exact_holding_and_restart_cannot_sell_twice():
    values=rejected(price=90.);rt=recovery_runtime(values)
    recover_rejected(rt,operator_authorized=True);rt.tick()
    assert rt.state['status']=='CLOSED' and values[3].position_quantity==0
    exits=[o for o in rt.state['operations'] if o['action']=='STOP_EXIT']
    assert len(exits)==1 and exits[0]['intent']['qty']==10
    assert all(l['remaining']==0 for l in rt.state['lots'])
    rt.tick();assert len([i for i in values[3].calls if i.side=='sell'])==1


def test_lost_protective_exit_response_reconciles_same_id_without_reposting():
    values=rejected(price=90.);rt=recovery_runtime(values)
    recover_rejected(rt,operator_authorized=True);values[3].fail_post=True
    with pytest.raises(TimeoutError):rt.tick()
    assert rt.state['operations'][-1]['status']=='RESERVED'
    rt.tick()
    assert rt.state['status']=='CLOSED' and len([i for i in values[3].calls if i.side=='sell'])==1


def test_stop_crossing_between_position_read_and_post_uses_broker_rejection_receipt():
    values=rejected(price=100.);rt=recovery_runtime(values)
    op=rt.state['operations'][-1]
    op['broker_rejection']=dict(http_status=422,code='42210000',message='stop price must be less than current price')
    op['definitive_rejection']='[422] Unprocessable Entity'
    rt.save()
    assert recover_rejected(rt)
    rt.tick()
    assert rt.state['status']=='CLOSED' and values[3].position_quantity==0


def test_only_breached_lots_are_sold_and_other_lots_keep_their_original_stop():
    from copy import deepcopy
    values=rejected(price=95.);rt=recovery_runtime(values)
    first=rt.state['lots'][0];second=deepcopy(first)
    first.update(quantity=3,remaining=3)
    second.update(parent_id='second-lot',quantity=7,remaining=7,stop=94.)
    rt.state['lots'].append(second);rt.save()
    recover_rejected(rt,operator_authorized=True);rt.tick()
    assert rt.state['lots'][0]['remaining']==0 and rt.state['lots'][1]['remaining']==7
    assert rt.state['lots'][1]['stop_order_id'] and rt.state['lots'][1]['stop']==94.
    assert values[3].position_quantity==7
    assert [i.qty for i in values[3].calls if i.side=='sell']==[3]


@pytest.mark.parametrize('problem',['open_order','quantity_mismatch','existing_broker_protection'])
def test_ambiguous_exposure_prevents_manual_recovery(problem):
    values=rejected();rt=recovery_runtime(values);broker=values[3]
    if problem=='open_order':broker.open_orders=lambda symbol:[dict(id='other',side='sell')]
    if problem=='quantity_mismatch':broker.position_quantity+=1
    if problem=='existing_broker_protection':broker.lookup=lambda intent:dict(id='existing',status='new')
    with pytest.raises(ValueError):recover_rejected(rt,operator_authorized=True)
    assert rt.state['manual_review'] and len(broker.calls)==1


def test_rejection_detail_keeps_provider_reason_without_headers_or_credentials():
    result=rejection_detail(BrokerApiError(403,'Forbidden',json.dumps(dict(code=40310000,
        message='potential wash trade detected',related_order_id='buy1',api_key='never-copy'))))
    assert result==dict(http_status=403,code='40310000',message='potential wash trade detected',related_order_id='buy1')
