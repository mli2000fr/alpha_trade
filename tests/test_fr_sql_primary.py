from datetime import UTC,datetime,date
from pathlib import Path
from contextlib import nullcontext
from types import SimpleNamespace
import gzip
import json

import pytest
from sqlalchemy import text

from service.fr import collection_storage as sql,operational_batch_15a as runner
from fr_sql_primary_helpers import sqlite_primary


@pytest.fixture
def repository(tmp_path,monkeypatch):
    engine=sqlite_primary(tmp_path/'primary.sqlite')
    repo=sql.Repository(engine,root=tmp_path/'fr')
    with sql.use(repo):
        sql.write_bytes(repo.root/'sprint6c_reference/identities.jsonl.gz',gzip.compress(
            b'{"isin":"FR0000120321","provider_symbol":"OR.PA","identity_state":"VERIFIED_RESEARCH"}\n'))
    monkeypatch.setattr(sql.Repository,'check_schema',lambda self:None)
    monkeypatch.setattr('service.fr.batch_research_store.engine_fr',lambda:engine)
    yield repo
    engine.dispose()


def test_roundtrip_versions_and_binary_chunks_without_creating_any_data_file(repository):
    repo=repository;root=repo.root/'operations/fr_options_open_interest_sync'
    with sql.use(repo):
        raw=b'x'*2_500_001
        sql.write_bytes(root/'raw'/sql.sha(raw),raw)
        assert sql.read_bytes(root/'raw'/sql.sha(raw))==raw
        sql.write_json(root/'progress.json',{'status':'RUNNING'})
        sql.write_json(root/'progress.json',{'status':'PARTIAL'})
        sql.write_json(root/'progress.json',{'status':'RUNNING'})
        assert json.loads(sql.read_text(root/'progress.json'))['status']=='RUNNING'
        assert sql.paths(root)==[root/'progress.json']
    assert not repo.root.exists()
    with repo.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM fr_collection_object_parts WHERE content_sha256=:hash'),
                         {'hash':sql.sha(raw)}).scalar()==3
        assert c.execute(text("SELECT count(*) FROM fr_collection_versions WHERE resource_key LIKE '%progress.json'")).scalar()==2


def test_missing_sql_resource_never_reads_existing_file(repository):
    path=repository.root/'operations/fr_amf_short_sync/latest.json'
    path.parent.mkdir(parents=True);path.write_text('{"not_sql":true}')
    with sql.use(repository):
        assert not sql.exists(path)
        with pytest.raises(FileNotFoundError,match='SQL'): sql.read_bytes(path)


def test_corrupted_blob_is_blocked(repository):
    path=repository.root/'operations/fr_options_open_interest_sync/raw/hash'
    with sql.use(repository): sql.write_bytes(path,b'real')
    with repository.engine.begin() as c:
        c.execute(text('UPDATE fr_collection_object_parts SET body=:body WHERE content_sha256=:hash'),
                  {'body':b'fake','hash':sql.sha(b'real')})
    with sql.use(repository),pytest.raises(ValueError,match='corrompu'): sql.read_bytes(path)


def test_typed_calendar_is_transactionally_published(repository):
    path=repository.root/'operations/calendar/today.json'
    with sql.use(repository):
        sql.write_json(path,{'market_code':'FR_EQ','observed_at':datetime.now(UTC).isoformat(),
            'sessions':[{'session_date':'2027-01-04','status':'open','open_at_utc':'2027-01-04T08:00:00Z',
                         'close_at_utc':'2027-01-04T16:30:00Z','source':'library:XPAR'}]})
    with repository.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM fr_calendar_sessions_research')).scalar()==1
        assert c.execute(text('SELECT count(*) FROM fr_batch_research_file_versions')).scalar()==0


def test_invalid_parsing_retains_raw_without_advancing_current_state(repository):
    path=repository.root/'operations/calendar/current.json'
    with sql.use(repository):
        sql.write_json(path,{'market_code':'FR_EQ','sessions':[]})
        with pytest.raises(ValueError): sql.write_json(path,{'market_code':'US_EQ','sessions':[]})
        assert json.loads(sql.read_text(path))['market_code']=='FR_EQ'
    with repository.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM fr_collection_versions WHERE available_at IS NULL')).scalar()==1


