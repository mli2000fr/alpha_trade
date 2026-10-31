"""Resume exact admitted PAPER Winner plans after user disables the count gate.

No new selection, risk binding, execution claim or campaign is created/reset.
Only the verified test1 service is restarted. Native watcher risk and OMS submit.
"""
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import time
import uuid

from sqlalchemy import text

from common.verified_http import verified_session
from database.connection import get_sqlalchemy_engine
from execution_engine.db_io import ExecutionRepository
from execution_engine.winner_campaign_store import WinnerCampaignStore
from execution_engine.winner_live_risk import campaign_risk_config
from execution_engine.winner_plans import require_current_watcher_code
from ihm.services.pipeline_runner import PipelineLaunchOptions
from service.alpaca.trading_client import AlpacaTradingClient
from service.forward_pit.watcher_startup import ensure_watcher, find_running_service, healthy_service
from service.options_directional.accounts import consumer_directory, require_paper_account, validate_risk_binding
from service.options_directional.store import sealed_report, validate_window, write_new
from scripts.operations.run_options_other_accounts_20261029 import PLAN, BUNDLE


ACCOUNT='test1'
FILTER='opt-8a87b50f7aef406cb4e3dfcaa7f4d0ed'
RISK='3524c36a4ee84930'
SYMBOLS={'TXG','ICHR','PENG','FN','SDGR','HPE'}


def summarize_records(records):
    return [dict(campaign_id=r['state']['campaign_id'],symbol=r['state']['symbol'],
        risk_run_id=r['state']['risk_run_id'],version=r['version'],
        status=r['state']['status'],initial_quantity=r['state']['initial_quantity'],
        operations=r['state']['operations'],lots=r['state']['lots']) for r in records]


