"""T5.6: synthetic fixtures only. Never read/write real databases or secrets."""
from copy import deepcopy
import gzip
import io
import json
import os
from pathlib import Path
import platform
import shutil
import tarfile
import time

import pytest

from service.migration import engine,environment,inventory,storage
from service.migration.mysql import Connection,DATABASES

PASSWORD='test-only-password-7346'
TOKEN='synthetic-api-secret-NOT-REAL-583'


class FakeDB:
    def __init__(self,tag='source'):
        self.state={n:dict(tag=tag,rows=3,index='v1') for n in DATABASES}
        self.connections={n:Connection(user='local',password='target-test-secret') for n in DATABASES}
        self.calls=[];self.fail_load=None
    def inspect(self,n,allow_missing=False,count_rows=True):
        if n not in self.state:
            if allow_missing:return None
            raise ValueError('Missing database')
        row=dict(name='items',kind='BASE TABLE',engine='InnoDB')
        if count_rows:row['rows']=self.state[n]['rows']
        return dict(database=n,version='8.0.42',charset='utf8mb4',collation_name='utf8mb4_0900_ai_ci',
            tables=[row],objects={'index':self.state[n]['index']},event_definitions=[],definers=[])
    def public_metadata(self,meta):return {k:v for k,v in meta.items() if k!='event_definitions'}
    def check_destination(self,metadata,**kwargs):assert set(metadata)<=set(DATABASES)
    def dump(self,n,output,check=lambda:None):
        check();output.write(gzip.compress(json.dumps(self.state[n]).encode()))
    def recreate(self,n,meta):self.calls.append(('recreate',n));self.state[n]={}
    def drop(self,n):self.calls.append(('drop',n));self.state.pop(n,None)
    def load(self,n,stream,check=lambda:None):
        check()
        if self.fail_load==n:self.fail_load=None;raise RuntimeError('Synthetic import failure')
        self.state[n]=json.loads(gzip.decompress(stream.read()))
    def load_events_disabled(self,*args):pass
    def validate(self,n,expected):
        actual=self.inspect(n,count_rows=any('rows' in t for t in expected['tables']))
        assert actual['tables']==expected['tables']
        assert actual['objects']==expected['objects']
    def reset_runtime_locks(self):self.calls.append(('reset_ephemeral',))


def quiet(*args,**kwargs):return []


@pytest.fixture(scope='module')
def backup(tmp_path_factory):
    base=tmp_path_factory.mktemp('migration');source=base/'source';source.mkdir()
    fixtures={'app.py':'# uncommitted current code\n','config.yaml':'provider: alpaca_sip\n',
        'config/univers_batch/tradable.txt':'A,B,C',
        'artifacts/models/run/weights.bin':b'fake-model-weights'*1000,
        'artifacts/options_directional/run/execution.claim.json':'{"business_claim":true}',
        'artifacts/ihm_pipeline_runs/job/record.json':'{"status":"running","pid":999}',
        'artifacts/config_vault/key':'local-vault-fixture',
        'log/execution.log':'old log', '.venv/ignored.txt':'must not migrate',
        '.git/ignored.txt':'must not migrate'}
    for name,value in fixtures.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(value if isinstance(value,bytes) else value.encode())
    output=base/'backup';db=FakeDB()
    captured=dict(values={'OPENAI_API_KEY':TOKEN,'ALPACA_TEST1_API_KEY':'account-fixture'},
        variables=[dict(name='OPENAI_API_KEY',present=True,scope='Process')])
    versions=lambda root:dict(python=platform.python_version(),system=platform.system(),machine=platform.machine(),requirements='pytest==8.0.0\n')
    # Prove an active source does not block or stop a normal online export.
    def active_source(*a,**k):raise AssertionError('Online export must not query/stop source jobs')
    engine.export(source,output,PASSWORD,db,quiet=active_source,versions=versions,captured=captured,limit=1024)
    return source,output,db


def plan_and_restore(backup,tmp_path,monkeypatch,db=None,writer=None,on_progress=None):
    source,folder,_=backup;target=tmp_path/'target';target.mkdir()
    (target/'app.py').write_text('old code')
    (target/'unrelated').mkdir();(target/'unrelated/preserved.txt').write_text('untouched')
    (target/'artifacts/models/obsolete').mkdir(parents=True)
    (target/'artifacts/models/obsolete/old.bin').write_text('old model')
    db=db or FakeDB('old')
    monkeypatch.setattr(environment,'registry_values',lambda scope:{})
    plan=engine.inspect_restore(folder,target,PASSWORD,db,quiet=quiet)
    values={}
    def write(items):
        for n,v in items.items():
            if v is None:values.pop(n,None)
            else:values[n]=v
    result=engine.restore(folder,target,PASSWORD,db,tmp_path/'report',approved_plan=plan['fingerprint'],
        quiet=quiet,env_writer=writer or write,env_reader=lambda:{},on_progress=on_progress)
    return target,db,result,values


