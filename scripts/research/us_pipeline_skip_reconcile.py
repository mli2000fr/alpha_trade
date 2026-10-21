"""One exact orphan reconciliation, guarded by the archived terminal log.

Never starts a batch, a provider collection or an order. Default is read-only.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

RUN_ID='us_pipeline-20261021072915-2a214683'
START=datetime(2026,10,21,7,29,15,812818)
FINISH=datetime(2026,10,21,7,29,17)


def validate(row, log):
    if (row['run_id']!=RUN_ID or row['batch_name']!='us_pipeline'
            or row['started_at']!=START or row['status']!='RUNNING' or row['finished_at'] is not None):
        raise ValueError('Exact orphan precondition not satisfied; no mutation')
    if (RUN_ID not in log or "'status': 'SKIPPED_SESSION_NOT_CLOSED'" not in log
            or '[2026-10-21 09:29:17] FIN us_pipeline status=ERROR exit=1' not in log):
        raise ValueError('Terminal log evidence absent; no mutation')


def run(output, apply=False):
    output=Path(output)
    if output.exists():raise ValueError('Fresh output required')
    log_path=Path('log/batch/us_pipeline.txt')
    log_bytes=log_path.read_bytes();log=log_bytes.decode('utf-8',errors='replace')
    engine=get_sqlalchemy_engine()
    output.mkdir(parents=True)
    def save(name,value):
        with (output/name).open('x',encoding='utf-8') as handle:
            json.dump(value,handle,indent=2,ensure_ascii=False,default=str)
    with engine.begin() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':raise ValueError('US DB only')
        row=dict(conn.execute(text('SELECT * FROM pit_collection_runs WHERE run_id=:id FOR UPDATE'),{'id':RUN_ID}).mappings().one())
        validate(row,log)
        save('before.json',row)
        details=json.loads(row.get('details_json') or '{}')
        details.update(counter_unit='pipeline_steps',skip_reason='SESSION_NOT_CLOSED',trade_date='2026-10-21',
            warnings=[],historical_persistence_repair=dict(
                repaired_at_utc=datetime.now(timezone.utc).isoformat(),
                original_intended_status='SKIPPED_SESSION_NOT_CLOSED',
                original_error='Data too long for column status (VARCHAR(24))',
                terminal_log=str(log_path),terminal_log_sha256=hashlib.sha256(log_bytes).hexdigest(),
                actual_finish_from_log_utc=FINISH.isoformat()+'Z',script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
        if apply:
            result=conn.execute(text('''UPDATE pit_collection_runs SET status='SKIPPED',finished_at=:finish,
                requested_count=0,received_count=0,persisted_count=0,empty_count=0,failed_count=0,warning_count=0,
                error_message=:error,details_json=:details
                WHERE run_id=:id AND status='RUNNING' AND finished_at IS NULL AND started_at=:started'''),
                dict(finish=FINISH,id=RUN_ID,started=START,details=json.dumps(details),
                error='Historical persistence error (status too long); reconciled intended SESSION_NOT_CLOSED skip. Original terminal log retained.'))
            if result.rowcount!=1:raise ValueError('Concurrent row change; rollback')
        after=dict(conn.execute(text('SELECT * FROM pit_collection_runs WHERE run_id=:id'),{'id':RUN_ID}).mappings().one())
    save('after.json',after)
    report=dict(status='APPLIED' if apply else 'READ_ONLY',run_id=RUN_ID,
                before_status=row['status'],after_status=after['status'],rows_changed=1 if apply else 0,
                orders=0,files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()})
    save('report.json',report);print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true');parser.add_argument('--output-dir',required=True)
    args=parser.parse_args();run(args.output_dir,args.apply)
