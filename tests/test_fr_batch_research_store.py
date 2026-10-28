import csv
from contextlib import contextmanager
from datetime import date, datetime
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import (Boolean, Column, Date, DateTime, ForeignKeyConstraint, Integer,
                        MetaData, Table, Text, create_engine, event, text)

from service.fr import batch_research_store as store
from service.fr import operational_batch_15a as runner
from service.fr.event_data_qualification_11b import POSITION, PUBLICATION, END, HOLDER, ISIN

IDS = {'FR0000120321': 'OR.PA'}


def write(path, data, hashed=False):
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True).encode()
    if hashed:
        path = path.parent/(store.sha(raw)+'.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


@pytest.fixture
def operations(tmp_path, monkeypatch):
    root = tmp_path/'operations'
    write(root/'calendar/2026-10-06.json', dict(market_code='FR_EQ', observed_at='2026-10-06T08:00:00Z',
        sessions=[dict(session_date='2026-10-06',status='open',open_at_utc='2026-10-06T07:00:00Z',
                       close_at_utc='2026-10-06T15:30:00Z',source='library:XPAR')]))
    state = dict(market_code='FR_EQ', canonical_go=False, base_sha256='base', last_observed_at='2026-10-06T08:00:00Z',
        symbols=[dict(isin='FR0000120321', market_reference=[dict(mic='XPAR', versions=[dict(
            asof_from='2018-01-01', asof_to=None, name="L'Oréal", currency='EUR', event='Full')])])])
    write(root/'fr_security_master_sync/checkpoint.json', state)
    write(root/'fr_security_master_sync/versions/placeholder.json', state, True)
    corp = write(root/'fr_corporate_actions_sync/raw/placeholder.json', dict(symbol='OR.PA',kind='div',
        window=['2026-10-01','2026-10-06'],rows=[dict(date='2026-10-05',value='1.23456789')]), True)
    write(root/'fr_corporate_actions_sync/observations/receipt.json',
        dict(raw_sha256=corp.stem,observed_at='2026-10-06T07:00:00Z',available_at='2026-10-06T07:00:01Z'))
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer,fieldnames=[POSITION,PUBLICATION,END,HOLDER,ISIN,'Ratio'],delimiter=';')
    writer.writeheader()
    writer.writerow({POSITION:'2026-10-04',PUBLICATION:'2026-10-05',END:'',HOLDER:'Example Fund',
                     ISIN:'FR0000120321','Ratio':'0,7'})
    write(root/'fr_amf_short_sync/raw/placeholder.json', dict(csv_utf8=buffer.getvalue()), True)
    write(root/'fr_dila_disclosures_sync/raw/placeholder.json', dict(query_window=['2026-10-01','2026-10-06'],
        records=[dict(identificationsociete_iso_cd_isi='FR0000120321',uin_idt_uin='123',
            uin_dat_amf='2026-10-05T08:00:00Z',informationdeposee_inf_tit_inf='Résultats',
            fichierdecontenu_inf_fic_nom='report.pdf')]), True)
    monkeypatch.setattr(store, 'identity_map', lambda: IDS)
    return root


@pytest.fixture
def engine(operations, monkeypatch):
    examples = {}
    for batch in store.PROVIDERS:
        folder = operations/store.FOLDERS[batch] if batch in store.FOLDERS else operations/'runs'/batch
        receipts = store.observation_index(folder)
        for path in store.files_for(batch, operations):
            doc, receipt, table, rows = store.prepare(path,batch,operations,IDS,receipts)
            examples[store.DOCUMENTS], examples[store.FILES] = doc,receipt
            if rows:
                examples[table] = rows[0]
    e = create_engine('sqlite:///:memory:')
    @event.listens_for(e,'connect')
    def fks(c, record):
        c.execute('PRAGMA foreign_keys=ON')
    metadata = MetaData()
    for name, sample in examples.items():
        keys = ('document_id',) if name==store.DOCUMENTS else (
            ('batch_name','path_sha256','document_id') if name==store.FILES else ('document_id','record_sha256'))
        columns = []
        for key,value in sample.items():
            kind = (DateTime if isinstance(value,datetime) else Date if isinstance(value,date)
                    else Boolean if isinstance(value,bool) else Integer if isinstance(value,int) else Text)
            columns.append(Column(key,kind,primary_key=key in keys))
        if name!=store.DOCUMENTS:
            columns.append(ForeignKeyConstraint(['document_id'],[store.DOCUMENTS+'.document_id']))
        Table(name,metadata,*columns)
    metadata.create_all(e)
    monkeypatch.setattr(store, 'check_schema', lambda engine: None)
    yield e
    e.dispose()


