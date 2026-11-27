"""Exact user-authorized PAPER replay of Nov19 after cancelling its pending buys.

No recurring configuration change, historical clock, training or prior-step
collection. Native workflows retain locks, human approval and account sizing.
"""
from dataclasses import asdict,replace
from datetime import UTC,date,datetime
import json
import os
from pathlib import Path
import sys
import time
import uuid

from sqlalchemy import text

ROOT=Path(__file__).resolve().parents[2]
AUDIT=ROOT/'artifacts/operations/us_pipeline_gpt_replay_20261120'
SOURCE='us_pipeline-20261120002400-9f87a4a4'
DAY=date(2026,11,19)
ACCOUNTS=('default','test1','test2')


def cancel_exact():
    from database.connection import get_sqlalchemy_engine
    from service.q051_paper.pipeline import make_broker
    from service.forward_pit.us_pipeline import require_paper_account
    from execution_engine.winner_campaign_store import WinnerCampaignStore
    from execution_engine.winner_broker import NativeWinnerBroker
    from execution_engine.winner_runtime import WinnerCampaignRuntime
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    if engine.url.database!='alpha_trade':raise ValueError('US database required')
    store=WinnerCampaignStore(engine)
    receipt=dict(source_batch_run_id=SOURCE,authorization='Explicit user cancellation then GPT replay',accounts=[])
    for account in ACCOUNTS:
        require_paper_account(account)
        before=json.loads((AUDIT/(account+'-before.json')).read_text())
        repo,broker,cfg=make_broker(engine,account)
        if broker._client.base_url!='https://paper-api.alpaca.markets':raise ValueError('PAPER required')
        broker._client._session.headers.update({'Cache-Control':'no-cache','Pragma':'no-cache'})
        owner=uuid.uuid4().hex
        if not repo.acquire_execution_lock(account_id=account,exec_run_id=owner):raise ValueError('Account busy')
        try:
            if broker._client.is_market_open() or broker._client.get_positions():
                raise ValueError('Cancellation scope requires closed market and flat account')
            native=NativeWinnerBroker(repo,broker,cfg)
            runtime=WinnerCampaignRuntime(store,repo,native,cfg,market=None,risk=None,lifecycle_only=True)
            summary=dict(account_id=account,orders=[],campaigns=[])
            for old in before['campaigns']:
                row=store.get(old['state']['campaign_id']);state=row['state']
                if state['risk_run_id']!=before['risk_run_id'] or state['exec_run_id']!=before['exec_run_id'] or state['lots']:
                    raise ValueError('Source campaign changed or held lots exist')
                for operation in state['operations']:
                    if operation['action']!='ENTRY' or not operation.get('broker_id'):raise ValueError('Unexpected operation')
                    raw=native.get(operation['broker_id'])
                    if (raw['client_order_id']!=operation['intent']['submission_key'] or raw['symbol']!=state['symbol']
                            or raw['side']!='buy' or float(raw['filled_qty'] or 0)):
                        raise ValueError('Exact unfilled source entry required')
                    final=native.cancel(raw['id'])
                    for _ in range(20):
                        if final['status'] in {'canceled','cancelled','expired','rejected'}:break
                        time.sleep(.5);final=native.get(raw['id'])
                    if final['status'] not in {'canceled','cancelled','expired','rejected'} or float(final['filled_qty'] or 0):
                        raise ValueError('Cancellation unconfirmed or raced fill; no replay')
                    summary['orders'].append(dict(symbol=state['symbol'],order_id=raw['id'],status=final['status'],filled_qty=final['filled_qty']))
                runtime.state,runtime.version=state,row['version'];runtime.reconcile()
                if runtime.state['status'] not in {'CANCELED','EXPIRED'}:raise ValueError('Campaign not terminal')
                runtime.state['operator_cancellation']=dict(source_batch_run_id=SOURCE,
                    reason='Explicit cancellation before GPT replay',observed_at=datetime.now(UTC).isoformat())
                runtime.save()
                summary['campaigns'].append(dict(symbol=state['symbol'],status=runtime.state['status']))
            old_ids={o['id'] for o in before['orders']}
            for _ in range(20):
                remaining=broker._client.list_orders(status='open')
                if not any(o['id'] in old_ids for o in remaining):break
                time.sleep(.5)
            if any(o['id'] in old_ids for o in remaining):raise ValueError('Old open order still reported')
            summary.update(open_orders_after=len(remaining),positions_after=len(broker._client.get_positions()))
            receipt['accounts'].append(summary)
            (AUDIT/(account+'-cancellation.json')).write_text(json.dumps(summary,indent=2),encoding='utf-8')
            print(json.dumps(dict(account=account,confirmed_canceled=len(summary['orders']),
                open_orders_after=len(remaining),positions_after=summary['positions_after'])),flush=True)
        finally:repo.release_execution_lock(account_id=account,exec_run_id=owner)
    receipt.update(status='COMPLETED',cancelled_orders=sum(len(a['orders']) for a in receipt['accounts']),
        finished_at=datetime.now(UTC).isoformat())
    with (AUDIT/'cancellation.json').open('x',encoding='utf-8') as stream:json.dump(receipt,stream,indent=2)


