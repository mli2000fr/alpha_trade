"""Adopt running2022/2024 repairs; qualify/resume TOP50 without duplicate work.

Execution-only orchestration amendment. Original locks, hashes, profiles,
correction, legacy core, audits and workers remain unchanged. No provider/SQL.
"""
import argparse
from datetime import datetime,timezone
import logging
import os
from pathlib import Path

ROOT=Path('artifacts/operations/winner-top50-priority-20261025-v1')
TARGET='scripts.research.us_winner_cent_qualification_20261024'


def choose(jobs,active,adopted):
    if len(active)+len(adopted)>=3:return None
    priorities={'top50-2017':0,'2x-2024':1,'1x-2024':2}
    available=[j for j in jobs if j['name'] not in active and j['name'] not in adopted
        and not j['blocked'] and not j['resolved']]
    available.sort(key=lambda j:(priorities.get(j['name'],3),not j['qualified'],j['name']))
    if not available:return None
    j=available[0];return j['name'],'resume' if j['qualified'] else 'qualify'


def refresh_top_parent(cent,now):
    """Only orchestration progress, never change old reports or protocols."""
    top=cent.RUNS['top50'];parent=top.parent
    marker=cent.job_root('top50',2017)
    if not (marker/'progress.json').exists():return
    state=cent.read_json(marker/'progress.json')
    year=cent.read_json(top/'year-2017.json')
    finished=(top/'report.json').exists()
    if (marker/'blocked.json').exists():status='PARTIAL_FAILED'
    elif finished:status='COMPLETED_AUDITED_EXPLORATORY'
    elif state.get('status')=='RESUMING':status='RUNNING'
    else:status='QUALIFYING_CORRECTION'
    total=len(list((top/'cases').glob('2017-*/report.json')))
    detail=dict(year);detail['correction_phase']=state.get('status')
    if not finished and status!='RUNNING':detail['prior_failure']=year
    old=cent.read_json(parent/'progress.json')
    grids=[r for r in old['grids'] if r['top_n']!=50]
    grids.append(dict(top_n=50,completed_runs=total,total_runs=300,status=status,detail=detail))
    complete=all(r['status']=='COMPLETED_AUDITED_EXPLORATORY' for r in grids)
    cent.grid.atomic_json(parent/'progress.json',dict(status='COMPLETED_AUDITED_EXPLORATORY' if complete else status,
        completed_runs=sum(r['completed_runs'] for r in grids),total_runs=600,grids=grids,
        errors=[] if status!='PARTIAL_FAILED' else [dict(top_n=50,detail=state)],
        recovery_protocol=str(ROOT/'handoff.json'),updated_at_utc=now()))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replace-orchestrator-pid',type=int,required=True)
    parser.add_argument('--adopt-worker-pid',type=int,action='append',required=True)
    args=parser.parse_args()
    os.environ.update(SSLKEYLOGFILE='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    import psutil
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    parent=psutil.Process(args.replace_orchestrator_pid)
    if 'scripts.research.us_winner_2024_priority_20261025' not in parent.cmdline():
        raise ValueError('Exact current priority parent required')
    # Fresh legacy install BEFORE importing simulator consumers.
    from scripts.research import us_winner_legacy_resume_20261024 as legacy
    legacy.install_legacy();legacy.prepare();legacy.install_dispatch()
    from scripts.research import us_winner_cent_qualification_20261024 as cent
    base=cent.grid.base;cent.seal()
    base.verify(base.read(cent.ROOT/'protocol.json')['sources'])
    old_handoff=base.read('artifacts/operations/winner-2024-priority-20261025-v1/handoff.json')
    adopted={}
    for pid in args.adopt_worker_pid:
        proc=psutil.Process(pid);command=proc.cmdline()
        if TARGET not in command or '--phase' not in command or command[command.index('--phase')+1]!='resume':
            raise ValueError('Unexpected adopted command')
        kind=command[command.index('--kind')+1];year=int(command[command.index('--year')+1]);name=f'{kind}-{year}'
        if name not in ('1x-2022','1x-2024') or name in adopted:raise ValueError('Only existing2022/2024 may be adopted')
        if proc.ppid()!=parent.pid and not (pid==old_handoff['adopted_pid'] and proc.create_time()==old_handoff['adopted_create_time']):
            raise ValueError('Adopted worker lineage missing')
        adopted[name]=dict(pid=pid,created=proc.create_time(),kind=kind,year=year,command=command)
    if set(adopted)!= {'1x-2022','1x-2024'}:raise ValueError('Both active original workers required')
    if psutil.virtual_memory().available < 6*2**30:raise ValueError('Not enough free memory for one additional qualification')
    if not (cent.job_root('top50',2017)/'request.json').exists():raise ValueError('TOP50 incident not registered')
    ROOT.mkdir(parents=True,exist_ok=True)
    now=lambda:datetime.now(timezone.utc).isoformat()
    base.save_new(ROOT/'handoff.json',dict(created_at_utc=now(),replaced_parent_pid=parent.pid,adopted=adopted,
        old_top_progress=cent.read_json(cent.RUNS['top50'].parent/'progress.json'),
        maximum_cents_workers=3,priority=['top50-2017','2x-2024'],active_replays_stopped=False,
        sources={str(p):base.digest(p) for p in [Path(__file__),Path('tests/test_us_winner_top50_priority_20261025.py'),
            Path('doc/ml/winner_incident_top50_2017_20261025.md')]},
        production_changed=False,legacy_economic_rules_unchanged=True,SQL_writes=False,orders=False))
    parent.terminate();parent.wait(timeout=10)
    logging.basicConfig(level=logging.WARNING,force=True)
    import requests
    requests.Session.request=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('No HTTP in TOP50 recovery'))
    def alive_adopted():
        living={}
        for name,item in adopted.items():
            try:
                proc=psutil.Process(item['pid'])
                alive=proc.create_time()==item['created'] and proc.is_running() and proc.status()!=psutil.STATUS_ZOMBIE
            except psutil.NoSuchProcess:alive=False
            if alive:living[name]=item
            elif not (cent.job_root(item['kind'],item['year'])/'resolution.json').exists():
                raise RuntimeError('Adopted worker exited without audited resolution: '+name)
        return living
    def next_task(active):
        living=alive_adopted();folders={};jobs=[]
        for folder in sorted(cent.ROOT.glob('*-20*')):
            if not (folder/'request.json').exists():continue
            folders[folder.name]=folder
            jobs.append(dict(name=folder.name,qualified=(folder/'qualified.json').exists(),
                blocked=(folder/'blocked.json').exists(),resolved=(folder/'resolution.json').exists()))
        selected=choose(jobs,active,living)
        cent.grid.atomic_json(ROOT/'progress.json',dict(status='RUNNING',adopted_active=living,
            active_new_jobs=list(active),next_job=selected,updated_at_utc=now()))
        refresh_top_parent(cent,now)
        if selected is None:return None
        name,phase=selected;folder=folders[name]
        return folder,phase,base.read(folder/'request.json')
    cent.next_task=next_task
    cent.supervise()
    refresh_top_parent(cent,now)
    cent.grid.atomic_json(ROOT/'progress.json',dict(status='COMPLETED',updated_at_utc=now()))


if __name__=='__main__':main()
