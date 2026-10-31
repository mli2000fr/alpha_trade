"""Only temporary backup trees; never delete or stop a real project worker."""
import json
from pathlib import Path
from datetime import datetime,timezone

import pytest
from streamlit.testing.v1 import AppTest

from service.migration import locking
from service.migration import cleanup as cleaning
from ihm.services import migration_runner


def make_tree(root):
    for directory in ('backups/migrations/old','backups/migration_jobs/old-job'):
        path=root/directory;path.mkdir(parents=True)
        (path/'progress.json').write_text(json.dumps({'status':'FAILED'}))
        (path/'payload.bin').write_bytes(b'old backup fixture')
    for directory in ('backups/db','backups/ml','backups/fr','backups/cn','artifacts/models','config'):
        path=root/directory;path.mkdir(parents=True);(path/'preserve').write_text('must remain')


def test_dead_lock_is_archived_and_new_ownership_is_removed(tmp_path,monkeypatch):
    receipt={'pid':123,'started_at':'2026-10-31T00:00:00+00:00'}
    (tmp_path/locking.LOCK).write_text(json.dumps(receipt))
    monkeypatch.setattr(locking,'owner_state',lambda value:'dead')
    with locking.migration_lock(tmp_path) as recovered:
        assert recovered['owner_pid']==123
        assert json.loads((tmp_path/recovered['archive']).read_text())==receipt
        assert json.loads((tmp_path/locking.LOCK).read_text())['token']
    assert not (tmp_path/locking.LOCK).exists()


def test_live_lock_and_parallel_guard_are_never_stolen(tmp_path):
    with locking.migration_lock(tmp_path):
        original=(tmp_path/locking.LOCK).read_bytes()
        with pytest.raises(locking.MigrationLockError):
            with locking.migration_lock(tmp_path):pytest.fail('acquired twice')
        assert (tmp_path/locking.LOCK).read_bytes()==original


def test_corrupt_legacy_lock_is_preserved(tmp_path):
    (tmp_path/locking.LOCK).write_text('invalid')
    with pytest.raises(locking.MigrationLockError,match='illisible'):
        with locking.migration_lock(tmp_path):pass
    assert (tmp_path/locking.LOCK).read_text()=='invalid'


def test_pid_reuse_is_not_considered_a_live_owner(monkeypatch):
    class Process:
        def is_running(self):return True
        def status(self):return 'running'
        def create_time(self):return 1000.
    monkeypatch.setattr(locking.psutil,'Process',lambda pid:Process())
    assert locking.owner_state({'pid':1,'process_created_at':100.})=='dead'
    assert locking.owner_state({'pid':1,'process_created_at':1000.})=='alive'


def test_cleanup_deletes_only_listed_t56_and_dead_lock(tmp_path,monkeypatch):
    make_tree(tmp_path)
    (tmp_path/locking.LOCK).write_text(json.dumps({'pid':123,'started_at':'2026-10-31T00:00:00+00:00'}))
    monkeypatch.setattr(cleaning,'owner_state',lambda receipt:'dead')
    plan=cleaning.preview_cleanup(tmp_path)
    assert len(plan['entries'])==2
    result=cleaning.cleanup(tmp_path,approved_plan=plan['fingerprint'])
    assert result['status']=='CLEANED' and result['lock_released']
    assert len(result['deleted'])==2
    for directory in ('backups/db','backups/ml','backups/fr','backups/cn','artifacts/models','config'):
        assert (tmp_path/directory/'preserve').read_text()=='must remain'
    assert Path(result['audit_path']).is_file()
    assert not (tmp_path/locking.LOCK).exists()


def test_changed_inventory_refuses_cleanup(tmp_path):
    make_tree(tmp_path);plan=cleaning.preview_cleanup(tmp_path)
    (tmp_path/'backups/migrations/old/new-file').write_text('new data')
    with pytest.raises(ValueError,match='changé'):cleaning.cleanup(tmp_path,approved_plan=plan['fingerprint'])
    assert (tmp_path/'backups/migrations/old/payload.bin').exists()


def test_cleanup_refuses_active_guard_or_legacy_owner(tmp_path,monkeypatch):
    make_tree(tmp_path)
    with locking.migration_lock(tmp_path):
        with pytest.raises(locking.MigrationLockError):cleaning.preview_cleanup(tmp_path)
    (tmp_path/locking.LOCK).write_text(json.dumps({'pid':123}))
    monkeypatch.setattr(cleaning,'owner_state',lambda value:'alive')
    with pytest.raises(locking.MigrationLockError):cleaning.preview_cleanup(tmp_path)
    assert (tmp_path/'backups/migrations/old/payload.bin').exists()


def test_registry_prefers_actual_worker_pid_over_python_launcher(tmp_path,monkeypatch):
    (tmp_path/'job.json').write_text(json.dumps({'pid':111}))
    (tmp_path/'progress.json').write_text(json.dumps({'pid':222,'status':'STARTED','updated_at':datetime.now(timezone.utc).isoformat()}))
    inspected=[]
    monkeypatch.setattr(migration_runner,'owner_state',lambda value:inspected.append(value['pid']) or 'dead')
    assert migration_runner.job_state(tmp_path)['worker_ended_without_result']
    assert inspected==[222]


def test_cleanup_ui_requires_preview_and_confirmation(tmp_path,monkeypatch):
    make_tree(tmp_path)
    app=AppTest.from_string(f"from ihm.components.migration_cleanup import render_migration_cleanup\nrender_migration_cleanup({str(tmp_path)!r})").run()
    assert not app.exception
    app.button(key='t56_cleanup_preview').click().run()
    assert not app.exception
    assert app.button(key='t56_cleanup_apply').disabled
    assert (tmp_path/'backups/migrations/old/payload.bin').exists()
    app.checkbox(key='t56_cleanup_confirm').check().run()
    app.button(key='t56_cleanup_apply').click().run()
    assert not app.exception
    assert app.success and not (tmp_path/'backups/migrations/old').exists()


@pytest.mark.parametrize('module',['service.migration.cli','restaurer.ps1'])
def test_cleanup_detects_worker_with_forward_slash_backup_path(tmp_path,monkeypatch,module):
    from types import SimpleNamespace
    root=tmp_path/'backups/migrations'
    process=SimpleNamespace(pid=101,info={'name':'python.exe','cmdline':[module,'--backup-dir',root.as_posix()+'/archive'],'cwd':str(tmp_path)})
    monkeypatch.setattr(cleaning.psutil,'process_iter',lambda *a:[process])
    assert cleaning._live_workers([root])==[101]
