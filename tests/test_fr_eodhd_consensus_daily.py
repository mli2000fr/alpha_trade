from datetime import datetime, timezone
import gzip
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, Integer, MetaData,
    String, Table, Text, UniqueConstraint, create_engine, text)

from service.fr import eodhd_consensus_daily as mod


def payload(value='10'):
    return dict(trends=[[dict(code='OR.PA',date='2026-12-31',period='0y',
        earningsEstimateAvg=value,earningsEstimateNumberOfAnalysts='12',epsTrend7daysAgo='9.5')]])


def scope(tmp_path):
    path=tmp_path/'ids.gz'
    row=dict(provider_symbol='OR.PA',identity_state='VERIFIED_RESEARCH',provider_status_current='active',
        isin='FR0000120321',market_reference=[dict(mic='XPAR',versions=[dict(name="L'OREAL",asof_to=None)])])
    with gzip.open(path,'wt',encoding='utf-8') as stream:
        stream.write(json.dumps(row)+'\n')
    return path,row


def result():
    return dict(requested_count=0,received_count=0,persisted_count=0,failed_count=0,warning_count=0)


def sqlite_engine():
    engine=create_engine('sqlite:///:memory:')
    meta=MetaData()
    Table(mod.RAW_TABLE,meta,Column('id',Integer,primary_key=True),Column('provider',String),
        Column('symbol',String),Column('observation_day',Date),Column('run_id',String),
        Column('observed_at',DateTime),Column('available_at',DateTime),Column('raw_hash',String),
        Column('payload_json',Text),Column('parse_status',String),Column('normalized_rows',Integer,server_default='0'))
    example=mod.parse(payload(),'OR.PA',dict(provider_symbol='OR.PA',isin='FR0000120321'),
        datetime.now(timezone.utc),'fixture','hash')[0]
    example['raw_payload_id']=1
    columns=[]
    for key,value in example.items():
        typ=(DateTime if key in ('observed_at','available_at') else Date if key in ('snapshot_date','fiscal_period_end')
            else Boolean if key.endswith('_qualified') else Integer if key=='raw_payload_id' or 'count' in key
            else Float if key in mod.FIELDS else Text)
        columns.append(Column(key,typ,nullable=True))
    Table(mod.TABLE,meta,Column('id',Integer,primary_key=True),*columns,
        UniqueConstraint('provider','symbol','snapshot_date','fiscal_period_end','horizon_raw'))
    meta.create_all(engine)
    return engine


def test_parser_shared_values_but_fr_identity_paris_date_and_unknown_currency():
    observed=datetime(2026,10,15,23,30,tzinfo=timezone.utc)
    row=mod.parse(payload(),'OR.PA',dict(provider_symbol='OR.PA',isin='FR0000120321'),observed,'test','hash')[0]
    assert str(row['snapshot_date'])=='2026-10-16'
    assert row['eps_avg']==10 and row['eps_analyst_count']==12
    assert row['eps_7d_ago']==9.5 and row['revisions_down_7d'] is None
    assert row['currency'] is None and row['market_code']=='FR_EQ' and row['available_at'] is None
    assert not row['fiscal_identity_qualified'] and not row['historical_pit_qualified']


def test_unexpected_us_symbol_or_issuer_never_normalized():
    with pytest.raises(ValueError):
        mod.parse(payload(),'OR.PA',dict(provider_symbol='SU.PA',isin='FR0000121972'),datetime.now(timezone.utc),'test','hash')
    data=payload()
    data['trends'][0][0]['code']='OR.US'
    with pytest.raises(ValueError,match='Unexpected consensus symbol'):
        mod.parse(data,'OR.PA',dict(provider_symbol='OR.PA',isin='FR0000120321'),datetime.now(timezone.utc),'test','hash')


def test_wrong_database_fails_before_connect_or_network():
    class Engine:
        url=SimpleNamespace(database='alpha_trade')
        def connect(self):
            pytest.fail('US connection forbidden')
    with pytest.raises(ValueError,match='alpha_trade_fr'):
        mod.check_schema(Engine())


