"""Continue the exact authorized 11/12 run after its pre-execution watcher stop."""
from dataclasses import replace
import json
import os
from pathlib import Path
import time

import psutil
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine
from execution_engine.db_io import ExecutionRepository
from ihm.services.pipeline_runner import PipelineLaunchOptions
from ihm.services.process_registry import start_pipeline_workflow, poll_pipeline_run
from service.forward_pit.watcher_startup import find_running_service, ensure_watcher
from service.options_directional.accounts import shared_qualified, validate_risk_binding
from service.options_directional.store import directory, write_new


def main():
    root=Path(__file__).resolve().parents[2]
    operation=root/'artifacts/operations/options_default_rerun/20261029T071919Z-e4104b9c'
    bundle=operation/'verified-ca-bundle.pem'
    if not bundle.is_file(): raise ValueError('Verified CA bundle missing')
    os.environ['REQUESTS_CA_BUNDLE']=str(bundle)
    run_id='opt-6db23593b84f432cb4e0959de7cd18e1'
    risk_id='acaf833cb3494c74'
    folder=directory(run_id)
    old_result=json.loads((operation/'result.json').read_text(encoding='utf-8'))
    report=shared_qualified(run_id,trade_date='2026-10-28',account_id='default')
    binding,summary=[json.loads((folder/name).read_text(encoding='utf-8'))
                     for name in ['risk_binding.json','risk_summary.json']]
    validate_risk_binding(report,binding,summary,'default')
    if (binding['risk_run_id']!=risk_id or old_result['status']!='failed'
            or old_result['workflow_completed_steps']!=1
            or len(old_result['workflow_child_run_ids'])!=1
            or (folder/'execution.claim.json').exists()):
        raise ValueError('Not the proven pre-execution watcher failure')
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    with engine.connect() as conn:
        executions=conn.execute(text('SELECT COUNT(*) FROM execution_runs WHERE risk_run_id=:risk'),
                                {'risk':risk_id}).scalar_one()
        active=conn.execute(text("SELECT COUNT(*) FROM execution_runs WHERE account_id='default' AND status='RUNNING'")).scalar_one()
        lock=conn.execute(text("SELECT locked_by_run_id FROM execution_locks WHERE account_id='watcher:default'")).scalar_one_or_none()
    if executions or active: raise ValueError('Execution already exists or another execution active')
    # The old PID was terminated and waited for by the preceding operation.
    if psutil.pid_exists(16836) or find_running_service('default') is not None:
        raise ValueError('Watcher process still present; do not release its lease')
    if lock is not None:
        if lock!='watch-service-cd9f3486a04e4d52': raise ValueError('Unexpected watcher lease owner')
        ExecutionRepository(engine).release_execution_lock(account_id='watcher:default',exec_run_id=lock)
        write_new(operation/'old_watcher_lease_released.json',dict(old_pid=16836,
            scope='watcher:default',owner=lock,old_process_confirmed_dead=True,
            execution_claims_untouched=True))
    original=json.loads((root/'artifacts/operations/us_pipeline/us_pipeline-20261028220502-5a75b98b/plan.json').read_text(encoding='utf-8'))
    options=replace(PipelineLaunchOptions(**original['options']),options_filter_run_id=run_id,
                    execution_run_id=None,risk_account_equity=float(summary['account_equity']))

    def before_step(step,current_options,stop_event):
        return ensure_watcher(engine,current_options,directory=operation,stop_event=stop_event)

    workflow=start_pipeline_workflow(options,db_config={'name':'alpha_trade'},
        selected_step_keys=('execution',),before_step=before_step)
    write_new(operation/'execution_workflow.json',dict(run_id=workflow.run_id,
        options_filter_run_id=run_id,risk_run_id=risk_id,account_id='default',selected_steps=[12]))
    print(json.dumps(dict(phase='EXECUTION_WORKFLOW_STARTED',run_id=workflow.run_id)),flush=True)
    previous=None
    while True:
        state=poll_pipeline_run(workflow.run_id)
        key=(state.get('status'),state.get('workflow_current_step_key'),state.get('workflow_completed_steps'))
        if key!=previous:
            print(json.dumps(dict(phase='WORKFLOW_STATUS',run_id=workflow.run_id,status=key[0],
                current_step=key[1],completed_steps=key[2])),flush=True)
            previous=key
        if state.get('status') not in ('scheduled','starting','running'):
            write_new(operation/'execution_result.json',state)
            print(json.dumps(dict(phase='FINISHED',status=state['status'],
                children=state.get('workflow_child_run_ids'))),flush=True)
            if state['status']!='completed': raise RuntimeError('Execution workflow failed; reconcile before any retry')
            break
        time.sleep(1)
    engine.dispose()


if __name__=='__main__':main()
