"""Synthetic backups only: file restore must never reach any DB adapter."""
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from service.migration import cli, engine, environment, files_only
from ihm.services import migration_runner
from tests.test_migration_complete import backup, PASSWORD, quiet


def test_standalone_files_restore_preserves_database_environment_and_venv(backup,tmp_path,monkeypatch):
    _,folder,db=backup
    target=tmp_path/'target';target.mkdir()
    (target/'app.py').write_text('old')
    (target/'.env').write_text('DB_NAME=keep-target')
    (target/'.venv').mkdir();(target/'.venv/keep').write_text('venv')
    (target/'artifacts/models/old').mkdir(parents=True)
    (target/'artifacts/models/old/old.bin').write_text('old weights')
    def forbidden(*a,**k):raise AssertionError('Database/environment access forbidden')
    monkeypatch.setattr(cli,'adapter',forbidden)
    monkeypatch.setattr(environment,'write_user',forbidden)
    monkeypatch.setattr(environment,'registry_values',forbidden)
    monkeypatch.setattr(cli.inventory,'quiescent',quiet)
    # Record exactly which encrypted packages are read, including preview.
    original=engine.decrypted_input;opened=[]
    def tracked(location,package,*a,**k):
        opened.append(package['kind']);return original(location,package,*a,**k)
    monkeypatch.setattr(engine,'decrypted_input',tracked)
    # Default arguments bind the original scanner; tests supply the safe one.
    inspect=files_only.inspect_files_only;restore=files_only.restore_files_only
    monkeypatch.setattr(files_only,'inspect_files_only',lambda *a,**k:inspect(*a,**dict(k,quiet=quiet)))
    monkeypatch.setattr(files_only,'restore_files_only',lambda *a,**k:restore(*a,**dict(k,quiet=quiet)))
    request=dict(action='plan_files_only',folder=str(folder),target=str(target),password=PASSWORD)
    plan=cli.run_request(request,tmp_path/'preview')
    assert plan['mode']=='FILES_ONLY' and not plan['databases_touched']
    result=cli.run_request(dict(request,action='restore_files_only',approved_plan=plan['fingerprint'],
        report_dir=str(tmp_path/'report')),tmp_path/'worker')
    assert result['status']=='FILES_ONLY_RESTORED' and not result['databases_touched']
    assert set(opened)=={'files'} and not db.calls
    assert (target/'.env').read_text()=='DB_NAME=keep-target'
    assert (target/'.venv/keep').read_text()=='venv'
    assert (target/'artifacts/models/run/weights.bin').exists()
    assert not (target/'artifacts/models/old').exists()
    assert (Path(result['local_previous_files'])/'artifacts/models/old/old.bin').read_text()=='old weights'


def test_files_only_failure_rolls_back_existing_files(backup,tmp_path,monkeypatch):
    _,folder,_=backup;target=tmp_path/'target';target.mkdir()
    (target/'app.py').write_text('original')
    (target/engine.PENDING).write_text('{"reason":"previous-marker"}')
    plan=files_only.inspect_files_only(folder,target,PASSWORD,quiet=quiet)
    original=engine.install_managed_roots
    def fail(*a,**k):original(*a,**k);raise OSError('synthetic install failure')
    monkeypatch.setattr(engine,'install_managed_roots',fail)
    with pytest.raises(OSError):
        files_only.restore_files_only(folder,target,PASSWORD,tmp_path/'report',approved_plan=plan['fingerprint'],quiet=quiet)
    assert (target/'app.py').read_text()=='original'
    assert json.loads((target/engine.PENDING).read_text())['reason']=='previous-marker'
    assert json.loads((tmp_path/'report/progress.json').read_text())['status']=='FAILED_ROLLED_BACK'


def test_changed_file_plan_and_active_target_rejected(backup,tmp_path):
    _,folder,_=backup;target=tmp_path/'target';target.mkdir();(target/'app.py').write_text('original')
    plan=files_only.inspect_files_only(folder,target,PASSWORD,quiet=quiet)
    (target/'app.py').write_text('changed and longer')
    with pytest.raises(ValueError,match='Plan fichiers changé'):
        files_only.restore_files_only(folder,target,PASSWORD,tmp_path/'report',approved_plan=plan['fingerprint'],quiet=quiet)
    active=lambda *a,**k:[dict(pid=123)]
    plan=files_only.inspect_files_only(folder,target,PASSWORD,quiet=active)
    with pytest.raises(ValueError,match='PC cible'):
        files_only.restore_files_only(folder,target,PASSWORD,tmp_path/'report2',approved_plan=plan['fingerprint'],quiet=active)


def test_ui_files_only_does_not_require_mysql_credentials(tmp_path,monkeypatch):
    monkeypatch.setattr(migration_runner,'PROJECT_ROOT',tmp_path)
    calls=[]
    def launch(request,**kwargs):calls.append(request);return str(tmp_path/'file-plan')
    monkeypatch.setattr(migration_runner,'start_job',launch)
    monkeypatch.setattr(migration_runner,'job_state',lambda p:dict(result=dict(mode='FILES_ONLY',fingerprint='test-plan')))
    app=AppTest.from_string('from ihm.components.migration_panel import render_migration_panel\nrender_migration_panel()').run()
    app.text_input(key='t56_folder').set_value(str(tmp_path/'backup'))
    app.text_input(key='t56_target').set_value(str(tmp_path/'target'))
    app.text_input(key='t56_password').set_value(PASSWORD).run()
    app.button(key='t56_plan_files_only').click().run()
    assert not app.exception and calls[-1]['action']=='plan_files_only'
    assert 'connections' not in calls[-1] and 'mysql' not in calls[-1]
    assert app.button(key='t56_restore_files_only').disabled
    app.checkbox(key='t56_files_confirm').check().run()
    app.button(key='t56_restore_files_only').click().run()
    assert not app.exception and calls[-1]['action']=='restore_files_only'
    assert 'connections' not in calls[-1] and 'mysql' not in calls[-1]
