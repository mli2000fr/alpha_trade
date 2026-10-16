"""Freeze the completed collection and a bounded, price-blind review sample.

SQL READ ONLY, four exhaustive half-open ID ranges, no provider or LLM calls.
This prepares source reading, not event approval or independent human review.
"""
from collections import Counter
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path

from sqlalchemy import create_engine, func, select, text

from scripts.research import us_news_event_qualification as evidence

RANGES = [(None,'eodhd:4'),('eodhd:4','eodhd:8'),('eodhd:8','eodhd:c'),('eodhd:c',None)]


def complete_snapshot(conn,since,cutoff,cap=5000):
    obs=evidence.archive.OBSERVATIONS
    count=conn.execute(select(func.count(func.distinct(obs.c.article_id))).where(
        obs.c.available_at>=since.replace(tzinfo=None),obs.c.available_at<cutoff.replace(tzinfo=None),
        obs.c.observed_at<cutoff.replace(tzinfo=None),obs.c.origin=='PROVIDER_COLLECTION')).scalar_one()
    merged=dict(article_ids=[],observations=[],raw_versions=[],mapping_versions=[],
                pending_receipts=0,truncated=False)
    records={key:{} for key in ('observations','raw_versions','mapping_versions')}
    partitions=[]
    for low,high in RANGES:
        part=evidence.read_snapshot(conn,since,cutoff,cap,article_start=low,article_end=high)
        if part['truncated']:
            raise ValueError('Partition truncated: subdivide before any full-corpus conclusion')
        if set(merged['article_ids']) & set(part['article_ids']):
            raise ValueError('Overlapping article ID partitions')
        merged['article_ids']+=part['article_ids']
        merged['pending_receipts']=max(merged['pending_receipts'],part['pending_receipts'])
        for key,values in records.items():
            for row in part[key]:
                if row['id'] in values and values[row['id']]!=row:
                    raise ValueError('Conflicting immutable archive versions')
                values[row['id']]=row
        partitions.append(dict(start_inclusive=low,end_exclusive=high,
            article_ids=len(part['article_ids']),observations=len(part['observations']),truncated=False))
    if len(merged['article_ids'])!=count:
        raise ValueError('Partition union does not cover the full SQL population')
    for key,values in records.items():
        merged[key]=[values[k] for k in sorted(values)]
    merged['partition_manifest']=dict(exhaustive=True,sql_distinct_articles=int(count),
        total_distinct_articles=len(merged['article_ids']),per_query_article_cap=cap,partitions=partitions)
    return merged


def select_review(items):
    # Defined before source reading. Old publications and short/unqualified
    # bodies remain in the full corpus but cannot pass this current-event sample.
    eligible=[r for r in items if not r['temporal_reservations']]
    screened=sorted((r for r in eligible if r['screened']),key=lambda r:r['evidence_key'])[:20]
    controls=sorted((r for r in eligible if not r['screened']),key=lambda r:r['evidence_key'])[:10]
    return screened+controls


def run(output,validation,since,cutoff):
    checked=json.loads((validation/'report.json').read_text(encoding='utf-8'))
    if checked['status']!='VALIDATED_COLLECTION_ONLY' or not checked['final']:
        raise ValueError('Require completed validated collection')
    universe=evidence.UNIVERSE
    if evidence.sha(universe)!=checked['current_universe_sha256']:
        raise ValueError('Universe changed since run validation')
    since,cutoff=evidence.utc(since),evidence.utc(cutoff)
    now=datetime.now(timezone.utc)
    if not since<cutoff<=now or output.exists():
        raise ValueError('Require bounded past window and fresh output')
    from common.universe_files import load_universe_file_symbols
    from database.connection import get_sqlalchemy_engine
    symbols=set(load_universe_file_symbols('universe-file:'+str(universe)))
    engine=create_engine(get_sqlalchemy_engine().url,pool_size=1,max_overflow=0,pool_pre_ping=True,
        connect_args={'connect_timeout':10,'read_timeout':25,'write_timeout':10},echo=False)
    try:
        with engine.connect() as conn:
            conn.execute(text("SET SESSION time_zone='+00:00'"))
            conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=15000'))
            if conn.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade':
                raise ValueError('US alpha_trade required')
            snapshot=complete_snapshot(conn,since,cutoff)
            conn.rollback()
    finally:
        engine.dispose()
    full=output/'full'
    full_report=evidence.build_pack(full,snapshot,symbols,since,cutoff,
        universe_sha256=evidence.sha(universe),now=now)
    items=json.loads((full/'evidence.json').read_text(encoding='utf-8'))
    selected=select_review(items)
    bounded=output/'bounded_review'
    bounded.mkdir()
    protocol=json.loads((full/'protocol.json').read_text(encoding='utf-8'))
    protocol.update(parent_report_sha256=evidence.sha(full/'report.json'),
        parent_evidence_sha256=evidence.sha(full/'evidence.json'),
        selection='Eligible publication/body/time only; stable evidence hash, max 20 screened + 10 controls; no prices',
        review_is_independent=False,code_sha256=evidence.sha(Path(__file__)))
    evidence.save(bounded/'protocol.json',protocol)
    evidence.save(bounded/'evidence.json',selected)
    evidence.save(bounded/'review_template.json',evidence.review_template(selected))
    report=dict(status='BOUNDED_REVIEW_REQUIRED',article_ids=len({r['article_id'] for r in selected}),
        confirmed_observations=len(snapshot['observations']),observations_count_scope='full parent corpus',
        candidate_article_symbol_pairs=len(selected),screened_pairs=sum(r['screened'] for r in selected),
        unique_screened_texts=len({r['text_hash'] for r in selected if r['screened']}),
        pending_receipts=snapshot['pending_receipts'],query_truncated=False,qualified_events=0,
        sample_not_complete_corpus=True,sql_writes=False,api_calls=0,training=False,
        files={p.name:evidence.sha(p) for p in bounded.iterdir() if p.is_file()})
    evidence.save(bounded/'report.json',report)
    result=dict(status='FULL_CORPUS_FROZEN_BOUNDED_REVIEW_PENDING',created_at_utc=now,
        run_id=checked['run_id'],validation_sha256=evidence.sha(validation/'report.json'),
        since_utc=since,cutoff_utc=cutoff,full_report=full_report,
        partition_manifest=snapshot['partition_manifest'],bounded_report=report,
        eligible_pairs=sum(not r['temporal_reservations'] for r in items),
        eligible_screened_pairs=sum(r['screened'] and not r['temporal_reservations'] for r in items),
        reservation_counts=dict(Counter(x for r in items for x in r['temporal_reservations'])),
        selection_keys=[r['evidence_key'] for r in selected],prices_used_for_selection=False,
        sql_writes=False,api_calls=0,llm_calls=0,training=False,economic_test=False)
    evidence.save(output/'preparation_report.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--validation',type=Path,required=True)
    parser.add_argument('--since',default='2026-10-14T00:00:00Z')
    parser.add_argument('--cutoff',required=True)
    args=parser.parse_args()
    result=run(args.output,args.validation,args.since,args.cutoff)
    print(json.dumps({k:result[k] for k in ('status','partition_manifest','bounded_report','eligible_pairs','eligible_screened_pairs')},ensure_ascii=False))
