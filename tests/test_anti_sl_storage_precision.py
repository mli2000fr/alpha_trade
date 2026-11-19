"""Precision regression: strict contract checks must survive real SQL round trips."""
from datetime import date,datetime,UTC
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest
from sqlalchemy import Double,Float,create_engine
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from modelFactory.oracle_path import anti_sl_store as store

THRESHOLD=0.16660042812602094
PROBABILITY=0.12673859128946362


def manifest(monkeypatch):
    monkeypatch.setattr(store,'load_manifest',lambda root:(dict(models=[dict(year=2026,
        threshold=THRESHOLD,available='2025-12-31',sha256='m'*64)]),'a'*64))


def frame():
    return pd.DataFrame([dict(date=pd.Timestamp('2026-11-18'),symbol='ABC',
        anti_sl_probability=PROBABILITY,anti_sl_threshold=THRESHOLD,
        anti_sl_model_sha256='m'*64,anti_sl_manifest_sha256='a'*64,
        anti_sl_available=date(2025,12,31),anti_sl_status='SCORED',anti_sl_features_sha256='f'*64)])


def test_new_mysql_table_has_double_precision_for_both_values():
    ddl=str(CreateTable(store.table()).compile(dialect=mysql.dialect()))
    assert 'anti_sl_probability DOUBLE' in ddl and 'anti_sl_threshold DOUBLE' in ddl
    assert ' FLOAT' not in ddl


def test_threshold_round_trip_keeps_strict_manifest_and_cutoff(monkeypatch):
    manifest(monkeypatch)
    engine=create_engine('sqlite://')
    data=frame();oracle=data[['date','symbol']]
    with engine.begin() as conn:store.write(conn,data,'batch')
    got=store.read(engine,None,oracle,'batch',cutoff=datetime.now(UTC))
    assert got.anti_sl_threshold.iloc[0]==THRESHOLD
    assert got.anti_sl_probability.iloc[0]==PROBABILITY
    corrupt=got.copy();corrupt['anti_sl_threshold']=0.1666
    with pytest.raises(ValueError,match='contrat'):store.validate(None,oracle,corrupt)
    with pytest.raises(ValueError,match='manquants'):
        store.read(engine,None,oracle,'batch',cutoff=datetime(2020,1,1,tzinfo=UTC))
    engine.dispose()


@pytest.mark.parametrize('dtype',[Double(),mysql.DOUBLE()])
def test_migrated_mysql_columns_are_accepted(monkeypatch,dtype):
    monkeypatch.setattr(store,'inspect',lambda conn:SimpleNamespace(get_columns=lambda name:
        [dict(name=n,type=dtype) for n in ('anti_sl_probability','anti_sl_threshold')]))
    store.require_storage_precision(SimpleNamespace(dialect=SimpleNamespace(name='mysql')))


@pytest.mark.parametrize('name',['anti_sl_threshold','anti_sl_probability'])
def test_legacy_mysql_float_requires_migration_before_deleting_or_publishing_scores(monkeypatch,name):
    types={n:Double() for n in ('anti_sl_probability','anti_sl_threshold')};types[name]=Float()
    monkeypatch.setattr(store,'inspect',lambda conn:SimpleNamespace(get_columns=lambda table:
        [dict(name=n,type=t) for n,t in types.items()]))
    with pytest.raises(ValueError,match='migration_0089'):
        store.require_storage_precision(SimpleNamespace(dialect=SimpleNamespace(name='mysql')))


def test_legacy_storage_blocks_write_before_any_score_deletion(monkeypatch):
    conn=SimpleNamespace(dialect=SimpleNamespace(name='mysql'),execute=Mock())
    monkeypatch.setattr(store,'table',lambda:SimpleNamespace(create=Mock()))
    monkeypatch.setattr(store,'inspect',lambda connection:SimpleNamespace(get_columns=lambda name:
        [dict(name=n,type=Float()) for n in ('anti_sl_probability','anti_sl_threshold')]))
    with pytest.raises(ValueError,match='stockage DOUBLE requis'):
        store.write(conn,frame(),'batch')
    conn.execute.assert_not_called()


@pytest.mark.parametrize('column,value',[
    ('anti_sl_threshold',THRESHOLD+1e-5),('anti_sl_model_sha256','other'),
    ('anti_sl_available',date(2026,11,18)),('anti_sl_manifest_sha256','other')])
def test_precision_fix_does_not_accept_changed_models_dates_or_thresholds(monkeypatch,column,value):
    manifest(monkeypatch)
    data=frame();oracle=data[['date','symbol']].copy();data[column]=value
    with pytest.raises(ValueError):store.validate(None,oracle,data)
