from datetime import datetime,UTC,date
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine,select,func,text
from service.market import cn_collection_storage as sql


@pytest.fixture
def repository(tmp_path,monkeypatch):
    monkeypatch.setattr(sql,'ROOT',tmp_path)
    engine=create_engine('sqlite://')
    sql.create_schema(engine)
    repo=sql.Repository(engine)
    with sql.use(repo):yield repo,tmp_path


def test_exact_large_bytes_versions_no_disk_fallback_and_corruption(repository):
    repo,root=repository
    path=sql.DataPath(root/'artifacts/cn/raw/provider.bin')
    raw=b'x'*2_100_000
    path.write_bytes(raw)
    assert not Path(path).exists() and path.read_bytes()==raw
    path.write_bytes(raw)
    with repo.engine.connect() as c:assert c.execute(select(func.count()).select_from(sql.versions)).scalar()==1
    path.write_bytes(b'new')
    with repo.engine.connect() as c:assert c.execute(select(func.count()).select_from(sql.versions)).scalar()==2
    Path(path).parent.mkdir(parents=True);Path(path).write_bytes(b'forbidden fallback')
    path.unlink()
    with pytest.raises(FileNotFoundError):path.read_bytes()
    path.write_bytes(raw)
    with repo.engine.begin() as c:c.execute(sql.parts.update().where(sql.parts.c.part_no==1).values(body=b'bad'))
    with pytest.raises(ValueError,match='integrity'):path.read_bytes()


def test_atomic_publication_parquet_typed_rows_and_exclusive_write(repository):
    repo,root=repository
    base=sql.DataPath(root/'artifacts/research/cn_oracle_prospective_15d8')
    temporary=base/'.partial';temporary.mkdir(parents=True)
    frame=pd.DataFrame([dict(decision_date='2026-10-08',exchange='SZSE',code='000001',
        oracle_score=.912345678901,score_available_at_utc='2026-10-07T12:00:00+00:00')])
    sql.write_parquet(frame,temporary/'oracle_top20.parquet',index=False)
    (temporary/'report.json').write_text(json.dumps(dict(status='PROSPECTIVE_RESEARCH_ONLY')))
    temporary.replace(base/'2026-10-08')
    assert not temporary.exists()
    pd.testing.assert_frame_equal(sql.read_parquet(base/'2026-10-08/oracle_top20.parquet'),frame)
    assert [p.name for p in base.glob('*/oracle_top20.parquet')]==['oracle_top20.parquet']
    assert list(base.glob('*.json'))==[]
    with repo.engine.connect() as c:
        row=c.execute(select(sql.candidates)).mappings().one()
        assert row['code']=='000001' and row['oracle_score']==pytest.approx(.912345678901)
    with pytest.raises(FileExistsError):
        with (base/'2026-10-08/report.json').open('x') as stream:stream.write('{}')
    duplicate=base/'.duplicate';duplicate.mkdir()
    (duplicate/'report.json').write_text('{}')
    with pytest.raises(FileExistsError):duplicate.replace(base/'2026-10-08')


def test_compressed_checkpoints_and_model_packages_remain_readable(repository):
    repo,root=repository
    folder=sql.DataPath(root/'artifacts/cn/inputs');folder.mkdir(parents=True)
    path=folder/'rows.jsonl.gz'
    with sql.gzip_open(path,'wt',encoding='utf-8') as stream:stream.write('{"x":1}\n')
    with sql.gzip_open(path,'rt',encoding='utf-8') as stream:assert stream.read()=='{"x":1}\n'
    model=Path(folder/'model.txt');model.parent.mkdir(parents=True,exist_ok=True);model.write_text('weights')
    receipt=Path(folder/'report.json');receipt.write_text('{"model":"frozen"}')
    assert sql.DataPath(receipt).read_text()=='{"model":"frozen"}'
    assert 'report.json' in {p.name for p in folder.rglob('*.json')}


def test_collector_and_reader_use_sql_without_changing_observation_or_rights(repository,monkeypatch):
    repo,root=repository
    from service.market import cn_dragon_tiger_prospective_15d5 as collector
    monkeypatch.setattr(collector,'official_sse',lambda d:([dict(date=d,exchange='SSE',code='600001',reason_code='X')],{}))
    monkeypatch.setattr(collector,'official_szse',lambda d:([],{}))
    folder=sql.DataPath(root/'artifacts/research/cn_dragon_tiger_15d6/observations')
    path=collector.run(date(2026,9,30),folder)
    assert not Path(path).exists()
    snapshot=json.loads(path.read_text())
    assert snapshot['pit_usable'] is False
    previous=collector.prior_observations(folder/'2026-09-30')
    assert previous==[snapshot]
    with repo.engine.connect() as c:
        row=c.execute(select(sql.snapshots)).mappings().one()
        assert row['historical_pit_qualified'] is False
        assert row['observed_at_utc']==sql.timestamp(snapshot['observed_at_utc'])
        assert c.execute(select(func.count()).select_from(sql.events)).scalar()==1