def test_daily_bars_recover_checkpoint_and_prepare_staging_from_sql(repository,monkeypatch):
    from service.fr import eodhd_daily_15b as daily,publish_daily_bars_staging as stage
    monkeypatch.setenv('EODHD_API_TOKEN','test')
    monkeypatch.setattr(daily,'symbol_windows',lambda *a,**kw:{'OR.PA':(date(2026,10,5),date(2026,10,5))})
    calls=[]
    monkeypatch.setattr(daily,'_fetch',lambda *a,**kw: calls.append(1) or [dict(date='2026-10-05',open=10,high=12,low=9,close=11,adjusted_close=11,volume=100)])
    root=repository.root/'operations/eodhd_daily';ids=repository.root/'sprint6c_reference/identities.jsonl.gz'
    def result():return dict(received_count=0,persisted_count=0,failed_count=0,warning_count=0)
    with sql.use(repository):
        a=result();daily.collect({'lookback_days':1},a,root=root,identities=ids,today=date(2026,10,5))
        b=result();daily.collect({'lookback_days':1},b,root=root,identities=ids,today=date(2026,10,5),resume=True)
        payloads,errors,_=stage.prepare(root,['OR.PA'],date(2026,10,5),date(2026,10,5))
    assert len(calls)==1 and b['resumed_symbols']==1 and len(payloads)==1 and not errors
    assert not repository.root.exists()


def test_corporate_actions_resume_from_sql(repository,monkeypatch):
    from service.fr import operational_collectors_15c as actions
    monkeypatch.setenv('EODHD_API_TOKEN','test')
    monkeypatch.setattr(actions,'symbols_from_identities',lambda _:['OR.PA'])
    calls=[]
    monkeypatch.setattr(actions,'_fetch',lambda *a,**kw:calls.append(1) or [])
    root=repository.root/'operations/fr_corporate_actions_sync';ids=repository.root/'sprint6c_reference/identities.jsonl.gz'
    def result():return dict(received_count=0,persisted_count=0,failed_count=0,warning_count=0)
    with sql.use(repository):
        actions.corporate({},result(),root=root,identities=ids,today=date(2026,10,5))
        b=result();actions.corporate({},b,root=root,identities=ids,today=date(2026,10,5),resume=True)
    assert len(calls)==2 and b['resumed_count']==2 and not repository.root.exists()


def test_oi_collector_writes_no_market_or_progress_files(repository,monkeypatch):
    from service.fr import public_options_oi as oi
    from test_fr_public_options_oi import PRODUCT,MONTH,directory,chain
    monkeypatch.setattr(oi,'check_schema',lambda _:None)
    monkeypatch.setattr(oi,'reference_scope',lambda _:(1,{'OR.PA':({'isin':PRODUCT['underlying_isin']},set())},[]))
    monkeypatch.setattr(oi,'verified_session',lambda:nullcontext(SimpleNamespace(headers={})))
    def fetch(method,url,params):
        if url.endswith('robots.txt'): return b'User-agent: *\nAllow: /',200
        if '/list' in url:return directory(),200
        if '/getUnderlying/' in url:return b'<tr><td>ISIN</td><td>FR0000120321</td></tr>',200
        if '/getPricesOptionsForm/' in url:return f'<select id="maturityDates"><option value="{MONTH}"></option></select>'.encode(),200
        if '/submitOptionsForm/' in url:return b'<div id="price_option_details_0"></div>',200
        return chain(),200
    with sql.use(repository):
        result={}
        oi.collect({},result,root=repository.root/'operations'/oi.BATCH,identities=Path('unused'),
                   engine=repository.engine,fetcher=fetch,sleep=lambda _:None)
    assert result['persisted_count']==2 and result['data_status']=='PARTIAL' and not repository.root.exists()


def test_runner_retains_partial_counts_in_sql_only(repository,monkeypatch):
    monkeypatch.setattr(runner,'load_section',lambda *a:dict(enabled=True,status='ACTIVE',provider='test'))
    def fail(name,cfg,result,**kw):
        result.update(requested_count=5,received_count=3,persisted_count=7)
        raise ValueError('Partial source')
    monkeypatch.setattr(runner,'_handle',fail)
    result=runner.run('fr_calendar_snapshot')
    assert result['status']=='FAILED' and result['persisted_count']==7
    last=runner.latest_run('fr_calendar_snapshot')
    assert last['status']=='FAILED' and last['received_count']==3


