"""Install/import/reuse saved research answers in US MySQL. NO paid API entrypoint."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path

from sqlalchemy import func, select

from .news_cache import CACHE,ARTICLES,USES,IMPORTS,NewsCache,atomic_json,install,request_identity,sha
from .stored_news import parse


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def saved_requests(root):
    root=Path(root).resolve()
    manifest=read(root/'analysis.json')
    # Verify full saved inputs/responses before any import, not current news_raw
    # projections which could have changed since the original paid request.
    prepared=read(root/'prepare.json')
    if 'packets.json' not in prepared['files']:raise ValueError('Unsealed input packets')
    expected_files=dict(prepared['files'])
    for name,expected in manifest['files'].items():
        if name in expected_files and expected_files[name]!=expected:
            raise ValueError('Conflicting source manifests')
        expected_files[name]=expected
    for name,expected in expected_files.items():
        path=(root/name).resolve()
        if not path.is_relative_to(root) or file_sha(path)!=expected:
            raise ValueError('Saved research evidence changed: '+name)
    packets=read(root/'packets.json')
    paths=sorted((root/'api').glob('*.request.json'))
    if not paths:paths=sorted(root.glob('*.request.json'))
    if len(paths)!=manifest['actual_calls']:raise ValueError('Incomplete paid request inventory')
    rows=[]
    for path in paths:
        response_path=path.with_name(path.name.replace('.request.json','.response.json'))
        if str(path.relative_to(root)) not in manifest['files'] or str(response_path.relative_to(root)) not in manifest['files']:
            raise ValueError('Unsealed paid response')
        request,response=read(path),read(response_path)
        context=json.loads(request['input'])
        packet=next(p for p in packets if p['symbol']==context['symbol'] and p['decision_date']==context['decision_date'])
        if {k:packet[k] for k in context}!=context:raise ValueError('Saved packet/request mismatch')
        request_identity(request,'SYMBOL_DATE_BUNDLE')
        rows.append((path,request,response))
    return root,rows


def import_run(engine,root):
    root,rows=saved_requests(root);cache=NewsCache(engine);counts=Counter()
    consumer='import:'+hashlib.sha256(str(root).encode()).hexdigest()
    refs=[]
    for path,request,response in rows:
        result=cache.import_response(request,response,scope='SYMBOL_DATE_BUNDLE',consumer=consumer,
            provenance=dict(source_run=str(root),request_file=str(path.relative_to(root)),
                request_file_sha256=file_sha(path),response_file_sha256=file_sha(path.with_name(
                    path.name.replace('.request.json','.response.json'))),
                original_request_file_mtime_utc=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),
                historical_text_pit_certified=False,qualifier_sha256=hashlib.sha256(inspect.getsource(parse).encode()).hexdigest()),
            qualifier=parse)
        counts['inserted' if result['created'] else 'reused']+=1;counts[result['status']]+=1
        context=json.loads(request['input'])
        refs.append(dict(cache_key=result['cache_key'],symbol=context['symbol'],decision_date=context['decision_date']))
    # The full candidate/UNKNOWN panel is retained as well, not only paid cases.
    # This enables a database-only replay after local research files are moved.
    snapshot=dict(packets=read(root/'packets.json'),requests=refs,
        original_analysis_manifest=read(root/'analysis.json'),source=str(root),research_only=True,
        qualifier_sha256=hashlib.sha256(inspect.getsource(parse).encode()).hexdigest())
    import_id=cache.save_import(str(root),snapshot)
    return dict(source=str(root),import_id=import_id,**counts,api_calls=0)


def replay_run(engine,root,output):
    root,rows=saved_requests(root);cache=NewsCache(engine)
    output=Path(output).resolve()
    if output==root or output.is_relative_to(root):raise ValueError('Do not overwrite sealed research run')
    imported=cache.get_import(sha(str(root)))
    return replay_import(engine,imported['import_id'],output)


def replay_import(engine,import_id,output):
    cache=NewsCache(engine);snapshot=json.loads(cache.get_import(import_id)['snapshot_json'])
    output=Path(output).resolve();root=Path(snapshot['source'])
    if output==root or output.is_relative_to(root):raise ValueError('Do not overwrite sealed research run')
    packets=snapshot['packets'];outcomes={}
    consumer='replay:'+hashlib.sha256(str(output).encode()).hexdigest()
    for ref in snapshot['requests']:
        cached=cache.get(ref['cache_key'])
        if cached is None:raise ValueError('Imported response missing in database')
        request=json.loads(cached['request_json'])
        if request_identity(request,'SYMBOL_DATE_BUNDLE')[0]!=ref['cache_key']:
            raise ValueError('Cached request integrity failure')
        value=cache.execute(request,scope='SYMBOL_DATE_BUNDLE',consumer=consumer,qualifier=parse)
        context=json.loads(request['input']);outcomes[(context['decision_date'],context['symbol'])]=value
    # Nothing is published if one cache entry was absent/unresolved.
    results=[]
    for packet in packets:
        value=outcomes.get((packet['decision_date'],packet['symbol']))
        if value is None:
            if packet['articles']:raise ValueError('Missing text-bearing assessment')
            assessment=dict(decision='UNKNOWN_NO_QUALIFIED_TEXT',veto_long=False,technical_status='NO_INPUT')
        else:
            assessment=dict(value['assessment'],technical_status='VALID' if value['status']=='VALID' else 'INVALID_PRESERVED',
                cache_key=value['cache_key'])
        results.append(dict(assessment,decision_date=packet['decision_date'],symbol=packet['symbol'],oracle_rank=packet['oracle_rank']))
    output.mkdir(parents=True,exist_ok=True)
    atomic_json(output/'assessments.json',results)
    report=dict(status='REUSED_DATABASE_RESEARCH_ONLY',candidates=len(results),cache_hits=len(snapshot['requests']),
        decisions=dict(Counter(x['decision'] for x in results)),api_calls=0,
        source=str(root),historical_pit_certified=False,production_publication=False)
    atomic_json(output/'report.json',report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--install',action='store_true')
    group.add_argument('--import-run',type=Path,action='append')
    group.add_argument('--replay-run',type=Path)
    group.add_argument('--replay-import')
    group.add_argument('--find-article')
    group.add_argument('--show-analysis')
    group.add_argument('--status',action='store_true')
    parser.add_argument('--symbol');parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    from database.connection import get_sqlalchemy_engine
    engine=get_sqlalchemy_engine();cache=NewsCache(engine)
    try:
        if args.install:result=install(engine)
        elif args.import_run:result=[import_run(engine,root) for root in args.import_run]
        elif args.replay_run:
            if args.output is None:parser.error('--output required')
            result=replay_run(engine,args.replay_run,args.output)
        elif args.replay_import:
            if args.output is None:parser.error('--output required')
            result=replay_import(engine,args.replay_import,args.output)
        elif args.find_article:
            if not args.symbol:parser.error('--symbol required')
            result=cache.find_article(args.symbol,args.find_article)
        elif args.show_analysis:
            result=cache.get(args.show_analysis)
            if result is None:raise ValueError('Analysis absent')
            result={k:v for k,v in result.items() if k!='owner_token'}
            result['research_only']=True
        else:
            with engine.connect() as conn:
                result={table.name:conn.execute(select(func.count()).select_from(table)).scalar_one()
                    for table in (CACHE,ARTICLES,USES,IMPORTS)}
        print(json.dumps(result,ensure_ascii=False,default=str,indent=2))
    finally:engine.dispose()


if __name__=='__main__':main()
