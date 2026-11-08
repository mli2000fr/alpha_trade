from types import SimpleNamespace
from unittest.mock import MagicMock
import socket

import psutil
import pytest
from sqlalchemy import create_engine, text

from execution_engine.watcher_lease import release_dead_local_watcher_lease


@pytest.fixture
def engine(monkeypatch):
    engine = create_engine('sqlite://')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE execution_locks (account_id TEXT PRIMARY KEY,locked_by_run_id TEXT,acquired_at TEXT,expires_at TEXT)')
        conn.exec_driver_sql('CREATE TABLE watcher_heartbeats (account_id TEXT,watcher_name TEXT,pid INTEGER,hostname TEXT,last_heartbeat_at TEXT,status TEXT)')
        conn.execute(text("INSERT INTO execution_locks VALUES ('watcher:default','watch-service-old','2026-11-01 14:00:00','2026-11-01 14:10:00')"))
        conn.execute(text("INSERT INTO watcher_heartbeats VALUES ('default','execution_protection_watcher',999,:host,'2026-11-01 14:05:00','RUNNING')"),dict(host=socket.gethostname()))
    def missing(pid):
        raise psutil.NoSuchProcess(pid)
    monkeypatch.setattr(psutil,'Process',missing)
    monkeypatch.setattr(psutil,'process_iter',lambda attrs: [])
    return engine


def counts(engine):
    with engine.connect() as conn:
        return conn.execute(text('SELECT COUNT(*) FROM execution_locks')).scalar_one(),conn.execute(text('SELECT status FROM watcher_heartbeats')).scalar_one()


def test_reclaims_only_dead_local_lease_and_marks_old_heartbeat_stopped(engine):
    assert release_dead_local_watcher_lease(engine,'default',dry_run=True)
    assert counts(engine) == (1,'RUNNING')
    assert release_dead_local_watcher_lease(engine,'default')
    assert counts(engine) == (0,'STOPPED')
    assert not release_dead_local_watcher_lease(engine,'default')


def test_live_or_reused_pid_retains_lease(engine,monkeypatch):
    monkeypatch.setattr(psutil,'Process',lambda pid: object())
    assert not release_dead_local_watcher_lease(engine,'default')
    assert counts(engine) == (1,'RUNNING')


def test_unverifiable_process_never_authorizes_cleanup(engine,monkeypatch):
    def denied(pid):
        raise psutil.AccessDenied(pid)
    monkeypatch.setattr(psutil,'Process',denied)
    with pytest.raises(RuntimeError,match='non vérifiable'):
        release_dead_local_watcher_lease(engine,'default')
    assert counts(engine) == (1,'RUNNING')


@pytest.mark.parametrize('mutation',[
    "UPDATE watcher_heartbeats SET hostname='another-pc'",
    "UPDATE execution_locks SET acquired_at='2026-11-01 14:06:00'",
    "UPDATE execution_locks SET locked_by_run_id='unrelated-owner'",
    "UPDATE watcher_heartbeats SET watcher_name='other-watcher'",
])
def test_foreign_new_or_unmatched_owner_is_preserved(engine,mutation):
    with engine.begin() as conn:
        conn.exec_driver_sql(mutation)
    assert not release_dead_local_watcher_lease(engine,'default')
    assert counts(engine) == (1,'RUNNING')


def test_another_local_watcher_starting_prevents_cleanup(engine,monkeypatch):
    from execution_engine import watcher_lease
    command=['python',str(watcher_lease.Path(watcher_lease.__file__).with_name('protection_watcher.py')),
             '--mode','service','--account','default']
    monkeypatch.setattr(psutil,'process_iter',lambda attrs:[SimpleNamespace(info=dict(cmdline=command))])
    assert not release_dead_local_watcher_lease(engine,'default')
    assert counts(engine) == (1,'RUNNING')


def test_dead_pid_error_at_admission_is_actionable_and_keeps_gate_closed(monkeypatch):
    from execution_engine.config import ExecutionConfig
    from execution_engine.winner_plans import require_campaign_watcher
    repo=MagicMock()
    repo.is_watcher_healthy.return_value=True
    repo.engine.connect.return_value.__enter__.return_value.execute.return_value.mappings.return_value.first.return_value={
        'pid':999,'hostname':socket.gethostname()}
    def missing(pid):
        raise psutil.NoSuchProcess(pid)
    monkeypatch.setattr(psutil,'Process',missing)
    with pytest.raises(ValueError,match='ancien heartbeat sans processus actif'):
        require_campaign_watcher(repo,ExecutionConfig())
