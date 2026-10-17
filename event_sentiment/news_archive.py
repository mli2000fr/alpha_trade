"""Prospective news versions and conservative, post-commit availability receipts.

No provider calls, historical backdating or implicit DDL. Version bodies are
immutable; only an observation's initially NULL availability is sealed once.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Column, DateTime,
    ForeignKey, Index, Integer, JSON, MetaData, String, Table, Text, UniqueConstraint,
    inspect, select, text, tuple_, update)
from sqlalchemy.dialects.mysql import DATETIME, MEDIUMTEXT, insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

META = MetaData()
ID = BigInteger().with_variant(Integer, 'sqlite')
BODY = Text().with_variant(MEDIUMTEXT(), 'mysql')
TS = DateTime(timezone=False).with_variant(DATETIME(fsp=6),'mysql')
RAW_VERSIONS = Table('news_raw_versions', META,
    Column('id',ID,primary_key=True,autoincrement=True),
    Column('article_id',String(128),nullable=False),
    Column('received_article_id',String(128),nullable=False),
    Column('ingestion_source',String(50),nullable=False),
    Column('snapshot_hash',String(64),nullable=False),
    Column('text_hash',String(64),nullable=False),
    Column('headline',String(1000),nullable=False),
    Column('summary',Text),Column('content',BODY),
    Column('source',String(100)),Column('author',String(255)),Column('url',String(2083)),
    Column('published_at_utc',TS),
    Column('provider_publication',String(128)),
    Column('publication_precision',String(32),nullable=False),
    Column('publication_utc',TS),
    Column('raw_payload',JSON,nullable=False),
    Column('first_observed_at',TS,nullable=False),
    UniqueConstraint('article_id','snapshot_hash',name='uq_news_raw_version'),
    Index('ix_news_raw_versions_publication','published_at_utc'),
    mysql_engine='InnoDB',mysql_charset='utf8mb4')
MAP_VERSIONS = Table('news_ticker_map_versions', META,
    Column('id',ID,primary_key=True,autoincrement=True),
    Column('article_id',String(128),nullable=False),
    Column('raw_version_id',ID,ForeignKey('news_raw_versions.id',ondelete='RESTRICT'),nullable=False),
    Column('snapshot_hash',String(64),nullable=False),
    Column('mapping_rows',JSON,nullable=False),Column('mapping_context',JSON,nullable=False),
    Column('payload_scope_complete',Boolean,nullable=False),
    Column('first_observed_at',TS,nullable=False),
    UniqueConstraint('article_id','snapshot_hash',name='uq_news_map_version'),
    mysql_engine='InnoDB',mysql_charset='utf8mb4')
OBSERVATIONS = Table('news_archive_observations', META,
    Column('id',ID,primary_key=True,autoincrement=True),
    Column('batch_id',String(32),nullable=False),
    Column('article_id',String(128),nullable=False),
    Column('stream_key',String(128),nullable=False),
    Column('origin',String(32),nullable=False),
    Column('raw_version_id',ID,ForeignKey('news_raw_versions.id',ondelete='RESTRICT')),
    Column('mapping_version_id',ID,ForeignKey('news_ticker_map_versions.id',ondelete='RESTRICT')),
    Column('observed_at',TS,nullable=False),
    Column('available_at',TS),
    CheckConstraint('(raw_version_id IS NULL) <> (mapping_version_id IS NULL)',name='ck_news_archive_one_version'),
    Index('ix_news_archive_stream','article_id','stream_key','id'),
    Index('ix_news_archive_available','available_at'),
    Index('ix_news_archive_batch','batch_id'),
    mysql_engine='InnoDB',mysql_charset='utf8mb4')

RAW_FIELDS = ('headline','summary','content','source','author','url','published_at_utc',
    'event_timestamp_utc','event_timestamp_ny','effective_trade_date','market_session_tag',
    'ingestion_source','is_major_event','dedupe_hash','raw_payload')
MAP_FIELDS = ('symbol','sector','sector_source','sector_updated_at','is_primary_ticker',
    'relevance_score','relevance_components')


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def json_value(value: Any) -> Any:
    """Canonical JSON values, including historical double-encoded JSON columns."""
    if isinstance(value,datetime):
        return value.isoformat()
    if isinstance(value,date):
        return value.isoformat()
    if isinstance(value,dict):
        return {str(k):json_value(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):
        return [json_value(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value,(str,bool,int,float)):
        return value
    raise TypeError('Unsupported archive JSON value: '+type(value).__name__)


def decode_json(value):
    for _ in range(3):
        if not isinstance(value,str):
            break
        value=json.loads(value)
    return json_value(value)


def canonical_hash(value) -> str:
    encoded=json.dumps(json_value(value),sort_keys=True,ensure_ascii=False,
        separators=(',',':'),allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def publication_details(payload):
    payload=payload if isinstance(payload,dict) else {}
    nested=payload.get('raw_provider_payload')
    nested=nested if isinstance(nested,dict) else {}
    original=next((obj.get(key) for obj in (nested,payload) for key in
        ('date','published_at','created_at') if obj.get(key)),None)
    if original is None:
        return None,'UNKNOWN',None
    original=str(original)
    # Do not invent midnight or an offset for date-only / timezone-naive inputs.
    try:
        if len(original)<=10:
            date.fromisoformat(original)
            return original,'DATE_ONLY',None
        parsed=datetime.fromisoformat(original.replace('Z','+00:00'))
        if parsed.tzinfo is None:
            return original,'TIMEZONE_UNKNOWN',None
        return original,'EXPLICIT_TIMEZONE',parsed.astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError:
        return original,'INVALID',None


def raw_snapshot(record, canonical_id, observed_at):
    clean={key:record.get(key) for key in RAW_FIELDS}
    clean['raw_payload']=decode_json(record.get('raw_payload',{}))
    original,precision,published=publication_details(clean['raw_payload'])
    if len(original or '')>128:
        # The full unmodified value remains in raw_payload; never silently truncate.
        raise ValueError('Provider publication string exceeds archive column')
    return dict(article_id=canonical_id,received_article_id=str(record['article_id']),
        ingestion_source=str(record['ingestion_source']),snapshot_hash=canonical_hash({
            'received_article_id':record['article_id'],'fields':clean}),
        text_hash=canonical_hash({k:clean[k] for k in ('headline','summary','content')}),
        **{key:clean[key] for key in ('headline','summary','content','source','author','url','published_at_utc')},
        provider_publication=original,publication_precision=precision,publication_utc=published,
        raw_payload=clean['raw_payload'],first_observed_at=observed_at)


def mapping_snapshot(article_id, raw_version_id, rows, context, complete, observed_at):
    by_symbol={}
    for row in rows:
        value={key:row.get(key) for key in MAP_FIELDS}
        if value['relevance_components'] is not None:
            value['relevance_components']=decode_json(value['relevance_components'])
        by_symbol[value['symbol']]=json_value(value)
    maps=[by_symbol[symbol] for symbol in sorted(by_symbol)]
    context=json_value(context)
    stable=dict(raw_version_id=raw_version_id,rows=maps,context=context,complete=bool(complete))
    return dict(article_id=article_id,raw_version_id=raw_version_id,
        snapshot_hash=canonical_hash(stable),mapping_rows=maps,mapping_context=context,
        payload_scope_complete=bool(complete),first_observed_at=observed_at)


def _insert_version(conn, table, value):
    found=conn.execute(select(table.c.id).where(table.c.article_id==value['article_id'],
        table.c.snapshot_hash==value['snapshot_hash'])).scalar_one_or_none()
    if found is not None:
        return int(found),False
    if conn.dialect.name=='sqlite':
        statement=sqlite_insert(table).values(value).on_conflict_do_nothing(
            index_elements=['article_id','snapshot_hash'])
    else:
        statement=mysql_insert(table).values(value).on_duplicate_key_update(id=table.c.id)
    conn.execute(statement)
    return int(conn.execute(select(table.c.id).where(table.c.article_id==value['article_id'],
        table.c.snapshot_hash==value['snapshot_hash'])).scalar_one()),True


def _observe(conn, batch_id, article_id, stream, origin, observed_at, *, raw_id=None, map_id=None):
    latest=conn.execute(select(OBSERVATIONS).where(OBSERVATIONS.c.article_id==article_id,
        OBSERVATIONS.c.stream_key==stream).order_by(OBSERVATIONS.c.id.desc()).limit(1)).mappings().first()
    if (latest and (latest['available_at'] is not None or latest['batch_id']==batch_id)
            and latest['origin']==origin and latest['raw_version_id']==raw_id and latest['mapping_version_id']==map_id):
        return 0
    conn.execute(OBSERVATIONS.insert().values(batch_id=batch_id,article_id=article_id,
        stream_key=stream,origin=origin,observed_at=observed_at,available_at=None,
        raw_version_id=raw_id,mapping_version_id=map_id))
    return 1


def seal_observations(engine, batch_id, expected):
    if not expected:
        return
    # The bodies/current projection are already committed. This instant is an
    # intentionally conservative upper bound for their local availability.
    available_at=utc_now()
    with engine.begin() as conn:
        observed=conn.execute(select(OBSERVATIONS.c.observed_at).where(OBSERVATIONS.c.batch_id==batch_id)).scalars().all()
        if observed and available_at<max(observed):
            raise RuntimeError('Clock moved backwards; archive availability remains unqualified')
        conn.execute(update(OBSERVATIONS).where(OBSERVATIONS.c.batch_id==batch_id,
            OBSERVATIONS.c.available_at.is_(None)).values(available_at=available_at))
        rows=conn.execute(select(OBSERVATIONS.c.available_at).where(OBSERVATIONS.c.batch_id==batch_id)).scalars().all()
        if len(rows)!=expected or any(x is None for x in rows):
            raise RuntimeError('News archive receipts not sealed; ingestion checkpoint must not advance')


def persist_page(repo, raw_rows, ticker_rows=None, *, mapping_context=None):
    """Atomic page: current projections + immutable snapshots + pending receipts.

    Lock current raw parents before reading archive streams. Receipts are sealed
    after commit; a failure raises to ingestion and cannot silently advance it.
    """
    if not raw_rows:
        return dict(landed=0,ticker_maps=0,raw_versions=0,map_versions=0,observations=0)
    observed_at=utc_now()
    batch_id=uuid4().hex
    duplicate_check={}
    for row in raw_rows:
        fingerprint=canonical_hash(raw_snapshot(row,row['article_id'],observed_at))
        if row['article_id'] in duplicate_check and duplicate_check[row['article_id']]!=fingerprint:
            raise ValueError('Conflicting duplicate article snapshots within one page')
        duplicate_check[row['article_id']]=fingerprint
    raw_table=repo._table('news_raw')
    if ticker_rows is not None:
        repo._table('news_ticker_map')
    stats=dict(landed=len(raw_rows),ticker_maps=0,raw_versions=0,map_versions=0,observations=0)
    with repo.engine.begin() as conn:
        # Source/hash aliases are resolved before upsert, then rechecked under
        # parent write locks. Never archive an alias as a separate canonical issuer.
        pairs=sorted({(r['ingestion_source'],r['dedupe_hash']) for r in raw_rows})
        existing=conn.execute(select(raw_table.c.article_id,raw_table.c.ingestion_source,
            raw_table.c.dedupe_hash).where(tuple_(raw_table.c.ingestion_source,
            raw_table.c.dedupe_hash).in_(pairs)).with_for_update()).mappings().all()
        by_hash={(r['ingestion_source'],r['dedupe_hash']):r['article_id'] for r in existing}
        existing_ids=set(conn.execute(select(raw_table.c.article_id).where(
            raw_table.c.article_id.in_(sorted({r['article_id'] for r in raw_rows})))).scalars())
        alias={}
        current=[]
        for row in raw_rows:
            key=(row['ingestion_source'],row['dedupe_hash'])
            canonical_id=by_hash.setdefault(key,row['article_id'])
            if row['article_id'] in existing_ids and canonical_id!=row['article_id']:
                raise ValueError('Conflicting existing article identities; no automatic merge')
            alias[row['article_id']]=canonical_id
            value=dict(row,article_id=canonical_id,raw_payload=decode_json(row.get('raw_payload',{})))
            current.append(value)
        repo._upsert('news_raw',current,{'article_id'},connection=conn)
        # Concurrent insert of the same provider/hash may have kept an older id.
        persisted=conn.execute(select(raw_table.c.article_id,raw_table.c.ingestion_source,
            raw_table.c.dedupe_hash).where(tuple_(raw_table.c.ingestion_source,
            raw_table.c.dedupe_hash).in_(pairs))).mappings().all()
        by_hash.update({(r['ingestion_source'],r['dedupe_hash']):r['article_id'] for r in persisted})
        for row in raw_rows:
            alias[row['article_id']]=by_hash.get((row['ingestion_source'],row['dedupe_hash']),alias[row['article_id']])
        maps=defaultdict(list)
        for row in ticker_rows or []:
            if row['article_id'] not in alias:
                raise ValueError('Mapping references an article outside its collected page')
            maps[row['article_id']].append(dict(row,article_id=alias[row['article_id']]))
        persisted_maps=[r for values in maps.values() for r in values]
        if persisted_maps:
            repo._upsert('news_ticker_map',persisted_maps,{'article_id','symbol'},connection=conn)
        stats['ticker_maps']=len(persisted_maps)
        for row in raw_rows:
            article_id=alias[row['article_id']]
            raw_id,new=_insert_version(conn,RAW_VERSIONS,raw_snapshot(row,article_id,observed_at))
            stats['raw_versions']+=int(new)
            stats['observations']+=_observe(conn,batch_id,article_id,'article','PROVIDER_COLLECTION',observed_at,raw_id=raw_id)
            if ticker_rows is not None:
                context=dict(mapping_context or {})
                map_id,new=_insert_version(conn,MAP_VERSIONS,mapping_snapshot(article_id,raw_id,
                    maps[row['article_id']],context,True,observed_at))
                stats['map_versions']+=int(new)
                scope=str(context.get('queried_symbol') or '__received_payload__')
                stats['observations']+=_observe(conn,batch_id,article_id,'mapping:payload:'+scope,
                    'PROVIDER_COLLECTION',observed_at,map_id=map_id)
    seal_observations(repo.engine,batch_id,stats['observations'])
    return stats


def persist_mapping_refresh(repo, rows):
    """Archive partial relevance updates, never present them as a full symbol set."""
    if not rows:
        return 0
    raw_table,map_table=repo._table('news_raw'),repo._table('news_ticker_map')
    observed_at,batch_id=utc_now(),uuid4().hex
    count=0
    with repo.engine.begin() as conn:
        ids=sorted({r['article_id'] for r in rows})
        parents={r['article_id']:dict(r) for r in conn.execute(select(raw_table).where(
            raw_table.c.article_id.in_(ids)).with_for_update()).mappings()}
        if set(parents)!=set(ids):
            raise ValueError('Cannot archive mapping refresh without its raw article')
        pairs=[(r['article_id'],r['symbol']) for r in rows]
        prior={(r['article_id'],r['symbol']):dict(r) for r in conn.execute(select(map_table).where(
            tuple_(map_table.c.article_id,map_table.c.symbol).in_(pairs))).mappings()}
        merged=[]
        for row in rows:
            value=dict(prior.get((row['article_id'],row['symbol']),{}),**row)
            value.pop('created_at',None)
            value.pop('updated_at',None)
            if value.get('relevance_components') is not None:
                value['relevance_components']=decode_json(value['relevance_components'])
            merged.append(value)
        repo._upsert('news_ticker_map',merged,{'article_id','symbol'},connection=conn)
        grouped=defaultdict(list)
        for row in merged:
            grouped[row['article_id']].append(row)
        for article_id,part in grouped.items():
            raw_id,_=_insert_version(conn,RAW_VERSIONS,raw_snapshot(parents[article_id],article_id,observed_at))
            count+=_observe(conn,batch_id,article_id,'article:current_row_review','CURRENT_ROW_REVIEW',observed_at,raw_id=raw_id)
            context=dict(reason='partial_mapping_refresh')
            map_id,_=_insert_version(conn,MAP_VERSIONS,mapping_snapshot(article_id,raw_id,part,context,False,observed_at))
            stream='mapping:partial:'+canonical_hash(sorted(x['symbol'] for x in part))
            count+=_observe(conn,batch_id,article_id,stream,'PARTIAL_MAPPING_REFRESH',observed_at,map_id=map_id)
    seal_observations(repo.engine,batch_id,count)
    return len(rows)


def status(engine):
    with engine.connect() as conn:
        if conn.dialect.name!='mysql' or conn.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade':
            raise RuntimeError('News archive status requires US alpha_trade')
        names=set(inspect(conn).get_table_names())
        out={}
        for table in META.sorted_tables:
            if table.name not in names:
                out[table.name]=dict(installed=False)
            else:
                from sqlalchemy import func
                out[table.name]=dict(installed=True,rows=conn.execute(select(func.count()).select_from(table)).scalar_one())
        if OBSERVATIONS.name in names:
            from sqlalchemy import func
            out['pending_receipts']=conn.execute(select(func.count()).select_from(OBSERVATIONS).where(
                OBSERVATIONS.c.available_at.is_(None))).scalar_one()
        return out


def install(engine):
    """Only the three additive archive tables; never upgrade unrelated revisions.

    The local database may have manually deployed schemas newer than its Alembic
    stamp. Retain that stamp, do not pretend all intervening migrations ran.
    """
    source=Path(__file__).resolve().parents[1]/'database/sql/news/news_archive_versions.sql'
    with engine.connect() as conn:
        if conn.dialect.name!='mysql' or conn.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade':
            raise RuntimeError('News archive installation requires US alpha_trade')
        names=set(inspect(conn).get_table_names())
        if not {'news_raw','news_ticker_map'}.issubset(names):
            raise RuntimeError('Existing US news tables required; no implicit application bootstrap')
        for statement in source.read_text(encoding='utf-8').split(';'):
            if statement.strip():
                conn.execute(text(statement))
        conn.commit()
        inspector=inspect(conn)
        for table in META.sorted_tables:
            actual={x['name'] for x in inspector.get_columns(table.name)}
            if actual!=set(table.c.keys()):
                raise RuntimeError('Existing archive schema differs: '+table.name)
    return status(engine)


def load_article_as_of(conn, article_id, cutoff):
    """Last locally proven version, NOT earliest worldwide news publication.

    Ordering by transactional observation id also handles A -> B -> A and
    out-of-order receipt sealing. Pending observations never qualify.
    """
    if cutoff.tzinfo is None:
        raise ValueError('An explicit timezone is required for archive cutoff')
    cutoff=cutoff.astimezone(timezone.utc).replace(tzinfo=None)
    observation=conn.execute(select(OBSERVATIONS).where(OBSERVATIONS.c.article_id==article_id,
        OBSERVATIONS.c.stream_key=='article',OBSERVATIONS.c.available_at.is_not(None),
        OBSERVATIONS.c.available_at<cutoff,OBSERVATIONS.c.observed_at<cutoff)
        .order_by(OBSERVATIONS.c.id.desc()).limit(1)).mappings().first()
    if observation is None:
        return None
    version=conn.execute(select(RAW_VERSIONS).where(
        RAW_VERSIONS.c.id==observation['raw_version_id'])).mappings().one()
    return dict(version,observation_id=observation['id'],observed_at=observation['observed_at'],
        available_at=observation['available_at'],observation_origin=observation['origin'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--status',action='store_true')
    mode.add_argument('--install',action='store_true')
    args=parser.parse_args()
    from database.connection import get_sqlalchemy_engine
    engine=get_sqlalchemy_engine()
    print(json.dumps(install(engine) if args.install else status(engine),indent=2))


if __name__=='__main__':
    main()
