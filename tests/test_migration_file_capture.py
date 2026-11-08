import hashlib
import json
import os
from pathlib import Path
import tarfile

import pytest

from service.migration import engine,inventory,storage
from service.migration.file_capture import FileCaptureError,open_source
from service.migration.tracking import Progress
from tests.test_migration_complete import FakeDB,PASSWORD


RUN='opt-'+'a'*32
NAME='risk.claim.json'


def source(tmp_path):
    root=tmp_path/'source'
    relative=f'artifacts/options_directional/{RUN}/{NAME}'
    path=root/relative
    path.parent.mkdir(parents=True)
    path.write_bytes(b'{"approval":"fixture-only"}')
    stat=path.stat()
    return root,path,dict(path=relative,size=stat.st_size,mtime_ns=stat.st_mtime_ns)


def move_to_archive(path,record,*,directory='manual_rearms',bad_hash=False):
    folder=path.parent/directory/'attempt'
    folder.mkdir(parents=True)
    archived=folder/path.name
    path.rename(archived)
    digest=hashlib.sha256(archived.read_bytes()).hexdigest()
    (folder/'authorization.json').write_text(json.dumps(dict(run_id=RUN,account_id='default',
        hashes={path.name:'0'*64 if bad_hash else digest})),encoding='utf-8')
    return archived


def test_inventory_excludes_only_known_atomic_json_temporary_siblings(tmp_path):
    for name in ('progress.json.a1b2c3d4e5f6.tmp','progress.json.tmp','progress.json','data.tmp','final.json'):
        (tmp_path/name).write_text('fixture')
    names=[f['path'] for group in inventory.scan(tmp_path).values() for f in group]
    assert set(names)=={'progress.json','data.tmp','final.json'}


def test_live_pack_recovers_verified_moved_claim_without_restoring_source(tmp_path):
    root,path,record=source(tmp_path)
    archived=move_to_archive(path,record)
    events=[]
    package=engine.pack_files(root,tmp_path/'package','files',[record],PASSWORD,1024,None,
        live=True,on_progress=lambda phase,**kw:events.append(kw))
    assert not path.exists()
    assert package['files'][0]['source_recovered_from']==archived.relative_to(root).as_posix()
    assert any(event.get('warning') for event in events)
    with storage.decrypted_input(tmp_path/'package',package,PASSWORD) as stream:
        with tarfile.open(fileobj=stream,mode='r|gz') as archive:
            member=next(iter(archive))
            assert member.name==record['path']
            assert archive.extractfile(member).read()==archived.read_bytes()


@pytest.mark.parametrize('bad_hash',[False,True])
def test_nonlive_or_unverified_copy_does_not_authorize_omission(tmp_path,bad_hash):
    root,path,record=source(tmp_path)
    move_to_archive(path,record,bad_hash=bad_hash)
    with pytest.raises(FileCaptureError,match='source inventorié introuvable'):
        open_source(root,record,live=bad_hash)  # Nonlive, or live with a wrong receipt.


def test_core_file_missing_is_named_and_never_silently_skipped(tmp_path):
    root=tmp_path/'source';root.mkdir()
    record=dict(path='app.py',size=10,mtime_ns=0)
    (tmp_path/'job').mkdir()
    progress=Progress(tmp_path/'job','export')
    progress.update('FILES_EXPORT',package='application',files_total=1)
    with pytest.raises(FileCaptureError) as error:
        engine.pack_files(root,tmp_path/'package','files',[record],PASSWORD,1024,None,live=True,on_progress=progress.update)
    progress.update('FAILED',**error.value.details,failure_reason=error.value.public_message)
    state=json.loads((tmp_path/'job/tracking.json').read_text(encoding='utf-8'))
    assert state['failed_path']==state['item']=='app.py'
    assert state['package']=='application'
    assert state['cause_type']=='FileNotFoundError'
    assert 'app.py' in (tmp_path/'job/events.jsonl').read_text(encoding='utf-8').splitlines()[-1]
    assert state['status']=='FAILED' and state['percent']<100


def test_complete_online_backup_verifies_recovered_version_after_inventory(tmp_path):
    root,path,record=source(tmp_path)
    db=FakeDB()
    real_dump=db.dump
    moved=[]
    def dump(name,output,check=lambda:None):
        if not moved:
            moved.append(move_to_archive(path,record))
        real_dump(name,output,check)
    db.dump=dump
    folder=tmp_path/'backup'
    manifest=engine.export(root,folder,PASSWORD,db,guard=False,
        captured=dict(values={},variables=[]),versions=lambda r:dict(python='3.14',system='Windows',machine='AMD64',requirements=''))
    assert manifest['archived_file_versions_recovered']==1
    assert engine.verify(folder,PASSWORD)['status']=='COMPLETE'
    assert not path.exists()


def test_file_disappearance_after_inventory_leaves_failed_backup_with_exact_context(tmp_path):
    root=tmp_path/'source';root.mkdir()
    path=root/'app.py';path.write_text('fixture')
    db=FakeDB();real_dump=db.dump
    def dump(name,output,check=lambda:None):
        path.unlink(missing_ok=True)
        real_dump(name,output,check)
    db.dump=dump
    folder=tmp_path/'backup';progress=Progress(tmp_path/'job','export')
    with pytest.raises(FileCaptureError):
        engine.export(root,folder,PASSWORD,db,guard=False,on_progress=progress.update,
            captured=dict(values={},variables=[]),versions=lambda r:{})
    state=json.loads((folder/'progress.json').read_text(encoding='utf-8'))
    assert state['status']=='FAILED' and state['failed_path']=='app.py'
    assert not (folder/'manifest.json').exists()
    assert progress.state['package']=='application' and progress.state['failed_path']=='app.py'


@pytest.mark.parametrize('change',['account','run','mtime'])
def test_archive_from_another_scope_or_version_never_substitutes_the_file(tmp_path,change):
    root,path,record=source(tmp_path)
    archived=move_to_archive(path,record)
    auth=archived.parent/'authorization.json'
    data=json.loads(auth.read_text(encoding='utf-8'))
    if change=='account':data['account_id']='test1'
    elif change=='run':data['run_id']='opt-'+'b'*32
    else:os.utime(archived,ns=(record['mtime_ns']+1_000_000_000,record['mtime_ns']+1_000_000_000))
    auth.write_text(json.dumps(data),encoding='utf-8')
    with pytest.raises(FileCaptureError):open_source(root,record,live=True)
    assert archived.exists() and not path.exists()
