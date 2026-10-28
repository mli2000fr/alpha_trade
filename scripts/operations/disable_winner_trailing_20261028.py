"""Explicit PAPER trailing-only amendment for existing P and OKTA campaigns.

All broker requests are GET. Standing SL/TP orders, quantities, fill history,
horizon, risk budgets and execution claims stay unchanged. The local watcher
is reloaded under the account lock to stop unnecessary intraday collection.
"""
import argparse
from dataclasses import replace
from datetime import UTC,datetime
import hashlib
import json
import math
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import uuid

from sqlalchemy import text

CAMPAIGNS={'P':'wp-92e5c4eaa6d6365742c3f7e84633255a03827604',
    'OKTA':'wp-d81922854ed7f3d1e434c03850d5bc929c7233f6'}
FILTER='opt-917380c30aab40cbb99362b3ead15e7c'
STARTUP=Path('artifacts/operations/winner_request_id_20261028/36d964b1ba3c443483fcebe12f29d1df/watcher-deee06a4/startup.json')
AUTHORIZATION='Human user requested trailing=None for existing P and OKTA; keep SL, TP, horizon and quantities unchanged, 2026-10-28'


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()


def run(apply=False):
    import psutil
    from common.verified_http import verified_session
    from common.winner_pyramiding import load_winner_pyramiding_config
    from database.connection import get_sqlalchemy_engine
    from execution_engine.db_io import ExecutionRepository
    from execution_engine.winner_campaign_store import WinnerCampaignStore
    from execution_engine.winner_plans import require_campaign_watcher
    from ihm.services.pipeline_runner import pipeline_page_default_options
    from service.alpaca.accounts import AccountRegistry
    from service.alpaca.trading_client import AlpacaTradingClient
    from service.forward_pit.watcher_startup import _compatible,_is_watcher_command,ensure_watcher
    from service.options_directional.risk_attempts import risk_lock
    from service.options_directional.store import directory

    engine=get_sqlalchemy_engine()
    policy=load_winner_pyramiding_config()
    if (engine.url.database!='alpha_trade' or AccountRegistry.get().resolve('default').mode!='paper'
            or policy.trailing_stop_pct is not None or policy.reinforcement_enabled):
        raise ValueError('Principal US PAPER account and configured trailing/add OFF required')
    repo=ExecutionRepository(engine);store=WinnerCampaignStore(engine)
    owner='trail-off-'+uuid.uuid4().hex[:22]
    with risk_lock(directory(FILTER),lock_name='execution.lock'):
        deadline=time.monotonic()+20
        while not repo.acquire_execution_lock(account_id='default',exec_run_id=owner,ttl_seconds=180):
            if time.monotonic()>deadline:raise RuntimeError('Account busy; no amendment')
            time.sleep(.5)
        try:
            rows={symbol:store.get(key) for symbol,key in CAMPAIGNS.items()}
            for symbol,row in rows.items():
                if row is None:raise ValueError('Campaign absent: '+symbol)
                state=row['state']
                if (state['symbol']!=symbol or state['status']!='OPEN'
                        or state['account_id']!='default' or state['broker_mode']!='paper'
                        or state['policy']['reinforcement_enabled']
                        or any(o['status'] in ('RESERVED','UNKNOWN','SUBMITTED') for o in state['operations'])):
                    raise ValueError('Campaign changed or ambiguous: '+symbol)
            claim=directory(FILTER)/'execution.claim.json'
            claim_hash=hashlib.sha256(claim.read_bytes()).hexdigest()
            proof=dict(observed_at=datetime.now(UTC).isoformat(),account='default',broker_mode='paper',
                protection_orders=[],claim_sha256=claim_hash)
            with verified_session() as session:
                request=session.request
                def get_only(method,*a,**kw):
                    if method.upper()!='GET':raise RuntimeError('Trailing amendment forbids broker mutations')
                    return request(method,*a,**kw)
                session.request=get_only
                client=AlpacaTradingClient(broker_mode='paper',account_id='default',session=session)
                positions=client.get_positions()
                if {p['symbol'] for p in positions}!=set(CAMPAIGNS):
                    raise ValueError('Account holdings changed; inspect before service reload')
                proof['positions']=positions
                for symbol,row in rows.items():
                    state=row['state'];position=next(p for p in positions if p['symbol']==symbol)
                    remaining=sum(l['remaining'] for l in state['lots'])
                    if position['side']!='long' or remaining<=0 or float(position['qty'])!=remaining:
                        raise ValueError('Held quantities differ from campaign: '+symbol)
                    for lot in state['lots']:
                        if not lot['remaining']:continue
                        for id_field,price_field,broker_price in [('stop_order_id','stop','stop_price'),
                                ('tp_order_id','tp','limit_price')]:
                            if price_field=='tp' and lot['tp'] is None:continue
                            if not lot.get(id_field):raise ValueError('Standing protection missing')
                            raw=client._request('GET','/v2/orders/'+lot[id_field],params={'nested':'true'})
                            if (raw.get('symbol')!=symbol or raw.get('side')!='sell'
                                    or raw.get('status') not in ('new','accepted','held','pending_new','partially_filled')
                                    or float(raw['qty'])-float(raw.get('filled_qty') or 0)!=lot['remaining']
                                    or not math.isclose(float(raw[broker_price]),float(lot[price_field]),abs_tol=1e-8)):
                                raise ValueError('Protection state/price unqualified: '+symbol)
                            proof['protection_orders'].append(dict(symbol=symbol,role=id_field,raw=raw))
            with engine.connect() as conn:
                leader=conn.execute(text("SELECT locked_by_run_id FROM execution_locks WHERE account_id='watcher:default'")).scalar_one()
            if not apply:
                print(json.dumps(dict(status='VERIFIED_READ_ONLY',proof_sha256=digest(proof),
                    campaigns={s:dict(version=r['version'],trailing=r['state']['policy']['trailing_stop_pct']) for s,r in rows.items()})))
                return
            startup=json.loads(STARTUP.read_text(encoding='utf-8'))
            processes=[]
            for proc in psutil.process_iter(['pid','cmdline']):
                command=proc.info.get('cmdline') or []
                if not _is_watcher_command(command):continue
                account=command[command.index('--account')+1] if '--account' in command else 'default'
                if account!='default':continue
                if not _compatible(command,'default') or command!=startup['command']:
                    raise ValueError('Watcher identity changed')
                processes.append((proc,command))
            if not processes:raise ValueError('Expected local PAPER service absent')
            folder=Path('artifacts/operations/winner_trailing_off_20261028')/uuid.uuid4().hex
            folder.mkdir(parents=True,exist_ok=False)
            for name,value in [('protection_proof.json',proof),('states_before.json',rows)]:
                with (folder/name).open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2,default=str)
            for proc,command in processes:
                if proc.cmdline()!=command:raise ValueError('Watcher process changed')
                proc.terminate()
            _,alive=psutil.wait_procs([p for p,c in processes],timeout=10)
            if alive:raise RuntimeError('Old service still active; no campaign changed')
            repo.release_execution_lock(account_id='watcher:default',exec_run_id=leader)
            changes={}
            for symbol,row in rows.items():
                result=store.disable_trailing(CAMPAIGNS[symbol],row['version'],account_id='default',
                    authorization=AUTHORIZATION,protection_proof_sha256=digest(proof))
                before=json.loads(json.dumps(row['state']));after=json.loads(json.dumps(result['state']))
                after['policy']['trailing_stop_pct']=before['policy']['trailing_stop_pct']
                after['policy_amendments']=before.get('policy_amendments',[])
                before['policy_amendments']=before.get('policy_amendments',[])
                if after!=before:raise RuntimeError('Unexpected campaign amendment')
                changes[symbol]=dict(changed=result['changed'],version=result['version'],
                    previous_trailing_stop_pct=row['state']['policy']['trailing_stop_pct'],trailing_stop_pct=None)
            if hashlib.sha256(claim.read_bytes()).hexdigest()!=claim_hash:raise RuntimeError('Execution claim changed')
            options=replace(pipeline_page_default_options(trade_date='2026-10-27'),execution_mode='paper',account_id='default',
                execution_take_profit_pct=.08,execution_trailing_stop_pct=.05,execution_manual_buy_stop_loss_pct=.05,
                execution_trailing_trigger='multiple_r',execution_trailing_r_multiple=1.,execution_trailing_profit_pct=.03)
            service=ensure_watcher(engine,options,directory=folder,stop_event=threading.Event(),timeout_seconds=50)
            require_campaign_watcher(repo,SimpleNamespace(resolved_account_id='default',broker_mode='paper'))
            receipt=dict(status='TRAILING_DISABLED',changes=changes,protection_proof_sha256=digest(proof),
                broker_mutations=False,execution_claim_unchanged=True,sl_tp_horizon_and_lots_unchanged=True,service=service)
            with (folder/'receipt.json').open('x',encoding='utf-8') as stream:json.dump(receipt,stream,indent=2)
            print(json.dumps(dict(folder=str(folder),**receipt)))
        finally:
            repo.release_execution_lock(account_id='default',exec_run_id=owner)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    run(apply=parser.parse_args().apply)
