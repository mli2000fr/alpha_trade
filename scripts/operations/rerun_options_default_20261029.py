"""Human-authorized PAPER 11/12 rerun; preserve the old sealed zero-target run.

Refresh only the SQL-backed options analysis from existing Oracle predictions.
Use the ordinary managed workflow, its account-bound claims, and native guards.
No claim deletion, provider data download, LLM call or other account execution.
"""
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import ssl
import time
import uuid

import certifi
from sqlalchemy import text

from common.verified_http import verified_session
from database.connection import get_sqlalchemy_engine
from ihm.services.pipeline_runner import PipelineLaunchOptions
from ihm.services.process_registry import start_pipeline_workflow, poll_pipeline_run
from service.alpaca.trading_client import AlpacaTradingClient
from service.options_directional.accounts import require_paper_account, shared_qualified
from service.options_directional.runner import analyze
from service.options_directional.store import directory, write_new


OLD = 'opt-5f789c9df25b434b9d4506d78085a4fc'
OLD_RISK = 'de209d7cf1f949c3'
ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT/'artifacts/operations/us_pipeline/us_pipeline-20261028220502-5a75b98b/plan.json'


def main():
    require_paper_account('default')
    original = json.loads(PLAN.read_text(encoding='utf-8'))
    options = PipelineLaunchOptions(**original['options'])
    if options.account_id != 'default' or options.execution_mode != 'paper' or options.llm_filter_enabled:
        raise ValueError('Expected exact default PAPER options workflow')
    old = shared_qualified(OLD, trade_date=options.trade_date, account_id='default',
        batch_id=options.ml_live_predict_batch_id, symbol_source=options.ml_predict_symbol_source)
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    with engine.connect() as conn:
        counts = {key:int(conn.execute(text(sql),{'risk':OLD_RISK}).scalar_one()) for key,sql in {
            'old_targets':'SELECT COUNT(*) FROM portfolio_targets WHERE run_id=:risk',
            'old_executions':'SELECT COUNT(*) FROM execution_runs WHERE risk_run_id=:risk',
            'active_default_execution':"SELECT COUNT(*) FROM execution_runs WHERE account_id='default' AND status='RUNNING'"
        }.items()}
        # The preceding user-authorized attempt failed before plan/order
        # creation. Prove that outcome, never reset its consumed claim.
        previous_risk='acaf833cb3494c74'
        previous=[dict(r) for r in conn.execute(text('SELECT exec_run_id,status,total_submitted,total_filled '
            'FROM execution_runs WHERE risk_run_id=:risk'),{'risk':previous_risk}).mappings()]
        counts['previous_order_requests']=int(conn.execute(text('SELECT COUNT(*) FROM execution_order_requests '
            'WHERE risk_run_id=:risk'),{'risk':previous_risk}).scalar_one())
        counts['previous_campaigns']=int(conn.execute(text('SELECT COUNT(*) FROM execution_winner_campaigns '
            'WHERE risk_run_id=:risk'),{'risk':previous_risk}).scalar_one())
    if len(previous)!=1 or previous[0] != dict(exec_run_id='6b50bfd9742d49c0',status='FAILED',total_submitted=0,total_filled=0):
        raise ValueError('Previous PAPER execution outcome not proven empty')
    if any(counts.values()) or (directory(OLD)/'execution.claim.json').exists():
        raise ValueError(f'Existing targets/execution require reconciliation: {counts}')
    with verified_session() as session:
        broker = AlpacaTradingClient(broker_mode='paper',account_id='default',session=session)
        account = broker.get_account()
        if account.get('trading_blocked') or float(account['equity']) <= 0:
            raise ValueError('Broker account unavailable for entries')
        positions = broker.get_positions()
        orders = broker.list_orders(status='open',limit=500)
        subsequent=broker._request('GET','/v2/orders',params=dict(status='all',
            after='2026-10-29T07:19:19Z',limit=500,direction='asc',nested='true'))
        if not isinstance(subsequent,list) or subsequent:
            raise ValueError('Account has subsequent broker orders; reconcile before rerun')
    operation = ROOT/'artifacts/operations/options_default_rerun'/(
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    operation.mkdir(parents=True,exist_ok=False)
    # Trust the same Certifi + Windows ROOT certificates as verified_session;
    # keep verification enabled for normal clients in child processes too.
    bundle = operation/'verified-ca-bundle.pem'
    pem = Path(certifi.where()).read_text(encoding='ascii')
    for certificate,encoding,_ in ssl.enum_certificates('ROOT'):
        if encoding == 'x509_asn':
            pem += '\n'+ssl.DER_cert_to_PEM_cert(certificate)
    bundle.write_text(pem,encoding='ascii')
    os.environ['REQUESTS_CA_BUNDLE'] = str(bundle)
    write_new(operation/'preflight.json',dict(account_id='default',mode='paper',
        old_filter=OLD,old_risk=OLD_RISK,sql_counts=counts,previous_execution=previous,
        equity=account['equity'],buying_power=account['buying_power'],
        positions=[{k:p.get(k) for k in ('symbol','qty','side')} for p in positions],
        open_orders=[{k:o.get(k) for k in ('symbol','side','qty','type','status')} for o in orders],
        authorization='User requested step 11 and 12 on default account on 2026-10-29',
        old_archives_preserved=True))
    new_id = 'opt-'+uuid.uuid4().hex
    report = analyze(engine,run_id=new_id,batch_id=old['batch_id'],trade_date=old['trade_date'],
        symbol_source=old['symbol_source'],capital_preset_key=old['capital_preset_key'],
        artifacts_dir=options.ml_artifacts_dir,producer_account_id='default')
    options=replace(options,options_filter_run_id=new_id,execution_run_id=None,allow_fractional_shares=False,
                    risk_account_equity=float(account['equity']))
    write_new(operation/'selection_refresh.json',dict(old_filter=OLD,new_filter=new_id,
        old_selected=old['selected'],new_selected=report['selected'],
        oracle_predictions_reused=True,llm_calls=0,provider_downloads=0))
    print(json.dumps(dict(phase='FILTER_REFRESHED',operation=str(operation),
        options_filter_run_id=new_id,selected=report['selected'])),flush=True)

    def before_step(step,current_options,stop_event):
        if step.key != 'execution': return None
        from service.forward_pit.watcher_startup import find_running_service, ensure_watcher
        from execution_engine.winner_plans import require_current_watcher_code
        process=find_running_service('default')
        if process is not None:
            try:
                require_current_watcher_code(process)
            except ValueError:
                # Exact account/PAPER/path already checked by find_running_service.
                # Broker SL/TP stay in place during the bounded local restart.
                print(json.dumps(dict(phase='RESTART_STALE_WATCHER',pid=process.pid)),flush=True)
                with engine.connect() as conn:
                    lease=conn.execute(text("SELECT locked_by_run_id FROM execution_locks "
                        "WHERE account_id='watcher:default'")).scalar_one_or_none()
                    heartbeat=conn.execute(text("SELECT pid FROM watcher_heartbeats WHERE account_id='default' "
                        "AND watcher_name='execution_protection_watcher' ORDER BY last_heartbeat_at DESC LIMIT 1")).scalar_one_or_none()
                if heartbeat is None or int(heartbeat)!=process.pid:
                    raise ValueError('Watcher heartbeat/lease identity mismatch; restart refused')
                process.terminate()
                process.wait(timeout=15)
                if find_running_service('default') is not None:
                    raise ValueError('Another watcher appeared during restart; lease retained')
                if lease is not None:
                    from execution_engine.db_io import ExecutionRepository
                    ExecutionRepository(engine).release_execution_lock(account_id='watcher:default',exec_run_id=lease)
                write_new(operation/'watcher_restart.json',dict(old_pid=process.pid,
                    account_id='default',broker_mode='paper',reason='STALE_WINNER_CODE',
                    released_lease_owner=lease,
                    broker_orders_untouched=True,restarted_at=datetime.now(timezone.utc).isoformat()))
        return ensure_watcher(engine,current_options,directory=operation,stop_event=stop_event)

    workflow=start_pipeline_workflow(options,db_config={'name':'alpha_trade'},
        selected_step_keys=('risk_management','execution'),before_step=before_step)
    write_new(operation/'workflow.json',dict(run_id=workflow.run_id,options_filter_run_id=new_id,
        account_id='default',mode='paper',selected_steps=[11,12]))
    print(json.dumps(dict(phase='WORKFLOW_STARTED',run_id=workflow.run_id)),flush=True)
    previous=None
    while True:
        state=poll_pipeline_run(workflow.run_id)
        key=(state.get('status'),state.get('workflow_current_step_key'),state.get('workflow_completed_steps'))
        if key != previous:
            print(json.dumps(dict(phase='WORKFLOW_STATUS',run_id=workflow.run_id,status=key[0],
                current_step=key[1],completed_steps=key[2])),flush=True)
            previous=key
        if state.get('status') not in ('scheduled','starting','running'):
            write_new(operation/'result.json',state)
            print(json.dumps(dict(phase='FINISHED',run_id=workflow.run_id,status=state['status'],
                children=state.get('workflow_child_run_ids'),operation=str(operation))),flush=True)
            if state['status'] != 'completed':
                raise RuntimeError('Workflow failed; inspect exact child logs; no automatic retry')
            break
        time.sleep(1)
    engine.dispose()


if __name__ == '__main__':
    main()
