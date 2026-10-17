"""All writes use isolated SQLite memory databases, never alpha_trade."""
from datetime import datetime, timedelta, timezone
import json

import pytest
from sqlalchemy import (Column, DateTime, Integer, JSON, MetaData, String, Table,
    Text, UniqueConstraint, create_engine, event, func, select)
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from event_sentiment import news_archive as archive
from event_sentiment.db_io import EventSentimentRepository


@pytest.fixture
def repo(monkeypatch):
    engine=create_engine('sqlite:///:memory:')
    @event.listens_for(engine,'connect')
    def foreign_keys(connection,_):
        connection.execute('PRAGMA foreign_keys=ON')
    meta=MetaData()
    raw=Table('news_raw',meta,Column('article_id',String,primary_key=True),
        Column('headline',String,nullable=False),Column('summary',Text),Column('content',Text),
        Column('source',String),Column('author',String),Column('url',String),
        Column('published_at_utc',DateTime),Column('event_timestamp_utc',DateTime),
        Column('event_timestamp_ny',DateTime),Column('effective_trade_date',String),
        Column('market_session_tag',String),Column('ingestion_source',String),
        Column('dedupe_hash',String),Column('is_major_event',Integer),Column('raw_payload',JSON),
        Column('created_at',DateTime,server_default=func.current_timestamp()),
        Column('updated_at',DateTime,server_default=func.current_timestamp()),
        UniqueConstraint('ingestion_source','dedupe_hash'))
    maps=Table('news_ticker_map',meta,Column('article_id',String,primary_key=True),
        Column('symbol',String,primary_key=True),Column('sector',String),Column('sector_source',String),
        Column('sector_updated_at',DateTime),Column('is_primary_ticker',Integer),
        Column('relevance_score',Integer),Column('relevance_components',JSON),
        Column('created_at',DateTime,server_default=func.current_timestamp()),
        Column('updated_at',DateTime,server_default=func.current_timestamp()))
    meta.create_all(engine)
    archive.META.create_all(engine)
    repository=object.__new__(EventSentimentRepository)
    repository.engine=engine
    repository.metadata=meta
    repository._tables={'news_raw':raw,'news_ticker_map':maps}
    current=[datetime(2026,10,15,0,0,0,123456)]
    def clock():
        current[0]+=timedelta(milliseconds=1)
        return current[0]
    monkeypatch.setattr(archive,'utc_now',clock)
    yield repository
    engine.dispose()


def article(content='A', article_id='eodhd:one', dedupe_hash='hash'):
    published=datetime(2025,1,2,14)
    return dict(article_id=article_id,headline='Issuer update',summary=None,content=content,
        source='Example',author=None,url='https://example.test/story',published_at_utc=published,
        event_timestamp_utc=published,event_timestamp_ny=datetime(2025,1,2,9),
        effective_trade_date='2025-01-02',market_session_tag='regular',ingestion_source='eodhd',
        dedupe_hash=dedupe_hash,is_major_event=0,raw_payload={
            'created_at':'2025-01-02T15:00:00+01:00','content':content,'symbols':['TEST']})


def mapping(symbol='TEST',article_id='eodhd:one'):
    return dict(article_id=article_id,symbol=symbol,sector='Technology',sector_source='test',
        sector_updated_at=None,is_primary_ticker=1,relevance_score=1,relevance_components={'x':1})


def count(repo,table):
    with repo.engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(table)).scalar_one()


def rows(repo,table):
    with repo.engine.connect() as conn:
        return [dict(x) for x in conn.execute(select(table).order_by(table.c.id)).mappings()]


def write(repo,content='A',maps=None):
    return repo.persist_news_page([article(content)], [mapping()] if maps is None else maps,
        mapping_context={'queried_symbol':'TEST','identity_qualified':False})