def test_online_complete_and_secrets_encrypted(backup):
    source,folder,db=backup
    manifest=engine.verify(folder,PASSWORD)
    assert manifest['source_mode']=='online' and not manifest['cross_database_atomic']
    assert manifest['source_services_unchanged'] and not manifest['row_counts_authoritative']
    assert len([p for p in manifest['packages'] if p['kind']=='sql'])==3
    assert (folder/'restaurer.ps1').is_file()
    assert (source/'.venv/ignored.txt').is_file() and not (source/engine.LOCK).exists()
    for path in folder.rglob('*'):
        if path.is_file():assert TOKEN.encode() not in path.read_bytes()


def test_restore_mirrors_models_preserves_business_claims(backup,tmp_path,monkeypatch):
    target,db,result,values=plan_and_restore(backup,tmp_path,monkeypatch)
    assert result['status']=='RESTORED_PAUSED' and not result['services_auto_restart']
    assert values['OPENAI_API_KEY']==TOKEN
    assert values['PASSWORD_DB']=='target-test-secret'
    assert all(db.state[n]['tag']=='source' for n in DATABASES)
    assert not (target/'artifacts/models/obsolete').exists()
    assert (target/'artifacts/models/run/weights.bin').is_file()
    assert (target/'unrelated/preserved.txt').read_text()=='untouched'
    assert json.loads((target/'artifacts/options_directional/run/execution.claim.json').read_text())=={'business_claim':True}
    ui=json.loads((target/'artifacts/ihm_pipeline_runs/job/record.json').read_text())
    assert ui['status']=='interrupted' and ui['pid'] is None
    assert (target/'artifacts/ihm_pipeline_runs/job/record.source.json').is_file()
    assert (tmp_path/'report/existant-chiffre/recovery.json').is_file()


def test_import_failure_rolls_back_all_three_databases(backup,tmp_path,monkeypatch):
    db=FakeDB('old');before=deepcopy(db.state);db.fail_load='alpha_trade_fr'
    with pytest.raises(RuntimeError):plan_and_restore(backup,tmp_path,monkeypatch,db=db)
    assert db.state==before
    assert (tmp_path/'target/app.py').read_text()=='old code'
    assert (tmp_path/'target/artifacts/models/obsolete/old.bin').read_text()=='old model'
    assert json.loads((tmp_path/'report/progress.json').read_text())['status']=='FAILED_ROLLED_BACK'


def test_environment_failure_rolls_back_files_and_database(backup,tmp_path,monkeypatch):
    db=FakeDB('old');before=deepcopy(db.state);calls=[]
    def fail_once(values):
        calls.append(dict(values))
        if len(calls)==1:raise OSError('Synthetic registry failure')
    with pytest.raises(OSError):plan_and_restore(backup,tmp_path,monkeypatch,db=db,writer=fail_once)
    assert db.state==before and len(calls)==2
    assert (tmp_path/'target/app.py').read_text()=='old code'


@pytest.mark.parametrize('damage',['missing','ciphertext','manifest','password','incomplete','tool'])
def test_invalid_backup_rejected_before_any_drop(backup,tmp_path,damage,monkeypatch):
    folder=tmp_path/'backup';shutil.copytree(backup[1],folder)
    manifest=json.loads((folder/'manifest.json').read_text())
    password=PASSWORD
    first=next(folder.rglob('*.part0001'))
    if damage=='missing':first.unlink()
    elif damage=='ciphertext':first.write_bytes(first.read_bytes()[:-1]+b'X')
    elif damage=='manifest':
        manifest['payload']['source_root']='tampered';storage.atomic_json(folder/'manifest.json',manifest)
    elif damage=='password':password='incorrect-password-334'
    elif damage=='incomplete':storage.atomic_json(folder/'progress.json',{'status':'FAILED'})
    elif damage=='tool':(folder/'restaurer.ps1').write_text('malicious tool')
    db=FakeDB('old');monkeypatch.setattr(environment,'registry_values',lambda scope:{})
    with pytest.raises((ValueError,OSError)):
        engine.inspect_restore(folder,tmp_path/'target',password,db,quiet=quiet)
    assert not db.calls


