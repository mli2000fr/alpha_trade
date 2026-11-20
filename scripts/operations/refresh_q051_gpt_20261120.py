"""User-authorized GPT-only refresh; keep the sealed Oracle/LONG candidate set."""
from copy import deepcopy
from dataclasses import fields,replace
from datetime import UTC,date,datetime
import json
import os
from pathlib import Path
import shutil
import sys

from sqlalchemy import text

ROOT=Path(__file__).resolve().parents[2]
AUDIT=ROOT/'artifacts/operations/us_pipeline_gpt_replay_20261120'
SOURCE='q051-2a33ff771fe14e1992b5cae6056e8637'
WORKFLOW='20261120_083804_5b6893b5'
BATCH_RUN='us_pipeline-20261120073803-55994d74'
MODULE='scripts.operations.refresh_q051_gpt_20261120'


def source_candidates(engine,*,batch,day,artifacts_dir):
    import pandas as pd
    from service.q051_paper import pipeline as p
    folder,report=p.qualified(SOURCE,batch=batch,day=day,artifacts_dir=artifacts_dir,
                              engine=engine,require_human=False)
    if (folder/'human_selection.json').exists() or (folder/'accounts').exists():
        raise ValueError('Source already approved or risk/execution attempted; no replacement')
    frame=pd.read_parquet(folder/'selection.parquet')
    if 'selected_before_llm' not in frame:raise ValueError('Exact pre-GPT selection unavailable')
    frame=frame.drop(columns=[c for c in frame if c.startswith('llm_')]).copy()
    frame['selected']=frame.selected_before_llm.astype(bool)
    if int(frame.selected.sum())!=10:raise ValueError('Expected exact ten source LONGs')
    return folder,report,frame


def refresh_predict(engine,*,run_id,batch,day,artifacts_dir,account='default',llm_filter_enabled=False):
    from common.q051_paper import reference
    from service.q051_paper import pipeline as p
    from service.q051_paper.probability_filter import apply
    if account!='default' or not llm_filter_enabled:raise ValueError('Explicit default PAPER GPT refresh required')
    source,original,frame=source_candidates(engine,batch=batch,day=day,artifacts_dir=artifacts_dir)
    folder=p.directory(run_id);folder.mkdir(parents=True,exist_ok=False)
    cutoff=datetime.now(UTC)
    p.write(folder/'started.json',dict(batch_id=batch,trade_date=str(day),profile=reference(),
        source_selection_run_id=SOURCE,reanalysis_scope='GPT_ONLY_SAME_ORACLE_AND_LONG_CANDIDATES',
        started_at=cutoff.isoformat()))
    for name in ['coverage.json','alpaca_assets.json']:shutil.copyfile(source/name,folder/name)
    ranked,receipt=apply(engine,frame,run_id=run_id,batch=batch,day=day,
                         horizon=original['profile']['winner']['horizon_sessions'])
    ranked.to_parquet(folder/'selection.parquet',index=False)
    report=deepcopy(original)
    report.update(run_id=run_id,cutoff=cutoff.isoformat(),llm_filter=receipt,
        prediction_cutoff=original.get('prediction_cutoff',original['cutoff']),
        source_selection_run_id=SOURCE,source_selection_report_sha256=p.digest(source/'selection.json'),
        source_selection_parquet_sha256=p.digest(source/'selection.parquet'),
        reanalysis_scope='GPT_ONLY_SAME_ORACLE_AND_LONG_CANDIDATES',
        selected=ranked[ranked.selected].sort_values('rank').symbol.tolist(),
        selection_sha256=p.digest(folder/'selection.parquet'))
    p.write(folder/'selection.json',report)
    p.write(folder/'seal.json',dict(report_sha256=p.digest(folder/'selection.json')))
    print('GPT-only refresh published; Oracle/LONG scores reused from '+SOURCE,flush=True)
    return report