def test_two_identical_collections_do_not_duplicate_versions_or_receipts(repo):
    first=write(repo)
    before=rows(repo,archive.OBSERVATIONS)
    second=write(repo)
    assert first['raw_versions']==first['map_versions']==1
    assert second['raw_versions']==second['map_versions']==second['observations']==0
    assert count(repo,archive.RAW_VERSIONS)==count(repo,archive.MAP_VERSIONS)==1
    assert rows(repo,archive.OBSERVATIONS)==before
    assert all(r['available_at']>r['observed_at'] for r in before)
    with repo.engine.connect() as conn:
        assert isinstance(conn.execute(select(repo._table('news_raw').c.raw_payload)).scalar_one(),dict)
        assert isinstance(conn.execute(select(repo._table('news_ticker_map').c.relevance_components)).scalar_one(),dict)


def test_change_and_return_to_old_content_preserve_state_without_copying_old_body(repo):
    write(repo,'A')
    first=rows(repo,archive.RAW_VERSIONS)[0]
    write(repo,'B')
    middle=rows(repo,archive.OBSERVATIONS)[-1]['available_at']+timedelta(microseconds=1)
    write(repo,'A')
    versions=rows(repo,archive.RAW_VERSIONS)
    assert len(versions)==2 and versions[0]==first
    assert count(repo,archive.OBSERVATIONS)==6
    with repo.engine.connect() as conn:
        old=archive.load_article_as_of(conn,'eodhd:one',middle.replace(tzinfo=timezone.utc))
        latest=archive.load_article_as_of(conn,'eodhd:one',datetime(2026,10,16,tzinfo=timezone.utc))
    assert old['content']=='B' and latest['content']=='A'
    assert latest['id']==first['id']


def test_mapping_changes_empty_set_and_partial_refresh_are_distinct(repo):
    write(repo,maps=[mapping('TEST'),mapping('OTHER')])
    write(repo,maps=[])
    versions=rows(repo,archive.MAP_VERSIONS)
    assert len(versions)==2 and versions[1]['mapping_rows']==[]
    assert versions[1]['payload_scope_complete']
    repo.upsert_news_ticker_map([dict(article_id='eodhd:one',symbol='TEST',relevance_score=0)])
    latest=rows(repo,archive.MAP_VERSIONS)[-1]
    assert not latest['payload_scope_complete']
    assert latest['mapping_rows'][0]['sector']=='Technology'
    assert latest['mapping_rows'][0]['relevance_score']==0


def test_provider_alias_uses_canonical_id_and_keeps_original_id(repo):
    write(repo)
    alias=article(article_id='eodhd:alias')
    repo.persist_news_page([alias],[mapping(article_id='eodhd:alias')])
    versions=rows(repo,archive.RAW_VERSIONS)
    assert {x['article_id'] for x in versions}=={'eodhd:one'}
    assert versions[-1]['received_article_id']=='eodhd:alias'
    assert count(repo,repo._table('news_raw'))==1
    assert {x['article_id'] for x in rows(repo,archive.MAP_VERSIONS)}=={'eodhd:one'}


def test_archive_failure_rolls_back_current_projection_and_versions(repo,monkeypatch):
    write(repo,'A')
    original=archive._insert_version
    def failure(conn,table,value):
        if table.name==archive.MAP_VERSIONS.name:
            raise RuntimeError('archive test failure')
        return original(conn,table,value)
    monkeypatch.setattr(archive,'_insert_version',failure)
    with pytest.raises(RuntimeError,match='test failure'):
        write(repo,'B')
    assert count(repo,archive.RAW_VERSIONS)==1
    with repo.engine.connect() as conn:
        assert conn.execute(select(repo._table('news_raw').c.content)).scalar_one()=='A'