def test_active_target_and_existing_venv_block_replacement(backup,tmp_path,monkeypatch):
    db=FakeDB('old');target=tmp_path/'target';target.mkdir()
    monkeypatch.setattr(environment,'registry_values',lambda scope:{})
    plan=engine.inspect_restore(backup[1],target,PASSWORD,db,quiet=lambda *a,**k:[{'pid':42}])
    assert plan['active_processes']
    with pytest.raises(ValueError,match='Fermer'):
        engine.restore(backup[1],target,PASSWORD,db,tmp_path/'reports',approved_plan=plan['fingerprint'],quiet=lambda *a,**k:[{'pid':42}])
    (target/'.venv').mkdir()
    with pytest.raises(ValueError,match='venv'):engine.inspect_restore(backup[1],target,PASSWORD,db,quiet=quiet)
    assert not db.calls


def test_changed_plan_rejected(backup,tmp_path,monkeypatch):
    monkeypatch.setattr(environment,'registry_values',lambda scope:{})
    db=FakeDB('old');target=tmp_path/'target';target.mkdir()
    plan=engine.inspect_restore(backup[1],target,PASSWORD,db,quiet=quiet)
    db.state['alpha_trade']['rows']+=1
    with pytest.raises(ValueError,match='Plan'):
        engine.restore(backup[1],target,PASSWORD,db,tmp_path/'report',approved_plan=plan['fingerprint'],quiet=quiet)
    assert not db.calls


def test_recover_encrypted_preimage(backup,tmp_path,monkeypatch):
    target,db,report,_=plan_and_restore(backup,tmp_path,monkeypatch)
    restored={}
    result=engine.recover(tmp_path/'report/existant-chiffre',PASSWORD,db,tmp_path/'recover',quiet=quiet,env_writer=restored.update)
    assert result['status']=='RECOVERED_PAUSED'
    assert all(db.state[n]['tag']=='old' for n in DATABASES)
    assert (target/'app.py').read_text()=='old code'
    assert (target/'artifacts/models/obsolete/old.bin').read_text()=='old model'


def test_environment_discovery_scope_and_exclusions(tmp_path):
    (tmp_path/'app.py').write_text("import os\na=os.getenv('SEC_USER_AGENT')\nb=os.environ['PATH']")
    result=environment.capture(tmp_path,['app.py'],process={'OPENAI_API_KEY':'process','PATH':'bad','ALPACA_TEST2_SECRET_KEY':'dynamic'},
        user={'OPENAI_API_KEY':'user'},machine={'OPENAI_API_KEY':'machine','UNRELATED_SECRET':'bad','SEC_USER_AGENT':'agent'})
    assert result['values']=={'OPENAI_API_KEY':'process','ALPACA_TEST2_SECRET_KEY':'dynamic','SEC_USER_AGENT':'agent'}
    assert 'process' not in json.dumps(result['variables'])


@pytest.mark.parametrize('name',['../outside','/absolute','C:/root','a/../../b','a\\b','file:ads','./a','a//../b'])
def test_paths_reject_escape(tmp_path,name):
    with pytest.raises(ValueError):storage.safe_path(tmp_path,name)


def test_stream_rejects_truncated_authenticated_end(tmp_path):
    with storage.encrypted_output(tmp_path,'test',PASSWORD,1024) as (stream,parts):stream.write(os.urandom(9000))
    last=tmp_path/parts[-1]['path'];last.write_bytes(last.read_bytes()[:-1])
    # Even if the outer checksum is recomputed, the authenticated EOF is required.
    parts[-1].update(size=last.stat().st_size,sha256=storage.sha_file(last))
    with pytest.raises(ValueError):
        with storage.decrypted_input(tmp_path,dict(label='test',parts=parts),PASSWORD) as stream:stream.read()


