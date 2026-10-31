"""Full portable export/restore. No provider calls, orders or schema upgrades.

Restore is deliberately all-or-replace for the three schemas. Files are staged
before any destructive operation; an encrypted preimage precedes replacement.
"""
from contextlib import contextmanager
from datetime import datetime,timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import tarfile
import threading
import uuid

from . import environment,inventory
from .mysql import DATABASES
from .tracking import emit,CountingWriter
from .locking import LOCK,migration_lock,MigrationLockError
from .storage import (BLOCK,atomic_json,canonical,decrypted_input,encrypted_output,open_manifest,
                      safe_path,seal_manifest,sha_file,checked_directory)

PENDING='.alpha_trade_restore_pending.json'
PROTOCOL='alpha-trade-migration-v1'


def utc():return datetime.now(timezone.utc).isoformat()


def check_cancel(cancel):
    if cancel and cancel():raise InterruptedError('Opération interrompue à un point sûr')


@contextmanager
def maintenance(root,quiet,*,allow_ui,on_progress=None):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
    with migration_lock(root) as recovered:
        if recovered:emit(on_progress,'LOCK_RECOVERED',owner_pid=recovered['owner_pid'])
        active=quiet(root,allow_ui=allow_ui) if quiet else []
        if active:raise ValueError('Arrêter les tâches/processus du projet avant migration : '+', '.join(str(p.get('pid',p.get('task'))) for p in active))
        yield


@contextmanager
def observe(root,quiet,*,allow_ui):
    """Abort this migration on new workers; never stop/block operational code."""
    stopped=threading.Event();problems=[]
    def poll():
        while not stopped.wait(2):
            try:
                scanner=inventory.running_processes if quiet is inventory.quiescent else quiet
                if scanner(root,allow_ui=allow_ui):problems.append(True);return
            except Exception:problems.append(True);return
    thread=threading.Thread(target=poll,daemon=True);thread.start()
    def check():
        if problems:raise ValueError('Activité concurrente détectée ; migration interrompue')
    try:yield check
    finally:stopped.set();thread.join(timeout=35)


class HashReader:
    def __init__(self,stream,on_bytes=None):self.stream=stream;self.digest=hashlib.sha256();self.on_bytes=on_bytes
    def read(self,n=-1):
        value=self.stream.read(n);self.digest.update(value)
        if self.on_bytes:self.on_bytes(len(value))
        return value


def pack_files(root,folder,label,files,password,limit,cancel,*,live=False,on_progress=None):
    records=[];processed=0
    def counted(n):
        nonlocal processed
        processed+=n;emit(on_progress,processed_bytes=processed)
    with encrypted_output(folder,label,password,limit) as (encrypted,parts):
        with tarfile.open(fileobj=encrypted,mode='w|gz') as archive:
            for index,record in enumerate(files):
                check_cancel(cancel)
                emit(on_progress,item=record['path'],files_done=index,files_total=len(files))
                path=safe_path(root,record['path'])
                with path.open('rb') as stream:
                    before=os.fstat(stream.fileno())
                    if not live and (before.st_size,before.st_mtime_ns)!=(record['size'],record['mtime_ns']):raise ValueError('Fichier modifié pendant la sauvegarde')
                    info=tarfile.TarInfo(record['path']);info.size=before.st_size;info.mode=0o600;info.mtime=int(before.st_mtime)
                    hashed=HashReader(stream,counted);archive.addfile(info,hashed)
                    after=os.fstat(stream.fileno())
                append_log=live and Path(record['path']).parts[0] in ('log','logs') and after.st_size>=before.st_size
                if not append_log and (after.st_size,after.st_mtime_ns)!=(before.st_size,before.st_mtime_ns):raise ValueError('Fichier modifié pendant la sauvegarde')
                records.append(dict(path=record['path'],size=info.size,sha256=hashed.digest.hexdigest()))
                emit(on_progress,files_done=index+1)
    emit(on_progress,files_done=len(files),checkpoint=True)
    return dict(label=label,parts=parts,files=records,kind='files')


def write_private_json(folder,label,value,password,limit):
    with encrypted_output(folder,label,password,limit) as (stream,parts):stream.write(canonical(value))
    return dict(label=label,parts=parts,kind='json')


