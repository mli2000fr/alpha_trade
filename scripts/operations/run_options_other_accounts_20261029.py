"""User-authorized PAPER 11/12 for secondary accounts; shared selection, isolated state."""
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time
import uuid

from sqlalchemy import text

from common.verified_http import verified_session
from database.connection import get_sqlalchemy_engine
from execution_engine.db_io import ExecutionRepository
from ihm.services.pipeline_runner import PipelineLaunchOptions
from ihm.services.process_registry import start_pipeline_workflow, poll_pipeline_run
from service.alpaca.accounts import AccountRegistry
from service.alpaca.trading_client import AlpacaTradingClient
from service.forward_pit.watcher_startup import find_running_service, ensure_watcher, healthy_service
from service.options_directional.accounts import consumer_directory, require_paper_account, shared_qualified
from service.options_directional.store import directory, write_new


ROOT=Path(__file__).resolve().parents[2]
FILTER='opt-7ff9f854eb384c6daefb1a5036aa75c5'
PLAN=ROOT/'artifacts/operations/us_pipeline/us_pipeline-20261028220502-5a75b98b/plan.json'
BUNDLE=ROOT/'artifacts/operations/options_default_rerun/20261029T074243Z-34a184d2/verified-ca-bundle.pem'


def main(account_id=None):
    if not BUNDLE.is_file(): raise ValueError('Verified CA bundle unavailable')
    os.environ['REQUESTS_CA_BUNDLE']=str(BUNDLE)
    original=json.loads(PLAN.read_text(encoding='utf-8'))
    base=PipelineLaunchOptions(**original['options'])
    accounts=[a.account_id for a in AccountRegistry.get().list_accounts()
              if a.account_id!='default' and a.mode=='paper'
              and (account_id is None or a.account_id==account_id)]
    if not accounts: raise ValueError('No secondary PAPER accounts configured')
    old_files={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
               for p in directory(FILTER).iterdir() if p.is_file()}
    operation=ROOT/'artifacts/operations/options_secondary_accounts'/(
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    operation.mkdir(parents=True,exist_ok=False)
    write_new(operation/'authorization.json',dict(accounts=accounts,mode='paper',steps=[11,12],
        options_filter_run_id=FILTER,default_account_excluded=True,
        authorization='User requested step 11 and 12 for the other accounts on 2026-10-29',
        default_artifacts_sha256=old_files))
    print(json.dumps(dict(phase='OPERATION_STARTED',accounts=accounts,directory=str(operation))),flush=True)
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    results=[]
    for account_id in accounts:
        folder=operation/account_id
        folder.mkdir(exist_ok=False)
        try:
            require_paper_account(account_id)
            report=shared_qualified(FILTER,account_id=account_id,trade_date=base.trade_date,
                batch_id=base.ml_live_predict_batch_id,symbol_source=base.ml_predict_symbol_source)
            consumer=consumer_directory(FILTER,account_id)
            if any(consumer.glob('*')):
                raise ValueError('Consumer already used; claims and results preserved, no automatic retry')
            with engine.connect() as conn:
                active=conn.execute(text("SELECT COUNT(*) FROM execution_runs WHERE account_id=:account AND status='RUNNING'"),
                                    {'account':account_id}).scalar_one()
            if active: raise ValueError('Another execution is already active for this account')
            with verified_session() as session:
                broker=AlpacaTradingClient(broker_mode='paper',account_id=account_id,session=session)
                account=broker.get_account()
                equity=float(account['equity'])
                if not math.isfinite(equity) or equity<=0 or account.get('trading_blocked'):
                    raise ValueError('Account equity/trading unavailable')
                positions=broker.get_positions()
                orders=broker.list_orders(status='open',limit=500)
            write_new(folder/'preflight.json',dict(account_id=account_id,broker_mode='paper',
                equity=equity,buying_power=account['buying_power'],shared_selection=report['selected'],
                positions=[{k:p.get(k) for k in ('symbol','qty','side')} for p in positions],
                orders=[{k:o.get(k) for k in ('symbol','side','type','qty','status')} for o in orders]))
            options=replace(base,account_id=account_id,execution_mode='paper',execution_run_id=None,
                options_filter_enabled=True,options_filter_run_id=FILTER,llm_filter_enabled=False,
                allow_fractional_shares=False,risk_account_equity=equity)

            def before_step(step,current_options,stop_event):
                if step.key!='execution':return None
                from execution_engine.winner_plans import require_current_watcher_code
                process=find_running_service(account_id)
                if process is not None:
                    try:
                        require_current_watcher_code(process)
                    except ValueError:
                        with engine.connect() as conn:
                            lease=conn.execute(text('SELECT locked_by_run_id FROM execution_locks WHERE account_id=:scope'),
                                {'scope':'watcher:'+account_id}).scalar_one_or_none()
                            pid=conn.execute(text("SELECT pid FROM watcher_heartbeats WHERE account_id=:account "
                                "AND watcher_name='execution_protection_watcher' ORDER BY last_heartbeat_at DESC LIMIT 1"),
                                {'account':account_id}).scalar_one_or_none()
                        if pid is None or int(pid)!=process.pid:raise ValueError('Watcher identity mismatch')
                        process.terminate()
                        process.wait(timeout=15)
                        if find_running_service(account_id) is not None:raise ValueError('Another watcher appeared')
                        if lease is not None:
                            ExecutionRepository(engine).release_execution_lock(account_id='watcher:'+account_id,exec_run_id=lease)
                        write_new(folder/'watcher_restart.json',dict(old_pid=process.pid,account_id=account_id,
                            released_lease_owner=lease,broker_orders_untouched=True))
                result=ensure_watcher(engine,current_options,directory=folder,stop_event=stop_event)
                write_new(folder/'watcher_ready.json',result)
                return result

            broker_since=datetime.now(timezone.utc).isoformat()
            workflow=start_pipeline_workflow(options,db_config={'name':'alpha_trade'},
                selected_step_keys=('risk_management','execution'),before_step=before_step)
            print(json.dumps(dict(phase='WORKFLOW_STARTED',account_id=account_id,run_id=workflow.run_id)),flush=True)
            write_new(folder/'workflow.json',dict(run_id=workflow.run_id,account_id=account_id,
                options_filter_run_id=FILTER,steps=[11,12]))
            previous=None
            while True:
                state=poll_pipeline_run(workflow.run_id)
                key=(state.get('status'),state.get('workflow_current_step_key'),state.get('workflow_completed_steps'))
                if key!=previous:
                    print(json.dumps(dict(phase='STATUS',account_id=account_id,status=key[0],
                        current_step=key[1],completed_steps=key[2])),flush=True)
                    previous=key
                if state.get('status') not in ('scheduled','starting','running'):
                    write_new(folder/'result.json',state)
                    break
                time.sleep(1)
            result=dict(account_id=account_id,workflow_run_id=workflow.run_id,status=state['status'])
            if (consumer/'risk_summary.json').is_file():
                summary=json.loads((consumer/'risk_summary.json').read_text(encoding='utf-8'))
                result['risk_run_id']=summary['run_id']
                result['accepted_symbols']=summary.get('accepted_symbols')
                with engine.connect() as conn:
                    result['executions']=[dict(r) for r in conn.execute(text('SELECT exec_run_id,status,'
                        'total_submitted,total_filled,error_message FROM execution_runs WHERE risk_run_id=:risk AND account_id=:account'),
                        {'risk':summary['run_id'],'account':account_id}).mappings()]
            result['watcher_healthy']=healthy_service(ExecutionRepository(engine),account_id)
            with verified_session() as session:
                broker=AlpacaTradingClient(broker_mode='paper',account_id=account_id,session=session)
                orders=broker._request('GET','/v2/orders',params=dict(status='all',after=broker_since,
                    limit=500,direction='asc',nested='true'))
                result['broker_orders']=[{k:o.get(k) for k in ('id','symbol','side','qty','type','time_in_force',
                    'limit_price','status','filled_qty','filled_avg_price')} for o in orders]
            write_new(folder/'confirmation.json',result)
            results.append(result)
            print(json.dumps(dict(phase='ACCOUNT_FINISHED',**result),default=str),flush=True)
        except Exception as exc:
            result=dict(account_id=account_id,status='FAILED',error=str(exc))
            write_new(folder/'error.json',result)
            results.append(result)
            print(json.dumps(dict(phase='ACCOUNT_FAILED',**result)),flush=True)
    current={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
             for p in directory(FILTER).iterdir() if p.is_file()}
    if current!=old_files: raise ValueError('Default/shared archive changed during operation')
    write_new(operation/'summary.json',dict(accounts=results,default_artifacts_unchanged=True))
    engine.dispose()
    print(json.dumps(dict(phase='FINISHED',accounts=results,default_artifacts_unchanged=True),default=str),flush=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--account')
    parser.add_argument('--filter-run-id',default=FILTER)
    args=parser.parse_args()
    FILTER=args.filter_run_id
    main(args.account)