def test_all_families_import_exact_values_and_rerun_adds_nothing(engine,operations):
    for batch in store.PROVIDERS:
        store.publish_batch(engine,batch,operations=operations)
    with engine.connect() as conn:
        assert conn.execute(text('SELECT COUNT(*) FROM fr_calendar_sessions_research')).scalar_one()==1
        # Checkpoint and immutable version have the same content: one record, two file links.
        assert conn.execute(text('SELECT COUNT(*) FROM fr_reference_versions_research')).scalar_one()==1
        assert conn.execute(text('SELECT cash_amount FROM fr_corporate_actions_research')).scalar_one()=='1.23456789'
        assert conn.execute(text('SELECT ratio_percent FROM fr_amf_positions_research')).scalar_one()=='0.7'
        assert conn.execute(text('SELECT title FROM fr_dila_disclosures_research')).scalar_one()=='Résultats'
        docs=conn.execute(text('SELECT * FROM fr_batch_research_documents')).mappings().all()
        for d in docs:
            assert not d['canonical'] and not d['ml_eligible'] and not d['historical_pit_qualified']
            assert store.sha(d['document_json'].encode())==d['content_sha256']
        corp=next(d for d in docs if d['batch_name']=='fr_corporate_actions_sync' and d['record_count'])
        assert str(corp['source_available_at']).startswith('2026-10-06 07:00:01')
        assert corp['sql_available_at']!=corp['source_available_at']
        amf=next(d for d in docs if d['batch_name']=='fr_amf_short_sync')
        assert amf['source_available_at'] is None  # No receipt, never use mtime.
    for batch in store.PROVIDERS:
        report=store.publish_batch(engine,batch,operations=operations)
        assert report['documents_inserted']==report['records_inserted']==report['file_versions_inserted']==0


def test_known_corrupt_raw_is_still_rejected_on_repeat(engine,operations):
    store.publish_batch(engine,'fr_corporate_actions_sync',operations=operations)
    path=next((operations/'fr_corporate_actions_sync/raw').glob('*.json'))
    path.write_text('{}')
    with pytest.raises(ValueError,match='corrompue'):
        store.publish_batch(engine,'fr_corporate_actions_sync',operations=operations)


def test_rollback_prevents_partial_document_success(engine,operations,monkeypatch):
    original=store.insert
    def fail(conn,table,rows):
        if table==store.TYPED[0]:
            raise RuntimeError('SQL unavailable')
        original(conn,table,rows)
    monkeypatch.setattr(store,'insert',fail)
    with pytest.raises(RuntimeError):
        store.publish_batch(engine,'fr_calendar_snapshot',operations=operations)
    with engine.connect() as conn:
        assert conn.execute(text('SELECT COUNT(*) FROM fr_batch_research_documents')).scalar_one()==0


def test_new_version_is_preserved_not_overwritten(engine,operations):
    store.publish_batch(engine,'fr_calendar_snapshot',operations=operations)
    path=operations/'calendar/2026-10-06.json'
    data=json.loads(path.read_text())
    data['sessions'][0]['close_at_utc']='2026-10-06T12:00:00Z'
    write(path,data)
    assert store.publish_batch(engine,'fr_calendar_snapshot',operations=operations)['records_inserted']==1
    with engine.connect() as conn:
        assert conn.execute(text('SELECT COUNT(*) FROM fr_calendar_sessions_research')).scalar_one()==2


def test_dry_publication_has_no_database_dependency(operations):
    report=store.publish_batch(None,'fr_calendar_snapshot',operations=operations,apply=False)
    assert report['records_verified']==1 and report['documents_inserted']==0


def test_wrong_database_fails_before_connect():
    class Engine:
        url=SimpleNamespace(database='alpha_trade')
        def connect(self):
            pytest.fail('US SQL forbidden')
    with pytest.raises(ValueError,match='alpha_trade_fr'):
        store.check_schema(Engine())


def test_consensus_raw_hash_is_logical_not_file_bytes(operations):
    folder=operations/'fr_consensus_snapshot/eodhd/raw'
    path=write(folder/('a'*64+'.json'),dict(trends=[]))
    result=store.prepare(path,'fr_consensus_snapshot',operations,IDS,{})
    assert result[0]['content_sha256']==store.sha(path.read_bytes())


def test_future_dila_and_invalid_corporate_remain_unqualified():
    table,rows=store.normalized('fr_dila_disclosures_sync','fr_dila_disclosures_sync/raw/file.json',
        dict(query_window=['2026-10-01','2026-10-06'],records=[dict(
            identificationsociete_iso_cd_isi='FR0000120321',uin_idt_uin='x',uin_dat_amf='2026-10-07T08:00:00Z')]),IDS)
    assert rows[0]['validation_status']=='INVALID'
    _,rows=store.normalized('fr_corporate_actions_sync','fr_corporate_actions_sync/raw/file.json',
        dict(symbol='OR.PA',kind='div',window=['2026-10-01','2026-10-06'],rows=[dict(date='2026-10-08',value='2')]),IDS)
    assert rows[0]['validation_status']=='INVALID'