def export(root,output,password,db,*,quiet=inventory.quiescent,cancel=None,versions=inventory.installed_versions,
           captured=None,limit=2*1024**3,quiescent_confirmed=False,guard=True,source_mode='online',on_progress=None):
    root=Path(root).resolve();output=Path(output).resolve()
    if source_mode not in ('online','quiescent'):raise ValueError('Mode de sauvegarde inconnu')
    online=source_mode=='online'
    if not online and not quiescent_confirmed:raise ValueError('Confirmer la fermeture des autres tâches avant la sauvegarde')
    if output==root or output.is_relative_to(root) and not output.is_relative_to(root/'backups'):
        raise ValueError('Destination requise hors du projet ou dans son dossier backups')
    if limit<1024:raise ValueError('Taille de partie trop petite')
    try:output.mkdir(parents=True,exist_ok=False)
    except FileExistsError as exc:raise ValueError('Le répertoire de sauvegarde existe déjà : choisir un nouveau répertoire, sans écraser la tentative précédente.') from exc
    def progress(phase,**extra):
        atomic_json(output/'progress.json',dict(status='RUNNING',phase=phase,updated_at=utc(),**extra))
        emit(on_progress,phase,**extra)
    @contextmanager
    def noop():yield
    try:
        progress('ONLINE_BACKUP' if online else 'QUIESCENCE')
        scanner=(lambda *a,**k:[]) if online else quiet
        with (maintenance(root,None if online else quiet,allow_ui=True,on_progress=on_progress) if guard else noop()), observe(root,scanner,allow_ui=True) as observed:
            original_cancel=cancel
            def cancel():
                observed()
                return original_cancel() if original_cancel else False
            model_checks(root)
            entries=inventory.scan(root);names=[r['path'] for records in entries.values() for r in records]
            env=captured if captured is not None else environment.capture(root,names)
            metadata={};packages=[]
            for index,name in enumerate(DATABASES):
                check_cancel(cancel);progress('DATABASE_INVENTORY',database=name,completed=index,total=3)
                metadata[name]=db.inspect(name,count_rows=not online)
            for index,name in enumerate(DATABASES):
                progress('DATABASE_EXPORT',database=name,completed=index,total=3)
                folder=output/'donnees'/name;label=name+'.sql.gz'
                started=utc()
                with encrypted_output(folder,label,password,limit) as (stream,parts):
                    db.dump(name,CountingWriter(stream,on_progress),lambda:check_cancel(cancel))
                packages.append(dict(kind='sql',database=name,folder=f'donnees/{name}',label=label,parts=parts,
                    export_started_at=started,export_finished_at=utc()))
                emit(on_progress,completed=index+1,checkpoint=True)
            for index,(name,files) in enumerate(entries.items()):
                progress('FILES_EXPORT',package=name,files_total=len(files),total_bytes=sum(f['size'] for f in files),part_index=index,parts_total=len(entries))
                package=pack_files(root,output/name,name+'.tar.gz',files,password,limit,cancel,live=online,on_progress=on_progress)
                packages.append(dict(package,folder=name))
            progress('ENVIRONMENT_EXPORT')
            packages.append(dict(write_private_json(output/'environnement','variables.enc',env,password,limit),
                folder='environnement',role='environment'))
            private=dict(databases=metadata,versions=versions(root))
            packages.append(dict(write_private_json(output/'configuration','runtime.enc',private,password,limit),
                folder='configuration',role='runtime'))
            # Online exports intentionally allow DML on the source. Schema drift
            # fails validation. Per-schema snapshots are not globally atomic.
            for index,name in enumerate(DATABASES):
                progress('DATABASE_RECHECK',database=name,completed=index,total=3)
                if db.public_metadata(db.inspect(name,count_rows=not online))!=db.public_metadata(metadata[name]):
                    raise ValueError('Base modifiée pendant la sauvegarde : '+name)
            if not online and quiet(root,allow_ui=True):raise ValueError('Un nouveau processus du projet est apparu')
            payload=dict(protocol=PROTOCOL,id=uuid.uuid4().hex,status='COMPLETE',created_at=utc(),
                source_root=str(root),packages=packages,databases={n:db.public_metadata(m) for n,m in metadata.items()},
                environment_variables=env['variables'],runtime=dict(python=private['versions']['python'],
                system=private['versions']['system'],machine=private['versions']['machine']),
                exclusions=sorted(inventory.SKIP_ROOT),services_auto_restart=False)
            payload.update(source_mode=source_mode,cross_database_atomic=False,
                row_counts_authoritative=not online,source_services_unchanged=True)
            payload['dependency_review_count']=private['versions'].get('unportable_requirement_count',0)
            if guard:payload['portable_files']=install_portable_tools(output)
            atomic_json(output/'manifest.json',seal_manifest(payload,password))
            progress('VERIFYING')
            verify(output,password,cancel=cancel,_in_progress=True,on_progress=on_progress)
            check_cancel(cancel)
            atomic_json(output/'progress.json',dict(status='COMPLETE',finished_at=utc(),packages=len(packages)))
            emit(on_progress,'COMPLETE')
            return payload
    except BaseException as exc:
        # Error text can contain secrets from providers/SQL. Keep only a bounded
        # local operation class; UI shows typed validation errors separately.
        atomic_json(output/'progress.json',dict(status='CANCELED' if isinstance(exc,InterruptedError) else 'FAILED',
            error_type=type(exc).__name__,finished_at=utc()))
        if (output/'manifest.json').exists():os.replace(output/'manifest.json',output/'manifest.incomplete.json')
        extra=dict(error_code=exc.code,owner_pid=exc.owner_pid) if isinstance(exc,MigrationLockError) else {}
        emit(on_progress,'CANCELED' if isinstance(exc,InterruptedError) else 'FAILED',**extra)
        raise


