"""Read-only audit of an existing US daily-news run; never launches collection."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from sqlalchemy import bindparam, create_engine, text

from common.universe_files import load_universe_file_symbols
from scripts.research import us_news_event_qualification as evidence

ROOT=Path(__file__).resolve().parents[2]
BATCH='eodhd_news_ingestion_sync'


def assess(progress,pit,checkpoint_count,archive):
    details=progress['details']
    accounted=sum(int(details[k]) for k in ('completed_symbols','skipped_completed','pending_symbols'))+int(progress['failed'])
    errors=[]
    if accounted!=progress['requested']:
        errors.append('SYMBOL_ACCOUNTING_INCONSISTENT')
    if archive['unsealed_mapping_receipts'] or archive['missing_raw_versions'] or archive['wrong_provider']:
        errors.append('ARCHIVE_INTEGRITY_UNQUALIFIED')
    final=pit is not None and pit['status'] not in ('RUNNING','STARTING')
    if not final:
        return dict(status='RUNNING_NOT_YET_VALIDATED',errors=errors,final=False)
    if pit['status']!='COMPLETED' or progress['failed'] or details['pending_symbols']:
        errors.append('COLLECTION_NOT_FULLY_SUCCESSFUL')
    if details.get('status')!='COMPLETED':
        errors.append('LOCAL_REPORT_NOT_COMPLETE')
    if details['completed_symbols']+details['skipped_completed']!=progress['requested']:
        errors.append('UNIVERSE_NOT_FULLY_PROCESSED')
    if checkpoint_count!=progress['requested']:
        errors.append('SUCCESSFUL_CYCLE_CHECKPOINTS_INCOMPLETE')
    for field in ('requested','received','persisted','empty','failed'):
        if pit[field+'_count']!=progress[field]:
            errors.append('PIT_COUNTER_MISMATCH_'+field.upper())
    if archive['map_versions']!=details['archive']['map_versions']:
        errors.append('RUN_MAPPING_VERSION_COUNT_MISMATCH')
    return dict(status='VALIDATED_COLLECTION_ONLY' if not errors else 'FAILED_OR_INCOMPLETE_VALIDATION',
        errors=errors,final=True,direction_signal_validated=False)


def run(run_id,output):
    if Path(run_id).name!=run_id or not run_id.startswith(BATCH+'-'):
        raise ValueError('Explicit daily-news run id required')
    directory=ROOT/'artifacts/operations'/BATCH/run_id
    source=directory/('report.json' if (directory/'report.json').exists() else 'progress.json')
    raw=source.read_bytes()
    progress=json.loads(raw)
    if progress['details']['provider']!='eodhd' or progress['details']['market_code']!='US_EQ':
        raise ValueError('Unexpected source market/provider')
    if output.exists():
        raise FileExistsError('Fresh audit directory required')
    symbols=load_universe_file_symbols('universe-file:config/univers_batch/univers_filtred_tradable.txt')
    if len(symbols)!=progress['requested']:
        raise ValueError('Current universe size differs from run; explicit historical manifest required')
    from database.connection import get_sqlalchemy_engine
    engine=create_engine(get_sqlalchemy_engine().url,pool_size=1,max_overflow=0,pool_pre_ping=True,
        connect_args={'connect_timeout':10,'read_timeout':25,'write_timeout':10},echo=False)
    try:
        with engine.connect() as conn:
            conn.execute(text("SET SESSION time_zone='+00:00'"))
            conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=15000'))
            if conn.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade':
                raise ValueError('US alpha_trade required')
            row=conn.execute(text('''SELECT run_id,status,started_at,finished_at,
                requested_count,received_count,persisted_count,empty_count,failed_count,warning_count
                FROM pit_collection_runs WHERE run_id=:run AND batch_name=:batch'''),
                {'run':run_id,'batch':BATCH}).mappings().first()
            pit=dict(row) if row else None
            if pit is None:
                raise ValueError('No corresponding scheduled/manual batch run; smoke is not a full run')
            stmt=text('''SELECT COUNT(*) FROM news_ingestion_checkpoint
                WHERE source_name='eodhd_news_daily' AND status='success'
                AND news_ingested_at>=:cycle AND symbol IN :symbols''').bindparams(bindparam('symbols',expanding=True))
            checkpoint_count=conn.execute(stmt,{'cycle':evidence.utc(progress['details']['collection_cycle_started_at']).replace(tzinfo=None),
                'symbols':symbols}).scalar_one()
            archive=dict(conn.execute(text('''SELECT COUNT(DISTINCT m.id) map_versions,
                COALESCE(SUM(o.available_at IS NULL),0) unsealed_mapping_receipts,
                COALESCE(SUM(r.id IS NULL),0) missing_raw_versions,
                COALESCE(SUM(r.ingestion_source<>'eodhd'),0) wrong_provider,
                MIN(o.observed_at) first_observed,MAX(o.available_at) latest_available
                FROM news_ticker_map_versions m
                LEFT JOIN news_archive_observations o ON o.mapping_version_id=m.id
                    AND o.origin='PROVIDER_COLLECTION'
                LEFT JOIN news_raw_versions r ON r.id=m.raw_version_id
                WHERE JSON_UNQUOTE(JSON_EXTRACT(m.mapping_context,'$.window_end_utc'))=:window_end
                    AND m.first_observed_at>=:started'''),
                {'window_end':progress['details']['window_end'],'started':pit['started_at']}).mappings().one())
            for key in ('map_versions','unsealed_mapping_receipts','missing_raw_versions','wrong_provider'):
                archive[key]=int(archive[key])
            conn.rollback()
    finally:
        engine.dispose()
    verdict=assess(progress,pit,checkpoint_count,archive)
    output.mkdir(parents=True)
    evidence.save(output/'progress_snapshot.json',progress)
    result=dict(**verdict,run_id=run_id,checked_at_utc=datetime.now(timezone.utc),pit_run=pit,
        scoped_successful_cycle_checkpoints=checkpoint_count,archive=archive,
        source_path=str(source),source_sha256=evidence.hashlib.sha256(raw).hexdigest(),
        current_universe_sha256=evidence.sha(Path('config/univers_batch/univers_filtred_tradable.txt')),
        universe_identity_certified_by_count_only=False,
        archive_lineage='exact window_end UTC + run start, no new run-id field added during collection',
        sql_writes=False,api_calls=0,training=False,orders=False,
        source_may_be_live=not verdict['final'],code_sha256=evidence.sha(Path(__file__)))
    evidence.save(output/'report.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=run(args.run_id,args.output)
    print(json.dumps(evidence.archive.json_value(report),ensure_ascii=False))
