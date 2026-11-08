"""Independent read-only completeness check of the finished local FIRDS import."""
import argparse
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
from unittest.mock import patch
import zipfile

from sqlalchemy import text,bindparam

from service.fr.batch_research_store import engine_fr
from service.fr.collection_storage import Repository,use,zip_source
from service.fr.firds_sql_history_import import source_files


def verify(output):
    output=Path(output).resolve()
    report=json.loads((output/'report.json').read_text(encoding='utf-8'))
    if report.get('status')!='COMPLETED':raise ValueError('Finished full import required')
    manifest=json.loads((output/'source-manifest.json').read_text(encoding='utf-8'))
    source=Path(manifest['source_root']);records={}
    for line in (output/'files.jsonl').read_text(encoding='utf-8').splitlines():
        row=json.loads(line);records[row['path']]=row
    expected={r['path']:r for r in manifest['files']}
    if set(records)!=set(expected):raise ValueError('File journal coverage differs from source manifest')
    if source_files(source)!=manifest['files']:raise ValueError('Local sources changed during import')
    if not report['verified']==report['files_total']==len(expected) or report['failed']:
        raise ValueError('Incomplete run counters')
    if sum(r['bytes'] for r in records.values())!=manifest['total_bytes']:
        raise ValueError('Journal byte count mismatch')
    if any(r['status'] not in ('IMPORTED_VERIFIED','ALREADY_PRESENT_VERIFIED') for r in records.values()):
        raise ValueError('Unverified source entry in final journal')
    engine=engine_fr();repo=Repository(engine);db_versions={};objects={};chunks={}
    if engine.url.database!='alpha_trade_fr':raise ValueError('FR database only')
    try:
        with engine.connect() as c:
            c.execute(text("SET SESSION time_zone='+00:00'"))
            c.execute(text('SET SESSION TRANSACTION READ ONLY'))
            physical=c.execute(text('SELECT DATABASE()')).scalar_one()
            if physical!='alpha_trade_fr':raise ValueError('Wrong physical database')
            run=dict(c.execute(text('SELECT status,finished_at FROM fr_collection_runs WHERE operational_run_id=:run'),
                               dict(run=report['run_id'])).mappings().one())
            if run['status']!='COMPLETED' or run['finished_at'] is None:
                raise ValueError('SQL run not finalized')
            rows=c.execute(text('SELECT v.resource_key,v.content_sha256,v.available_at,o.byte_length,'
                'h.content_sha256 AS head_sha256 FROM fr_collection_versions v '
                'JOIN fr_collection_objects o ON o.content_sha256=v.content_sha256 '
                'LEFT JOIN fr_collection_heads h ON h.batch_name=v.batch_name AND h.resource_sha256=v.resource_sha256 '
                "WHERE v.batch_name='fr_reference_inputs' AND v.resource_key LIKE 'esma_firds/%'")).mappings()
            for row in rows:
                r=dict(row);db_versions[(r['resource_key'],r['content_sha256'])]=r
                objects[r['content_sha256']]=r['byte_length']
            hashes=sorted({r['sha256'] for r in records.values()})
            for offset in range(0,len(hashes),300):
                query=text('SELECT content_sha256,COUNT(*) n,MIN(part_no) first_part,MAX(part_no) last_part '
                    'FROM fr_collection_object_parts WHERE content_sha256 IN :hashes GROUP BY content_sha256')
                query=query.bindparams(bindparam('hashes',expanding=True))
                for row in c.execute(query,dict(hashes=hashes[offset:offset+300])).mappings():
                    chunks[row['content_sha256']]=dict(row)
            c.rollback()
        head_conflicts=0
        for path,record in records.items():
            stored=db_versions.get((record['resource_key'],record['sha256']))
            if stored is None or stored['byte_length']!=record['bytes'] or stored['available_at'] is None:
                raise ValueError('Missing/incomplete SQL version: '+path)
            parts=chunks.get(record['sha256']);n=max(1,(record['bytes']+999999)//1000000)
            if parts is None or (parts['n'],parts['first_part'],parts['last_part'])!=(n,0,n-1):
                raise ValueError('Missing SQL object chunks: '+path)
            if stored['head_sha256']!=record['sha256']:
                if not record['head_preserved']:raise ValueError('Unexpected current-version mismatch')
                head_conflicts+=1
        # Representative SQL-only opening: no source file body may be read.
        samples=[]
        for year in range(2018,2027):
            matches=[r for r in records.values() if '/'+str(year)+'/' in r['path'] and r['path'].endswith('.zip')
                     and not r['head_preserved']]
            if not matches:raise ValueError('No representative archive for '+str(year))
            row=sorted(matches,key=lambda r:r['path'])[0]
            path=source/row['path']
            with patch.object(Path,'read_bytes',side_effect=AssertionError('Local file body read forbidden')):
                with use(repo):
                    stream=zip_source(path)
                    raw=stream.getvalue()
                    if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('Sample SQL checksum mismatch')
                    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                        names=archive.namelist()
                        if not names or any(not n.endswith('.xml') for n in names):raise ValueError('Invalid sample ZIP')
            samples.append(dict(year=year,path=row['resource_key'],bytes=row['bytes'],sha256=row['sha256'],SQL_only=True))
    finally:engine.dispose()
    result=dict(status='VERIFIED_COMPLETE',verified_at=datetime.now(timezone.utc).isoformat(),
        sql_database=physical,sql_run_id=report['run_id'],sql_run_finalized=True,
        manifest_files=len(expected),verified_versions=len(records),source_bytes=manifest['total_bytes'],
        unique_objects=len(hashes),unique_object_bytes=sum(objects[h] for h in hashes),
        verified_chunk_numbers=sum(chunks[h]['n'] for h in hashes),head_conflicts_preserved=head_conflicts,
        sql_only_archive_samples=samples,source_tree_unchanged=True,source_files_deleted=0,
        SQL_writes=False,provider_calls=0,review='Same assistant, separate verification code; not independent human review')
    (output/'verification.json').write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='sql_only_archive_samples'},default=str),flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    verify(parser.parse_args().output)