def test_future_calendar_schedule_is_not_a_future_observation():
    _, rows = store.normalized('fr_calendar_snapshot', 'calendar/next.json', dict(market_code='FR_EQ',
        sessions=[dict(session_date='2090-01-03', status='open', open_at_utc='2090-01-03T08:00:00Z',
                       close_at_utc='2090-01-03T16:30:00Z',source='library:XPAR')]), IDS)
    assert rows[0]['open_at_utc'] == datetime(2090,1,3,8)
    assert rows[0]['close_at_utc'] == datetime(2090,1,3,16,30)
    assert store.clock('2090-01-03T08:00:00Z') is None


def test_runner_fails_before_collection_if_sql_unavailable(tmp_path,monkeypatch):
    monkeypatch.setattr(runner,'OPS',tmp_path/'ops')
    monkeypatch.setattr(runner,'load_section',lambda *a: dict(enabled=True,status='ACTIVE',archive_research_sql=True))
    monkeypatch.setattr(store,'engine_fr',lambda: (_ for _ in ()).throw(RuntimeError('SQL unavailable')))
    monkeypatch.setattr(runner,'_handle',lambda *a,**kw: pytest.fail('Provider forbidden'))
    result=runner.run('fr_calendar_snapshot')
    assert result['status']=='FAILED' and 'SQL unavailable' in result['error_message']


def test_runner_partial_collection_is_imported_but_still_failed(tmp_path,monkeypatch):
    from service.fr import collection_storage as primary
    from fr_sql_primary_helpers import sqlite_primary
    engine=sqlite_primary(tmp_path/'runner.sqlite')
    monkeypatch.setattr(runner,'load_section',lambda *a:dict(enabled=True,status='ACTIVE'))
    monkeypatch.setattr(store,'engine_fr',lambda:engine)
    monkeypatch.setattr(primary.Repository,'check_schema',lambda self:None)
    monkeypatch.setattr(store,'publish_batch',lambda *a,**kw:pytest.fail('No file mirror in operational runs'))
    def fail(name,cfg,result,**kw):
        result['persisted_count']=1
        raise RuntimeError('Source partial')
    monkeypatch.setattr(runner,'_handle',fail)
    result=runner.run('fr_calendar_snapshot')
    assert result['status']=='FAILED' and result['persisted_count']==1
    assert runner.latest_run('fr_calendar_snapshot')['status']=='FAILED'
    assert 'research_sql_archive' not in result


def test_disabled_batch_stays_disabled_without_sql_or_provider(tmp_path,monkeypatch):
    monkeypatch.setattr(runner,'OPS',tmp_path/'ops')
    monkeypatch.setattr(runner,'load_section',lambda *a: dict(enabled=False,status='BLOCKED_INPI_RETENTION',archive_research_sql=True))
    monkeypatch.setattr(store,'engine_fr',lambda:pytest.fail('Blocked collector SQL forbidden'))
    monkeypatch.setattr(runner,'_handle',lambda *a,**kw:pytest.fail('Blocked provider forbidden'))
    assert runner.run('fr_fundamentals_sync')['status']=='SKIPPED_DISABLED_OR_UNQUALIFIED'


def test_mysql_publication_releases_batch_lock_even_on_failure(monkeypatch):
    seen=[]
    class Gate:
        def execute(self,sql,args):
            seen.append(str(sql))
            return SimpleNamespace(scalar_one=lambda:1)
    class Engine:
        dialect=SimpleNamespace(name='mysql')
        @contextmanager
        def connect(self):
            yield Gate()
    monkeypatch.setattr(store,'check_schema',lambda e:None)
    monkeypatch.setattr(store,'_publish_batch',lambda *a,**kw: (_ for _ in ()).throw(RuntimeError('failure')))
    with pytest.raises(RuntimeError,match='failure'):
        store.publish_batch(Engine(),'fr_amf_short_sync')
    assert len(seen)==2 and 'GET_LOCK' in seen[0] and 'RELEASE_LOCK' in seen[1]


def test_runner_receipt_sql_failure_cannot_leave_local_success(tmp_path,monkeypatch):
    from contextlib import nullcontext
    from service.fr import collection_storage as primary
    monkeypatch.setattr(runner,'OPS',tmp_path/'ops')
    monkeypatch.setattr(runner,'load_section',lambda *a:dict(enabled=True,status='ACTIVE'))
    monkeypatch.setattr(store,'engine_fr',lambda:SimpleNamespace(dispose=lambda:None))
    monkeypatch.setattr(runner,'_handle',lambda *a,**kw:None)
    class Repository:
        def __init__(self,engine): self.calls=0
        def check_schema(self): pass
        def lock(self,name):return nullcontext()
        def save_run(self,*args):
            self.calls+=1
            if self.calls==2: raise RuntimeError('Receipt SQL failed')
    monkeypatch.setattr(primary,'Repository',Repository)
    result=runner.run('fr_calendar_snapshot')
    assert result['status']=='FAILED' and 'Receipt SQL failed' in result['error_message']
    assert not (tmp_path/'ops').exists()
