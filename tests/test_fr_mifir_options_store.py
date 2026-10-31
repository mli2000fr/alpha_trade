from datetime import date, datetime
from decimal import Decimal
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import (Boolean, Column, Date, DateTime, ForeignKeyConstraint, Integer,
                        MetaData, Numeric, String, Table, Text, create_engine, event, text)

from service.fr import mifir_options_daily as daily
from service.fr import mifir_options_store as store
from test_fr_mifir_options_daily import fake_fetch
from test_fr_mifir_options_poc import trade


@pytest.fixture
def archives(tmp_path, monkeypatch):
    root = tmp_path / 'collection'
    monkeypatch.setattr(daily, 'reference_scope', lambda path: (2, {
        'OR.PA': ({'isin': 'FR0000120321'}, []), 'BN.PA': ({'isin': 'FR0000120644'}, [])}, []))
    monkeypatch.setattr(daily.source, 'now', lambda: '2026-10-06T07:01:00+00:00')
    rows = [trade(), trade(TradeUniqueIdentifier='cancelled'),
            trade(TradeUniqueIdentifier='cancelled', MmtModificationIndicator='CANC')]
    result = dict(persisted_count=0, failed_count=0)
    daily._collect_files({}, result, root=root, identities=tmp_path / 'ids',
        clock=store.source.instant('2026-10-06T08:00:00Z'), fetch=fake_fetch([], rows=rows))
    path = next((root / 'snapshots').glob('*.json'))
    attempt = next((root / 'attempts').glob('*.json'))
    return root, path, attempt


def sqlite_store(archive, attempt):
    engine = create_engine('sqlite:///:memory:')
    @event.listens_for(engine, 'connect')
    def foreign_keys(conn, record):
        conn.execute('PRAGMA foreign_keys=ON')
    snapshot, contracts, trades = store.prepare_snapshot(archive)
    receipt, _ = attempt
    meta = MetaData()
    for table_name, example, primary in zip(store.TABLES,
        [snapshot, contracts[0], trades[0], receipt],
        [('snapshot_id',), ('snapshot_id', 'option_isin'), ('snapshot_id', 'source_row_sha256'), ('observation_id',)]):
        cols = []
        for key, value in example.items():
            kind = (DateTime if isinstance(value, datetime) else Date if isinstance(value, date)
                    else Boolean if isinstance(value, bool) else Integer if isinstance(value, int)
                    else Numeric(38, 12) if isinstance(value, Decimal) else Text)
            cols.append(Column(key, kind, primary_key=key in primary))
        if table_name in store.TABLES[1:3]:
            cols.append(ForeignKeyConstraint(['snapshot_id'], [store.TABLES[0] + '.snapshot_id']))
        Table(table_name, meta, *cols)
    meta.create_all(engine)
    return engine


def install_sqlite(monkeypatch, archives):
    root, path, attempt = archives
    engine = sqlite_store(store.load_snapshot(path, root), store.load_attempt(attempt, root))
    monkeypatch.setattr(store, 'check_schema', lambda e: None)
    return engine


def test_import_preserves_receipts_clocks_rejections_and_is_idempotent(monkeypatch, archives):
    engine = install_sqlite(monkeypatch, archives)
    root, path, attempt = archives
    first = store.persist_archive(engine, root, path, attempt)
    assert first == dict(sql_snapshots=1, sql_contracts=1, sql_trades=3,
                         sql_observations=1, sql_snapshots_reused=0)
    again = store.persist_archive(engine, root, path, attempt)
    assert again['sql_snapshots_reused'] == 1
    assert again['sql_trades'] == again['sql_observations'] == 0
    with engine.connect() as conn:
        row = conn.execute(text('SELECT * FROM fr_option_mifir_snapshots')).mappings().one()
        assert str(row['observed_at']).startswith('2026-10-06 07:01:00')
        assert str(row['available_at']).startswith('2026-10-06 07:01:00')
        assert row['imported_at'] != row['available_at']
        assert not row['ml_eligible'] and not row['canonical'] and not row['historical_pit_qualified']
        assert conn.execute(text("SELECT COUNT(*) FROM fr_option_mifir_trades WHERE acceptance_status='REJECTED'"
                                 " AND rejection_reason='CANCELLED_ID'")).scalar_one() == 2
        assert conn.execute(text('SELECT SUM(quantity_unit_qualified)+SUM(ml_eligible) '
                                 'FROM fr_option_mifir_trades')).scalar_one() == 0
        assert json.loads(row['archive_json']) == json.loads(path.read_text())


def test_second_receipt_for_same_snapshot_does_not_duplicate_trades(monkeypatch, archives):
    engine = install_sqlite(monkeypatch, archives)
    root, path, attempt = archives
    store.persist_archive(engine, root, path, attempt)
    data = json.loads(attempt.read_text())
    data['finished_at'] = '2026-10-06T08:02:00Z'
    second = attempt.with_name('second.json')
    second.write_text(json.dumps(data))
    stats = store.persist_archive(engine, root, path, second)
    assert stats['sql_snapshots_reused'] == stats['sql_observations'] == 1
    assert stats['sql_trades'] == 0


def test_different_snapshot_versions_are_not_silently_merged(monkeypatch, archives):
    engine = install_sqlite(monkeypatch, archives)
    root, path, attempt = archives
    store.persist_archive(engine, root, path, attempt)
    prepared = store.prepare_snapshot(store.load_snapshot(path, root))
    prepared[0]['archive_sha256'] = 'f' * 64
    with engine.begin() as conn, pytest.raises(ValueError, match='écrasement interdit'):
        store.store_prepared(conn, prepared)


