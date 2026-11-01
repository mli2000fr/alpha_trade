"""Import CN data archives, verify SQL bytes/rows, then remove verified sources.

Never downloads, trains, activates a batch or deletes a model/database dump.
Migration receipts and the complete imported bytes remain in alpha_trade_cn.
"""
from datetime import datetime,UTC
import argparse
import json
from pathlib import Path
from sqlalchemy import select,func

from service.market import cn_collection_storage as store


def source_files(*,include_transient=False):
    roots=[store.ROOT/'artifacts/cn']+list((store.ROOT/'artifacts/research').glob('cn_*'))
    result=[]
    for root in roots:
        if not root.is_dir():continue
        for path in root.rglob('*'):
            if not path.is_file() or path.is_symlink():continue
            if not store.managed(path):continue
            if path.suffix.lower() in ('.log','.pyc','.pyo'):continue
            transient=path.suffix.lower() in ('.lock','.tmp')
            if transient and not include_transient:continue
            if (path.name.startswith('.') and not (include_transient and transient)) or '__pycache__' in path.parts:continue
            result.append(path)
    return sorted(result)


def migrate(repo,*,delete_sources=False,include_transient=False):
    # Snapshot the finite scope before importing anything. Never recursive-delete.
    sources=source_files(include_transient=include_transient)
    count=0;size=0
    with repo.lock('CN_SQL_PRIMARY_MIGRATION'):
        for path in sources:
            resolved=path.resolve()
            if not resolved.is_relative_to(store.ROOT/'artifacts') or not store.managed(resolved):
                raise ValueError('Unsafe CN migration path')
            before=path.stat();raw=path.read_bytes();digest=store.sha(raw)
            key=store.resource_key(path);version=store.sha((key+'\0'+digest).encode())
            repo.put(path,raw)
            if repo.get(path)!=raw:raise ValueError('SQL byte verification failed: '+key)
            after=path.stat()
            if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
                raise ValueError('CN source changed while importing: '+key)
            values=dict(version_id=version,resource_key=key,content_sha256=digest,
                byte_length=len(raw),source_mtime_ns=after.st_mtime_ns,verified_at=store.now())
            with repo.engine.begin() as c:
                if not c.execute(select(store.migrations.c.version_id).where(store.migrations.c.version_id==version)).first():
                    c.execute(store.migrations.insert(),values)
            count+=1;size+=len(raw)
            if count%100==0:print(json.dumps(dict(phase='IMPORT_AND_VERIFY',completed=count,total=len(sources),bytes=size)),flush=True)
        # No deletion until EVERY source imported successfully, then re-verify
        # against the committed SQL receipt immediately before each unlink.
        deleted=0
        if delete_sources:
            for path in sources:
                key=store.resource_key(path)
                raw=path.read_bytes();digest=store.sha(raw)
                version=store.sha((key+'\0'+digest).encode())
                with repo.engine.connect() as c:
                    row=c.execute(select(store.migrations).where(store.migrations.c.version_id==version)).mappings().one()
                if path.stat().st_mtime_ns!=row['source_mtime_ns'] or len(raw)!=row['byte_length'] or repo.get(path)!=raw:
                    raise ValueError('CN source changed after verification; deletion refused: '+key)
                if path.is_symlink() or not path.resolve().is_relative_to(store.ROOT/'artifacts'):
                    raise ValueError('Unsafe CN delete path')
                path.unlink()
                with repo.engine.begin() as c:
                    c.execute(store.migrations.update().where(store.migrations.c.version_id==version).values(deleted_at=store.now()))
                deleted+=1
                if deleted%100==0:print(json.dumps(dict(phase='DELETE_VERIFIED_SOURCES',completed=deleted,total=len(sources))),flush=True)
        report=dict(batch='cn_collection_sql_migration',status='COMPLETED',stored_at_utc=datetime.now(UTC).isoformat(),
            imported_files=count,verified_bytes=size,deleted_files=deleted,source_files_remaining=len(source_files(include_transient=include_transient)),
            includes_transient_inputs=include_transient,
            provider_calls=0,canonical_market_data_modified=False,collectors_activated=False)
        path=store.ROOT/'artifacts/research/cn_storage_migration'/('report-'+datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
        repo.put(path,store.encode(report).encode())
        print(json.dumps(report),flush=True)
        return report


def cleanup_verified(repo):
    """Delete only previously committed/verified versions; do not reimport."""
    sources=source_files()
    with repo.lock('CN_SQL_PRIMARY_MIGRATION'):
        with repo.engine.connect() as c:
            receipts={r['resource_key']:r for r in c.execute(select(store.migrations)).mappings()}
        # Validate the complete deletion scope before removing the first file.
        for path in sources:
            key=store.resource_key(path);row=receipts.get(key);stat=path.stat()
            if row is None or stat.st_size!=row['byte_length'] or stat.st_mtime_ns!=row['source_mtime_ns']:
                raise ValueError('Unverified/changed CN source; cleanup refused: '+key)
            if not path.resolve().is_relative_to(store.ROOT/'artifacts') or path.is_symlink():
                raise ValueError('Unsafe CN cleanup target')
        deleted=0;size=0
        for path in sources:
            key=store.resource_key(path);row=receipts[key]
            raw=path.read_bytes()
            if store.sha(raw)!=row['content_sha256'] or repo.get(path)!=raw:
                raise ValueError('CN SQL/source byte mismatch; cleanup refused: '+key)
            if path.stat().st_mtime_ns!=row['source_mtime_ns'] or not path.resolve().is_relative_to(store.ROOT/'artifacts') or path.is_symlink():
                raise ValueError('CN source changed before deletion: '+key)
            path.unlink()
            with repo.engine.begin() as c:
                c.execute(store.migrations.update().where(store.migrations.c.version_id==row['version_id']).values(deleted_at=store.now()))
            deleted+=1;size+=len(raw)
            if deleted%100==0:print(json.dumps(dict(phase='DELETE_VERIFIED_SOURCES',completed=deleted,total=len(sources),bytes=size)),flush=True)
        report=dict(batch='cn_collection_sql_cleanup',status='COMPLETED',stored_at_utc=datetime.now(UTC).isoformat(),
            deleted_files=deleted,verified_bytes=size,source_files_remaining=len(source_files()),provider_calls=0)
        path=store.ROOT/'artifacts/research/cn_storage_migration'/('cleanup-'+datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
        repo.put(path,store.encode(report).encode())
        print(json.dumps(report),flush=True)
        return report


def verify_projections(repo):
    """Rebuild small query projections from their sealed sources, then check rows."""
    import io
    import pandas as pd
    checked=[]
    for key,kind in repo.keys():
        if kind!='file':continue
        if not (Path(key).name.startswith('snapshot-') and key.endswith('.json') or
                key.endswith('/oracle_top20.parquet') or key.endswith('/outcome_blind_matches.parquet')):continue
        raw=repo.get(store.ROOT/key);digest=store.sha(raw)
        if key.endswith('.json'):
            value=json.loads(raw)
            if value.get('schema')!='cn_dragon_tiger_observation_v1':continue
            table=store.events;expected=len(value['events'])
        else:
            frame=pd.read_parquet(io.BytesIO(raw));expected=len(frame)
            table=store.candidates if key.endswith('/oracle_top20.parquet') else store.matches
        with repo.engine.begin() as c:
            # Original bytes and receipt hashes are never changed.
            c.execute(table.delete().where(table.c.content_sha256==digest))
            if table is store.events:c.execute(store.snapshots.delete().where(store.snapshots.c.content_sha256==digest))
            repo._project(c,key,digest,raw)
            observed=c.execute(select(func.count()).select_from(table).where(table.c.content_sha256==digest)).scalar()
            if observed!=expected:raise ValueError('CN normalized SQL count mismatch: '+key)
            if table is store.candidates:
                rows=c.execute(select(store.candidates).where(store.candidates.c.content_sha256==digest).order_by(store.candidates.c.row_no)).mappings().all()
                if any(r['oracle_score']!=float(frame.iloc[i].oracle_score) for i,r in enumerate(rows)):
                    raise ValueError('CN normalized Oracle score precision mismatch')
        checked.append(dict(resource_key=key,rows=expected,content_sha256=digest))
    report=dict(batch='cn_collection_projection_validation',status='COMPLETED',documents=checked,
        source_bytes_modified=False,observed_at_utc=datetime.now(UTC).isoformat())
    repo.put(store.ROOT/'artifacts/research/cn_storage_migration/projections.json',store.encode(report).encode())
    print(json.dumps(report),flush=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--delete-sources',action='store_true')
    parser.add_argument('--cleanup-only',action='store_true')
    parser.add_argument('--verify-projections',action='store_true')
    parser.add_argument('--include-transient',action='store_true',help='Explicit final cleanup of old inactive .tmp/.lock receipts')
    args=parser.parse_args()
    if not args.apply:
        paths=source_files(include_transient=args.include_transient)
        print(json.dumps(dict(files=len(paths),bytes=sum(p.stat().st_size for p in paths),database='alpha_trade_cn',write=False)))
        return
    repo=store.repository()
    if args.verify_projections:verify_projections(repo)
    elif args.cleanup_only:
        if not args.delete_sources:parser.error('--cleanup-only requires --delete-sources')
        cleanup_verified(repo)
    else:migrate(repo,delete_sources=args.delete_sources,include_transient=args.include_transient)


if __name__=='__main__':main()
