"""User-requested, narrowly scoped history cleanup; never deletes news or receipts."""
from datetime import datetime,timezone
import json
from pathlib import Path

from sqlalchemy import bindparam,text

BATCH='eodhd_news_ingestion_sync'
STEP='batch:'+BATCH


def main():
    from dotenv import load_dotenv
    load_dotenv()
    from common.config_loader import load_batch_config
    from database.connection import get_sqlalchemy_engine
    from ihm.services.process_registry import HISTORY_INDEX_PATH,delete_pipeline_history_run
    import psutil
    if load_batch_config()[BATCH].get('enabled') is not False:
        raise ValueError('Batch must remain explicitly disabled')
    for process in psutil.process_iter(['pid','name','cmdline']):
        try:
            args=process.info.get('cmdline') or []
            if '-m' in args:
                module=args[args.index('-m')+1]
                if module=='service.eodhd.news_ingestion_daily':
                    raise RuntimeError('Daily news process active; cleanup refused')
                if module=='service.forward_pit.batch' and '--batch' in args and args[args.index('--batch')+1]==BATCH:
                    raise RuntimeError('Batch process active; cleanup refused')
        except (psutil.AccessDenied,psutil.NoSuchProcess,IndexError):
            continue
    history=json.loads(HISTORY_INDEX_PATH.read_text(encoding='utf-8'))
    targets={k:v for k,v in history.items() if v.get('step_key')==STEP and not v.get('history_deleted')}
    if any(v.get('status') not in ('completed','failed','timeout','stopped') for v in targets.values()):
        raise ValueError('Nonterminal IHM history; cleanup refused')
    engine=get_sqlalchemy_engine()
    if engine.url.database!='alpha_trade':
        raise ValueError('US schema only')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=Path('backups/operations_history')/BATCH/stamp
    backup.mkdir(parents=True,exist_ok=False)
    with engine.begin() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade':
            raise ValueError('Wrong actual schema')
        rows=[dict(r) for r in conn.execute(text('SELECT * FROM pit_collection_runs '
            'WHERE batch_name=:batch ORDER BY id FOR UPDATE'),dict(batch=BATCH)).mappings()]
        if len(rows)>1000 or any(r['status']=='RUNNING' or not r['run_id'].startswith(BATCH+'-') for r in rows):
            raise ValueError('Unexpected/nonterminal history; deletion refused')
        references=conn.execute(text('''SELECT COUNT(*) FROM information_schema.key_column_usage
            WHERE referenced_table_schema=DATABASE() AND referenced_table_name='pit_collection_runs' ''')).scalar_one()
        if references:
            raise ValueError('Foreign keys require a separate reviewed plan')
        (backup/'pit_collection_runs.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
        (backup/'ihm_history_entries.json').write_text(json.dumps(targets,ensure_ascii=False,indent=2),encoding='utf-8')
        deleted=0
        if rows:
            statement=text('DELETE FROM pit_collection_runs WHERE batch_name=:batch AND id IN :ids')
            statement=statement.bindparams(bindparam('ids',expanding=True))
            deleted=conn.execute(statement,dict(batch=BATCH,ids=[r['id'] for r in rows])).rowcount
            if deleted!=len(rows):
                raise ValueError('Unexpected delete count; transaction rolled back')
    hidden=0
    for run_id in targets:
        hidden+=int(delete_pipeline_history_run(run_id,expected_step_key=STEP))
    with engine.connect() as conn:
        remaining=conn.execute(text('SELECT COUNT(*) FROM pit_collection_runs WHERE batch_name=:batch'),dict(batch=BATCH)).scalar_one()
    receipt=dict(batch=BATCH,sql_history_deleted=deleted,ihm_history_hidden=hidden,sql_history_remaining=remaining,
        preserved=['news_raw','news_ticker_map','news_raw_versions','news_ticker_map_versions',
                   'news_archive_observations','news_ingestion_checkpoint','pit_raw_payloads',
                   'budget/cooldown files','operational research reports'],backup=str(backup))
    (backup/'cleanup_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':
    main()