def verify(folder,password,*,cancel=None,_in_progress=False,on_progress=None):
    emit(on_progress,'VERIFYING')
    folder=Path(folder).resolve();payload=open_manifest(folder/'manifest.json',password)
    if not _in_progress:
        progress=json.loads((folder/'progress.json').read_text(encoding='utf-8'))
        if progress.get('status')!='COMPLETE':raise ValueError('Sauvegarde non finalisée')
    if payload.get('status')!='COMPLETE' or set(payload.get('databases',{}))!=set(DATABASES):raise ValueError('Sauvegarde complète des trois bases requise')
    sql=[p['database'] for p in payload['packages'] if p['kind']=='sql']
    if sorted(sql)!=sorted(DATABASES):raise ValueError('Packages SQL manquants ou dupliqués')
    seen=set()
    for item in payload.get('portable_files',[]):
        if sha_file(safe_path(folder,item['path']))!=item['sha256']:raise ValueError('Outil portable altéré')
    for index,package in enumerate(payload['packages']):
        check_cancel(cancel)
        emit(on_progress,'VERIFYING',package=package['folder'],part_index=index,parts_total=len(payload['packages']),
            total_bytes=sum(f['size'] for f in package.get('files',[])) or None,processed_bytes=0)
        processed=0
        def counted(n):
            nonlocal processed
            processed+=n;emit(on_progress,processed_bytes=processed)
        location=safe_path(folder,package['folder'])
        with decrypted_input(location,package,password) as stream:
            if package['kind']=='files':
                declared={f['path']:f for f in package['files']};actual=set()
                with tarfile.open(fileobj=stream,mode='r|gz') as archive:
                    for member in archive:
                        check_cancel(cancel)
                        emit(on_progress,item=member.name)
                        safe_path(folder,member.name)
                        if not member.isfile() or member.name not in declared:raise ValueError('Entrée d’archive interdite')
                        normalized=member.name.casefold()
                        if normalized in seen:raise ValueError('Fichier dupliqué entre packages')
                        seen.add(normalized);actual.add(member.name)
                        record=declared[member.name]
                        if record['size']!=member.size:raise ValueError('Taille de fichier incohérente')
                        hashed=HashReader(archive.extractfile(member),counted)
                        while hashed.read(BLOCK):check_cancel(cancel)
                        if hashed.digest.hexdigest()!=record['sha256']:raise ValueError('Empreinte de fichier incorrecte')
                if actual!=set(declared):raise ValueError('Fichiers manquants dans une archive')
            elif package['kind']=='sql':
                with gzip.GzipFile(fileobj=stream,mode='rb') as raw:
                    while chunk:=raw.read(BLOCK):check_cancel(cancel);counted(len(chunk))
            elif package['kind']=='json':json.load(stream)
            else:raise ValueError('Type de package inconnu')
    return payload


