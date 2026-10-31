"""Audit des SL PAPER, restauration ciblée de l'OCO Winner OKTA autorisée."""
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
import uuid

import psutil
from sqlalchemy import text

from common.verified_http import verified_session
from common.market_calendar import get_market_calendar
from common.winner_pyramiding import load_winner_pyramiding_config
from database.connection import get_sqlalchemy_engine
from execution_engine.config import ExecutionConfig
from execution_engine.db_io import ExecutionRepository
from execution_engine.models import OrderIntent, IntentRole
from execution_engine.broker_adapter import BrokerAdapter
from execution_engine.winner_broker import NativeWinnerBroker, make_intent
from execution_engine.winner_campaign_store import WinnerCampaignStore
from ihm.services.pipeline_runner import pipeline_page_default_options
from service.alpaca.trading_client import AlpacaTradingClient
from service.forward_pit.watcher_startup import find_running_service, ensure_watcher
from service.options_directional.accounts import require_paper_account
from service.options_directional.store import write_new


ROOT=Path(__file__).resolve().parents[2]
CAMPAIGN='wp-d81922854ed7f3d1e434c03850d5bc929c7233f6'


def audit(engine):
    result=[]
    store=WinnerCampaignStore(engine)
    policy=load_winner_pyramiding_config()
    for account in ['default','test1','test2']:
        require_paper_account(account)
        with verified_session() as session:
            client=AlpacaTradingClient(broker_mode='paper',account_id=account,session=session)
            positions=client.get_positions()
            rows=store.rows(account,'paper')
            represented=set()
            for row in rows:
                state=row['state'];represented.add(state['symbol'])
                for lot in state['lots']:
                    if not lot['remaining']:continue
                    expected=round(lot['entry']*(1-policy.stop_loss_pct),2)
                    raw=client._request('GET','/v2/orders/'+lot['stop_order_id'],params={'nested':'true'})
                    actual=float(raw.get('stop_price') or 0)
                    good=(raw['type']=='stop' and raw['side']=='sell' and raw['symbol']==state['symbol']
                        and raw['status'] in ('new','accepted','held','pending_new','partially_filled')
                        and actual+1e-8>=expected
                        and float(raw['qty'])-float(raw.get('filled_qty') or 0)==lot['remaining'])
                    result.append(dict(account=account,symbol=state['symbol'],campaign=state['campaign_id'],
                        entry=lot['entry'],quantity=lot['remaining'],expected_stop=expected,
                        actual_stop=actual,status=raw['status'],type=raw['type'],qualified=good,
                        frozen_sl_pct=state['policy']['stop_loss_pct'],broker_id=raw['id']))
            if {p['symbol'] for p in positions}-represented:
                raise ValueError('Position sans campagne : audit séparé nécessaire')
    return result


