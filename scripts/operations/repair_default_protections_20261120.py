"""Apply the user's authorized SL5 repair to the exact affected PAPER campaigns."""
from datetime import UTC,datetime
import json
import os
from pathlib import Path
import time
import uuid
import argparse

os.environ.pop('SSLKEYLOGFILE',None)

from database.connection import get_sqlalchemy_engine
from service.q051_paper.pipeline import make_broker
from execution_engine.winner_campaign_store import WinnerCampaignStore
from execution_engine.winner_broker import NativeWinnerBroker
from execution_engine.winner_runtime import WinnerCampaignRuntime
from execution_engine.winner_protection_recovery import recover_rejected

engine=get_sqlalchemy_engine(db_name='alpha_trade')
if engine.url.database!='alpha_trade':raise ValueError('US database required')
parser=argparse.ArgumentParser();parser.add_argument('--account',choices=['default','test1','test2'],default='default')
account=parser.parse_args().account
source=json.loads((Path('artifacts/q051_paper/q051-b43c2635d2594ad6b805fefc50b1da05/accounts')/account/'execution.json').read_text(encoding='utf-8'))
repo,broker,cfg=make_broker(engine,account)
if broker._client.base_url!='https://paper-api.alpaca.markets':raise ValueError('PAPER required')
store=WinnerCampaignStore(engine);native=NativeWinnerBroker(repo,broker,cfg)
folder=Path('artifacts/operations/default_stop_audit_20261120')/('repair-'+account+'-'+datetime.now(UTC).strftime('%H%M%S'))
folder.mkdir(parents=True,exist_ok=False)
owner='repair-'+uuid.uuid4().hex[:25]
deadline=time.monotonic()+30
while not repo.acquire_execution_lock(account_id=account,exec_run_id=owner):
    if time.monotonic()>deadline:raise ValueError('Account busy; no repair mutation')
    time.sleep(.5)
results=[]
try:
    before=dict(positions=native.positions(),orders=broker._client.list_orders(status='open'))
    (folder/'before.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
    rows=store.rows(account,'paper')
    for row in rows:
        s=row['state']
        if s['symbol'] not in {'ASX','FLEX','STX','ZS'} or not s.get('manual_review'):continue
        if s['exec_run_id']!=source['exec_run_id'] or s['policy']['stop_loss_pct']!=.05:
            raise ValueError('Affected campaign differs from exact authorized source')
        rt=WinnerCampaignRuntime(store,repo,native,cfg,market=None,risk=None,lifecycle_only=True)
        live=store.get(s['campaign_id']);rt.state,rt.version=live['state'],live['version']
        rt.reconcile()
        recover_rejected(rt,operator_authorized=True)
        rt.tick()
        end=time.monotonic()+45
        while any(o['action']=='STOP_EXIT' for o in rt.pending()) and time.monotonic()<end:
            time.sleep(.5);rt.reconcile()
        rt.tick()
        item=dict(symbol=s['symbol'],campaign_id=s['campaign_id'],status=rt.state['status'],
            manual_review=rt.state.get('manual_review'),remaining=sum(l['remaining'] for l in rt.state['lots']),
            stops=[l['stop_order_id'] for l in rt.state['lots'] if l['remaining']],metrics=rt.metrics)
        results.append(item)
        (folder/(s['symbol']+'-after.json')).write_text(json.dumps(rt.state,indent=2,default=str),encoding='utf-8')
        print(json.dumps(item),flush=True)
finally:
    try:
        after=dict(positions=native.positions(),orders=broker._client.list_orders(status='all',limit=100))
        (folder/'after.json').write_text(json.dumps(after,indent=2),encoding='utf-8')
        (folder/'result.json').write_text(json.dumps(dict(authorization='User: corriger anomalie SL5',
            account_id=account,broker_mode='paper',finished_at=datetime.now(UTC).isoformat(),results=results),indent=2),encoding='utf-8')
    finally:
        repo.release_execution_lock(account_id=account,exec_run_id=owner)