def private_json(folder,payload,role,password):
    packages=[p for p in payload['packages'] if p.get('role')==role]
    if len(packages)!=1:raise ValueError('Métadonnées privées manquantes')
    package=packages[0]
    with decrypted_input(safe_path(folder,package['folder']),package,password) as stream:return json.load(stream)


def extract_files(folder,payload,target,password,cancel=None,on_progress=None):
    processed=0;done=0
    files=[f for p in payload['packages'] if p['kind']=='files' for f in p['files']]
    emit(on_progress,total_bytes=sum(f['size'] for f in files),files_total=len(files),processed_bytes=0,files_done=0)
    for package in payload['packages']:
        if package['kind']!='files':continue
        with decrypted_input(safe_path(folder,package['folder']),package,password) as stream:
            with tarfile.open(fileobj=stream,mode='r|gz') as archive:
                for member in archive:
                    check_cancel(cancel)
                    emit(on_progress,item=member.name)
                    if not member.isfile():raise ValueError('Lien/répertoire d’archive non autorisé')
                    path=safe_path(target,member.name);path.parent.mkdir(parents=True,exist_ok=True)
                    with path.open('xb') as out:
                        source=archive.extractfile(member)
                        while block:=source.read(BLOCK):
                            check_cancel(cancel);out.write(block);processed+=len(block)
                            emit(on_progress,processed_bytes=processed)
                    os.utime(path,(member.mtime,member.mtime))
                    done+=1;emit(on_progress,files_done=done)


def model_checks(stage):
    # File hashes were verified for ALL models. Additionally check path-model
    # frozen fingerprints/checkpoints without unpickling untrusted models.
    for root in (Path(stage)/'artifacts').glob('models*'):
        for path in root.glob('*/oracle_path/protocol.json'):
            protocol=json.loads(path.read_text(encoding='utf-8'));fingerprint=protocol.pop('fingerprint',None)
            if hashlib.sha256(json.dumps(protocol,sort_keys=True,default=str).encode()).hexdigest()!=fingerprint:
                raise ValueError('Contrat de modèle corrompu')
            for checkpoint in path.parent.glob('folds/*/done.json'):
                done=json.loads(checkpoint.read_text(encoding='utf-8'))
                for name,digest in done.get('files',{}).items():
                    if sha_file(safe_path(checkpoint.parent,name))!=digest:raise ValueError('Poids de modèle corrompus')


def inspect_restore(folder,target,password,db,*,quiet=inventory.quiescent,on_progress=None):
    folder=Path(folder).resolve();target=checked_directory(target)
    if target==Path(target.anchor) or folder==target or folder.is_relative_to(target):
        raise ValueError('La sauvegarde doit être hors de la destination à remplacer')
    if target.is_symlink() or target.is_junction():raise ValueError('Destination lien/jonction interdite')
    if (target/'.venv').exists():raise ValueError('Renommer manuellement le .venv existant avant restauration ; il ne sera pas remplacé')
    payload=verify(folder,password,on_progress=on_progress)
    emit(on_progress,'RESTORE_PREFLIGHT')
    runtime=private_json(folder,payload,'runtime',password)
    if runtime['versions']['python'].split('.')[:2]!=platform.python_version().split('.')[:2]:
        raise ValueError('Installer la même version majeure.mineure de Python que la source')
    if runtime['versions']['system']!=platform.system() or runtime['versions']['machine']!=platform.machine():
        raise ValueError('Système et architecture Python identiques à la source requis')
    db.check_destination(runtime['databases'])
    existing={name:db.inspect(name,allow_missing=True) for name in DATABASES}
    env=private_json(folder,payload,'environment',password)
    names=sorted(env['values']);present=environment.registry_values('User')
    managed=sorted({Path(f['path']).parts[0] for p in payload['packages'] if p['kind']=='files' for f in p['files']})
    # Old model trees / stale app archives must not survive a mirror restore.
    managed=sorted(set(managed)|({'artifacts'} if (target/'artifacts').exists() else set()))
    plan=dict(backup_id=payload['id'],target_root=str(target),target_database_names=list(DATABASES),
        existing_databases=[n for n,m in existing.items() if m is not None],
        replace_roots=[n for n in managed if (target/n).exists()],managed_roots=managed,
        environment_names=names,environment_conflicts=sorted(set(names)&set(present)),
        active_processes=quiet(target,allow_ui=False),services_auto_restart=False,
        estimated_staging_bytes=sum(f['size'] for p in payload['packages'] if p['kind']=='files' for f in p['files']))
    stable={k:v for k,v in plan.items() if k!='active_processes'}
    stable['existing_database_state']={n:db.public_metadata(m) if m else None for n,m in existing.items()}
    plan['fingerprint']=hashlib.sha256(canonical(stable)).hexdigest()
    return plan