def test_migration_is_idempotent_verifies_all_before_delete_and_preserves_models(repository):
    repo,root=repository
    from service.market.cn_collection_migration import migrate
    folder=root/'artifacts/research/cn_legacy';folder.mkdir(parents=True)
    (folder/'data.json').write_bytes(b'{"value":1}')
    (folder/'model.txt').write_bytes(b'weights')
    first=migrate(repo)
    assert first['imported_files']==1 and (folder/'data.json').exists()
    second=migrate(repo,delete_sources=True)
    assert second['deleted_files']==1 and not (folder/'data.json').exists()
    assert (folder/'model.txt').read_bytes()==b'weights'
    assert repo.get(folder/'data.json')==b'{"value":1}'
    with repo.engine.connect() as c:
        receipt=c.execute(select(sql.migrations)).mappings().one()
        assert receipt['deleted_at'] is not None


def test_wrong_database_is_refused_before_ddl_or_write(monkeypatch):
    class FakeConnection:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def execute(self,*a):return type('Result',(),{'scalar':lambda self:'alpha_trade'})()
    engine=type('Engine',(),{'dialect':type('Dialect',(),{'name':'mysql'})(), 'connect':lambda self:FakeConnection()})()
    with pytest.raises(ValueError,match='alpha_trade_cn'):sql.Repository(engine)


def test_projection_failure_leaves_no_partial_object_or_deleted_source(repository):
    repo,root=repository
    from service.market.cn_collection_migration import migrate
    folder=root/'artifacts/research/cn_legacy';folder.mkdir(parents=True)
    (folder/'a.json').write_text('{}')
    bad=dict(schema='cn_dragon_tiger_observation_v1',counts=dict(events=1),events=[])
    (folder/'bad.json').write_text(json.dumps(bad))
    with pytest.raises(ValueError,match='event count'):migrate(repo,delete_sources=True)
    assert (folder/'a.json').exists() and (folder/'bad.json').exists()
    assert not repo.exists(folder/'bad.json')


def test_cleanup_only_refuses_changed_file_then_deletes_verified_version(repository):
    repo,root=repository
    from service.market.cn_collection_migration import migrate,cleanup_verified
    folder=root/'artifacts/research/cn_legacy';folder.mkdir(parents=True)
    path=folder/'data.json';path.write_bytes(b'{}')
    migrate(repo)
    path.write_bytes(b'{"changed":true}')
    with pytest.raises(ValueError,match='changed CN source'):cleanup_verified(repo)
    assert path.exists()
    migrate(repo)
    result=cleanup_verified(repo)
    assert result['deleted_files']==1 and result['source_files_remaining']==0
    assert repo.get(path)==b'{"changed":true}'


def test_full_d10_sql_matching_reuses_observations_and_publication_without_files(repository):
    import yaml
    from tests.test_cn_dragon_tiger_matched_15d7 import _snapshot,_candidates,CALENDAR,PROTOCOL
    from service.market import cn_dragon_tiger_daily_15d10 as daily
    repo,root=repository
    observations=sql.DataPath(root/'artifacts/research/cn_dragon_tiger_15d6/observations')
    _snapshot(observations)
    fixture=root/'fixture.parquet';_candidates(fixture)
    folder=sql.DataPath(root/'artifacts/research/cn_oracle_prospective_15d8/2026-09-30')
    folder.mkdir(parents=True)
    raw=fixture.read_bytes();(folder/'oracle_top20.parquet').write_bytes(raw)
    (folder/'report.json').write_text(json.dumps(dict(status='PROSPECTIVE_RESEARCH_ONLY',decision_date='2026-09-30',
        candidate_export_sha256=sql.sha(raw),score_available_at_utc='2026-09-29T15:00:00+00:00',
        export_published_at_utc='2026-09-29T15:01:00+00:00',decision_cutoff_utc='2026-09-30T01:15:00+00:00',quality=dict(top20=12))))
    output=sql.DataPath(root/'artifacts/research/cn_dragon_tiger_15d10')
    config=root/'batch.yaml';config.write_text(yaml.safe_dump({daily.BATCH_NAME:dict(enabled=True,status='RESEARCH_ONLY',
        calendar=str(CALENDAR.resolve()),protocol=str(PROTOCOL.resolve()),snapshot_root=str(observations),
        oracle_output_root=str(folder.parent),output_root=str(output))}))
    result=daily.execute(batch_config=config,now=datetime(2026,9,30,1,30,tzinfo=UTC))
    assert result['status']=='COMPLETED_RESEARCH_ONLY',result
    assert not Path(output).exists()
    assert (output/'2026-09-30/outcome_blind_matches.parquet').is_file()
    assert daily.execute(batch_config=config,now=datetime(2026,9,30,1,31,tzinfo=UTC))['status']=='SKIP_ALREADY_MATCHED'
    with repo.engine.connect() as c:
        assert c.execute(select(func.count()).select_from(sql.matches)).scalar()>0


def test_explicit_transient_cleanup_retains_old_partial_bytes_in_sql(repository):
    repo,root=repository
    from service.market.cn_collection_migration import migrate,source_files
    folder=root/'artifacts/cn/sprint7c_daily';folder.mkdir(parents=True)
    (folder/'state.tmp').write_bytes(b'{"old":"partial"}')
    (folder/'run-all.lock').write_bytes(b'0')
    assert source_files()==[]
    result=migrate(repo,delete_sources=True,include_transient=True)
    assert result['deleted_files']==2 and source_files(include_transient=True)==[]
    assert repo.get(folder/'state.tmp')==b'{"old":"partial"}'
