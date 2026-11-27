"""Resume the exact V12 proposal with the user's optional-evidence policy.

No prediction, provider call or implicit human approval. Native 11/12 only,
one account at a time, and the original exact sealed proposal stays intact.
"""
from dataclasses import asdict,replace
from datetime import UTC,date,datetime
import json
import os
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parents[2]
AUDIT=ROOT/'artifacts/operations/us_pipeline_gpt_replay_20261120'
SELECTION='q051-b43c2635d2594ad6b805fefc50b1da05'
ACCOUNTS=('default','test1','test2')


def handler(engine,cfg,run_id,dry_run):
    from service.forward_pit import batch,us_pipeline
    from service.q051_paper import pipeline as p
    from service.q051_paper.human_selection import selection_policy
    from common.q051_paper import settings,profile_scope
    from service.q051_paper.coverage import latest_completed
    from ihm.services.pipeline_lock import list_active_locks
    from ihm.services.process_registry import start_pipeline_workflow,poll_pipeline_run
    day=date(2026,11,19)
    if engine.url.database!='alpha_trade' or latest_completed(datetime.now(UTC))!=day:
        raise ValueError('Exact US PAPER proposal for latest closed Nov19 required')
    if any(v['scope'] in {'pipeline','backtesting'} for v in list_active_locks()):
        raise ValueError('Another workflow still owns the pipeline')
    stop=json.loads((AUDIT/'gpt-manual-policy-stop.json').read_text())
    if stop['source_selection']!=SELECTION or stop['status']!='STOPPED_BEFORE_RISK':
        raise ValueError('Exact idle-stop receipt required')
    active=settings()
    with profile_scope(active['profile_id']):
        folder,report=p.qualified(SELECTION,batch=active['model_batch_id'],day=day,
            artifacts_dir=active['artifacts_dir'],engine=engine,require_human=False)
    if (folder/'accounts').exists():raise ValueError('Risk/execution already attempted')
    if report['llm_filter']['protocol']!='oracle-long-probabilities-v12':raise ValueError('V12 proposal required')
    if selection_policy()['require_qualified_evidence'] is not False:
        raise ValueError('Explicit optional-evidence configuration required')
    policy=us_pipeline.load_pipeline_policy()
    options=us_pipeline.fresh_pipeline_options(cfg,policy,day,us_pipeline.selected_steps([10,11,12]))
    options=replace(options,q051_run_id=SELECTION)
    steps=us_pipeline.selected_steps([11,12])
    others=us_pipeline.additional_paper_accounts(options,policy,steps)
    if not options.q051_paper_enabled or not options.llm_filter_enabled or options.execution_mode!='paper' or (options.account_id,*others)!=ACCOUNTS:
        raise ValueError('Exact native PAPER Q051/default/test1/test2 configuration required')
    plan=dict(source_selection=SELECTION,source_llm_run_id=report['llm_filter']['run_id'],
        selection_sha256=p.digest(folder/'selection.json'),scope='RESUME_HUMAN_GATE_THEN_NATIVE_11_12',
        trade_date=str(day),options=asdict(options),account_workflows=[],counter_unit='pipeline_steps',
        provider_calls=0,predictions=0,human_approval_automatic=False)
    outcome=batch.Outcome(requested=6,details=plan)
    if dry_run:return outcome
    directory=ROOT/'artifacts/operations/us_pipeline'/run_id;directory.mkdir(parents=True,exist_ok=False)
    (directory/'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    pointer=dict(batch_run_id=run_id,q051_run_id=SELECTION,plan_path=str(directory/'plan.json'),
        source_llm_run_id=report['llm_filter']['run_id'],started_at=datetime.now(UTC).isoformat())
    def before(step,opts,stop_event):
        if step.key=='risk_management':
            from service.q051_paper.human_selection import wait_for_selection
            return wait_for_selection(opts,stop_event)
        if step.key=='execution':
            from service.forward_pit.watcher_startup import ensure_watcher
            return ensure_watcher(engine,opts,directory=directory,stop_event=stop_event)
    for account in ACCOUNTS:
        workflow=start_pipeline_workflow(replace(options,account_id=account),db_config={'name':'alpha_trade'},
            selected_step_keys=tuple(s.key for s in steps),before_step=before)
        item=dict(account_id=account,workflow_run_id=workflow.run_id,status='running')
        plan['account_workflows'].append(item)
        pointer['account_workflows']=plan['account_workflows']
        (AUDIT/'manual-policy-resume.json').write_text(json.dumps(pointer,indent=2),encoding='utf-8')
        offset=outcome.persisted;deadline=None;previous=None
        try:
            while True:
                snapshot=poll_pipeline_run(workflow.run_id)
                if snapshot is None:raise ValueError('Workflow state missing')
                completed=int(snapshot.get('workflow_completed_steps') or 0)
                outcome.received=outcome.persisted=offset+completed
                state=(snapshot['status'],snapshot.get('workflow_current_step_key'),completed)
                if state!=previous:print(json.dumps(dict(account=account,status=state[0],step=state[1],completed=completed)),flush=True);previous=state
                if snapshot['status'] in {'starting','running','scheduled'}:time.sleep(.5);continue
                if snapshot.get('workflow_finalizing'):
                    deadline=deadline or time.monotonic()+120
                    if time.monotonic()>deadline:raise ValueError('Finalization timeout')
                    time.sleep(.5);continue
                item.update(status=snapshot['status'],completed_steps=completed)
                if snapshot['status']!='completed' or completed!=2:raise ValueError('Account workflow incomplete')
                break
        except Exception as exc:
            outcome.failed=1
            raise batch.BatchRunError(str(exc),outcome) from exc
    return outcome


if __name__=='__main__':
    os.environ.pop('SSLKEYLOGFILE',None)
    from service.forward_pit import batch
    batch.HANDLERS['us_pipeline']=handler
    batch.main()
