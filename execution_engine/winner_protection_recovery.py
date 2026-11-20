"""Protection recovery under the campaign's canonical account lock.

Never replay an ambiguous POST. Cancel/reconcile a partial buy before a sell,
and retain both the original rejected operation and its exact client identity.
"""
import json
import math

from execution_engine.models import IntentRole,OrderIntent
from execution_engine.winner_broker import make_intent

TERMINAL={'filled','canceled','cancelled','rejected','expired'}


def rejection_detail(exc):
    try:body=json.loads(exc.body)
    except (ValueError,TypeError):body={}
    if not isinstance(body,dict):body={}
    return dict(http_status=exc.status_code,**{k:str(body[k])[:400] for k in
        ('code','message','related_order_id') if k in body and isinstance(body[k],(str,int,float))})


def stop_already_crossed(detail):
    return (detail.get('http_status')==422 and detail.get('code')=='42210000'
        and detail.get('message','').lower().startswith('stop price must be less than current price'))


def finish_partial_buys(rt):
    for op in list(rt.pending()):
        if op['action'] not in ('ENTRY','ADD'):continue
        if not op.get('broker_id'):
            rt.blocked('PROTECTION_WAITING_UNKNOWN_BUY');return False
        raw=rt.broker.get(op['broker_id'])
        if raw['status'] not in TERMINAL:
            raw=rt.broker.cancel(op['broker_id'])
        rt.reconcile()  # Books any raced fill before protecting the final quantity.
        if raw['status'] not in TERMINAL:
            rt.blocked('PROTECTION_WAITING_BUY_CANCEL');return False
    return True


def recover_rejected(rt,*,operator_authorized=False):
    reason=rt.state.get('manual_review','') or ''
    rejected=[o for o in rt.state['operations'] if o['action']=='PROTECT' and o['status']=='MANUAL_REVIEW']
    if not reason.startswith('Protective order definitively rejected;') or not rejected:
        return False
    for op in rejected:
        detail=op.get('broker_rejection',{})
        known_wash=detail.get('http_status')==403 and 'wash trade' in detail.get('message','').lower()
        if not known_wash and not stop_already_crossed(detail) and not (operator_authorized and op.get('definitive_rejection')=='[403] Forbidden'):
            raise ValueError('Protection rejection needs explicit review; no automatic retry')
        if rt.broker.lookup(OrderIntent(**op['intent'])) is not None:
            raise ValueError('Rejected protection has a broker order; reconcile before recovery')
    if any(o['action'] not in ('ENTRY','ADD') for o in rt.pending()):
        raise ValueError('Ambiguous sell/protection operation prevents recovery')
    if not finish_partial_buys(rt):return False
    positions=rt.broker.positions()
    own=next((p for p in positions if p['symbol']==rt.state['symbol']),None)
    held=sum(l['remaining'] for l in rt.state['lots'])
    if not own or own.get('side')!='long' or float(own['qty'])!=held:
        raise ValueError('Exact held quantity required before recovering rejected protection')
    if rt.broker.open_orders(rt.state['symbol']):
        raise ValueError('Open symbol orders prevent recovery; reconcile first')
    for op in rejected:op['status']='REJECTED_CONFIRMED'
    rt.state.setdefault('protection_recoveries',[]).append(dict(observed_at=rt.now.isoformat(),
        previous_manual_review=reason,operator_authorized=operator_authorized,
        rejected_intent_ids=[o['intent']['intent_id'] for o in rejected]))
    rt.state['manual_review']=None
    rt.save()
    return True


def exit_breached_unprotected(rt):
    if any(o['action']=='STOP_EXIT' for o in rt.pending()):return True
    missing=[i for i,l in enumerate(rt.state['lots']) if l['remaining'] and not l['stop_order_id']]
    if not missing:return False
    own=next((p for p in rt.broker.positions() if p['symbol']==rt.state['symbol']),None)
    if own is None:return False  # Normal reconciliation still checks actual orders.
    price=own.get('current_price')
    if price is None:return False
    price=float(price)
    if not math.isfinite(price) or price<=0:raise ValueError('Unqualified broker price for protection recovery')
    # A broker rejection is a contemporaneous crossing receipt, even when its
    # position endpoint still shows an older price or the price rebounds.
    rejected_crossings={o.get('lot_index') for o in rt.state['operations']
        if o['action']=='PROTECT' and stop_already_crossed(o.get('broker_rejection',{}))}
    breached=[i for i in missing if price<=rt.state['lots'][i]['stop'] or i in rejected_crossings]
    if not breached:return False
    if not rt.broker.market_open():
        rt.blocked('STOP_BREACHED_WAITING_REGULAR_SESSION');return True
    quantity=sum(rt.state['lots'][i]['remaining'] for i in breached)
    if own.get('side')!='long' or float(own['qty'])<sum(l['remaining'] for l in rt.state['lots']):
        raise ValueError('Broker holding does not cover protective exit')
    if float(own.get('qty_available',own['qty']))<quantity or rt.broker.open_orders(rt.state['symbol']):
        raise ValueError('Existing orders/reserved shares prevent protective exit')
    key=rt.state['campaign_id']+'-stop-exit-'+','.join(map(str,breached))
    if any(o['action']=='STOP_EXIT' and o.get('lot_indices')==breached for o in rt.state['operations']):
        raise ValueError('Prior protective exit needs reconciliation; no duplicate sell')
    intent=make_intent(rt.state,key,quantity=quantity,side='sell',role=IntentRole.EXIT,
        order_type='market',price=price)
    op=rt.reserve('STOP_EXIT',intent,booked_quantity=0,lot_indices=breached,
        reason='INITIAL_STOP_ALREADY_BREACHED',broker_price=price)
    try:order=rt.broker.submit(rt.state,intent)
    except Exception as exc:
        from service.alpaca.trading_client import BrokerApiError
        if isinstance(exc,BrokerApiError) and 400<=exc.status_code<500 and exc.status_code!=429 and 'client_order_id' not in str(exc.body):
            op.update(status='MANUAL_REVIEW',broker_rejection=rejection_detail(exc))
            rt.state['manual_review']='Protective market exit rejected; immediate reconciliation required'
            rt.save()
        raise
    op.update(status='SUBMITTED',broker_id=order.broker_order_id)
    rt.save();rt.metrics['winner_exits_submitted']+=1
    rt.reconcile()
    return any(o['action']=='STOP_EXIT' for o in rt.pending())
