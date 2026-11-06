"""Import local historical FIRDS bytes into existing FR SQL object storage.

No provider calls, source deletion, normalized market-table promotion or
backdated availability. Per-file transactions and verified SQL round trips.
"""
from __future__ import annotations

import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor,ProcessPoolExecutor
from contextlib import closing
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import uuid
import zipfile
import multiprocessing

from sqlalchemy import text

from service.fr.collection_storage import Repository,sha


def clock():return datetime.now(timezone.utc).isoformat()


def atomic(path,data):
    path=Path(path);temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(data,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
        os.replace(temporary,path)
    finally:temporary.unlink(missing_ok=True)


def verify_object(engine,content,expected_size):
    """Read every stored byte; contiguous chunk numbers, length and SHA must match."""
    h=hashlib.sha256();size=0;parts=0
    with engine.connect() as c:
        declared=c.execute(text('SELECT byte_length FROM fr_collection_objects WHERE content_sha256=:hash'),dict(hash=content)).scalar_one()
        if declared!=expected_size:raise ValueError('SQL object length differs from source')
        result=c.execution_options(stream_results=True).execute(text('SELECT part_no,body FROM fr_collection_object_parts '
            'WHERE content_sha256=:hash ORDER BY part_no'),dict(hash=content))
        try:
            for number,body in result:
                if number!=parts:raise ValueError('Missing or unordered SQL object chunk')
                h.update(body);size+=len(body);parts+=1
        finally:result.close()
    if not parts or size!=expected_size or h.hexdigest()!=content:
        raise ValueError('SQL object round-trip checksum mismatch')
    return parts


def source_files(root):
    root=Path(root).absolute()
    if root.is_symlink() or root.is_junction():raise ValueError('Source link/junction forbidden')
    rows=[]
    for current,dirs,names in os.walk(root,followlinks=False):
        for name in dirs+names:
            p=Path(current)/name
            if p.is_symlink() or p.is_junction():raise ValueError('Source contains link/junction')
        for name in sorted(names):
            p=Path(current)/name
            if not p.is_file():raise ValueError('Special source file forbidden')
            stat=p.stat()
            rows.append(dict(path=p.relative_to(root).as_posix(),size=stat.st_size,mtime_ns=stat.st_mtime_ns))
    return sorted(rows,key=lambda r:r['path'])


def import_file(repo,source,row):
    path=source/row['path'];stat=path.stat()
    if (stat.st_size,stat.st_mtime_ns)!=(row['size'],row['mtime_ns']):
        raise ValueError('Source modified since inventory')
    # Preserve the ZIP exactly; no materialization of the enclosed full XML.
    if path.suffix.lower()=='.zip':
        with zipfile.ZipFile(path) as z:
            members=z.infolist()
            if not members or any(m.is_dir() or not m.filename.endswith('.xml') for m in members):
                raise ValueError('Unexpected FIRDS ZIP structure')
    raw=path.read_bytes();content=sha(raw);stat_after=path.stat()
    if len(raw)!=row['size'] or (stat_after.st_size,stat_after.st_mtime_ns)!=(row['size'],row['mtime_ns']):
        raise ValueError('Source changed while reading')
    batch,rel,key=repo.identity(path)
    with repo.engine.connect() as c:
        old=c.execute(text('SELECT content_sha256 FROM fr_collection_heads WHERE batch_name=:batch '
            'AND resource_sha256=:key'),dict(batch=batch,key=key)).scalar_one_or_none()
        version=c.execute(text('SELECT available_at FROM fr_collection_versions WHERE batch_name=:batch '
            'AND resource_sha256=:key AND content_sha256=:hash'),dict(batch=batch,key=key,hash=content)).first()
    if version is not None:
        parts=verify_object(repo.engine,content,len(raw))
        # A stored version can exist without a published head after interruption.
        if old is None or version[0] is None:repo.put(path,raw,preserve_existing_head=True)
        status='ALREADY_PRESENT_VERIFIED'
    else:
        repo.put(path,raw,preserve_existing_head=True)
        parts=verify_object(repo.engine,content,len(raw));status='IMPORTED_VERIFIED'
    with repo.engine.connect() as c:
        head=c.execute(text('SELECT content_sha256 FROM fr_collection_heads WHERE batch_name=:batch '
            'AND resource_sha256=:key'),dict(batch=batch,key=key)).scalar_one_or_none()
    if head is None:raise ValueError('SQL resource head missing after import')
    return dict(path=row['path'],resource_key=rel,status=status,sha256=content,bytes=len(raw),parts=parts,
        source_mtime_ns=row['mtime_ns'],head_preserved=head!=content,verified_at=clock())


_PROCESS_REPO=None


def initialize_import_process():
    import atexit
    from service.fr.batch_research_store import engine_fr
    global _PROCESS_REPO
    engine=engine_fr()
    if engine.url.database!='alpha_trade_fr':raise ValueError('FR database only')
    with engine.connect() as c:
        if c.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade_fr':raise ValueError('Wrong physical database')
    _PROCESS_REPO=Repository(engine)
    atexit.register(engine.dispose)


def attempt_import(repo,source,row):
    try:return import_file(repo,source,row)
    except Exception as exc:
        item=dict(path=row['path'],status='FAILED',error_type=type(exc).__name__)
        if isinstance(exc,(ValueError,zipfile.BadZipFile)):item['reason']=str(exc)
        db_args=getattr(getattr(exc,'orig',None),'args',())
        if db_args and type(db_args[0]) is int:item['database_error_code']=db_args[0]
        return item


def process_import(source,row):
    if _PROCESS_REPO is None:raise RuntimeError('Import process not initialized')
    return attempt_import(_PROCESS_REPO,Path(source),row)


def import_outcomes(repo,source,rows,workers,executor='thread'):
    """Bounded concurrency: no more than workers archives in memory/in flight."""
    iterator=iter(rows);pending=deque()
    if executor=='process':
        pool=ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn'),
                                 initializer=initialize_import_process)
        def submit(row):return pool.submit(process_import,str(source),row)
    elif executor=='thread':
        pool=ThreadPoolExecutor(max_workers=workers)
        def submit(row):return pool.submit(attempt_import,repo,source,row)
    else:raise ValueError('Unknown import executor')
    try:
        for _ in range(workers):
            row=next(iterator,None)
            if row is not None:pending.append((row,submit(row)))
        while pending:
            row,future=pending.popleft()
            yield row,future.result()
            following=next(iterator,None)
            if following is not None:pending.append((following,submit(following)))
    finally:
        pool.shutdown(wait=True,cancel_futures=True)