def test_unsealed_commit_is_never_qualified_and_retry_does_not_backdate(repo,monkeypatch):
    seal=archive.seal_observations
    def failure(*args):
        raise RuntimeError('lost receipt')
    monkeypatch.setattr(archive,'seal_observations',failure)
    with pytest.raises(RuntimeError,match='lost receipt'):
        write(repo)
    assert count(repo,archive.RAW_VERSIONS)==1
    with repo.engine.connect() as conn:
        assert archive.load_article_as_of(conn,'eodhd:one',datetime(2026,10,16,tzinfo=timezone.utc)) is None
    pending=rows(repo,archive.OBSERVATIONS)
    monkeypatch.setattr(archive,'seal_observations',seal)
    write(repo)
    observations=rows(repo,archive.OBSERVATIONS)
    assert count(repo,archive.RAW_VERSIONS)==1
    assert all(r['available_at'] is None for r in observations[:len(pending)])
    assert all(r['available_at']>r['observed_at'] for r in observations[len(pending):])
    assert observations[-1]['observed_at']>pending[-1]['observed_at']


def test_legacy_backfill_does_not_gain_historical_availability(repo):
    value=article()
    value['raw_payload']=json.dumps(json.dumps(value['raw_payload']))
    repo.upsert_news_raw([value])
    version=rows(repo,archive.RAW_VERSIONS)[0]
    assert version['publication_precision']=='EXPLICIT_TIMEZONE'
    assert version['publication_utc']==datetime(2025,1,2,14)
    assert version['first_observed_at'].year==2026
    with repo.engine.connect() as conn:
        assert archive.load_article_as_of(conn,'eodhd:one',datetime(2025,1,3,tzinfo=timezone.utc)) is None
        with pytest.raises(ValueError,match='timezone'):
            archive.load_article_as_of(conn,'eodhd:one',datetime(2026,10,16))


@pytest.mark.parametrize('value,precision',[
    ('2025-01-02','DATE_ONLY'),('2025-01-02T14:00:00','TIMEZONE_UNKNOWN'),
    ('not a date','INVALID'),(None,'UNKNOWN'),('2025-01-02T14:00:00Z','EXPLICIT_TIMEZONE')])
def test_publication_precision_is_preserved(value,precision):
    original,status,utc=archive.publication_details({'created_at':value})
    assert status==precision
    if precision!='EXPLICIT_TIMEZONE':
        assert utc is None


def test_json_key_order_does_not_create_versions(repo):
    value=article()
    repo.upsert_news_raw([value])
    value['raw_payload']=dict(reversed(list(value['raw_payload'].items())))
    repo.upsert_news_raw([value])
    assert count(repo,archive.RAW_VERSIONS)==1


def test_clock_rollback_does_not_invent_availability(repo,monkeypatch):
    times=iter([datetime(2026,10,15),datetime(2026,10,14)])
    monkeypatch.setattr(archive,'utc_now',lambda:next(times))
    with pytest.raises(RuntimeError,match='Clock moved backwards'):
        write(repo)
    assert all(r['available_at'] is None for r in rows(repo,archive.OBSERVATIONS))


def test_mysql_schema_retains_microseconds_and_restricts_version_deletion():
    ddl='\n'.join(str(CreateTable(t).compile(dialect=mysql.dialect())) for t in archive.META.sorted_tables)
    assert 'DATETIME(6)' in ddl and 'MEDIUMTEXT' in ddl
    assert 'ON DELETE CASCADE' not in ddl and 'ON DELETE RESTRICT' in ddl
    assert 'uq_news_raw_version' in ddl and 'ck_news_archive_one_version' in ddl


