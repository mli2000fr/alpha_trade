"""One audited PAPER recovery of P's known local request-width failure.

Preserves the old intent and client_order_id. A 404 alone never authorizes
recovery: the exact local SQL failure, zero canonical requests/fills, flat
broker, full order/activity reads and untouched campaign are also required.
No broker mutation here; the reloaded watcher must obtain fresh native risk.
"""
import argparse
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import threading
import time
import uuid

from sqlalchemy import text

CAMPAIGN='wp-92e5c4eaa6d6365742c3f7e84633255a03827604'
RISK='404615885b1041ac'
EXEC='619852eab35b421e'
FILTER='opt-917380c30aab40cbb99362b3ead15e7c'
CLIENT='wp-201e493bb116ce0822af4fa0a6c81ead44da'
RESERVED_AT='2026-10-28T15:15:30.729099+00:00'
LOG=Path('artifacts/operations/beta_equity_20261028/watcher-cad92a02/stdout.log')
STARTUP=LOG.with_name('startup.json')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()


def repaired_state(state, proof):
    """Fixed scope only; preserve all admission fields and failed operation."""
    if (state.get('campaign_id')!=CAMPAIGN or state.get('risk_run_id')!=RISK
            or state.get('exec_run_id')!=EXEC or state.get('symbol')!='P'
            or state.get('account_id')!='default' or state.get('broker_mode')!='paper'
            or state.get('status')!='PENDING' or state.get('lots')
            or state.get('initial_attempted') is not True or state.get('operator_recoveries')
            or len(state.get('operations',[]))!=1):
        raise ValueError('Not the exact untouched PAPER campaign')
    old=state['operations'][0]
    intent=old.get('intent',{})
    if (old.get('action')!='ENTRY' or old.get('status')!='UNKNOWN' or old.get('broker_id')
            or old.get('quantity')!=1 or old.get('reserved_at')!=RESERVED_AT
            or old.get('key')!=CAMPAIGN+'-entry' or state['initial_quantity']!=1
            or intent.get('intent_id')!=CLIENT or intent.get('submission_key')!=CLIENT
            or intent.get('risk_run_id')!=RISK or intent.get('exec_run_id')!=EXEC
            or intent.get('winner_campaign_id')!=CAMPAIGN or intent.get('symbol')!='P'
            or intent.get('qty')!=1 or intent.get('side')!='buy' or intent.get('limit_price')!=142.89
            or intent.get('order_type')!='limit' or intent.get('time_in_force')!='day'
            or state.get('parents')!={CLIENT:dict(action='ENTRY',booked_quantity=0,booked_notional=0.)}):
        raise ValueError('Operation/receipt changed; no automatic release')
    zero={'sql_requests','sql_fills','broker_positions','broker_open_orders','broker_orders_today','broker_fills_today'}
    if (set(proof.get('zero_counts',{}))!=zero
            or any(type(v) is not int or v!=0 for v in proof['zero_counts'].values())
            or proof.get('old_client_order_absent') is not True
            or proof.get('pre_http_width_error') is not True
            or proof.get('request_id_max_length')!=32 or not proof.get('log_sha256')):
        raise ValueError('Incomplete proof; a broker 404 alone is insufficient')
    result=deepcopy(state)
    result['operations'][0].update(status='ABORTED_BEFORE_SUBMIT',
        operator_recovery=dict(reason='Exact local SQL 1406 request_id width failure before broker submit',
            observed_at=datetime.now(UTC).isoformat(),proof_sha256=digest(proof)))
    result['initial_attempted']=False
    result['operator_recoveries']=[dict(kind='REQUEST_ID_WIDTH_PRE_HTTP',proof_sha256=digest(proof),
        client_order_id_preserved=CLIENT,new_attempt_requires_fresh_risk=True)]
    return result