def test_failed_child_insert_rolls_back_whole_snapshot(monkeypatch, archives):
    engine = install_sqlite(monkeypatch, archives)
    root, path, attempt = archives
    original = store._insert
    def fail(conn, table, rows):
        if table == store.TABLES[2]:
            raise RuntimeError('SQL failure')
        original(conn, table, rows)
    monkeypatch.setattr(store, '_insert', fail)
    with pytest.raises(RuntimeError, match='SQL failure'):
        store.persist_archive(engine, root, path, attempt)
    with engine.connect() as conn:
        assert conn.execute(text('SELECT COUNT(*) FROM fr_option_mifir_snapshots')).scalar_one() == 0
        assert conn.execute(text('SELECT COUNT(*) FROM fr_option_mifir_contracts')).scalar_one() == 0
    monkeypatch.setattr(store, '_insert', original)
    assert store.persist_archive(engine, root, path, attempt)['sql_trades'] == 3


def test_corrupt_raw_or_promoted_archive_never_imported(monkeypatch, archives):
    root, path, attempt = archives
    data = json.loads(path.read_text())
    data['ml_eligible'] = True
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='promue'):
        store.load_snapshot(path, root)
    data['ml_eligible'] = False
    path.write_text(json.dumps(data))
    blob = root / 'objects' / data['reference_receipts'][1]['sha256']
    blob.write_bytes(b'bad')
    with pytest.raises(ValueError, match='corrompue'):
        store.load_snapshot(path, root)


def test_modified_analysis_or_future_receipt_is_rejected(archives):
    root, path, attempt = archives
    data = json.loads(path.read_text())
    data['analysis']['accepted'][0]['MifidQuantity'] = '999'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='Analyse archivée'):
        store.load_snapshot(path, root)
    data['reference_receipts'][0]['received_at'] = '2026-10-07T07:00:00Z'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='postérieur'):
        store.load_snapshot(path, root)


def test_wrong_database_blocked_before_connection():
    class WrongEngine:
        url = SimpleNamespace(database='alpha_trade')
        def connect(self):
            pytest.fail('US database connection forbidden')
    with pytest.raises(ValueError, match='alpha_trade_fr'):
        store.persist_archive(WrongEngine(), '.', None, None)


def test_sql_required_before_provider_and_dry_run_does_not_open_db(monkeypatch, tmp_path):
    monkeypatch.setattr(store, 'engine_fr', lambda: (_ for _ in ()).throw(RuntimeError('schema missing')))
    monkeypatch.setattr(daily, 'reference_scope', lambda path:
                        (1, {'OR.PA': ({'isin': 'FR0000120321'}, [])}, []))
    kwargs = dict(root=tmp_path, identities=tmp_path/'ids', fetch=lambda *a: pytest.fail('provider forbidden'))
    with pytest.raises(RuntimeError, match='schema missing'):
        daily.collect({}, {}, **kwargs)
    result = {}
    daily.collect({}, result, dry_run=True, **kwargs)
    assert result['requested_count'] == 1
    assert not (tmp_path/'snapshots').exists() and not (tmp_path/'attempts').exists()


def test_collector_sql_failure_keeps_archive_and_reports_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(store, 'check_schema', lambda engine: None)
    monkeypatch.setattr(store, 'persist_archive', lambda *a: (_ for _ in ()).throw(RuntimeError('SQL unavailable')))
    monkeypatch.setattr(daily, 'reference_scope', lambda path:
                        (1, {'OR.PA': ({'isin': 'FR0000120321'}, [])}, []))
    monkeypatch.setattr(daily.source, 'now', lambda: '2026-10-06T07:01:00+00:00')
    result = dict(persisted_count=0, failed_count=0)
    with pytest.raises(RuntimeError, match='SQL unavailable'):
        daily.collect({}, result, root=tmp_path, identities=tmp_path/'ids', engine=object(),
            clock=store.source.instant('2026-10-06T08:00:00Z'), fetch=fake_fetch([]))
    assert list((tmp_path/'snapshots').glob('*.json'))
    assert list((tmp_path/'attempts').glob('*.json'))
    assert result['sql_persistence_error'] == 'SQL unavailable'


def test_batch_is_configured_for_sql_storage():
    import yaml
    cfg = yaml.safe_load((store.ROOT/'batch_fr.yaml').read_text(encoding='utf-8'))['fr_options_mifir_trade_sync']
    assert cfg['enabled'] is True and cfg['sql_storage_enabled'] is True
    assert set(cfg['tables'].split(',')) == set(store.TABLES)


def test_daily_collector_feeds_sql_and_backfill_reuses_the_same_rows(monkeypatch, archives):
    engine = install_sqlite(monkeypatch, archives)
    root, path, attempt = archives
    rows = [trade(), trade(TradeUniqueIdentifier='cancelled'),
            trade(TradeUniqueIdentifier='cancelled', MmtModificationIndicator='CANC')]
    result = dict(persisted_count=0, failed_count=0)
    daily.collect({}, result, root=root, identities=root/'ids', engine=engine,
        clock=store.source.instant('2026-10-06T08:05:00Z'), fetch=fake_fetch([], rows=rows))
    assert result['sql_trades'] == 3 and result['sql_observations'] == 1
    assert result['database'] == 'alpha_trade_fr' and result['sql_writes'] is True
    report = store.backfill(engine, root, apply=True)
    assert report['sql_counts']['sql_snapshots_reused'] == 1
    assert report['sql_counts']['sql_trades'] == 0
    assert report['sql_counts']['sql_observations'] == 1  # Only the older file receipt was missing.
    assert store.backfill(engine, root, apply=True)['sql_counts']['sql_observations'] == 0