def run(output,*,source=None,max_files=None,workers=2,executor='thread'):
    from service.fr.batch_research_store import engine_fr
    project=Path(__file__).resolve().parents[2]
    source=Path(source or project/'artifacts/fr/esma_firds').absolute()
    if source.resolve()!=project/'artifacts/fr/esma_firds':raise ValueError('Fixed historical FIRDS source required')
    output=Path(output).resolve()
    if not output.is_relative_to(project/'artifacts/operations/firds_sql_history_import'):
        raise ValueError('Dedicated import reports directory required')
    output.mkdir(parents=True,exist_ok=True)
    manifest_path=output/'source-manifest.json'
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest['source_root']!=str(source):raise ValueError('Different import source')
        if source_files(source)!=manifest['files']:raise ValueError('Source tree changed; create a new import run')
    else:
        files=source_files(source)
        manifest=dict(source_root=str(source),created_at=clock(),files=files,
            total_files=len(files),total_bytes=sum(r['size'] for r in files))
        atomic(manifest_path,manifest)
    engine=engine_fr();repo=Repository(engine);repo.check_schema()
    if engine.url.database!='alpha_trade_fr':raise ValueError('FR database only')
    with engine.connect() as c:
        if c.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade_fr':raise ValueError('Wrong physical database')
        data=c.execute(text('SELECT @@datadir')).scalar_one()
    data_path=Path(data)
    # Space also needs to accommodate InnoDB overhead and binary logging.
    if engine.url.host in ('localhost','127.0.0.1','::1') and data_path.is_dir():
        if shutil.disk_usage(data_path).free<manifest['total_bytes']*3+10*1024**3:
            raise ValueError('Insufficient database disk reserve for archives and binary logs')
    summary=dict(batch='fr_firds_historical_sql_import',status='RUNNING',started_at=clock(),
        importer_sha256=sha(Path(__file__).read_bytes()),
        workers=workers,
        executor=executor,
        source_root=str(source),files_total=manifest['total_files'],bytes_total=manifest['total_bytes'],
        processed=0,verified=0,verified_bytes=0,imported=0,already_present=0,head_conflicts_preserved=0,
        failed=0,api_calls=0,source_files_deleted=0,sql_database='alpha_trade_fr',
        historical_pit_qualified=False,normalized_market_tables_changed=False,
        storage_tables=['fr_collection_objects','fr_collection_object_parts','fr_collection_versions','fr_collection_heads','fr_collection_runs'])
    run_id='fr-firds-import-'+uuid.uuid4().hex
    started=time.monotonic();consecutive_errors=0
    # Serialize only this importer; existing daily FR collectors keep running.
    try:
        selected=manifest['files'][:max_files] if max_files is not None else manifest['files']
        with repo.lock('fr_firds_historical_sql_import'),closing(import_outcomes(repo,source,selected,workers,executor)) as outcomes:
            repo.save_run(run_id,summary)
            for row,item in outcomes:
                summary['current']=row['path'];atomic(output/'progress.json',summary)
                if item['status']!='FAILED':
                    summary['verified']+=1;summary['verified_bytes']+=item['bytes']
                    summary['already_present']+=item['status']=='ALREADY_PRESENT_VERIFIED'
                    summary['imported']+=item['status']=='IMPORTED_VERIFIED'
                    summary['head_conflicts_preserved']+=bool(item['head_preserved'])
                    consecutive_errors=0
                else:
                    summary['failed']+=1;consecutive_errors+=1
                summary['processed']+=1
                with (output/'files.jsonl').open('a',encoding='utf-8') as log:
                    log.write(json.dumps(item,ensure_ascii=False)+'\n')
                summary['elapsed_seconds']=round(time.monotonic()-started,1)
                summary['updated_at']=clock()
                if summary['verified_bytes']:
                    summary['remaining_seconds_estimate']=round(summary['elapsed_seconds']*(summary['bytes_total']-summary['verified_bytes'])/summary['verified_bytes'])
                atomic(output/'progress.json',summary)
                if summary['processed']%25==0 or item['status']=='FAILED':
                    print(json.dumps({k:summary.get(k) for k in ('status','processed','files_total','verified_bytes','bytes_total','failed','current','elapsed_seconds','remaining_seconds_estimate')}),flush=True)
                    repo.save_run(run_id,summary)
                if consecutive_errors>=3:
                    summary['status']='BLOCKED_ERRORS';break
            else:
                summary['status']='INCOMPLETE' if summary['failed'] else 'PAUSED_LIMIT' if len(selected)<len(manifest['files']) else 'COMPLETED'
            if summary['status']=='RUNNING':summary['status']='INCOMPLETE'
    except BaseException:
        summary['status']='INTERRUPTED';raise
    finally:
        summary['finished_at']=clock();summary['run_id']=run_id
        atomic(output/'progress.json',summary);atomic(output/'report.json',summary)
        try:repo.save_run(run_id,summary)
        finally:engine.dispose()
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--max-files',type=int)
    parser.add_argument('--workers',type=int,choices=range(1,5),default=2)
    parser.add_argument('--executor',choices=['thread','process'],default='thread')
    args=parser.parse_args()
    if args.max_files is not None and args.max_files<1:parser.error('--max-files must be positive')
    result=run(args.output,max_files=args.max_files,workers=args.workers,executor=args.executor)
    raise SystemExit(0 if result['status']=='COMPLETED' else 2)
