"""UI/worker contract; no actual subprocess, API or database launched."""
import io
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from ihm.services import migration_runner
from service.migration import cli,engine,environment


def test_worker_launch_keeps_credentials_off_disk_and_argv(tmp_path,monkeypatch):
    from service.migration.locking import os_guard
    monkeypatch.setattr(migration_runner,'os_guard',lambda root:os_guard(tmp_path))
    calls=[]
    class Pipe(io.BytesIO):
        def close(self):self.contents=self.getvalue();super().close()
    class Process:
        pid=987654
        def __init__(self,cmd,**kwargs):
            self.stdin=Pipe();calls.append((cmd,kwargs,self))
        def kill(self):pass
        def wait(self):return 0
    monkeypatch.setattr(migration_runner.subprocess,'Popen',Process)
    secret='fixture-only-PASSWORD-582'
    request=dict(action='verify',folder='F:/fixture/archive',password=secret)
    job=Path(migration_runner.start_job(request,job_parent=tmp_path/'jobs'))
    command,kwargs,process=calls[0]
    assert secret not in ' '.join(command)
    assert json.loads(process.stdin.contents)['password']==secret
    for path in job.rglob('*'):
        if path.is_file():assert secret.encode() not in path.read_bytes()
    assert kwargs['stdout']==migration_runner.subprocess.DEVNULL
    assert kwargs['stderr']==migration_runner.subprocess.DEVNULL
    assert '-X' in command


def test_cli_worker_failure_has_no_secret_traceback(tmp_path,monkeypatch):
    secret='fixture-only-SECRET'
    monkeypatch.setattr(cli.sys,'stdin',io.StringIO(json.dumps({'action':'verify','password':secret})))
    def fail(*args,**kwargs):raise RuntimeError('private SQL credential '+secret)
    monkeypatch.setattr(cli,'run_request',fail)
    assert cli.main(['--request-stdin','--job-dir',str(tmp_path)])==1
    assert secret not in (tmp_path/'progress.json').read_text()


def test_ui_renders_without_exporting_secrets(tmp_path,monkeypatch):
    monkeypatch.setattr(migration_runner,'PROJECT_ROOT',tmp_path)
    app=AppTest.from_string('from ihm.components.migration_panel import render_migration_panel\nrender_migration_panel()').run()
    assert not app.exception
    labels=[x.label for x in app.button]
    assert 'Créer les packages chiffrés' in labels
    assert 'Prévisualiser la restauration' in labels
    assert any('PC source' in str(item.value) for item in app.info)
    assert next(x for x in app.button if x.key=='t56_export').disabled
    assert any('restaurer.ps1' in block.value and '-Action restore' in block.value for block in app.code)
    submitted=[]
    monkeypatch.setattr(migration_runner,'start_job',lambda request,**kw:submitted.append(dict(request)) or str(tmp_path/'job'))
    app.text_input(key='t56_password').set_value('fixture-only-password-443')
    app.text_input(key='t56_password_confirm').set_value('fixture-only-password-443')
    app.run()
    app.button(key='t56_export').click().run()
    assert not app.exception
    assert submitted[0]['action']=='export'
    assert 'quiescent_confirmed' not in submitted[0]
    assert app.text_input(key='t56_password').value==''
    assert app.text_input(key='t56_password_confirm').value==''


def test_restore_command_quotes_paths_without_expanding_powershell(tmp_path):
    folder=tmp_path/"Copie O'Brien $x; sauvegarde"
    command=migration_runner.build_restore_command(folder)
    expected=str(folder.resolve()/'restaurer.ps1').replace("'","''")
    assert command=="& '"+expected+"' -Action restore"
    assert 'password' not in command.lower()


def test_restore_command_rejects_multiline_path():
    import pytest
    with pytest.raises(ValueError):migration_runner.build_restore_command("F:/backup\nWrite-Host bad")


def test_cli_accepts_prefilled_backup_and_target_without_executing_restore(monkeypatch,tmp_path):
    calls=[]
    monkeypatch.setattr(cli,'interactive',lambda action,**kwargs:calls.append((action,kwargs)))
    assert cli.main(['restore','--backup-dir',str(tmp_path/'backup'),'--target-dir',str(tmp_path/'target')])==0
    assert calls==[('restore',dict(backup_dir=str(tmp_path/'backup'),target_dir=str(tmp_path/'target')))]


def test_source_uuid_blocks_same_database_server(monkeypatch):
    from service.migration.mysql import MySQL,Connection,DATABASES
    class Cursor:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def execute(self,sql,*args):self.sql=sql
        def fetchone(self):return {'v':'8.0.42'} if 'VERSION' in self.sql else {'server_uuid':'same-source'}
    class Conn:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def cursor(self):return Cursor()
    db=object.__new__(MySQL);db.connections={n:Connection() for n in DATABASES}
    monkeypatch.setattr(db,'connect',lambda n:Conn())
    import pytest
    with pytest.raises(ValueError,match='serveur source'):
        db.check_destination({'alpha_trade':dict(version='8.0.42',server_uuid='same-source')})
    db.check_destination({'alpha_trade':dict(version='8.0.42',server_uuid='same-source')},allow_same_server=True)


def test_database_cli_uses_transaction_and_env_not_password_arg(monkeypatch):
    from service.migration.mysql import MySQL,Connection,DATABASES
    db=object.__new__(MySQL);db.connections={n:Connection(user='operator',password='not-a-real-secret') for n in DATABASES}
    db.dump_tool='mysqldump'
    seen=[]
    class Process:
        returncode=0
        stdout=io.BytesIO(b'CREATE TABLE test (id INT);')
        def wait(self):return 0
    def fake(cmd,**kwargs):seen.append((cmd,kwargs));return Process()
    monkeypatch.setattr('service.migration.mysql.subprocess.Popen',fake)
    output=io.BytesIO();db.dump('alpha_trade',output)
    command,kwargs=seen[0]
    assert '--single-transaction' in command and '--skip-events' in command
    assert '--skip-lock-tables' in command
    assert 'not-a-real-secret' not in ' '.join(command)
    assert kwargs['env']['MYSQL_PWD']=='not-a-real-secret'