def main(*, refresh_existing=False):
    require_paper_account(ACCOUNT)
    if not BUNDLE.is_file():raise ValueError('Verified CA bundle unavailable')
    os.environ['REQUESTS_CA_BUNDLE']=str(BUNDLE)
    output=Path('artifacts/operations/test1_factor_gate_resume')/(
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    output.mkdir(parents=True,exist_ok=False)
    print(json.dumps(dict(phase='STARTED',directory=str(output.resolve()))),flush=True)
    report=sealed_report(FILTER)
    folder=consumer_directory(FILTER,ACCOUNT)
    binding=json.loads((folder/'risk_binding.json').read_text(encoding='utf-8'))
    summary=json.loads((folder/'risk_summary.json').read_text(encoding='utf-8'))
    validate_risk_binding(report,binding,summary,ACCOUNT)
    if binding['risk_run_id']!=RISK:raise ValueError('Unexpected exact risk binding')
    try:
        validate_window(report['trade_date'])
    except ValueError as exc:
        window_error=str(exc)
    else:
        window_error=None
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    repo=ExecutionRepository(engine)
    store=WinnerCampaignStore(engine)
    records=[r for r in store.rows(ACCOUNT,'paper') if r['state']['risk_run_id']==RISK]
    if ({r['state']['symbol'] for r in records}!=SYMBOLS or len(records)!=6
            or (not refresh_existing and any(r['state']['status']!='PENDING'
                or r['state']['operations'] or r['state']['lots'] for r in records))
            or (refresh_existing and any(r['state']['status'] not in ('PENDING','OPEN')
                or any(o['status'] in ('RESERVED','UNKNOWN') for o in r['state']['operations']) for r in records))):
        raise ValueError('Exact unsubmitted six-plan admission changed; inspect before any restart')
    with engine.connect() as conn:
        executions=[dict(r) for r in conn.execute(text('SELECT exec_run_id,status,total_submitted,total_filled '
            'FROM execution_runs WHERE risk_run_id=:risk AND account_id=:account'),
            dict(risk=RISK,account=ACCOUNT)).mappings()]
        active=conn.execute(text("SELECT COUNT(*) FROM execution_runs WHERE account_id=:account AND status='RUNNING'"),
            dict(account=ACCOUNT)).scalar_one()
    if active or len(executions)!=1 or executions[0]['status']!='COMPLETED':
        raise ValueError('Execution context active or incompatible; no duplicate workflow')
    since=datetime.now(timezone.utc).isoformat()
    with verified_session() as session:
        broker=AlpacaTradingClient(broker_mode='paper',account_id=ACCOUNT,session=session)
        account=broker.get_account()
        cfg=campaign_risk_config(float(account['equity']))
        if cfg.factor_diversification_check_enabled is not False or not cfg.enable_factor_model:
            raise ValueError('Expected count gate disabled and factor model enabled')
        before=dict(account_id=ACCOUNT,broker_mode='paper',equity=account['equity'],
            risk_run_id=RISK,options_filter_run_id=FILTER,executions=executions,
            factor_diversification_check_enabled=cfg.factor_diversification_check_enabled,
            factor_model_enabled=cfg.enable_factor_model,beta_limit=cfg.max_portfolio_beta,
            factor_concentration_limit=cfg.max_factor_concentration_pct,
            new_pipeline_11_12_not_replayed_reason=window_error,
            strategy='Resume already-admitted plans; fresh native risk on each order; claims untouched',
            authorization='User explicitly requested disabling minimum-factor gate and resuming test1 PAPER 11/12',
            positions=broker.get_positions(),open_orders=broker.list_orders(status='open',limit=500),
            campaigns=summarize_records(records))
        write_new(output/'preflight.json',before)
        options=replace(PipelineLaunchOptions(**json.loads(PLAN.read_text(encoding='utf-8'))['options']),
            account_id=ACCOUNT,execution_mode='paper',risk_account_equity=float(account['equity']),
            llm_filter_enabled=False,options_filter_enabled=True,options_filter_run_id=FILTER,
            allow_fractional_shares=False)
        process=find_running_service(ACCOUNT)
        if process is not None:
            try:require_current_watcher_code(process)
            except ValueError:
                with engine.connect() as conn:
                    lease=conn.execute(text('SELECT locked_by_run_id FROM execution_locks WHERE account_id=:scope'),
                        dict(scope='watcher:'+ACCOUNT)).scalar_one_or_none()
                    pid=conn.execute(text("SELECT pid FROM watcher_heartbeats WHERE account_id=:account "
                        "AND watcher_name='execution_protection_watcher' ORDER BY last_heartbeat_at DESC LIMIT 1"),
                        dict(account=ACCOUNT)).scalar_one_or_none()
                if pid is None or int(pid)!=process.pid:raise ValueError('Watcher identity mismatch')
                process.terminate()
                process.wait(timeout=15)
                if find_running_service(ACCOUNT) is not None:raise ValueError('Another watcher appeared')
                if lease is not None:
                    repo.release_execution_lock(account_id='watcher:'+ACCOUNT,exec_run_id=lease)
                write_new(output/'watcher_restart.json',dict(old_pid=process.pid,account_id=ACCOUNT,
                    released_lease_owner=lease,orders_and_campaigns_untouched=True))
        ready=ensure_watcher(engine,options,directory=output,stop_event=threading.Event(),timeout_seconds=55)
        write_new(output/'watcher_ready.json',ready)
        print(json.dumps(dict(phase='WATCHER_READY',status=ready['status'],account_id=ACCOUNT)),flush=True)
        previous=None
        deadline=time.monotonic()+(8 if refresh_existing else 50)
        while True:
            current=[r for r in store.rows(ACCOUNT,'paper',active_only=False) if r['state']['risk_run_id']==RISK]
            counts={r['state']['symbol']:dict(status=r['state']['status'],operations=len(r['state']['operations']),
                lots=len(r['state']['lots'])) for r in current}
            if counts!=previous:
                print(json.dumps(dict(phase='CAMPAIGNS',rows=counts)),flush=True)
                previous=counts
            if time.monotonic()>=deadline:break
            time.sleep(2)
        orders=broker._request('GET','/v2/orders',params=dict(status='all',after=since,
            limit=500,direction='asc',nested='true'))
        result=dict(account_id=ACCOUNT,broker_mode='paper',risk_run_id=RISK,
            watcher_healthy=healthy_service(repo,ACCOUNT),completed_at=datetime.now(timezone.utc).isoformat(),
            campaigns=summarize_records(current),
            orders=[{k:o.get(k) for k in ('id','client_order_id','symbol','side','qty','type','time_in_force',
                'limit_price','stop_price','status','filled_qty','filled_avg_price','legs')} for o in orders],
            positions=broker.get_positions(),new_pipeline_11_12_not_replayed_reason=window_error)
        write_new(output/'result.json',result)
        print(json.dumps(dict(phase='FINISHED',watcher_healthy=result['watcher_healthy'],
            orders=[{k:o.get(k) for k in ('symbol','side','qty','status','filled_qty','filled_avg_price')} for o in orders],
            report=str((output/'result.json').resolve()))),flush=True)
    engine.dispose()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-existing',action='store_true',help='Verify and reuse submitted operations; never new plans')
    main(refresh_existing=parser.parse_args().refresh_existing)
