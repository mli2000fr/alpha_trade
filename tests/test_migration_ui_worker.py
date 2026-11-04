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


def test_cli_worker_log_explains_stale_plan(tmp_path,monkeypatch):
    monkeypatch.setattr(cli.sys,'stdin',io.StringIO(json.dumps({'action':'restore','report_dir':str(tmp_path/'report')})))
    def fail(*args,**kwargs):raise ValueError('Plan de restauration changé : refaire la prévisualisation')
    monkeypatch.setattr(cli,'run_request',fail)
    assert cli.main(['--request-stdin','--job-dir',str(tmp_path)])==1
    assert 'refaire la prévisualisation' in (tmp_path/'events.jsonl').read_text(encoding='utf-8')


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


def test_preview_button_explains_missing_fields_without_launch(tmp_path,monkeypatch):
    monkeypatch.setattr(migration_runner,'PROJECT_ROOT',tmp_path)
    calls=[]
    monkeypatch.setattr(migration_runner,'start_job',lambda *a,**k:calls.append(a))
    app=AppTest.from_string('from ihm.components.migration_panel import render_migration_panel\nrender_migration_panel()').run()
    assert not app.button(key='t56_plan').disabled
    app.button(key='t56_plan').click().run()
    assert not app.exception and calls==[]
    message=' '.join(str(x.value) for x in app.error)
    assert 'manifest.json' in message and 'mot de passe des packages' in message and 'MySQL cible' in message


def test_verify_then_preview_keeps_credentials_and_plan_is_not_widget_state(tmp_path,monkeypatch):
    monkeypatch.setattr(migration_runner,'PROJECT_ROOT',tmp_path)
    calls=[]
    def launch(request,**kw):
        calls.append(request)
        return str(tmp_path/request['action'])
    plan=dict(fingerprint='synthetic-plan',target=str(tmp_path/'target'),databases=['alpha_trade','alpha_trade_fr','alpha_trade_cn'])
    def state(path):return dict(result=plan if str(path).endswith('plan') else dict(status='VERIFIED'))
    monkeypatch.setattr(migration_runner,'start_job',launch)
    monkeypatch.setattr(migration_runner,'job_state',state)
    app=AppTest.from_string('from ihm.components.migration_panel import render_migration_panel\nrender_migration_panel()').run()
    package_password='fixture-package-password-123'
    mysql_password='fixture-mysql-password-456'
    app.text_input(key='t56_password').set_value(package_password)
    app.text_input(key='t56_folder').set_value(str(tmp_path/'backup'))
    app.text_input(key='t56_target').set_value(str(tmp_path/'target'))
    app.text_input(key='t56_db_password').set_value(mysql_password)
    app.run()
    app.button(key='t56_verify').click().run()
    assert not app.exception and calls[-1]['action']=='verify'
    assert app.text_input(key='t56_password').value==package_password
    assert app.text_input(key='t56_db_password').value==mysql_password
    app.button(key='t56_plan').click().run()
    assert not app.exception
    assert calls[-1]['action']=='plan' and calls[-1]['password']==package_password
    assert all(c['password']==mysql_password for c in calls[-1]['connections'].values())
    assert app.text_input(key='t56_password').value==package_password
    assert app.text_input(key='t56_db_password').value==mysql_password
    assert app.session_state['t56_plan_result']==plan
    assert isinstance(app.session_state['t56_plan'],bool)
    assert app.button(key='t56_restore').disabled
    app.checkbox(key='t56_replace').check().run()
    assert not app.exception and not app.button(key='t56_restore').disabled
    # Another preview always requires a fresh approval, without changing data.
    app.button(key='t56_plan').click().run()
    assert not app.exception and not app.checkbox(key='t56_replace').value
    assert all(r['action'] in ('verify','plan') for r in calls)
    assert package_password not in ' '.join(str(x.value) for x in app.json)


def test_legacy_plan_widget_collision_is_discarded(tmp_path,monkeypatch):
    monkeypatch.setattr(migration_runner,'PROJECT_ROOT',tmp_path)
    app=AppTest.from_string('from ihm.components.migration_panel import render_migration_panel\nrender_migration_panel()')
    app.session_state['t56_plan']={'fingerprint':'old-plan'}
    app.run()
    assert not app.exception and not app.button(key='t56_plan').disabled
    assert isinstance(app.session_state['t56_plan'],bool)
    assert all(b.key!='t56_restore' for b in app.button)


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