def test_first_daily_observation_wins_and_raw_payload_remains(tmp_path):
    engine=sqlite_engine()
    _,ref=scope(tmp_path)
    now=datetime.now(timezone.utc)
    day=now.astimezone(mod.ZoneInfo('Europe/Paris')).date().isoformat()
    first=mod.persist(engine,tmp_path/'out','OR.PA',ref,'hash',payload('10'),now,'first',day)
    second=mod.persist(engine,tmp_path/'out','OR.PA',ref,'hash',payload('20'),now,'second',day)
    assert first['persisted']==1 and second['persisted']==0
    with engine.connect() as conn:
        assert conn.execute(text(f'SELECT COUNT(*) FROM {mod.RAW_TABLE}')).scalar_one()==2
        assert conn.execute(text(f'SELECT eps_avg FROM {mod.TABLE}')).scalar_one()==10
        assert conn.execute(text(f'SELECT COUNT(*) FROM {mod.TABLE} WHERE available_at IS NULL')).scalar_one()==0
    assert mod.completed(engine,'OR.PA',day)['status']=='COMPLETED'
    engine.dispose()


def test_entire_bad_schema_response_survives_and_remains_unsealed(tmp_path):
    engine=sqlite_engine()
    _,ref=scope(tmp_path)
    now=datetime.now(timezone.utc)
    with pytest.raises(ValueError):
        mod.persist(engine,tmp_path/'out','OR.PA',ref,'hash',{'unexpected':'schema'},now,'bad','2026-10-15')
    with engine.connect() as conn:
        raw=conn.execute(text(f'SELECT payload_json,available_at,parse_status FROM {mod.RAW_TABLE}')).one()
    assert json.loads(raw[0])=={'unexpected':'schema'} and raw[1] is None and raw[2]=='RECEIVED'
    engine.dispose()


def test_empty_consensus_is_normal_and_daily_resume_makes_no_network(tmp_path,monkeypatch):
    ids,_=scope(tmp_path)
    engine=sqlite_engine()
    monkeypatch.setattr(mod,'check_schema',lambda e:None)
    cfg=dict(provider='eodhd',request_interval_seconds=0)
    a=result()
    mod.collect(cfg,a,root=tmp_path/'out',identities=ids,engine=engine,
        fetcher=lambda s,session:{'trends':[]},sleep=lambda n:None)
    assert a['empty_count']==1 and a['failed_count']==0 and a['persisted_count']==0
    assert a['raw_payloads_persisted']==1 and a['coverage_complete']
    b=result()
    mod.collect(cfg,b,root=tmp_path/'out',identities=ids,engine=engine,
        fetcher=lambda *a:pytest.fail('duplicate API'),sleep=lambda n:None)
    assert b['skipped_completed']==1 and b['raw_payloads_persisted']==0
    engine.dispose()


def test_collect_counters_and_failure_are_not_silent(tmp_path,monkeypatch):
    ids,_=scope(tmp_path)
    engine=sqlite_engine()
    monkeypatch.setattr(mod,'check_schema',lambda e:None)
    cfg=dict(provider='eodhd',request_interval_seconds=0)
    a=result()
    def invalid(*args):
        raise RuntimeError('technical failure')
    with pytest.raises(RuntimeError,match='incomplet'):
        mod.collect(cfg,a,root=tmp_path/'out',identities=ids,engine=engine,fetcher=invalid,sleep=lambda n:None)
    assert a['requested_count']==a['failed_count']==a['pending_count']==1
    assert a['received_count']==a['persisted_count']==0
    assert a['errors'][0]['message']=='technical failure'
    engine.dispose()


def test_dry_run_has_no_database_or_file_side_effect(tmp_path,monkeypatch):
    ids,_=scope(tmp_path)
    monkeypatch.setattr(mod,'engine_fr',lambda:pytest.fail('dry-run DB'))
    a=result()
    mod.collect(dict(provider='eodhd'),a,root=tmp_path/'out',identities=ids,dry_run=True)
    assert a['requested_count']==1 and not (tmp_path/'out').exists()


def test_daily_budget_checkpoint_and_provider_separation(tmp_path,monkeypatch):
    ids,_=scope(tmp_path)
    engine=sqlite_engine()
    monkeypatch.setattr(mod,'check_schema',lambda e:None)
    cfg=dict(provider='eodhd',max_endpoint_calls_per_day=1,request_interval_seconds=0)
    a=result()
    with pytest.raises(RuntimeError):
        mod.collect(cfg,a,root=tmp_path/'out',identities=ids,engine=engine,
            fetcher=lambda *a:(_ for _ in ()).throw(RuntimeError('failed')),sleep=lambda n:None)
    b=result()
    with pytest.raises(RuntimeError,match='BUDGET'):
        mod.collect(cfg,b,root=tmp_path/'out',identities=ids,engine=engine,
            fetcher=lambda *a:pytest.fail('budget bypass'),sleep=lambda n:None)
    assert b['endpoint_calls_today']==1
    with pytest.raises(ValueError,match='Yahoo'):
        mod.collect(dict(provider='yahoo_finance_research'),result(),root=tmp_path/'out',identities=ids)
    engine.dispose()