def stop_previous_wait():
    """Exact idle controller only; never terminate a watcher or broker operation."""
    import psutil
    from database.connection import get_sqlalchemy_engine
    from ihm.services import process_registry as registry
    selection=ROOT/'artifacts/q051_paper'/SOURCE
    report=json.loads((selection/'selection.json').read_text(encoding='utf-8'))
    if report['selected'] or (selection/'human_selection.json').exists() or (selection/'accounts').exists():
        raise ValueError('Only the unapproved zero-eligible source can be stopped by this operation')
    record_path=ROOT/'artifacts/ihm_pipeline_runs/pipeline_workflow'/WORKFLOW/'record.json'
    record=json.loads(record_path.read_text(encoding='utf-8'))
    if (record['status']!='running' or record['workflow_completed_steps']!=1
            or record['workflow_current_child_run_id'] is not None):
        raise ValueError('Source workflow is not idle after step10')
    lock=json.loads((ROOT/'artifacts/ihm_pipeline_runs/.locks/pipeline.lock').read_text())
    if lock['run_id']!=WORKFLOW or lock['owner']!='pipeline_workflow':raise ValueError('Different lock owner')
    process=psutil.Process(int(lock['pid']))
    args=process.cmdline()
    if 'scripts.operations.replay_us_pipeline_gpt_20261120' not in args:
        raise ValueError('PID no longer belongs to the exact replay controller')
    if process.children(recursive=True):raise ValueError('Controller still has active children; no termination')
    # This worker owns only the verified idle wait. Its launcher observes its
    # exit normally; persistent protection services belong to other processes.
    process.terminate();process.wait(timeout=10)
    known={f.name for f in fields(registry.PipelineRunRecord)}
    old=registry.PipelineRunRecord(**{k:v for k,v in record.items() if k in known})
    stopped=replace(old,status='stopped',stop_requested=True,returncode=-3,
        finished_at=datetime.now().isoformat(timespec='seconds'),
        workflow_current_step_key=None,workflow_current_step_label=None,workflow_current_child_run_id=None)
    registry._persist_record(stopped)
    with Path(old.combined_path).open('a',encoding='utf-8') as stream:
        stream.write('\n[workflow] Explicit user GPT-only refresh: idle wait stopped, no11/12 attempted.\n')
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    if engine.url.database!='alpha_trade':raise ValueError('US database required')
    with engine.begin() as conn:
        conn.execute(text("UPDATE pit_collection_runs SET status='FAILED',finished_at=:now,"
            "requested_count=7,received_count=1,persisted_count=1,failed_count=1,"
            "error_message='STOPPED_BY_USER_FOR_GPT_ONLY_REFRESH' WHERE run_id=:run AND status='RUNNING'"),
            dict(now=datetime.now(UTC).replace(tzinfo=None),run=BATCH_RUN))
    (AUDIT/'gpt-only-stop.json').write_text(json.dumps(dict(source_selection=SOURCE,source_workflow=WORKFLOW,
        source_batch=BATCH_RUN,controller_pid=process.pid,status='STOPPED_BEFORE_RISK',
        stopped_at=datetime.now(UTC).isoformat())),encoding='utf-8')
    print('Previous idle wait stopped; source scores and responses preserved.',flush=True)


if __name__=='__main__':
    os.environ.pop('SSLKEYLOGFILE',None)
    if '--stop-previous-wait' in sys.argv:
        stop_previous_wait()
    elif '--stage' in sys.argv:
        from service.q051_paper import pipeline
        pipeline.predict=refresh_predict
        pipeline.main()
    else:
        from service.forward_pit import batch
        from scripts.operations.replay_us_pipeline_gpt_20261120 import handler
        from ihm.services import process_registry as registry
        original=registry.build_pipeline_command
        def command(step,options):
            value=original(step,options)
            if step=='ml_predict':
                if value[3]!='service.q051_paper.pipeline' or not options.llm_filter_enabled:
                    raise ValueError('Native Q051/GPT prediction command required')
                value[3]=MODULE
            return value
        registry.build_pipeline_command=command
        batch.HANDLERS['us_pipeline']=handler
        batch.main()
