"""Migration worker and portable interactive restore. Secrets travel on stdin."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from . import engine, environment, inventory
from .mysql import Connection, DATABASES, MySQL
from .storage import atomic_json
from .tracking import Progress,ConsoleProgress,emit
from .locking import MigrationLockError,worker_identity


def worker_status(job,status,**fields):
    atomic_json(Path(job)/'progress.json',dict(status=status,updated_at=engine.utc(),**worker_identity(),**fields))


def adapter(request):
    options={k:request.get(k) or None for k in ('mysqldump','mysql')}
    if request.get('connections'):
        return MySQL({n:Connection(**request['connections'][n]) for n in DATABASES},**options)
    return MySQL.source(request['root'],**options)


def run_request(request,job,*,tracker=None):
    """No subprocess arguments or persistent request JSON contain credentials."""
    job=Path(job).resolve();job.mkdir(parents=True,exist_ok=True)
    cancel=lambda:(job/'cancel.request').exists()
    action=request['action'];password=request.get('password')
    tracker=tracker or Progress(job,action,mirror=request.get('output') if action=='export' else request.get('report_dir'))
    report=tracker.update
    if action=='inventory':
        return inventory.preview(request['root'],on_progress=report,cancel=cancel)
    if action=='verify':
        result=engine.verify(request['folder'],password,cancel=cancel,on_progress=report)
        emit(report,'FINISHED')
        return dict(status='VERIFIED',backup_id=result['id'],source_mode=result.get('source_mode'))
    db=adapter(request)
    db.on_progress=report
    if action=='export':
        result=engine.export(request['root'],request['output'],password,db,cancel=cancel,on_progress=report)
        return dict(status='COMPLETE',folder=request['output'],backup_id=result['id'],source_mode='online')
    if action=='plan':
        result=engine.inspect_restore(request['folder'],request['target'],password,db,on_progress=report)
        emit(report,'FINISHED');return result
    if action=='restore':
        deadline=time.monotonic()+int(request.get('wait_seconds',900))
        while inventory.quiescent(request['target'],allow_ui=False):
            engine.check_cancel(cancel)
            if time.monotonic()>=deadline:raise ValueError('Le PC cible est toujours utilisé : restauration non commencée')
            worker_status(job,'WAITING_FOR_TARGET_STOP')
            emit(report,'WAITING_FOR_TARGET_STOP')
            time.sleep(2)
        report=engine.restore(request['folder'],request['target'],password,db,request['report_dir'],
            approved_plan=request['approved_plan'],cancel=cancel,on_progress=tracker.update)
        if request.get('rebuild_venv',True):
            worker_status(job,'BUILDING_PYTHON')
            emit(tracker.update,'BUILDING_PYTHON')
            try:
                rebuild_venv(request['target'],report['source_requirements'],request['report_dir'],on_progress=tracker.update)
                report['python_environment']='REBUILT'
            except Exception:
                report['python_environment']='BUILD_FAILED_RETRY_REQUIRED'
            atomic_json(Path(request['report_dir'])/'restore-report.json',report)
        emit(tracker.update,'FINISHED',warning=report.get('python_environment')=='BUILD_FAILED_RETRY_REQUIRED')
        return report
    if action=='recover':
        return engine.recover(request['preimage'],password,db,request['report_dir'],cancel=cancel,expected_target=request['target'],on_progress=report)
    raise ValueError('Action de migration inconnue')


def rebuild_venv(target,requirements,report_dir,*,on_progress=None):
    """Create a NEW venv only, never delete/reuse an existing environment."""
    target=Path(target).resolve();venv=target/'.venv'
    if venv.exists():raise ValueError('Environnement Python existant : reconstruction refusée')
    import venv as venv_module
    emit(on_progress,item='Création du nouvel environnement Python')
    venv_module.EnvBuilder(with_pip=True).create(venv)
    python=venv/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    pinned=Path(report_dir)/'requirements-source.txt';pinned.write_text(requirements,encoding='utf-8')
    # pip diagnostics can include authenticated URLs from machine settings.
    # Persist only its return code, never raw stdout/stderr.
    emit(on_progress,item='Installation des dépendances aux versions sauvegardées')
    result=subprocess.run([str(python),'-m','pip','install','-r',str(pinned)],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    atomic_json(Path(report_dir)/'python-environment.json',dict(returncode=result.returncode,auto_start=False))
    if result.returncode:raise RuntimeError('Installation des dépendances échouée')


def interactive(action,*,backup_dir=None,target_dir=None):
    folder=Path(backup_dir or input('Répertoire de sauvegarde : ').strip()).resolve()
    password=getpass.getpass('Mot de passe de sauvegarde : ')
    if action=='verify':
        result=engine.verify(folder,password);print('Sauvegarde vérifiée :',result['id']);return
    target=Path(target_dir or input('Répertoire du projet cible : ').strip()).resolve()
    dump=input('Chemin de mysqldump.exe : ').strip()
    mysql=input('Chemin de mysql.exe : ').strip()
    user=input('Utilisateur MySQL local : ').strip()
    db_password=getpass.getpass('Mot de passe MySQL local : ')
    connections={n:asdict(Connection(user=user,password=db_password)) for n in DATABASES}
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    job=folder/'journaux'/('restauration-'+stamp)
    request=dict(action='plan',folder=str(folder),target=str(target),password=password,
        connections=connections,mysqldump=dump,mysql=mysql)
    if action=='recover':
        request.update(action='recover',preimage=str(folder),report_dir=str(job))
        print('Récupération de l’état précédant une restauration interrompue.')
    else:
        plan=run_console(request,job/'plan');print(json.dumps(plan,ensure_ascii=False,indent=2))
        request.update(action='restore',approved_plan=plan['fingerprint'],report_dir=str(job/'rapport'))
    print('Les trois bases locales seront remplacées. Les services doivent rester arrêtés sur le PC cible.')
    if input('Saisir REMPLACER pour continuer : ').strip()!='REMPLACER':return
    if action=='restore':request['rebuild_venv']=input('Recréer le nouvel environnement Python ? [O/n] ').strip().lower()!='n'
    result=run_console(request,job);print(json.dumps(result,ensure_ascii=False,indent=2))


def run_console(request,job):
    job=Path(job);job.mkdir(parents=True,exist_ok=True)
    tracker=ConsoleProgress(job,request['action'],mirror=request.get('report_dir'))
    try:return run_request(request,job,tracker=tracker)
    except BaseException as exc:
        if tracker.state['phase'] not in ('FAILED_ROLLED_BACK','FAILED_ROLLBACK_INCOMPLETE'):
            extra=dict(error_code=exc.code,owner_pid=exc.owner_pid) if isinstance(exc,MigrationLockError) else {}
            emit(tracker.update,'CANCELED' if isinstance(exc,InterruptedError) else 'FAILED',**extra)
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description='Migration complète Alpha Trade')
    parser.add_argument('action',nargs='?',choices=['restore','verify','recover'],default='restore')
    parser.add_argument('--request-stdin',action='store_true')
    parser.add_argument('--job-dir')
    parser.add_argument('--backup-dir',help='Répertoire de sauvegarde ; demandé si absent')
    parser.add_argument('--target-dir',help='Projet cible ; demandé si absent')
    args=parser.parse_args(argv)
    if not args.request_stdin:
        try:interactive(args.action,backup_dir=args.backup_dir,target_dir=args.target_dir)
        except Exception as exc:
            print(str(exc) if type(exc) is ValueError or isinstance(exc,MigrationLockError) else 'Opération échouée : '+type(exc).__name__);return 1
        return 0
    job=Path(args.job_dir).resolve()
    tracker=None
    try:
        request=json.load(sys.stdin)
        tracker=Progress(job,request.get('action'),mirror=request.get('output') if request.get('action')=='export' else request.get('report_dir'))
        worker_status(job,'STARTED',action=request.get('action'))
        result=run_request(request,job,tracker=tracker)
        atomic_json(job/'result.json',result)
        atomic_json(job/'progress.json',dict(status='FINISHED',updated_at=engine.utc()))
        return 0
    except BaseException as exc:
        # Never persist repr(request), SQL parameters or raw provider exceptions.
        atomic_json(job/'progress.json',dict(status='CANCELED' if isinstance(exc,InterruptedError) else 'FAILED',
            error_type=type(exc).__name__,message=str(exc) if type(exc) is ValueError or isinstance(exc,MigrationLockError) else 'Consulter le rapport de phase ; aucune relance automatique.',updated_at=engine.utc()))
        if tracker and tracker.state.get('phase') not in ('FAILED_ROLLED_BACK','FAILED_ROLLBACK_INCOMPLETE'):
            extra=dict(error_code=exc.code,owner_pid=exc.owner_pid) if isinstance(exc,MigrationLockError) else {}
            emit(tracker.update,'CANCELED' if isinstance(exc,InterruptedError) else 'FAILED',**extra)
        return 1


if __name__=='__main__':sys.exit(main())
