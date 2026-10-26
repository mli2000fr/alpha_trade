"""User-requested stop of TOP10 2x only, keeping 1x workers alive.

The shared old scheduler must be replaced, not recursively killed: its existing
1x child is adopted by a 1x-only scheduler using the same sealed legacy engine.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import time

ROOT=Path('artifacts/operations/winner-stop-top10-2x-20261026-v1')
GRID=Path('artifacts/research/us_winner_native_grid_2017_2026/20261023-2x-v1')
CENTS=Path('artifacts/research/us_winner_cent_qualification/20261024-v1')
LEGACY='scripts.research.us_winner_legacy_resume_20261024'
SHARED='scripts.research.us_winner_consolidation_resume_20261026'
TARGETS={'scripts.research.us_winner_grid_supervisor_repair_20261023',
         'scripts.research.us_winner_cent_qualification_20261024'}


def now():return datetime.now(timezone.utc).isoformat()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    temporary=p.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8');temporary.replace(p)


def value(command,flag):
    try:return command[command.index(flag)+1]
    except (ValueError,IndexError):return None


def role(command):
    module=value(command,'-m')
    if module==SHARED and value(command,'--phase')=='supervise':return 'shared_supervisor'
    if module!=LEGACY or value(command,'--target') not in TARGETS or value(command,'--kind')!='2x':return None
    return '2x_worker' if value(command,'--phase') in ('year','resume','qualify') else '2x_supervisor'


def stop():
    import psutil
    if (ROOT/'stop-receipt.json').exists():raise ValueError('Already stopped; inspect receipt before another action')
    ROOT.mkdir(parents=True,exist_ok=True)
    targets=[];kept=[]
    for process in psutil.process_iter(['pid','name','cmdline','create_time','ppid']):
        info=process.info;command=info['cmdline'] or []
        if info['name'].lower() not in ('python.exe','pythonw.exe'):continue
        if not any(x in command for x in [LEGACY,SHARED]):continue
        if Path(process.cwd()).resolve()!=Path.cwd().resolve():raise ValueError('Unexpected research workspace')
        item=dict(pid=process.pid,created=info['create_time'],parent=info['ppid'],command=command)
        selected=role(command)
        if selected:targets.append(dict(item,role=selected))
        elif value(command,'--kind')=='1x':kept.append(item)
    if not targets:raise ValueError('No matching 2x/scheduler processes; inspect before stop')
    before={str(p):digest(p) for p in sorted((GRID/'cases').glob('*/report.json'))}
    snapshot=read(CENTS/'progress.json');old_grid=read(GRID/'progress.json')
    save(ROOT/'before-stop.json',dict(created_at_utc=now(),targets=targets,kept_1x=kept,
        cents_progress=snapshot,grid_progress=old_grid,completed_reports=before))
    order={'shared_supervisor':0,'2x_supervisor':1,'2x_worker':2}
    # Within each command class stop actual children before venv forwarding
    # parents. Never recurse through the shared parent's 1x children.
    by_id={x['pid']:x for x in targets}
    targets.sort(key=lambda x:(order[x['role']],-int(x['parent'] in by_id)))
    stopped=[]
    for item in targets:
        try:
            p=psutil.Process(item['pid'])
            if p.create_time()!=item['created'] or role(p.cmdline())!=item['role']:
                raise ValueError('PID identity changed before cancellation')
            p.terminate()
            try:p.wait(timeout=5)
            except psutil.TimeoutExpired:
                if p.create_time()!=item['created']:raise ValueError('PID reused during wait')
                p.kill();p.wait(timeout=5)
            stopped.append(item['pid'])
        except psutil.NoSuchProcess:stopped.append(item['pid'])
    for p,sha in before.items():
        if digest(p)!=sha:raise ValueError('A sealed report changed during stop')
    alive_kept=[]
    for item in kept:
        p=psutil.Process(item['pid'])
        if p.create_time()!=item['created'] or not p.is_running():raise ValueError('1x worker not preserved')
        alive_kept.append(item['pid'])
    # All future launches of this recovery will explicitly exclude 2x.
    request=dict(status='STOPPED_BY_USER',kind='2x',at_utc=now(),reason='Human asked to stop TOP10 leverage x2',
        completed_results_preserved=True,automatic_resume_authorized=False,recovery_receipt=str(ROOT/'stop-receipt.json'))
    save(GRID/'user-stop.json',request)
    for folder in sorted(CENTS.glob('2x-20*')):
        save(folder/'user-stop.json',request)
        if not (folder/'resolution.json').exists():save(folder/'progress.json',dict(request,year=int(folder.name[-4:])))
    count=len(list((GRID/'cases').glob('*/report.json')))
    save(GRID/'progress.json',dict(old_grid,**request,completed_runs=count,active_years={},
        pending_years=[],updated_at_utc=now()))
    receipt=dict(status='STOPPED_2X_PRESERVED_1X',at_utc=now(),terminated_pids=stopped,
        kept_1x_pids=alive_kept,completed_reports_before=len(before),completed_reports_after=count,
        preserved_report_hashes=before,all_sealed_reports_unchanged=True,no_recursive_process_kill=True,
        no_output_deleted=True)
    save(ROOT/'stop-receipt.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k!='preserved_report_hashes'}))


def eligible(name):return name.startswith('1x-')


def supervise():
    from scripts.research import us_winner_consolidation_resume_20261026 as recovery
    cent=recovery.initialize()
    import psutil
    base=cent.grid.base
    receipt=read(ROOT/'stop-receipt.json')
    if receipt['status']!='STOPPED_2X_PRESERVED_1X':raise ValueError('Missing verified stop')
    if (ROOT/'handoff-1x.json').exists():raise ValueError('Replacement already started; inspect before duplicate')
    snapshot=read(ROOT/'before-stop.json')['cents_progress']
    snapshot['active']={n:j for n,j in snapshot['active'].items() if eligible(n)}
    adopted=recovery.adopted_from_snapshot(cent,snapshot)
    sources={str(p):digest(p) for p in [Path(__file__),Path('tests/test_us_winner_stop_2x_20261026.py'),
        Path('doc/ml/winner_arret_top10_2x_20261026.md')]}
    save(ROOT/'handoff-1x.json',dict(at_utc=now(),adopted=adopted,pid=os.getpid(),sources=sources,
        excluded_kind='2x',no_worker_1x_stopped=True))
    runs=cent.RUNS;next_task=cent.next_task
    cent.RUNS={k:v for k,v in runs.items() if k!='2x'}
    def choose(active):
        living=recovery.living_adopted(cent,adopted,psutil.Process)
        folders={p.name:p for p in sorted(cent.ROOT.glob('1x-20*')) if (p/'request.json').exists()}
        jobs=[dict(name=n,qualified=(p/'qualified.json').exists(),blocked=(p/'blocked.json').exists(),
                   resolved=(p/'resolution.json').exists()) for n,p in folders.items()]
        choice=recovery.choose_job(jobs,active,living,available_bytes=psutil.virtual_memory().available)
        cent.grid.atomic_json(ROOT/'progress-1x.json',dict(status='RUNNING_1X_ONLY',adopted_active=living,
            active_new_jobs=list(active),next_job=choice,excluded_kind='2x',updated_at_utc=now()))
        if choice is None:return None
        name,phase=choice
        if not eligible(name):raise ValueError('Stopped 2x cannot be scheduled')
        folder=folders[name];return folder,phase,read(folder/'request.json')
    cent.next_task=choose
    try:
        with cent.grid.run_lock(ROOT):cent.supervise()
    finally:cent.RUNS=runs;cent.next_task=next_task
    save(ROOT/'progress-1x.json',dict(status='COMPLETED_1X_ONLY',excluded_kind='2x',updated_at_utc=now()))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=['stop','supervise'],required=True)
    args=parser.parse_args()
    os.environ.update(SSLKEYLOGFILE='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    {'stop':stop,'supervise':supervise}[args.phase]()


if __name__=='__main__':main()