def test_runner_fails_before_provider_if_sql_down(monkeypatch):
    monkeypatch.setattr(runner,'load_section',lambda *a:dict(enabled=True,status='ACTIVE'))
    monkeypatch.setattr('service.fr.batch_research_store.engine_fr',lambda:(_ for _ in ()).throw(RuntimeError('SQL unavailable')))
    monkeypatch.setattr(runner,'_handle',lambda *a,**kw:pytest.fail('Provider must not run'))
    result=runner.run('fr_calendar_snapshot')
    assert result['status']=='FAILED' and 'SQL unavailable' in result['error_message']


def test_consensus_daily_resume_is_sql_only(repository,monkeypatch):
    from service.fr import eodhd_consensus_daily as consensus
    from test_fr_eodhd_consensus_daily import sqlite_engine,payload
    dedicated=sqlite_engine()
    monkeypatch.setattr(consensus,'check_schema',lambda _:None)
    monkeypatch.setattr(consensus,'reference_scope',lambda _:(1,{'OR.PA':(
        {'provider_symbol':'OR.PA','isin':'FR0000120321'},set())},[]))
    monkeypatch.setattr(consensus,'verified_session',lambda:nullcontext(object()))
    calls=[]
    def result():return dict(received_count=0,persisted_count=0,failed_count=0,warning_count=0)
    root=repository.root/'operations/fr_consensus_snapshot'
    ids=repository.root/'sprint6c_reference/identities.jsonl.gz'
    with sql.use(repository):
        a=result();consensus.collect({'provider':'eodhd','request_interval_seconds':0},a,root=root,
            identities=ids,engine=dedicated,fetcher=lambda *a:calls.append(1) or payload(),sleep=lambda _:None)
        b=result();consensus.collect({'provider':'eodhd','request_interval_seconds':0},b,root=root,
            identities=ids,engine=dedicated,fetcher=lambda *a:pytest.fail('Completed symbol must not be fetched'))
    assert len(calls)==1 and b['skipped_completed']==1 and not repository.root.exists()
    dedicated.dispose()


def test_mifir_binary_sources_and_snapshot_replay_from_sql(repository,monkeypatch):
    from service.fr import mifir_options_daily as daily,mifir_options_store as store
    from test_fr_mifir_options_daily import fake_fetch
    monkeypatch.setattr(daily,'reference_scope',lambda _:(1,{'OR.PA':({'isin':'FR0000120321'},set())},[]))
    monkeypatch.setattr(store,'check_schema',lambda _:None)
    monkeypatch.setattr(daily.source,'now',lambda:'2026-10-06T07:01:00+00:00')
    root=repository.root/'operations/fr_options_mifir_trade_sync'
    with sql.use(repository):
        result=dict(persisted_count=0,failed_count=0)
        daily.collect({},result,root=root,identities=Path('unused'),engine=repository.engine,
            clock=store.source.instant('2026-10-06T08:00:00Z'),fetch=fake_fetch([]))
        snapshot=sql.paths(root/'snapshots')[0]
        parsed=store.load_snapshot(snapshot,root)
    assert parsed['data']['analysis']['coverage']['OR.PA']['accepted_trade_rows']==1
    assert result['sql_snapshots']==1 and not repository.root.exists()


def test_legacy_sql_document_read_does_not_need_its_old_file(repository):
    from service.fr import batch_research_store as old
    raw=b'{"checkpoint":true}';batch='fr_daily_bars_sync'
    digest=sql.sha(raw);doc=old.document_key(batch,digest)
    with repository.engine.begin() as c:
        old.insert(c,old.DOCUMENTS,[dict(document_id=doc,batch_name=batch,market_code='FR_EQ',provider='EODHD',
            parser_version=old.PARSER,content_sha256=digest,source_observed_at=None,source_available_at=None,
            sql_available_at=datetime.now(UTC).replace(tzinfo=None),document_json=raw.decode(),record_count=0,
            ml_eligible=False,canonical=False,historical_pit_qualified=False)])
        old.insert(c,old.FILES,[dict(batch_name=batch,path_sha256='x'*64,document_id=doc,
            relative_path='eodhd_daily/windows/test.json',archived_role='windows',
            file_modified_at=datetime.now(UTC).replace(tzinfo=None),imported_at=datetime.now(UTC).replace(tzinfo=None))])
    with sql.use(repository):
        assert sql.read_bytes(repository.root/'operations/eodhd_daily/windows/test.json')==raw
    assert not repository.root.exists()