def test_collector_uses_atomic_archive_writer_with_no_extra_provider_calls(repo,monkeypatch):
    from event_sentiment import ingestion
    from event_sentiment.config import EventSentimentConfig
    calls=[]
    class Mapper:
        def resolve(self,*args,**kwargs):
            return {'TEST':{'sector':'Technology','sector_source':'fixture','sector_updated_at':None}}
    monkeypatch.setattr(ingestion,'EntitySectorMapper',Mapper)
    payload=dict(id='one',created_at='2025-01-02T14:00:00Z',headline='Issuer update',
        content='body',source='Example',url='https://example.test/story',symbols=['TEST'])
    def provider(**kwargs):
        calls.append(kwargs)
        yield [payload],None
    monkeypatch.setitem(ingestion.NEWS_PROVIDERS,'eodhd',provider)
    monkeypatch.setattr(repo,'get_checkpoint',lambda *a:None)
    checkpoints=[]
    monkeypatch.setattr(repo,'upsert_checkpoint',lambda *a,**kw:checkpoints.append(a))
    service=ingestion.NewsIngestionService(repo,EventSentimentConfig.for_provider('eodhd'))
    result=service.run(datetime(2025,1,2,tzinfo=timezone.utc),datetime(2025,1,3,tzinfo=timezone.utc),['TEST'])
    assert len(calls)==1 and result['landed']==result['ticker_maps']==1
    assert count(repo,archive.RAW_VERSIONS)==count(repo,archive.MAP_VERSIONS)==1
    context=rows(repo,archive.MAP_VERSIONS)[0]['mapping_context']
    assert context['queried_symbol']=='TEST' and context['provider']=='eodhd'
    assert context['ticker_relevance_mode']=='provider_default'
    assert context['identity_qualified'] is False
    assert checkpoints[-1][-1]=='success'


def test_collector_failure_marks_checkpoint_failed_without_success(repo,monkeypatch):
    from event_sentiment import ingestion
    from event_sentiment.config import EventSentimentConfig
    class Mapper:
        def resolve(self,*a,**kw):
            return {}
    monkeypatch.setattr(ingestion,'EntitySectorMapper',Mapper)
    def provider(**kwargs):
        yield [dict(id='one',created_at='2025-01-02T14:00:00Z',headline='Issuer',symbols=['TEST'])],None
    monkeypatch.setitem(ingestion.NEWS_PROVIDERS,'eodhd',provider)
    monkeypatch.setattr(repo,'get_checkpoint',lambda *a:None)
    checkpoints=[]
    monkeypatch.setattr(repo,'upsert_checkpoint',lambda *a,**kw:checkpoints.append(a))
    def failure(*args):
        raise RuntimeError('receipt failure')
    monkeypatch.setattr(archive,'seal_observations',failure)
    service=ingestion.NewsIngestionService(repo,EventSentimentConfig.for_provider('eodhd'))
    with pytest.raises(RuntimeError,match='receipt failure'):
        service.run(datetime(2025,1,2,tzinfo=timezone.utc),datetime(2025,1,3,tzinfo=timezone.utc),['TEST'])
    assert checkpoints[-1][-1]=='failed'
    assert all(x[-1]!='success' for x in checkpoints)


def test_missing_archive_table_fails_without_silent_current_row_commit(repo):
    archive.OBSERVATIONS.drop(repo.engine)
    with pytest.raises(Exception):
        write(repo)
    assert count(repo,repo._table('news_raw'))==0
    assert count(repo,archive.RAW_VERSIONS)==0


def test_cutoff_is_strict_even_exactly_at_sealed_availability(repo):
    write(repo)
    first=rows(repo,archive.OBSERVATIONS)[0]
    with repo.engine.connect() as conn:
        assert archive.load_article_as_of(conn,'eodhd:one',first['available_at'].replace(tzinfo=timezone.utc)) is None
        assert archive.load_article_as_of(conn,'eodhd:one',
            (first['available_at']+timedelta(microseconds=1)).replace(tzinfo=timezone.utc)) is not None


def test_duplicate_in_same_page_is_not_an_extra_version_or_state_change(repo):
    repo.persist_news_page([article(),article()],[mapping(),mapping()])
    assert count(repo,archive.RAW_VERSIONS)==count(repo,archive.MAP_VERSIONS)==1
    assert count(repo,archive.OBSERVATIONS)==2
    assert len(rows(repo,archive.MAP_VERSIONS)[0]['mapping_rows'])==1


