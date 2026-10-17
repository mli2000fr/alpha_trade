"""Exercise the real MySQL writer ONLY in five session-temporary shadow tables.

All five SHOW CREATE results must explicitly say TEMPORARY before any data write.
Closing the private connection removes these copies, never the permanent tables.
"""
from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4

from sqlalchemy import MetaData, Table, create_engine, text
from sqlalchemy.pool import StaticPool

from database.connection import get_sqlalchemy_engine
from event_sentiment.db_io import EventSentimentRepository
from event_sentiment.news_archive import load_article_as_of, status

TABLES=('news_raw','news_ticker_map','news_raw_versions','news_ticker_map_versions','news_archive_observations')


def run():
    base=get_sqlalchemy_engine()
    before=status(base)
    definitions={}
    metadata=MetaData()
    with base.connect() as conn:
        for name in TABLES:
            definition=conn.exec_driver_sql(f'SHOW CREATE TABLE `{name}`').one()[1]
            if not definition.startswith(f'CREATE TABLE `{name}`'):
                raise RuntimeError('Expected a normal source table definition')
            # MySQL does not allow same-name CREATE TEMPORARY ... LIKE source.
            # Session copies omit FK/check constraints; installed DDL is checked
            # separately. Keep native columns and unique keys for this writer test.
            definition='\n'.join(line for line in definition.splitlines()
                if not line.lstrip().startswith('CONSTRAINT '))
            definition=definition.replace(',\n) ENGINE','\n) ENGINE')
            definitions[name]=definition.replace('CREATE TABLE','CREATE TEMPORARY TABLE',1)
        canonical={name:Table(name,metadata,autoload_with=conn) for name in TABLES[:2]}
    # Private single-session pool: temporary-table lifetime is connection-bound.
    engine=create_engine(base.url,poolclass=StaticPool,echo=False)
    article_id='eodhd:archive-smoke-'+uuid4().hex
    result={}
    try:
        with engine.connect() as conn:
            if conn.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade':
                raise RuntimeError('US database required')
            for name in TABLES:
                conn.exec_driver_sql(definitions[name])
            for name in TABLES:
                definition=conn.exec_driver_sql(f'SHOW CREATE TABLE `{name}`').one()[1]
                if 'CREATE TEMPORARY TABLE' not in definition.upper():
                    raise RuntimeError('Temporary table not proven; no test writes allowed')
            conn.commit()
        repo=object.__new__(EventSentimentRepository)
        repo.engine,repo.metadata,repo._tables=engine,metadata,canonical
        pub=datetime(2026,10,14,12,0,0,123456)
        record=dict(article_id=article_id,headline='Archive isolated smoke',summary=None,content='A — é €',
            source='isolated_test',author=None,url='https://example.invalid/no-network',
            published_at_utc=pub,event_timestamp_utc=pub,event_timestamp_ny=datetime(2026,10,14,8,0,0,123456),
            effective_trade_date=pub.date(),market_session_tag='regular',ingestion_source='eodhd',
            dedupe_hash=hashlib.sha256(article_id.encode()).hexdigest(),is_major_event=0,
            raw_payload={'created_at':'2026-10-14T12:00:00.123456Z','content':'A — é €','symbols':['TEST_ONLY']})
        maps=[dict(article_id=article_id,symbol='TEST_ONLY',sector='test',sector_source='fixture',
            sector_updated_at=None,is_primary_ticker=1,relevance_score=.5,relevance_components={'fixture':True})]
        context=dict(queried_symbol='TEST_ONLY',provider='eodhd',identity_qualified=False)
        first=repo.persist_news_page([record],maps,mapping_context=context)
        same=repo.persist_news_page([record],maps,mapping_context=context)
        if same['raw_versions'] or same['map_versions'] or same['observations']:
            raise RuntimeError('Duplicate unchanged smoke collection')
        changed=dict(record,content='B — é €',raw_payload=dict(record['raw_payload'],content='B — é €'))
        repo.persist_news_page([changed],maps,mapping_context=context)
        repo.persist_news_page([record],maps,mapping_context=context)
        with engine.connect() as conn:
            raw_type=conn.execute(text('SELECT JSON_TYPE(raw_payload) FROM news_raw WHERE article_id=:id'),{'id':article_id}).scalar_one()
            counts={name:conn.execute(text(f'SELECT COUNT(*) FROM `{name}`')).scalar_one() for name in TABLES}
            pending=conn.execute(text('SELECT COUNT(*) FROM news_archive_observations WHERE available_at IS NULL')).scalar_one()
            latest=load_article_as_of(conn,article_id,datetime.now(timezone.utc))
        if raw_type!='OBJECT' or counts['news_raw_versions']!=2 or counts['news_ticker_map_versions']!=2:
            raise RuntimeError('Native MySQL JSON or version counts differ')
        if counts['news_archive_observations']!=6 or pending or latest['content']!='A — é €':
            raise RuntimeError('Native MySQL recurrence/availability check failed')
        result=dict(status='MYSQL_SESSION_TEMPORARY_SHADOW_SMOKE_PASS',temporary_tables=list(TABLES),
            confirmed_temporary_before_writes=True,first_write=first,unchanged_write=same,
            temporary_row_counts=counts,pending_receipts=pending,json_payload_type=raw_type,
            recurrence='A_B_A_WITH_TWO_CONTENT_VERSIONS',provider_api_calls=0)
    finally:
        # Ends the private server session. No DROP or DELETE can target real data.
        engine.dispose()
    after=status(base)
    with base.connect() as conn:
        leaked=conn.execute(text('SELECT article_id FROM news_raw WHERE article_id=:id'),{'id':article_id}).first()
        if leaked is not None:
            raise RuntimeError('Smoke identifier unexpectedly present in permanent news')
    result.update(permanent_archive_counts_before=before,permanent_archive_counts_after=after,
        no_smoke_article_in_permanent_news=True)
    return result


if __name__=='__main__':
    print(json.dumps(run(),indent=2))