def run(apply=False):
    import psutil
    from common.verified_http import verified_session
    from database.connection import get_sqlalchemy_engine
    from execution_engine.db_io import ExecutionRepository
    from execution_engine.config import ExecutionConfig
    from execution_engine.broker_adapter import BrokerAdapter
    from execution_engine.models import OrderIntent
    from execution_engine.winner_broker import NativeWinnerBroker, make_intent
    from execution_engine.winner_campaign_store import WinnerCampaignStore
    from execution_engine.winner_plans import require_campaign_watcher
    from ihm.services.pipeline_runner import pipeline_page_default_options
    from service.alpaca.accounts import AccountRegistry
    from service.alpaca.trading_client import AlpacaTradingClient
    from service.forward_pit.watcher_startup import _compatible,_is_watcher_command,ensure_watcher
    from service.options_directional.risk_attempts import risk_lock
    from service.options_directional.store import directory
    from types import SimpleNamespace

    engine=get_sqlalchemy_engine()
    if engine.url.database!='alpha_trade' or AccountRegistry.get().resolve('default').mode!='paper':
        raise ValueError('Principal US PAPER account required')
    repo=ExecutionRepository(engine);store=WinnerCampaignStore(engine)
    owner='wp-id-repair-'+uuid.uuid4().hex[:19]
    root=Path('artifacts/operations/winner_request_id_20261028')
    with risk_lock(directory(FILTER),lock_name='execution.lock'):
        deadline=time.monotonic()+20
        while not repo.acquire_execution_lock(account_id='default',exec_run_id=owner,ttl_seconds=180):
            if time.monotonic()>deadline:raise RuntimeError('Account busy; no recovery')
            time.sleep(.5)
        try:
            row=store.get(CAMPAIGN);state=row['state']
            operations=state.get('operations',[])
            if len(operations)!=1:raise ValueError('Operation count changed')
            log_bytes=LOG.read_bytes();log_text=log_bytes.decode('utf-8')
            local_error=('2026-10-28 16:15:31' in log_text and 'BUY_REQUIRES_RECONCILIATION' in log_text
                and '(1406,' in log_text and 'Data too long for column' in log_text and 'request_id' in log_text)
            claim=directory(FILTER)/'execution.claim.json'
            claim_hash=hashlib.sha256(claim.read_bytes()).hexdigest()
            with engine.connect() as conn:
                requests=int(conn.execute(text('SELECT COUNT(*) FROM execution_order_requests WHERE risk_run_id=:r'),{'r':RISK}).scalar_one())
                fills=int(conn.execute(text('SELECT COUNT(*) FROM execution_broker_fills f JOIN execution_order_requests r '
                    'ON f.request_id=r.request_id WHERE r.risk_run_id=:r'),{'r':RISK}).scalar_one())
                if conn.execute(text("SELECT COUNT(*) FROM execution_runs WHERE account_id='default' AND status='RUNNING'")).scalar_one():
                    raise ValueError('Execution still running')
                width=conn.execute(text("SELECT CHARACTER_MAXIMUM_LENGTH FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
                    "AND TABLE_NAME='execution_order_requests' AND COLUMN_NAME='request_id'")).scalar_one()
                leader=conn.execute(text("SELECT locked_by_run_id FROM execution_locks WHERE account_id='watcher:default'")).scalar_one()
            with verified_session() as session:
                request=session.request
                def get_only(method,*a,**kw):
                    if method.upper()!='GET':raise RuntimeError('Recovery only observes broker')
                    return request(method,*a,**kw)
                session.request=get_only
                client=AlpacaTradingClient(broker_mode='paper',account_id='default',session=session)
                broker=BrokerAdapter(client,ExecutionConfig(broker_mode='paper',account_id='default'))
                responses=dict(broker_positions=client.get_positions(),broker_open_orders=client.list_orders(status='open',limit=500),
                    broker_orders_today=client._request('GET','/v2/orders',params=dict(status='all',after='2026-10-28T00:00:00Z',limit=500,nested='true')),
                    broker_fills_today=client._request('GET','/v2/account/activities/FILL',params=dict(after='2026-10-28T00:00:00Z',page_size=100)))
                if any(not isinstance(v,list) for v in responses.values()):raise ValueError('Unqualified broker response')
                old=OrderIntent(**operations[0]['intent'])
                absent=NativeWinnerBroker(repo,broker,ExecutionConfig()).lookup(old) is None
            proof=dict(zero_counts=dict(sql_requests=requests,sql_fills=fills,**{k:len(v) for k,v in responses.items()}),
                old_client_order_absent=absent,pre_http_width_error=local_error,request_id_max_length=width,
                log_sha256=hashlib.sha256(log_bytes).hexdigest(),claim_sha256=claim_hash,
                observed_at=datetime.now(UTC).isoformat(),state_sha256=digest(state))
            repaired=repaired_state(state,proof)
            new=make_intent(state,operations[0]['key'],quantity=1,price=142.89,tif='day',entry_mode='standard')
            if len(new.intent_id)>width or new.submission_key!=CLIENT:raise ValueError('Corrected request/client identity mismatch')
            if not apply:
                print(json.dumps(dict(status='VERIFIED_READ_ONLY',proof=proof,new_request_id=new.intent_id)))
                return
            # No arbitrary process or leadership lock is stopped/released.
            startup=json.loads(STARTUP.read_text(encoding='utf-8'))
            processes=[]
            for proc in psutil.process_iter(['pid','cmdline']):
                command=proc.info.get('cmdline') or []
                if not _is_watcher_command(command):continue
                account=command[command.index('--account')+1] if '--account' in command else 'default'
                if account!='default':continue
                if not _compatible(command,'default') or command!=startup['command']:raise ValueError('Watcher identity changed')
                processes.append((proc,command))
            if not processes:raise ValueError('Expected local service absent')
            folder=root/uuid.uuid4().hex;folder.mkdir(parents=True,exist_ok=False)
            for name,value in [('proof.json',proof),('state_before.json',row)]:
                with (folder/name).open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2,default=str)
            for proc,command in processes:
                if proc.cmdline()!=command:raise ValueError('Watcher process changed')
                proc.terminate()
            _,alive=psutil.wait_procs([p for p,c in processes],timeout=10)
            if alive:raise RuntimeError('Old service still active; no state changed')
            repo.release_execution_lock(account_id='watcher:default',exec_run_id=leader)
            if hashlib.sha256(claim.read_bytes()).hexdigest()!=claim_hash:raise ValueError('Execution claim changed')
            store.save(repaired,row['version'])
            options=replace(pipeline_page_default_options(trade_date='2026-10-27'),execution_mode='paper',account_id='default',
                execution_take_profit_pct=.08,execution_trailing_stop_pct=.05,execution_manual_buy_stop_loss_pct=.05,
                execution_trailing_trigger='multiple_r',execution_trailing_r_multiple=1.,execution_trailing_profit_pct=.03)
            service=ensure_watcher(engine,options,directory=folder,stop_event=threading.Event(),timeout_seconds=50)
            require_campaign_watcher(repo,SimpleNamespace(resolved_account_id='default',broker_mode='paper'))
            receipt=dict(status='RECOVERED_PENDING_FRESH_RISK',campaign=CAMPAIGN,client_order_id=CLIENT,
                new_request_id=new.intent_id,old_operation_preserved=True,execution_claim_unchanged=True,
                orders_submitted_by_recovery=False,service=service)
            with (folder/'receipt.json').open('x',encoding='utf-8') as stream:json.dump(receipt,stream,indent=2)
            print(json.dumps(dict(folder=str(folder),**receipt)))
        finally:
            repo.release_execution_lock(account_id='default',exec_run_id=owner)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    run(apply=parser.parse_args().apply)