def test_completed_plan_survives_new_session_without_secrets(tmp_path,monkeypatch):
    monkeypatch.setattr(migration_runner,'PROJECT_ROOT',tmp_path)
    job=tmp_path/'backups'/'migration_jobs'/'completed'
    job.mkdir(parents=True)
    context=dict(folder='F:/backup',target='D:/Projet',user='root',
                 mysqldump='dump.exe',mysql='mysql.exe')
    (job/'job.json').write_text(json.dumps(dict(action='plan',plan_context=context)))
    (job/'progress.json').write_text(json.dumps(dict(status='FINISHED')))
    (job/'result.json').write_text(json.dumps(dict(fingerprint='plan-1')))
    assert migration_runner.latest_completed_plan()==(str(job),context,dict(fingerprint='plan-1'))
    assert migration_runner.completed_plan_for(context)==(str(job),dict(fingerprint='plan-1'))
    assert migration_runner.completed_plan_for(context | dict(target='D:/Other')) is None


def test_restore_quiescence_ignores_ui_and_scheduler_but_blocks_batch(tmp_path,monkeypatch):
    from service.migration import inventory
    class Process:
        def __init__(self,pid,cmd):
            self.pid=pid
            self.info=dict(name='python.exe',cmdline=['python.exe',*cmd],exe='C:/Python/python.exe')
        def cwd(self):return str(tmp_path)
    processes=[Process(90001,['-m','streamlit','run',str(tmp_path/'ihm/app.py')]),
               Process(90002,[str(tmp_path/'run.py')]),
               Process(90003,['-m','service.forward_pit.batch','--batch','daily_bars_sync'])]
    import psutil
    monkeypatch.setattr(psutil,'process_iter',lambda *args:processes)
    assert [item['pid'] for item in inventory.running_processes(tmp_path)]==[90003]


def test_active_restore_precedes_old_plan_after_refresh(tmp_path):
    restore=tmp_path/'restore';plan=tmp_path/'plan'
    restore.mkdir();plan.mkdir()
    (restore/'job.json').write_text(json.dumps(dict(action='restore')))
    (restore/'progress.json').write_text(json.dumps(dict(status='WAITING_FOR_TARGET_STOP')))
    (plan/'job.json').write_text(json.dumps(dict(action='plan')))
    (plan/'progress.json').write_text(json.dumps(dict(status='FINISHED')))
    assert migration_runner.order_follow_jobs([str(plan),str(restore)])[0]==str(restore)


def test_file_resume_report_is_discovered_after_refresh(tmp_path):
    backup=tmp_path/'backup';target=tmp_path/'target';target.mkdir()
    report=backup/'journaux'/'restauration-20261104T010000Z';report.mkdir(parents=True)
    (report/'progress.json').write_text(json.dumps(dict(status='FILES_PENDING')))
    (report/'database-ready.json').write_text(json.dumps(dict(payload=dict(
        phase='DATABASE_VALIDATED',backup_folder=str(backup.resolve()),
        target=str(target.resolve()),report_dir=str(report.resolve())))))
    assert migration_runner.latest_files_pending(str(backup),str(target))==str(report)
    assert migration_runner.latest_files_pending(str(backup),str(tmp_path/'other')) is None


def test_worker_routes_file_resume_without_full_database_restore(tmp_path,monkeypatch):
    calls=[]
    class DB:pass
    monkeypatch.setattr(cli,'adapter',lambda request:DB())
    monkeypatch.setattr(cli.inventory,'quiescent',lambda *args,**kwargs:[])
    monkeypatch.setattr(cli.engine,'restore',lambda *args,**kwargs:(_ for _ in ()).throw(
        AssertionError('Full SQL restore must not run')))
    def resume(*args,**kwargs):
        calls.append((args,kwargs));return dict(status='RESTORED_PAUSED',source_requirements='')
    monkeypatch.setattr(cli.engine,'restore_files',resume)
    report=tmp_path/'report';report.mkdir()
    request=dict(action='restore_files',folder=str(tmp_path/'backup'),target=str(tmp_path/'target'),
        report_dir=str(report),password='fixture-only-password-443',rebuild_venv=False)
    result=cli.run_request(request,tmp_path/'job')
    assert result['status']=='RESTORED_PAUSED'
    assert len(calls)==1 and calls[0][0][4]==str(report)
