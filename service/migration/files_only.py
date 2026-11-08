"""Standalone file restore: never construct a database adapter or import SQL."""
from contextlib import nullcontext
import hashlib
from pathlib import Path
import shutil
import uuid

from . import engine, inventory
from .storage import atomic_json, canonical, checked_directory, open_manifest, safe_path, sha_file
from .tracking import emit


def file_payload(payload):
    """Retain only file packages; preserve local dotenv connection settings."""
    packages=[]
    for package in payload['packages']:
        if package['kind']!='files':continue
        for row in package['files']:
            path=Path(row['path'])
            if path.parts[0] in inventory.SKIP_ROOT or path.parts[0].startswith('.venv'):
                raise ValueError('Package de fichiers contenant un répertoire local protégé')
        packages.append(package)
    if not packages:raise ValueError('Aucun package de fichiers dans cette sauvegarde')
    return dict(payload,packages=packages)


def inspect_files_only(folder,target,password,*,quiet=inventory.quiescent,on_progress=None,verify_packages=True):
    folder=Path(folder).resolve();target=checked_directory(target)
    if target==Path(target.anchor) or folder==target or folder.is_relative_to(target):
        raise ValueError('La sauvegarde doit être hors de la destination à remplacer')
    if target.is_symlink() or target.is_junction():raise ValueError('Destination lien/jonction interdite')
    payload=engine.verify(folder,password,on_progress=on_progress,files_only=True) if verify_packages else open_manifest(folder/'manifest.json',password)
    payload=file_payload(payload)
    names=[f['path'] for p in payload['packages'] for f in p['files']]
    # Dotenv files are connection configuration; never replace them in this mode.
    managed=sorted({Path(n).parts[0] for n in names if not (len(Path(n).parts)==1 and Path(n).name.startswith('.env'))})
    existing={}
    for name in managed:
        path=safe_path(target,name)
        if path.is_symlink() or path.is_junction():raise ValueError('Lien/jonction cible interdit')
        if path.exists():
            st=path.stat();existing[name]=dict(size=st.st_size,mtime_ns=st.st_mtime_ns)
    plan=dict(mode='FILES_ONLY',backup_id=payload['id'],target_root=str(target),
        manifest_sha256=sha_file(folder/'manifest.json'),managed_roots=managed,
        replace_roots=sorted(existing),databases_touched=False,environment_touched=False,
        local_dotenv_preserved=True,existing_venv_preserved=True,services_auto_restart=False,
        active_processes=quiet(target,allow_ui=False),
        estimated_staging_bytes=sum(f['size'] for p in payload['packages'] for f in p['files']))
    stable={k:v for k,v in plan.items() if k!='active_processes'}
    plan['fingerprint']=hashlib.sha256(canonical(dict(stable,existing_files_state=existing))).hexdigest()
    emit(on_progress,'RESTORE_PREFLIGHT')
    return plan


def restore_files_only(folder,target,password,report_dir,*,approved_plan,
                       quiet=inventory.quiescent,cancel=None,on_progress=None,guard=True):
    folder=Path(folder).resolve();target=checked_directory(target);reports=checked_directory(report_dir)
    if reports==target or reports.is_relative_to(target):raise ValueError('Le journal doit être hors du projet cible')
    plan=inspect_files_only(folder,target,password,quiet=quiet,verify_packages=False)
    if plan['fingerprint']!=approved_plan:raise ValueError('Plan fichiers changé : refaire la prévisualisation')
    if plan['active_processes']:raise ValueError('Attendre la fin des tâches du PC cible')
    payload=file_payload(engine.verify(folder,password,cancel=cancel,on_progress=on_progress,files_only=True))
    target.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(target.parent).free<plan['estimated_staging_bytes']*1.2:
        raise ValueError('Espace insuffisant pour préparer les fichiers')
    reports.mkdir(parents=True,exist_ok=False,mode=0o700)
    target.mkdir(parents=True,exist_ok=True)
    stage=target.parent/('.alpha-migration-stage-'+uuid.uuid4().hex);stage.mkdir(mode=0o700)
    previous=target.parent/('.alpha-migration-previous-'+uuid.uuid4().hex);previous.mkdir(mode=0o700)
    failed=target.parent/('.alpha-migration-failed-'+uuid.uuid4().hex)
    atomic_json(reports/'local-directories.json',dict(staging=str(stage),previous=str(previous),failed=str(failed)))
    moves=[]
    old_marker=(target/engine.PENDING).read_bytes() if (target/engine.PENDING).exists() else None
    try:
        with (engine.maintenance(target,quiet,allow_ui=False,on_progress=on_progress) if guard else nullcontext()), engine.observe(target,quiet,allow_ui=False) as observed:
            def check():observed();engine.check_cancel(cancel)
            fresh=inspect_files_only(folder,target,password,quiet=quiet,verify_packages=False)
            if fresh['fingerprint']!=approved_plan:raise ValueError('Projet cible changé : refaire la prévisualisation')
            emit(on_progress,'STAGING')
            engine.extract_files(folder,payload,stage,password,check,on_progress)
            engine.model_checks(stage);check()
            emit(on_progress,'FILE_REPLACEMENT')
            engine.install_managed_roots(target,stage,previous,plan['managed_roots'],moves,check,on_progress)
            # No environment.write_user, SQL validation, lock reset or SQL import here.
            atomic_json(target/engine.PENDING,dict(reason='FILES_ONLY_REVIEW_REQUIRED',
                report_dir=str(reports),backup_id=payload['id'],restored_at=engine.utc()))
            result=dict(status='FILES_ONLY_RESTORED',mode='FILES_ONLY',backup_id=payload['id'],
                databases_touched=False,environment_touched=False,local_dotenv_preserved=True,
                existing_venv_preserved=True,services_auto_restart=False,
                local_previous_files=str(previous),local_staging=str(stage),managed_roots=plan['managed_roots'])
            atomic_json(reports/'restore-report.json',result)
            atomic_json(reports/'progress.json',dict(status='FINISHED',mode='FILES_ONLY',
                databases_touched=False,environment_touched=False,finished_at=engine.utc()))
            emit(on_progress,'FINISHED')
            return result
    except BaseException:
        emit(on_progress,'FILE_ROLLBACK')
        try:
            engine.rollback_managed_roots(moves,failed)
            if old_marker is None:(target/engine.PENDING).unlink(missing_ok=True)
            else:(target/engine.PENDING).write_bytes(old_marker)
            status='FAILED_ROLLED_BACK'
        except BaseException:
            status='FILES_ROLLBACK_INCOMPLETE'
        atomic_json(reports/'progress.json',dict(status=status,databases_touched=False,environment_touched=False))
        emit(on_progress,status)
        raise