def handler(engine,cfg,run_id,dry_run):
    from service.forward_pit import batch,us_pipeline
    from service.q051_paper.coverage import latest_completed
    from service.q051_paper.pipeline import digest
    from service.llm_directional.openai_client import ResponsesClient
    if engine.url.database!='alpha_trade' or latest_completed(datetime.now(UTC))!=DAY:
        raise ValueError('Exact replay only for the latest closed Nov19 US session')
    cancellation=json.loads((AUDIT/'cancellation.json').read_text())
    if cancellation['status']!='COMPLETED' or cancellation['source_batch_run_id']!=SOURCE or cancellation['cancelled_orders']!=18:
        raise ValueError('Complete exact cancellation proof required')
    with engine.connect() as conn:
        if conn.execute(text("SELECT status FROM pit_collection_runs WHERE run_id=:run"),dict(run=SOURCE)).scalar()!='COMPLETED':
            raise ValueError('Source batch changed')
    # Historical SQL RUNNING labels are not proof of a living worker. Native
    # locks remain authoritative; additionally reject an actual relevant runner.
    from ihm.services.pipeline_lock import list_active_locks
    if any(r['scope'] in {'pipeline','backtesting'} for r in list_active_locks()):
        raise ValueError('Conflicting native pipeline lock is active')
    import psutil
    inspectors={os.getpid(),*(p.pid for p in psutil.Process().parents())}
    for process in psutil.process_iter(['pid','cmdline']):
        if process.pid in inspectors:continue  # Windows venv launcher shares its child's -m command.
        try:
            args=process.info.get('cmdline') or []
            module=args[args.index('-m')+1] if '-m' in args and args.index('-m')+1<len(args) else None
            if module in {'service.forward_pit.batch','service.q051_paper.pipeline','scripts.operations.replay_us_pipeline_gpt_20261120'}:
                raise ValueError('Another actual US pipeline runner is active')
        except (psutil.AccessDenied,psutil.NoSuchProcess):continue
    policy=us_pipeline.load_pipeline_policy()
    if not us_pipeline.gpt_filter_enabled(policy):raise ValueError('Requested replay requires batch GPT switch true')
    steps=us_pipeline.selected_steps([10,11,12])
    options=us_pipeline.fresh_pipeline_options(cfg,policy,DAY,steps)
    if not options.q051_paper_enabled or not options.llm_filter_enabled or options.execution_mode!='paper':
        raise ValueError('Native Q051/B PAPER plus probability filter required')
    from service.q051_paper.probability_filter import config as probability_config
    llm_config=probability_config(10,10)
    ResponsesClient(llm_config)  # Check key presence before any prediction; no API call.
    others=us_pipeline.additional_paper_accounts(options,policy,steps)
    if (options.account_id,*others)!=ACCOUNTS:raise ValueError('Configured account scope changed')
    plan=dict(source_batch_run_id=SOURCE,trade_date=str(DAY),strategy_profile=options.q051_profile_id,
        defaults='FRESH_PIPELINE_PAGE',configuration_source='config.yaml:us_pipeline',
        date_override='EXPLICIT_USER_REPLAY_LATEST_CLOSED_SESSION_AFTER_CANCELLATION',
        options=asdict(options),account_id=options.account_id,other_paper_accounts=list(others),
        selected_step_numbers=[10,11,12],counter_unit='pipeline_steps',training=False,
        execution_mode='paper',cancellation_sha256=digest(AUDIT/'cancellation.json'),
        llm_provider=llm_config.provider,llm_model=llm_config.analysis_model,analysis_mode=llm_config.analysis_mode,
        account_workflows=[])
    outcome=batch.Outcome(requested=7,details=plan)
    if dry_run:
        print(json.dumps(dict(trade_date=str(DAY),q051_run_id=options.q051_run_id,
            steps=[10,11,12],accounts=ACCOUNTS,provider=llm_config.provider,model=llm_config.analysis_model,
            approval_required=True)),flush=True)
        return outcome
    directory=ROOT/'artifacts/operations/us_pipeline'/run_id;directory.mkdir(parents=True,exist_ok=False)
    (directory/'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    (AUDIT/'replay.json').write_text(json.dumps(dict(batch_run_id=run_id,q051_run_id=options.q051_run_id,
        plan_path=str(directory/'plan.json'),started_at=datetime.now(UTC).isoformat())),encoding='utf-8')
    from ihm.services.process_registry import start_pipeline_workflow,poll_pipeline_run
    def before(step,opts,stop):
        if step.key=='risk_management':
            from service.q051_paper.human_selection import wait_for_selection
            return wait_for_selection(opts,stop)
        if step.key=='execution':
            from service.forward_pit.watcher_startup import ensure_watcher
            return ensure_watcher(engine,opts,directory=directory,stop_event=stop)
    for account in ACCOUNTS:
        selected=steps if account==options.account_id else us_pipeline.selected_steps([11,12])
        workflow=start_pipeline_workflow(replace(options,account_id=account),db_config={'name':'alpha_trade'},
            selected_step_keys=tuple(s.key for s in selected),before_step=before)
        result=dict(account_id=account,workflow_run_id=workflow.run_id,selected_step_numbers=[int(s.num) for s in selected],status='running')
        plan['account_workflows'].append(result)
        offset=outcome.persisted;deadline=None;previous=None
        print(f'GPT replay account={account} workflow={workflow.run_id} selection={options.q051_run_id}',flush=True)
        try:
            while True:
                snapshot=poll_pipeline_run(workflow.run_id)
                if snapshot is None:raise ValueError('Workflow monitoring lost; subsequent accounts blocked')
                completed=int(snapshot.get('workflow_completed_steps') or 0)
                outcome.received=outcome.persisted=offset+completed
                progress=(snapshot['status'],snapshot.get('workflow_current_step_key'),completed)
                if progress!=previous:
                    print(json.dumps(dict(account=account,status=progress[0],step=progress[1],completed=completed)),flush=True)
                    previous=progress
                if snapshot['status'] in {'starting','running','scheduled'}:time.sleep(.5);continue
                if snapshot.get('workflow_finalizing'):
                    deadline=deadline or time.monotonic()+120
                    if time.monotonic()>deadline:raise ValueError('Workflow finalization timeout')
                    time.sleep(.5);continue
                result.update(status=snapshot['status'],completed_steps=completed,log=snapshot.get('combined_path'))
                if snapshot['status']!='completed' or completed!=len(selected):raise ValueError(f'Replay failed account={account}')
                break
        except Exception as exc:
            outcome.failed=1;plan['failed_account_id']=account
            raise batch.BatchRunError(str(exc),outcome) from exc
    return outcome


if __name__=='__main__':
    os.environ.pop('SSLKEYLOGFILE',None)  # Only the inaccessible debug keylog pipe; TLS stays verified.
    if '--cancel-exact-orders' in sys.argv:
        cancel_exact()
    else:
        from service.forward_pit import batch
        batch.HANDLERS['us_pipeline']=handler
        batch.main()