def main():
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    if engine.url.database!='alpha_trade':raise ValueError('US uniquement')
    policy=load_winner_pyramiding_config()
    if not policy.enabled or policy.stop_loss_pct!=.05 or policy.trailing_stop_pct is not None:
        raise ValueError('Politique Winner 5% sans trailing requise')
    folder=ROOT/'artifacts/operations/winner_stop_alignment'/(
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    folder.mkdir(parents=True,exist_ok=False)
    before=audit(engine)
    write_new(folder/'audit_before.json',before)
    mismatches=[r for r in before if not r['qualified'] or r['frozen_sl_pct']!=policy.stop_loss_pct]
    if len(mismatches)!=1 or mismatches[0]['campaign']!=CAMPAIGN:
        raise ValueError('Écarts différents de la seule protection OKTA constatée ; aucun ordre changé')
    # Le remplacement nécessite une annulation confirmée ; uniquement hors RTH,
    # où les stops/trailing concernés ne peuvent pas exécuter de vente.
    now=datetime.now(timezone.utc)
    cal=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    from zoneinfo import ZoneInfo
    day=now.astimezone(ZoneInfo('America/New_York')).date()
    for s in cal.sessions(day,day):
        if s.is_open and s.open_at_utc <= now < s.close_at_utc:
            raise ValueError('Réparation avec annulation réservée hors séance régulière')
    account='default';repo=ExecutionRepository(engine);store=WinnerCampaignStore(engine)
    owner='sl-repair-'+uuid.uuid4().hex[:22]
    deadline=time.monotonic()+20
    while not repo.acquire_execution_lock(account_id=account,exec_run_id=owner,ttl_seconds=180):
        if time.monotonic()>deadline:raise ValueError('Compte occupé ; aucun ordre changé')
        time.sleep(.5)
    try:
        process=find_running_service(account)
        if process is not None:
            with engine.connect() as conn:
                pid=conn.execute(text("SELECT pid FROM watcher_heartbeats WHERE account_id='default' "
                    "AND watcher_name='execution_protection_watcher' ORDER BY last_heartbeat_at DESC LIMIT 1")).scalar_one()
                lease=conn.execute(text("SELECT locked_by_run_id FROM execution_locks WHERE account_id='watcher:default'")).scalar_one_or_none()
            worker=psutil.Process(int(pid))
            if worker.pid!=process.pid and (worker.ppid()!=process.pid or worker.cmdline()!=process.cmdline()):
                raise ValueError('Identité watcher non qualifiée')
            worker.terminate();worker.wait(timeout=15)
            if worker.pid!=process.pid:
                process.wait(timeout=10)
            if find_running_service(account) is not None:raise ValueError('Un autre watcher reste présent')
            if lease:repo.release_execution_lock(account_id='watcher:default',exec_run_id=lease)
            write_new(folder/'watcher_stopped.json',dict(parent_pid=process.pid,worker_pid=worker.pid,lease=lease))
        row=store.get(CAMPAIGN);state=deepcopy(row['state']);version=row['version']
        if (state['status']!='OPEN' or state['account_id']!=account or len(state['lots'])!=1
                or state['lots'][0]['remaining']!=1
                or any(o['status'] in ('RESERVED','UNKNOWN','SUBMITTED') for o in state['operations'])):
            raise ValueError('Campagne non réconciliée ; réparation refusée')
        write_new(folder/'campaign_before.json',row)
        lot=state['lots'][0]
        with verified_session() as session:
            client=AlpacaTradingClient(broker_mode='paper',account_id=account,session=session)
            cfg=ExecutionConfig(broker_mode='paper',account_id=account,winner_pyramiding=policy)
            native=NativeWinnerBroker(repo,BrokerAdapter(client,cfg),cfg)
            position=next(p for p in client.get_positions() if p['symbol']=='OKTA')
            if position['side']!='long' or float(position['qty'])!=1:raise ValueError('Position OKTA modifiée')
            orders=client._request('GET','/v2/orders',params=dict(status='open',symbols='OKTA',limit=100,nested='true'))
            sell=[o for o in orders if o['symbol']=='OKTA' and o['side']=='sell']
            if len(sell)!=1 or sell[0]['type']!='trailing_stop' or float(sell[0]['qty'])!=1 or float(sell[0].get('filled_qty') or 0)!=0:
                raise ValueError('Protection concurrente différente de celle auditée')
            for key in ('stop_order_id','tp_order_id'):
                old=client._request('GET','/v2/orders/'+lot[key])
                if old['status'] not in ('canceled','cancelled','rejected','expired') or float(old.get('filled_qty') or 0):
                    raise ValueError('Ancien OCO non terminal ou exécuté')
            write_new(folder/'broker_before.json',dict(position=position,old_trailing=sell[0]))
            parent_op=next(o for o in state['operations'] if o.get('intent',{}).get('intent_id')==lot['parent_intent_id'])
            parent=OrderIntent(**parent_op['intent'])
            key=CAMPAIGN+'-sl-repair-20261030'
            stop=make_intent(state,key+'-sl',quantity=1,side='sell',role=IntentRole.INITIAL_STOP,
                order_type='stop',stop=lot['stop'],parent=parent.intent_id)
            tp=make_intent(state,key+'-tp',quantity=1,side='sell',role=IntentRole.TAKE_PROFIT,
                order_type='limit',price=lot['tp'],parent=parent.intent_id)
            repair=dict(key=key,action='PROTECT',lot_index=0,status='RESERVED',
                intent=asdict(tp),stop_intent=asdict(stop),reserved_at=datetime.now(timezone.utc).isoformat(),
                authorization='User requested matching all held stops to Winner, 2026-10-30')
            state['operations'].append(repair)
            version=store.save(state,version)  # Durable before DELETE and POST.
            canceled=native.cancel(sell[0]['id'])
            if canceled['status'] not in ('canceled','cancelled') or float(canceled.get('filled_qty') or 0):
                raise ValueError('Annulation ambiguë ; aucune deuxième vente envoyée')
            new_tp,new_stop=native.protect(state,lot,parent,tp_intent=tp,stop_intent=stop)
            lot.update(stop_order_id=new_stop.broker_order_id,tp_order_id=new_tp.broker_order_id)
            repair.update(status='DONE',broker_id=new_tp.broker_order_id,
                old_legacy_trailing_id=sell[0]['id'])
            state.setdefault('protection_repairs',[]).append(dict(observed_at=datetime.now(timezone.utc).isoformat(),
                reason='Legacy trailing replaced frozen Winner OCO; restore SL5/TP18',stop=lot['stop']))
            version=store.save(state,version)
            write_new(folder/'repair.json',dict(campaign=CAMPAIGN,new_stop_id=new_stop.broker_order_id,
                new_tp_id=new_tp.broker_order_id,stop=lot['stop'],tp=lot['tp'],version=version))
    finally:
        repo.release_execution_lock(account_id=account,exec_run_id=owner)
        options=replace(pipeline_page_default_options(trade_date='2026-10-29'),account_id=account,execution_mode='paper')
        ready=ensure_watcher(engine,options,directory=folder,stop_event=threading.Event())
        write_new(folder/'watcher_ready.json',ready)
    after=audit(engine)
    write_new(folder/'audit_after.json',after)
    print(json.dumps(dict(status='COMPLETED' if all(r['qualified'] for r in after) else 'INCOMPLETE',
        lots_checked=len(after),unqualified=[r for r in after if not r['qualified']],directory=str(folder)),default=str),flush=True)


if __name__=='__main__':main()