def test_conflicting_duplicate_in_same_page_is_not_silently_assigned_a_mapping(repo):
    with pytest.raises(ValueError,match='Conflicting duplicate'):
        repo.persist_news_page([article('A'),article('B')],[mapping(),mapping()])
    assert count(repo,repo._table('news_raw'))==count(repo,archive.RAW_VERSIONS)==0


def test_refresh_of_legacy_rows_is_not_presented_as_a_provider_collection(repo):
    # Simulate current rows existing before the deployment, without backdating any archive.
    with repo.engine.begin() as conn:
        repo._upsert('news_raw',[article()],{'article_id'},connection=conn)
        repo._upsert('news_ticker_map',[mapping()],{'article_id','symbol'},connection=conn)
    repo.upsert_news_ticker_map([dict(article_id='eodhd:one',symbol='TEST',relevance_score=0)])
    with repo.engine.connect() as conn:
        assert archive.load_article_as_of(conn,'eodhd:one',datetime(2026,10,16,tzinfo=timezone.utc)) is None
    repo.upsert_news_raw([article()])
    with repo.engine.connect() as conn:
        value=archive.load_article_as_of(conn,'eodhd:one',datetime(2026,10,16,tzinfo=timezone.utc))
    assert value['observation_origin']=='PROVIDER_COLLECTION'
    assert value['observed_at']>rows(repo,archive.OBSERVATIONS)[0]['observed_at']
    assert count(repo,archive.RAW_VERSIONS)==1


def test_out_of_order_sealing_cannot_reverse_transactional_version_order(repo):
    instant=datetime(2026,10,14)
    with repo.engine.begin() as conn:
        a,_=archive._insert_version(conn,archive.RAW_VERSIONS,archive.raw_snapshot(article('A'),'eodhd:one',instant))
        archive._observe(conn,'first','eodhd:one','article','PROVIDER_COLLECTION',instant,raw_id=a)
    with repo.engine.begin() as conn:
        b,_=archive._insert_version(conn,archive.RAW_VERSIONS,archive.raw_snapshot(article('B'),'eodhd:one',instant))
        archive._observe(conn,'second','eodhd:one','article','PROVIDER_COLLECTION',instant,raw_id=b)
    archive.seal_observations(repo.engine,'second',1)
    archive.seal_observations(repo.engine,'first',1)
    with repo.engine.connect() as conn:
        actual=archive.load_article_as_of(conn,'eodhd:one',datetime(2026,10,16,tzinfo=timezone.utc))
    assert actual['content']=='B'


def test_migration_is_scoped_and_never_performs_an_unrelated_upgrade(monkeypatch):
    import importlib.util
    from pathlib import Path
    path=Path('alembic/versions/0104_news_versions.py')
    spec=importlib.util.spec_from_file_location('migration_news_archive_test',path)
    migration=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    statements=[]
    monkeypatch.setattr(migration.context,'is_offline_mode',lambda:True)
    monkeypatch.setattr(migration.op,'execute',lambda statement:statements.append(str(statement)))
    migration.upgrade()
    assert len(statements)==3
    for statement in statements:
        assert 'CREATE TABLE IF NOT EXISTS news_' in statement
        assert 'ALTER TABLE' not in statement and 'DROP TABLE' not in statement
    assert migration.down_revision=='0103_oatr_max_returns'
    with pytest.raises(RuntimeError,match='retained'):
        migration.downgrade()


def test_migration_refuses_fr_database_before_any_ddl(monkeypatch):
    import importlib.util
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('migration_news_wrong_market',Path('alembic/versions/0104_news_versions.py'))
    migration=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    class Result:
        def scalar_one(self):
            return 'alpha_trade_fr'
    class Connection:
        def execute(self,statement):
            return Result()
    monkeypatch.setattr(migration.context,'is_offline_mode',lambda:False)
    monkeypatch.setattr(migration.op,'get_bind',lambda:Connection())
    with pytest.raises(RuntimeError,match='US alpha_trade'):
        migration.upgrade()