def test_legacy_entrypoint_cannot_fall_back_to_yahoo():
    from service.fr.consensus_snapshot import collect
    with pytest.raises(RuntimeError,match='Yahoo FR bloqué'):
        collect(dict(provider='yahoo_finance_research'),result(),root=None,identities=None)


def test_eodhd_ihm_reader_ignores_yahoo_day_state(tmp_path,monkeypatch):
    from ihm.services import batch_management
    monkeypatch.setattr(batch_management,'PROJECT_ROOT',tmp_path)
    spec=SimpleNamespace(name='fr_consensus_snapshot',raw_config={'provider':'eodhd'})
    old=tmp_path/'artifacts/fr/operations/fr_consensus_snapshot/days'
    old.mkdir(parents=True)
    (old/'2026-10-15.json').write_text(json.dumps(dict(market_code='FR_EQ',day='2026-10-15',provider='yahoo')))
    assert batch_management.read_fr_consensus_state(spec) is None
    new=old.parent/'eodhd/days'
    new.mkdir(parents=True)
    (new/'2026-10-15.json').write_text(json.dumps(dict(market_code='FR_EQ',day='2026-10-15',provider='eodhd')))
    assert batch_management.read_fr_consensus_state(spec)['provider']=='eodhd'


def test_catalog_eodhd_enabled_on_explicit_user_request():
    from ihm.services.batch_management import load_batch_specs
    spec=next(s for s in load_batch_specs('batch_fr.yaml') if s.name=='fr_consensus_snapshot')
    assert spec.provider=='eodhd' and spec.status=='ACTIVE_RESEARCH' and spec.enabled and spec.runnable
    assert spec.run_days==('0','1','2','3','4','5','6') and spec.run_hours==('20',)
    assert any('alpha_trade_fr.stock_analyst_consensus_eodhd_history'==t for t in spec.tables)


def test_committed_rows_with_missing_receipt_recovered_without_refetch(tmp_path,monkeypatch):
    engine=sqlite_engine()
    _,ref=scope(tmp_path)
    now=datetime.now(timezone.utc)
    day=now.astimezone(mod.ZoneInfo('Europe/Paris')).date().isoformat()
    original=mod.seal
    monkeypatch.setattr(mod,'seal',lambda *a:(_ for _ in ()).throw(RuntimeError('receipt failed')))
    with pytest.raises(RuntimeError,match='receipt failed'):
        mod.persist(engine,tmp_path/'out','OR.PA',ref,'hash',payload(),now,'first',day)
    with engine.connect() as conn:
        assert conn.execute(text(f'SELECT available_at FROM {mod.TABLE}')).scalar_one() is None
    monkeypatch.setattr(mod,'seal',original)
    assert mod.completed(engine,'OR.PA',day)['status']=='COMPLETED'
    with engine.connect() as conn:
        assert conn.execute(text(f'SELECT available_at FROM {mod.TABLE}')).scalar_one() is not None
    engine.dispose()


def test_clock_backwards_never_seals_availability(tmp_path):
    from datetime import timedelta
    engine=sqlite_engine()
    now=datetime.now(timezone.utc)
    with engine.begin() as conn:
        conn.execute(text(f'INSERT INTO {mod.RAW_TABLE} '
            "(id,observed_at,parse_status) VALUES (1,:observed,'READY')"),dict(observed=now.replace(tzinfo=None)))
    with pytest.raises(ValueError,match='Horloge'):
        mod.seal(engine,1,now=now-timedelta(seconds=1))
    engine.dispose()


def test_numeric_counts_without_estimates_not_counted_as_consensus(tmp_path):
    engine=sqlite_engine()
    _,ref=scope(tmp_path)
    data=payload(None)
    del data['trends'][0][0]['epsTrend7daysAgo']
    now=datetime.now(timezone.utc)
    row=mod.persist(engine,tmp_path/'out','OR.PA',ref,'hash',data,now,'count-only',str(now.date()))
    assert row['status']=='NO_COVERAGE' and row['persisted']==1
    engine.dispose()


def test_invalid_selection_and_local_budget_do_not_use_another_market(tmp_path):
    ids,_=scope(tmp_path)
    with pytest.raises(ValueError,match='hors référentiel'):
        mod.collect(dict(provider='eodhd',selected_symbols=['AAPL.US']),result(),root=tmp_path/'out',identities=ids,dry_run=True)
