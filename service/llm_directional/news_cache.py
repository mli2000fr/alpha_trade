"""US stored-news response cache, separate from prospective Web/order workflows.

One atomic claim per exact, versioned request. Never retry a paid/ambiguous
attempt, silently replace raw evidence, or turn an import into historical PIT.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile
import time
from uuid import uuid4

from sqlalchemy import (Column, DateTime, ForeignKey, Index, Integer, MetaData,
    String, Table, Text, inspect, select, text, update)
from sqlalchemy.dialects.mysql import DATETIME, LONGTEXT
from sqlalchemy.exc import IntegrityError

META=MetaData()
BODY=Text().with_variant(LONGTEXT(),'mysql')
TS=DateTime().with_variant(DATETIME(fsp=6),'mysql')
CACHE=Table('llm_news_analysis_cache',META,
    Column('cache_key',String(64),primary_key=True),
    Column('market_code',String(16),nullable=False),Column('symbol',String(100),nullable=False),
    Column('analysis_scope',String(32),nullable=False),Column('provider',String(20),nullable=False),
    Column('model_requested',String(128),nullable=False),Column('model_returned',String(128)),
    Column('protocol_sha256',String(64),nullable=False),Column('request_json',BODY,nullable=False),
    Column('response_json',BODY),Column('response_sha256',String(64)),Column('usage_json',BODY),
    Column('assessment_json',BODY),Column('status',String(24),nullable=False),
    Column('owner_token',String(32),nullable=False),Column('created_at',TS,nullable=False),
    Column('response_received_at',TS),Column('available_at',TS),Column('error_type',String(128)),
    Index('ix_llm_news_symbol','symbol','analysis_scope'),
    mysql_engine='InnoDB',mysql_charset='utf8mb4')
ARTICLES=Table('llm_news_analysis_articles',META,
    Column('cache_key',String(64),ForeignKey(CACHE.c.cache_key,ondelete='RESTRICT'),primary_key=True),
    Column('article_position',Integer,primary_key=True),Column('article_id',String(128),nullable=False),
    Column('article_sha256',String(64),nullable=False),
    Index('ix_llm_news_article','article_id','article_sha256'),
    mysql_engine='InnoDB',mysql_charset='utf8mb4')
USES=Table('llm_news_analysis_uses',META,
    Column('use_key',String(64),primary_key=True),
    Column('cache_key',String(64),ForeignKey(CACHE.c.cache_key,ondelete='RESTRICT'),nullable=False),
    Column('consumer_run_id',String(255),nullable=False),Column('use_kind',String(24),nullable=False),
    Column('recorded_at',TS,nullable=False),Column('details_json',BODY,nullable=False),
    Index('ix_llm_news_consumer','consumer_run_id'),
    mysql_engine='InnoDB',mysql_charset='utf8mb4')
IMPORTS=Table('llm_news_analysis_research_runs',META,
    Column('import_id',String(64),primary_key=True),Column('source_ref',Text,nullable=False),
    Column('snapshot_sha256',String(64),nullable=False),Column('snapshot_json',BODY,nullable=False),
    Column('imported_at',TS,nullable=False),
    mysql_engine='InnoDB',mysql_charset='utf8mb4')


class CacheMiss(RuntimeError):pass
class UnresolvedAttempt(RuntimeError):pass
class BundledEvidenceOnly(RuntimeError):pass


def now():return datetime.now(timezone.utc).replace(tzinfo=None)
def dumps(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))
def sha(value):return hashlib.sha256(dumps(value).encode('utf-8')).hexdigest()


def atomic_json(path,value):
    path=Path(path)
    descriptor,name=tempfile.mkstemp(prefix='.'+path.stem+'-',suffix='.tmp',dir=path.parent)
    temporary=Path(name)
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8') as stream:
            stream.write(dumps(value));stream.flush();os.fsync(stream.fileno())
        for attempt in range(20):
            try:
                temporary.replace(path);return
            except PermissionError:
                if attempt==19:raise
                time.sleep(min(.05*2**attempt,.5))
    finally:
        try:temporary.unlink(missing_ok=True)
        except OSError:logging.getLogger(__name__).warning('Temporary spool file retained: %s',temporary)


def request_identity(request,scope):
    if scope not in ('ARTICLE_AT_PUBLICATION','SYMBOL_DATE_BUNDLE'):
        raise ValueError('Explicit stored-news scope required')
    if request.get('tools') or any(key in request for key in ('previous_response_id','conversation')):
        raise ValueError('No Web, tools or implicit conversation in stored-news cache')
    if request.get('store') is not False or not isinstance(request.get('model'),str):
        raise ValueError('Explicit stateless model request required')
    context=json.loads(request['input'])
    allowed={'symbol','issuer_reference','articles','decision_date','cutoff_utc'}
    if not isinstance(context,dict) or set(context)-allowed:
        raise ValueError('Unexpected context, prices/outcomes are not allowed')
    symbol=context['symbol']
    if not isinstance(symbol,str) or not symbol or symbol!=symbol.upper() or len(symbol)>100:
        raise ValueError('Canonical US symbol required')
    articles=context['articles']
    if not articles or len({a['article_id'] for a in articles})!=len(articles):
        raise ValueError('Nonempty unique article versions required')
    for article in articles:
        if not isinstance(article['article_id'],str) or len(article['article_id'])>128:
            raise ValueError('Invalid article identifier')
        if set(article)-{'article_id','headline','summary','body','publication_utc','body_truncated','body_sha256'}:
            raise ValueError('Unexpected article fields')
        if not all(isinstance(article.get(field),str) for field in ('headline','summary','body')):
            raise ValueError('Exact supplied text fields required')
    if scope=='ARTICLE_AT_PUBLICATION' and (len(articles)!=1 or set(context)!= {'symbol','issuer_reference','articles'}):
        raise ValueError('Article analysis is independent of decision date, not a bundle verdict')
    if scope=='SYMBOL_DATE_BUNDLE' and set(context)!=allowed:
        raise ValueError('Bundle requires its exact date/cutoff context')
    key=sha(dict(market_code='US_EQ',provider='openai',scope=scope,request=request))
    protocol=sha({name:request.get(name) for name in ('instructions','text','reasoning','max_output_tokens')})
    return key,symbol,protocol,articles


class NewsCache:
    def __init__(self,engine):
        self.engine=engine
        if engine.dialect.name not in ('mysql','sqlite'):
            raise ValueError('Unsupported database')
        if engine.dialect.name=='mysql' and engine.url.database!='alpha_trade':
            raise ValueError('Stored news cache is US alpha_trade only')

    def get(self,key):
        with self.engine.connect() as conn:
            row=conn.execute(select(CACHE).where(CACHE.c.cache_key==key)).mappings().first()
        if row is None:return None
        row=dict(row)
        identity=request_identity(json.loads(row['request_json']),row['analysis_scope'])
        if identity[0]!=key or identity[1]!=row['symbol'] or row['market_code']!='US_EQ' or row['provider']!='openai':
            raise ValueError('Stored request integrity failure')
        if row['response_json'] is not None:
            response=json.loads(row['response_json'])
            if sha(response)!=row['response_sha256']:raise ValueError('Stored response integrity failure')
        return row

    def claim(self,request,scope):
        key,symbol,protocol,articles=request_identity(request,scope)
        owner=uuid4().hex
        try:
            with self.engine.begin() as conn:
                conn.execute(CACHE.insert().values(cache_key=key,market_code='US_EQ',symbol=symbol,
                    analysis_scope=scope,provider='openai',model_requested=request['model'],
                    protocol_sha256=protocol,request_json=dumps(request),status='CLAIMED',
                    owner_token=owner,created_at=now()))
                conn.execute(ARTICLES.insert(),[dict(cache_key=key,article_position=i,
                    article_id=a['article_id'],article_sha256=sha(a)) for i,a in enumerate(articles)])
            return key,owner,True
        except IntegrityError:
            existing=self.get(key)
            if existing is None:raise
            if json.loads(existing['request_json'])!=request:raise ValueError('Cache identity collision')
            return key,existing['owner_token'],False

    def save_raw(self,key,owner,response):
        # Commit raw evidence BEFORE parsing. Availability is confirmed separately
        # AFTER that commit; never copied from publication/provider.created time.
        with self.engine.begin() as conn:
            changed=conn.execute(update(CACHE).where(CACHE.c.cache_key==key,
                CACHE.c.owner_token==owner,CACHE.c.status.in_(('CLAIMED','TRANSPORT_UNKNOWN')),
                CACHE.c.response_json.is_(None)).values(response_json=dumps(response),
                    response_sha256=sha(response),usage_json=dumps(response.get('usage')),
                    model_returned=response.get('model'),response_received_at=now(),status='RECEIVED'))
            if changed.rowcount!=1:raise ValueError('Raw response already recorded or claim not owned')
        self.confirm_raw(key,sha(response))

    def confirm_raw(self,key,response_sha):
        row=self.get(key);receipt=now()
        if row is None or row['response_sha256']!=response_sha or row['response_received_at'] is None:
            raise ValueError('Cannot confirm absent or changed raw response')
        if receipt<row['response_received_at']:raise ValueError('Local clock moved backwards')
        with self.engine.begin() as conn:
            conn.execute(update(CACHE).where(CACHE.c.cache_key==key,CACHE.c.available_at.is_(None),
                CACHE.c.response_sha256==response_sha).values(available_at=receipt))

    def qualify(self,key,qualifier):
        row=self.get(key)
        if row is None or row['response_json'] is None or row['available_at'] is None:
            raise UnresolvedAttempt('Attempt unresolved; no automatic paid retry')
        try:
            assessment=qualifier(json.loads(row['response_json']),json.loads(row['request_json']))
            status,error='VALID',None
        except Exception as exc:
            assessment=dict(decision='UNKNOWN_INVALID_RESPONSE',veto_long=False,
                error_type=type(exc).__name__)
            status,error='INVALID',type(exc).__name__
        with self.engine.begin() as conn:
            # First qualification is immutable; later parser versions may reparse
            # the same raw response and record their result in USES, never repay it.
            conn.execute(update(CACHE).where(CACHE.c.cache_key==key,CACHE.c.status=='RECEIVED')
                .values(assessment_json=dumps(assessment),status=status,error_type=error))
        return dict(cache_key=key,status=status,assessment=assessment,response=json.loads(row['response_json']),
            available_at=row['available_at'],research_only=True)

    def use(self,key,consumer,kind,details):
        use_key=sha(dict(cache_key=key,consumer=consumer,kind=kind,details=details))
        try:
            with self.engine.begin() as conn:
                conn.execute(USES.insert().values(use_key=use_key,cache_key=key,consumer_run_id=consumer,
                    use_kind=kind,recorded_at=now(),details_json=dumps(details)))
        except IntegrityError:
            with self.engine.connect() as conn:
                if conn.execute(select(USES.c.use_key).where(USES.c.use_key==use_key)).scalar_one_or_none() is None:raise

    def import_response(self,request,response,*,scope,consumer,provenance,qualifier):
        key,owner,created=self.claim(request,scope)
        if created:self.save_raw(key,owner,response)
        else:
            saved=self.get(key)
            if saved['response_json'] is None:
                # A real saved response can recover an ambiguous attempt; no API.
                self.save_raw(key,owner,response)
            elif sha(response)!=saved['response_sha256']:
                raise ValueError('Different paid response for an existing request; do not overwrite')
            elif saved['available_at'] is None:
                # Explicit import of the matching durable raw response recovers
                # an interrupted receipt NOW, never at the old publication time.
                self.confirm_raw(key,sha(response))
        result=self.qualify(key,qualifier)
        self.use(key,consumer,'IMPORT',dict(provenance,qualification=result['assessment']))
        return dict(result,created=created,cache_hit=not created,api_calls=0)

    def execute(self,request,*,scope,consumer,qualifier,transport=None,allow_paid=False,journal_root=None):
        key,*_=request_identity(request,scope)
        row=self.get(key)
        if row is not None:
            if json.loads(row['request_json'])!=request:raise ValueError('Request mismatch')
            result=self.qualify(key,qualifier)
            self.use(key,consumer,'CACHE_HIT',dict(qualification=result['assessment']))
            return dict(result,cache_hit=True,api_calls=0)
        if not allow_paid or transport is None:
            raise CacheMiss('No identical analysis in database; paid call disabled')
        if journal_root is None:raise ValueError('Durable local response spool required before paid calls')
        key,owner,created=self.claim(request,scope)
        if not created:
            # The competing worker owns the single paid call. Never expire its claim.
            return self.execute(request,scope=scope,consumer=consumer,qualifier=qualifier)
        folder=Path(journal_root)/key;folder.mkdir(parents=True,exist_ok=True)
        atomic_json(folder/'request.json',request)
        try:
            response=transport(request)
            atomic_json(folder/'response.json',response)
        except Exception as exc:
            with self.engine.begin() as conn:
                conn.execute(update(CACHE).where(CACHE.c.cache_key==key,CACHE.c.owner_token==owner,
                    CACHE.c.response_json.is_(None)).values(status='TRANSPORT_UNKNOWN',error_type=type(exc).__name__))
            raise UnresolvedAttempt('Paid/transport outcome unknown; no automatic retry') from None
        self.save_raw(key,owner,response)
        result=self.qualify(key,qualifier)
        self.use(key,consumer,'NEW_CALL',dict(qualification=result['assessment']))
        return dict(result,cache_hit=False,api_calls=1)

    def find_article(self,symbol,article_id):
        # Related BUNDLE rows remain bundles: never masquerade as article verdicts.
        with self.engine.connect() as conn:
            return [dict(row) for row in conn.execute(select(CACHE.c.cache_key,CACHE.c.analysis_scope,
                CACHE.c.symbol,CACHE.c.model_requested,CACHE.c.status,CACHE.c.available_at,
                ARTICLES.c.article_sha256).join(ARTICLES,CACHE.c.cache_key==ARTICLES.c.cache_key)
                .where(CACHE.c.symbol==symbol,ARTICLES.c.article_id==article_id)).mappings()]

    def save_import(self,source,snapshot):
        key=sha(source);encoded=dumps(snapshot)
        try:
            with self.engine.begin() as conn:
                conn.execute(IMPORTS.insert().values(import_id=key,source_ref=source,snapshot_sha256=sha(snapshot),
                    snapshot_json=encoded,imported_at=now()))
        except IntegrityError:
            saved=self.get_import(key)
            # Parser version is provenance of the FIRST import, not part of the
            # paid inputs. A new parser may re-read raw replies without replacing
            # this snapshot or making a new paid call.
            previous=json.loads(saved['snapshot_json'])
            if {k:v for k,v in previous.items() if k!='qualifier_sha256'}!={k:v for k,v in snapshot.items() if k!='qualifier_sha256'}:
                raise ValueError('Imported run changed; no overwrite')
        return key

    def get_import(self,key):
        with self.engine.connect() as conn:
            row=dict(conn.execute(select(IMPORTS).where(IMPORTS.c.import_id==key)).mappings().one())
        if sha(json.loads(row['snapshot_json']))!=row['snapshot_sha256']:
            raise ValueError('Imported snapshot integrity failure')
        return row


def install(engine):
    NewsCache(engine)
    if engine.dialect.name!='mysql':raise ValueError('Explicit US MySQL installation only')
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade':raise ValueError('US required')
    META.create_all(engine,checkfirst=True)
    inspector=inspect(engine)
    for table in META.sorted_tables:
        if {c['name'] for c in inspector.get_columns(table.name)}!=set(table.c.keys()):
            raise ValueError('Existing cache schema differs: '+table.name)
        if inspector.get_pk_constraint(table.name)['constrained_columns']!=[c.name for c in table.primary_key.columns]:
            raise ValueError('Cache uniqueness contract differs: '+table.name)
        actual_indexes={tuple(i['column_names']) for i in inspector.get_indexes(table.name)}
        if any(tuple(c.name for c in index.columns) not in actual_indexes for index in table.indexes):
            raise ValueError('Cache lookup index missing: '+table.name)
    return {'installed':[table.name for table in META.sorted_tables]}