def sql_restore(folder,payload,runtime,password,db,check,on_progress=None):
    for name in DATABASES:
        emit(on_progress,'DATABASE_REPLACEMENT',database=name,item='Préparation du schéma',completed=0,total=3)
        db.recreate(name,runtime['databases'][name])
    for package in payload['packages']:
        if package['kind']!='sql':continue
        emit(on_progress,'DATABASE_REPLACEMENT',database=package['database'],completed=DATABASES.index(package['database']),total=3,processed_bytes=0)
        check()
        with decrypted_input(safe_path(folder,package['folder']),package,password) as stream:
            db.load(package['database'],stream,check)
        emit(on_progress,completed=DATABASES.index(package['database'])+1,checkpoint=True)
    for index,name in enumerate(DATABASES):
        emit(on_progress,'DATABASE_VALIDATION',database=name,completed=index,total=3)
        db.load_events_disabled(name,runtime['databases'][name].get('event_definitions',[]))
        db.validate(name,runtime['databases'][name])
        emit(on_progress,completed=index+1,checkpoint=True)


def restore(folder,target,password,db,report_dir,*,approved_plan,quiet=inventory.quiescent,
            env_writer=environment.write_user,env_reader=lambda:environment.registry_values('User'),
            cancel=None,install_environment=True,guard=True,on_progress=None):
    folder=Path(folder).resolve();target=checked_directory(target);reports=checked_directory(report_dir)
    if reports==target or reports.is_relative_to(target):raise ValueError('Le journal de restauration doit être hors destination')
    plan=inspect_restore(folder,target,password,db,quiet=quiet,on_progress=on_progress)
    if plan['fingerprint']!=approved_plan:raise ValueError('Plan de restauration changé : refaire la prévisualisation')
    if plan['active_processes']:raise ValueError('Fermer les processus du projet cible avant restauration')
    reports.mkdir(parents=True,exist_ok=False,mode=0o700)
    target.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(target.parent).free < plan['estimated_staging_bytes']*1.2:
        raise ValueError('Espace insuffisant pour préparer la restauration')
    payload=open_manifest(folder/'manifest.json',password);runtime=private_json(folder,payload,'runtime',password)
    exported_env=private_json(folder,payload,'environment',password)
    target.mkdir(parents=True,exist_ok=True)
    # Same-volume staging/quarantine keeps os.replace valid even when the
    # encrypted backup and its reports live on an external USB/network drive.
    stage=target.parent/('.alpha-migration-stage-'+uuid.uuid4().hex);stage.mkdir(mode=0o700)
    old_files=target.parent/('.alpha-migration-previous-'+uuid.uuid4().hex);old_files.mkdir(mode=0o700)
    failed_files=target.parent/('.alpha-migration-failed-'+uuid.uuid4().hex)
    preimage=reports/'existant-chiffre'
    atomic_json(reports/'local-directories.json',dict(staging=str(stage),previous=str(old_files),failed=str(failed_files)))
    old_env=env_reader();changed=[];moves=[];database_started=False;env_started=False
    def check():check_cancel(cancel)
    def progress(phase,**extra):
        atomic_json(reports/'progress.json',dict(status='RESTORING',phase=phase,updated_at=utc()))
        emit(on_progress,phase,**extra)
    @contextmanager
    def noop():yield
    try:
        with (maintenance(target,quiet,allow_ui=False,on_progress=on_progress) if guard else noop()), observe(target,quiet,allow_ui=False) as observed:
            def check():
                observed();check_cancel(cancel)
            progress('STAGING');extract_files(folder,payload,stage,password,cancel,on_progress);model_checks(stage)
            if shutil.disk_usage(reports).free < plan['estimated_staging_bytes']*.05:
                raise ValueError('Espace de sécurité insuffisant après extraction')
            progress('BACKUP_EXISTING')
            # A full encrypted preimage of existing schemas AND managed files
            # precedes the first DROP. Missing schemas are explicitly recorded.
            old_meta={n:db.inspect(n,allow_missing=True) for n in DATABASES}
            preimage.mkdir(mode=0o700);old_packages=[]
            old_file_packages=[]
            old_entries=inventory.scan(target)
            for index,(name,records) in enumerate(old_entries.items()):
                progress('BACKUP_EXISTING',package=name,part_index=index,parts_total=len(old_entries)+3,
                    total_bytes=sum(f['size'] for f in records),files_total=len(records))
                package=pack_files(target,preimage/('files-'+name),name+'.tar.gz',records,password,2*1024**3,cancel,on_progress=on_progress)
                old_file_packages.append(dict(package,folder='files-'+name))
            for index,(name,meta) in enumerate(old_meta.items()):
                if meta is None:continue
                progress('BACKUP_EXISTING',database=name,part_index=len(old_entries)+index,parts_total=len(old_entries)+3,processed_bytes=0)
                with encrypted_output(preimage/name,name+'.sql.gz',password) as (stream,parts):db.dump(name,CountingWriter(stream,on_progress),check)
                old_packages.append(dict(database=name,folder=name,label=name+'.sql.gz',parts=parts))
            # Store original user variables encrypted, even when not exporting all
            # application names. This is rollback material, never public JSON.
            rollback_names=set(exported_env['values'])|{prefix+suffix for prefix in ('DB_HOST','LOGIN_DB','PASSWORD_DB') for suffix in ('','_FR','_CN')}
            previous_environment=write_private_json(preimage,'previous-environment.enc',{n:old_env.get(n) for n in rollback_names},password,2*1024**3)
            recovery=write_private_json(preimage,'recovery.enc',dict(databases=old_meta,environment=previous_environment,
                packages=old_packages,file_packages=old_file_packages,managed_roots=plan['managed_roots'],
                target=str(target)),password,2*1024**3)
            atomic_json(preimage/'recovery.json',seal_manifest(dict(protocol=PROTOCOL,recovery=recovery),password))
            if quiet(target,allow_ui=False):raise ValueError('Une tâche cible est apparue avant remplacement')
            progress('DATABASE_REPLACEMENT');check();database_started=True
            sql_restore(folder,payload,runtime,password,db,check,on_progress)
            progress('FILE_REPLACEMENT');check()
            for index,name in enumerate(plan['managed_roots']):
                emit(on_progress,'FILE_REPLACEMENT',item=name,completed=index,total=len(plan['managed_roots']))
                destination=safe_path(target,name);incoming=safe_path(stage,name)
                previous=safe_path(old_files,name)
                if destination.exists():
                    previous.parent.mkdir(parents=True,exist_ok=True);os.replace(destination,previous)
                moves.append((destination,previous,incoming.exists()))
                if incoming.exists():os.replace(incoming,destination)
            values=environment.rebase(exported_env['values'],payload['source_root'],target)
            # Connections selected by the operator remain authoritative on the
            # new PC, instead of restoring old passwords pointing elsewhere.
            for dbname,suffix in [('alpha_trade',''),('alpha_trade_fr','_FR'),('alpha_trade_cn','_CN')]:
                c=db.connections[dbname]
                values.update({'DB_HOST'+suffix:c.host,'LOGIN_DB'+suffix:c.user,'PASSWORD_DB'+suffix:c.password,
                    'DB_NAME'+suffix:dbname})
            if install_environment:
                progress('USER_ENVIRONMENT');env_started=True;changed=list(values);env_writer(values)
            progress('FINALIZING');db.reset_runtime_locks()
            sanitize_local_status(target)
            atomic_json(target/PENDING,dict(protocol=PROTOCOL,backup_id=payload['id'],restored_at=utc(),
                report_dir=str(reports),reason='VALIDATION_AND_MANUAL_RESUME_REQUIRED'))
            atomic_json(reports/'restore-report.json',dict(status='RESTORED_PAUSED',backup_id=payload['id'],
                databases=list(DATABASES),validated=True,environment_names=sorted(values) if install_environment else [],
                events_restored_disabled=True,services_auto_restart=False,preimage=str(preimage),
                recovery_command='python -m portable_migration.cli recover',
                local_previous_files=str(old_files),local_staging=str(stage),
                dependency_review_count=runtime['versions'].get('unportable_requirement_count',0),
                external_path_variables=[v['name'] for v in exported_env['variables'] if v.get('external_path')],
                source_requirements=runtime['versions']['requirements'],python=runtime['versions']['python']))
            atomic_json(reports/'progress.json',dict(status='RESTORED_PAUSED',finished_at=utc()))
            emit(on_progress,'RESTORED_PAUSED')
    except BaseException as exc:
        # Rollback uses preimages, not the source migration. Never label a partial
        # restoration completed, and never restart a watcher after a failure.
        ok=True
        emit(on_progress,'ROLLBACK')
        try:
            if env_started:env_writer({name:old_env.get(name) for name in changed})
            for destination,previous,installed in reversed(moves):
                if destination.exists():
                    # Keep failed incoming files for diagnosis, no recursive delete.
                    failed=failed_files/destination.name;failed.parent.mkdir(exist_ok=True,mode=0o700)
                    os.replace(destination,failed)
                if previous.exists():os.replace(previous,destination)
            if database_started:
                for index,(name,meta) in enumerate(old_meta.items()):
                    emit(on_progress,'ROLLBACK',database=name,completed=index,total=3)
                    if meta is None:db.drop(name)
                    else:
                        db.recreate(name,meta)
                        package=next(p for p in old_packages if p['database']==name)
                        with decrypted_input(preimage/name,package,password) as stream:db.load(name,stream)
                        db.load_events_disabled(name,meta.get('event_definitions',[]));db.validate(name,meta)
        except BaseException:ok=False
        atomic_json(target/PENDING,dict(reason='RESTORE_FAILED_REVIEW_REQUIRED',report_dir=str(reports)))
        atomic_json(reports/'progress.json',dict(status='FAILED_ROLLED_BACK' if ok else 'FAILED_ROLLBACK_INCOMPLETE',
            error_type=type(exc).__name__,finished_at=utc(),services_auto_restart=False))
        emit(on_progress,'FAILED_ROLLED_BACK' if ok else 'FAILED_ROLLBACK_INCOMPLETE')
        raise
    return json.loads((reports/'restore-report.json').read_text(encoding='utf-8'))


