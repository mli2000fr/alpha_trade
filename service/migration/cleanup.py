"""Delete explicitly inventoried T5.6 packages/jobs, never databases or models."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid

import psutil

from .locking import LOCK,os_guard,owner_state,MigrationLockError
from .storage import atomic_json,canonical,checked_directory

TERMINAL={'COMPLETE','FINISHED','FAILED','CANCELED','RESTORED_PAUSED','FAILED_ROLLED_BACK',
          'FAILED_ROLLBACK_INCOMPLETE','VERIFIED','RECOVERED_PAUSED'}


def read(path):
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):return {}


def _live_workers(roots):
    result=[]
    for process in psutil.process_iter(['pid','name','cmdline','cwd']):
        if process.pid==os.getpid():continue
        try:
            args=' '.join(process.info.get('cmdline') or [])
            cwd=process.info.get('cwd')
            is_worker=any(name in args for name in ('portable_migration.cli','service.migration.cli','restaurer.ps1'))
            inside=bool(cwd) and any(Path(cwd).resolve().is_relative_to(root) for root in roots)
            normalized=args.replace('\\','/').casefold()
            python_inside=inside and 'python' in str(process.info.get('name') or '').lower()
            if python_inside or is_worker and (inside or any(str(root).replace('\\','/').casefold() in normalized for root in roots)):
                result.append(process.pid)
        except psutil.NoSuchProcess:continue
    return result


def _inventory(root,*,workers=_live_workers):
    root=checked_directory(root)
    roots=[checked_directory(root/'backups'/name) for name in ('migrations','migration_jobs')]
    live=workers(roots)
    if live:raise MigrationLockError('MIGRATION_BUSY',live[0])
    lock=root/LOCK;receipt=read(lock) if lock.exists() else None
    if receipt is not None and owner_state(receipt)!='dead':
        raise MigrationLockError('LOCK_OWNER_UNVERIFIED' if owner_state(receipt)=='unknown' else 'MIGRATION_BUSY',receipt.get('pid'))
    entries=[];blocked=[]
    for parent in roots:
        if not parent.exists():continue
        for path in sorted(parent.iterdir()):
            if not path.is_dir() or path.is_symlink() or path.is_junction():
                blocked.append(str(path));continue
            path=checked_directory(path)
            if path.parent!=parent:raise ValueError('Dossier hors du périmètre T5.6')
            progress=read(path/'progress.json');job=read(path/'job.json')
            if not progress and not (path/'manifest.json').is_file():
                blocked.append(str(path));continue
            pid=progress.get('pid') or job.get('pid')
            if pid:
                identity=dict(pid=pid,started_at=progress.get('updated_at'))
                if progress.get('process_created_at') is not None:identity['process_created_at']=progress['process_created_at']
                if owner_state(identity)!='dead':raise MigrationLockError('LOCK_OWNER_UNVERIFIED',pid)
            elif progress.get('status') not in TERMINAL and job:
                raise MigrationLockError('LOCK_OWNER_UNVERIFIED')
            files=[]
            for current,dirs,names in os.walk(path,followlinks=False):
                for name in dirs+names:
                    item=Path(current)/name
                    if item.is_symlink() or item.is_junction():raise ValueError('Lien/jonction dans un package : nettoyage refusé')
                for name in names:
                    item=Path(current)/name;stat=item.stat()
                    files.append((item.relative_to(path).as_posix(),stat.st_size,stat.st_mtime_ns))
            entries.append(dict(path=str(path),parent=str(parent),kind=parent.name,status=progress.get('status','UNKNOWN'),
                files=len(files),bytes=sum(f[1] for f in files),inventory_sha256=hashlib.sha256(canonical(sorted(files))).hexdigest()))
    plan=dict(root=str(root),entries=entries,blocked=blocked,stale_lock=receipt,
        total_bytes=sum(e['bytes'] for e in entries),total_files=sum(e['files'] for e in entries))
    plan['fingerprint']=hashlib.sha256(canonical(plan)).hexdigest()
    return plan


def preview_cleanup(root):
    root=checked_directory(root)
    with os_guard(root):return _inventory(root)


def cleanup(root,*,approved_plan):
    root=checked_directory(root)
    with os_guard(root):
        plan=_inventory(root)
        if plan['fingerprint']!=approved_plan:raise ValueError('Le contenu a changé : refaire l’inventaire avant suppression')
        report_dir=root/'backups'/'operations_history';report_dir.mkdir(parents=True,exist_ok=True)
        report_path=report_dir/('migration-cleanup-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]+'.json')
        report=dict(status='CLEANING',started_at=datetime.now(timezone.utc).isoformat(),plan=plan,deleted=[],errors=[],lock_released=False)
        atomic_json(report_path,report)
        for entry in plan['entries']:
            path=checked_directory(entry['path']);parent=checked_directory(entry['parent'])
            if parent not in (root/'backups/migrations',root/'backups/migration_jobs') or path.parent!=parent:
                raise ValueError('Cible de suppression hors des sauvegardes T5.6')
            try:
                shutil.rmtree(path)
                report['deleted'].append(entry['path'])
            except OSError as exc:report['errors'].append(dict(path=str(path),error_type=type(exc).__name__))
            atomic_json(report_path,report)
        if plan['stale_lock'] is not None:
            # Keep the receipt in the cleanup audit, then remove only this dead owner.
            path=root/LOCK;current=read(path)
            if current==plan['stale_lock'] and owner_state(current)=='dead':
                path.unlink();report['lock_released']=True
        report.update(status='CLEANED' if not report['errors'] else 'PARTIAL',finished_at=datetime.now(timezone.utc).isoformat())
        atomic_json(report_path,report)
        return dict(status=report['status'],deleted=report['deleted'],errors=report['errors'],
            lock_released=report['lock_released'],bytes_removed=sum(e['bytes'] for e in plan['entries'] if e['path'] in report['deleted']),
            audit_path=str(report_path))