def test_malicious_tar_rejected_before_restore(backup,tmp_path):
    folder=tmp_path/'backup';shutil.copytree(backup[1],folder)
    payload=storage.open_manifest(folder/'manifest.json',PASSWORD)
    original=next(p for p in payload['packages'] if p['kind']=='files')
    with storage.encrypted_output(folder/'evil','evil.tar.gz',PASSWORD) as (stream,parts):
        with tarfile.open(fileobj=stream,mode='w|gz') as tar:
            info=tarfile.TarInfo('../outside');info.size=1;tar.addfile(info,io.BytesIO(b'x'))
    original.update(folder='evil',label='evil.tar.gz',parts=parts,files=[dict(path='../outside',size=1,sha256='0')])
    storage.atomic_json(folder/'manifest.json',storage.seal_manifest(payload,PASSWORD))
    with pytest.raises(ValueError):engine.verify(folder,PASSWORD)
    assert not (tmp_path/'outside').exists()


def test_cancel_never_publishes_complete(tmp_path):
    root=tmp_path/'root';root.mkdir();output=tmp_path/'backup'
    with pytest.raises(InterruptedError):engine.export(root,output,PASSWORD,FakeDB(),cancel=lambda:True)
    assert not (output/'manifest.json').exists()
    assert json.loads((output/'progress.json').read_text())['status']=='CANCELED'


def test_real_detached_worker_verifies_synthetic_package(backup,tmp_path):
    from ihm.services.migration_runner import start_job,job_state
    job=start_job(dict(action='verify',folder=str(backup[1]),password=PASSWORD),job_parent=tmp_path/'jobs')
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        state=job_state(job)
        if (state['progress'] or {}).get('status') in ('FINISHED','FAILED'):break
        time.sleep(.1)
    assert state['progress']['status']=='FINISHED',state
    assert state['result']['status']=='VERIFIED'
    assert state['tracking']['percent']==100
    assert state['tracking']['status']=='FINISHED'
    assert state['events'] and any(e['phase']=='VERIFYING' for e in state['events'])
    for path in Path(job).rglob('*'):
        if path.is_file():assert PASSWORD.encode() not in path.read_bytes()


def test_model_contract_and_weights_checked_without_unpickling(tmp_path):
    root=tmp_path/'artifacts/models/example/oracle_path';fold=root/'folds/000';fold.mkdir(parents=True)
    protocol={'horizon':20}
    import hashlib
    protocol['fingerprint']=hashlib.sha256(json.dumps(protocol,sort_keys=True,default=str).encode()).hexdigest()
    storage.atomic_json(root/'protocol.json',protocol)
    (fold/'weights.bin').write_bytes(b'test-weights')
    storage.atomic_json(fold/'done.json',{'files':{'weights.bin':storage.sha_file(fold/'weights.bin')}})
    engine.model_checks(tmp_path)
    (fold/'weights.bin').write_bytes(b'corrupted')
    with pytest.raises(ValueError,match='Poids'):engine.model_checks(tmp_path)


@pytest.mark.parametrize('name',['CON','NUL.json','folder/name.','folder/name ','folder/a?b','a//b','COM1.bin'])
def test_windows_alias_paths_rejected(tmp_path,name):
    with pytest.raises(ValueError):storage.safe_path(tmp_path,name)


def test_restore_reports_staging_sql_and_completion(backup,tmp_path,monkeypatch):
    from service.migration.tracking import Progress
    job=tmp_path/'job';job.mkdir();tracker=Progress(job,'restore')
    plan_and_restore(backup,tmp_path,monkeypatch,on_progress=tracker.update)
    events=[json.loads(line) for line in (job/'events.jsonl').read_text().splitlines()]
    phases={e['phase'] for e in events}
    assert {'VERIFYING','RESTORE_PREFLIGHT','STAGING','BACKUP_EXISTING','DATABASE_REPLACEMENT',
        'DATABASE_VALIDATION','FILE_REPLACEMENT','FINALIZING','RESTORED_PAUSED'}<=phases
    assert any(e.get('processed_bytes',0)>0 for e in events)
    assert tracker.state['percent']<100  # Optional Python setup / worker finalization still follows.
    assert TOKEN not in (job/'events.jsonl').read_text()


def test_restore_failure_reports_rollback_without_false_completion(backup,tmp_path,monkeypatch):
    from service.migration.tracking import Progress
    job=tmp_path/'job';job.mkdir();tracker=Progress(job,'restore');db=FakeDB('old');db.fail_load='alpha_trade_fr'
    with pytest.raises(RuntimeError):plan_and_restore(backup,tmp_path,monkeypatch,db=db,on_progress=tracker.update)
    assert tracker.state['phase']=='FAILED_ROLLED_BACK' and tracker.state['percent']<100
    assert any(json.loads(line)['phase']=='ROLLBACK' for line in (job/'events.jsonl').read_text().splitlines())