def sanitize_local_status(target):
    # Historical business seals/claims stay byte-identical. Only UI process
    # registries get a retained .source.json and an interrupted local status.
    for name in ('ihm_pipeline_runs','ihm_backtesting_runs'):
        directory=Path(target)/'artifacts'/name
        paths=list(directory.glob('**/record.json'))+[directory/'history_index.json']
        for path in paths:
            if not path.is_file():continue
            original=path.read_bytes();value=json.loads(original)
            def update(v):
                if isinstance(v,dict):
                    if str(v.get('status','')).lower() in ('running','pending','starting'):
                        v.update(status='interrupted',pid=None,migration_note='SOURCE_PC_PROCESS_NOT_RESTORED')
                    for child in v.values():update(child)
                elif isinstance(v,list):
                    for child in v:update(child)
            update(value)
            if canonical(value)!=original:
                path.with_suffix('.source.json').write_bytes(original);atomic_json(path,value)


def recover(preimage,password,db,report_dir,*,quiet=inventory.quiescent,
            env_writer=environment.write_user,cancel=None,expected_target=None,on_progress=None):
    """Explicit operator recovery after a killed/interrupted restore process.

    The original files are encrypted before DROP. Partial incoming files are
    moved to the recovery report, never silently deleted or merged.
    """
    preimage=Path(preimage).resolve();reports=Path(report_dir).resolve()
    emit(on_progress,'RECOVERING')
    document=open_manifest(preimage/'recovery.json',password)
    package=document['recovery']
    with decrypted_input(preimage,package,password) as stream:data=json.load(stream)
    target=checked_directory(data['target'])
    if expected_target is not None and target!=Path(expected_target).resolve():
        raise ValueError('La destination demandée ne correspond pas à cette récupération')
    if reports==target or reports.is_relative_to(target) or preimage.is_relative_to(target):
        raise ValueError('Les rapports de récupération doivent être hors du projet cible')
    if set(data['databases'])!=set(DATABASES):raise ValueError('Périmètre de récupération invalide')
    if quiet(target,allow_ui=False):raise ValueError('Fermer les tâches du PC cible avant récupération')
    db.check_destination({n:m for n,m in data['databases'].items() if m},allow_same_server=True)
    reports.mkdir(parents=True,exist_ok=False,mode=0o700)
    stage=target.parent/('.alpha-migration-recovery-'+uuid.uuid4().hex);stage.mkdir(mode=0o700)
    partial=target.parent/('.alpha-migration-partial-'+uuid.uuid4().hex);partial.mkdir(mode=0o700)
    atomic_json(reports/'local-directories.json',dict(staging=str(stage),partial=str(partial)))
    # Fully decrypt/check archives before changing a destination schema.
    payload=dict(packages=data['file_packages'])
    extract_files(preimage,payload,stage,password,cancel,on_progress)
    for p in data['packages']:
        with decrypted_input(preimage/p['folder'],p,password) as stream:
            with gzip.GzipFile(fileobj=stream) as raw:
                while raw.read(BLOCK):check_cancel(cancel)
    env_package=data['environment']
    with decrypted_input(preimage,env_package,password) as stream:old_env=json.load(stream)
    with maintenance(target,quiet,allow_ui=False,on_progress=on_progress):
        atomic_json(reports/'progress.json',dict(status='RECOVERING',started_at=utc()))
        try:
            for name,meta in data['databases'].items():
                check_cancel(cancel)
                if meta is None:db.drop(name);continue
                db.recreate(name,meta)
                p=next(p for p in data['packages'] if p['database']==name)
                with decrypted_input(preimage/p['folder'],p,password) as stream:db.load(name,stream)
                db.load_events_disabled(name,meta.get('event_definitions',[]));db.validate(name,meta)
            for name in data['managed_roots']:
                current=safe_path(target,name);old=safe_path(stage,name)
                if current.exists():
                    quarantine=safe_path(partial,name);quarantine.parent.mkdir(parents=True,exist_ok=True)
                    os.replace(current,quarantine)
                if old.exists():os.replace(old,current)
            env_writer(old_env)
            atomic_json(target/PENDING,dict(reason='RECOVERED_MANUAL_REVIEW_REQUIRED',report_dir=str(reports)))
            result=dict(status='RECOVERED_PAUSED',services_auto_restart=False)
            emit(on_progress,'RECOVERED_PAUSED')
            atomic_json(reports/'progress.json',result);return result
        except BaseException:
            atomic_json(reports/'progress.json',dict(status='RECOVERY_INCOMPLETE',services_auto_restart=False))
            raise


def install_portable_tools(output):
    output=Path(output);tool=output/'outils'/'portable_migration';tool.mkdir(parents=True)
    for path in Path(__file__).parent.glob('*.py'):shutil.copy2(path,tool/path.name)
    from importlib.metadata import version
    (output/'outils'/'requirements-migration.txt').write_text(''.join(n+'=='+version(n)+'\n' for n in ('cryptography','PyMySQL','PyYAML','psutil')),encoding='utf-8')
    launcher=Path(__file__).parent/'restaurer.ps1'
    shutil.copy2(launcher,output/'restaurer.ps1')
    paths=[output/'restaurer.ps1',*(output/'outils').rglob('*')]
    return [dict(path=p.relative_to(output).as_posix(),sha256=sha_file(p)) for p in paths if p.is_file()]
