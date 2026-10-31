"""Detached T5.6 workers. Passwords only in an anonymous stdin pipe."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from service.migration.storage import atomic_json
from service.migration.locking import os_guard,owner_state

PROJECT_ROOT=Path(__file__).resolve().parents[2]


def build_restore_command(backup_dir):
    """PowerShell single quotes prevent expansion/injection in a copied path."""
    value=str(backup_dir).strip()
    if not value or any(c in value for c in ('\r','\n','\x00')):raise ValueError('Répertoire de sauvegarde invalide')
    script=str(Path(value).resolve()/'restaurer.ps1')
    return "& '"+script.replace("'","''")+"' -Action restore"


def start_job(request,*,job_parent=None):
    # Metadata inventory neither claims a migration nor mutates its packages.
    # It remains available while a long database backup holds the project guard.
    if request.get('action')=='inventory':return _start_job(request,job_parent=job_parent)
    with os_guard(PROJECT_ROOT):
        return _start_job(request,job_parent=job_parent)


def _start_job(request,*,job_parent=None):
    parent=Path(job_parent or PROJECT_ROOT/'backups'/'migration_jobs').resolve()
    target=Path(request.get('target',parent.parent/'unused')).resolve()
    if request['action'] in ('restore','recover') and parent.is_relative_to(target):
        raise ValueError('Les journaux doivent être hors du projet à remplacer')
    job=parent/uuid.uuid4().hex;job.mkdir(parents=True,mode=0o700)
    runtime=job/'runtime';tool=runtime/'portable_migration';tool.mkdir(parents=True)
    for path in (PROJECT_ROOT/'service'/'migration').glob('*.py'):shutil.copy2(path,tool/path.name)
    shutil.copy2(PROJECT_ROOT/'service'/'migration'/'restaurer.ps1',tool/'restaurer.ps1')
    command=[sys.executable,'-X','utf8','-m','portable_migration.cli','--request-stdin','--job-dir',str(job)]
    kwargs=dict(cwd=runtime,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if os.name=='nt':kwargs['creationflags']=subprocess.CREATE_NO_WINDOW|subprocess.DETACHED_PROCESS
    else:kwargs['start_new_session']=True
    atomic_json(job/'progress.json',dict(status='STARTING',action=request['action']))
    try:process=subprocess.Popen(command,**kwargs)
    except OSError:
        atomic_json(job/'progress.json',dict(status='FAILED',error_type='WORKER_START_FAILED'));raise
    try:
        process.stdin.write(json.dumps(request,ensure_ascii=False).encode('utf-8'));process.stdin.close()
    except BaseException:
        process.kill();process.wait();raise
    atomic_json(job/'job.json',dict(pid=process.pid,action=request['action'],
        output=request.get('output'),report_dir=request.get('report_dir')))
    return str(job)


def job_state(path):
    path=Path(path)
    def read(name):
        try:return json.loads((path/name).read_text(encoding='utf-8'))
        except (OSError,ValueError):return None
    state=dict(job=str(path),progress=read('progress.json'),result=read('result.json'),tracking=read('tracking.json'))
    state['events']=read_events(path/'events.jsonl')
    record=read('job.json') or {}
    if record.get('output'):state['operation_progress']=read_external(Path(record['output'])/'progress.json')
    if record.get('report_dir'):state['operation_progress']=read_external(Path(record['report_dir'])/'progress.json')
    if (state['progress'] or {}).get('status') in ('STARTING','STARTED','WAITING_FOR_TARGET_STOP','BUILDING_PYTHON'):
        progress=state['progress'] or {}
        pid=progress.get('pid') or record.get('pid')
        receipt=dict(pid=pid,started_at=progress.get('updated_at'))
        if progress.get('process_created_at') is not None:receipt['process_created_at']=progress['process_created_at']
        if pid and owner_state(receipt)=='dead':state['worker_ended_without_result']=True
    return state


def read_events(path,limit=150):
    """Bounded tail: do not reread multi-hour logs on every UI refresh."""
    try:
        with Path(path).open('rb') as stream:
            stream.seek(0,2);size=stream.tell();stream.seek(max(0,size-128*1024))
            data=stream.read()
        lines=data.decode('utf-8',errors='replace').splitlines()
        result=[]
        for line in lines[-limit:]:
            try:result.append(json.loads(line))
            except ValueError:continue
        return result
    except OSError:return []


def read_external(path):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return None


def catalog(parent):
    root=Path(parent)
    if not root.is_dir():return []
    result=[]
    for path in sorted(root.iterdir(),reverse=True):
        if not path.is_dir():continue
        progress=read_external(path/'progress.json')
        if progress is not None:result.append(dict(folder=str(path),**progress))
    return result
