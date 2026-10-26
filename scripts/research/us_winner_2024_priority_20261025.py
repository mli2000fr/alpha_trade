"""Replace only the cents ORCHESTRATOR; adopt its still-running2022 child.

Prioritize validated1x2024 resume, then2x2024 qualification/resume. Exactly
two cents workers incl adopted child, original annual locks/rules/audits.
Never edit sealed workers or stop replay children. No SQL/network/broker.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
import logging
import os
from pathlib import Path
import sys

ROOT=Path('artifacts/operations/winner-2024-priority-20261025-v1')
TARGET='scripts.research.us_winner_cent_qualification_20261024'


def choose_job(jobs,active,*,adopted_alive,adopted_name='1x-2022'):
    if len(active)+int(adopted_alive)>=2:
        return None
    available=[j for j in jobs if j['name'] not in active and not j['blocked'] and not j['resolved']
        and not (adopted_alive and j['name']==adopted_name)]
    priorities={'1x-2024':0,'2x-2024':1}
    available.sort(key=lambda j:(priorities.get(j['name'],2),not j['qualified'],j['name']))
    if not available:return None
    job=available[0]
    return job['name'],'resume' if job['qualified'] else 'qualify'


def matches(proc,*,orchestrator):
    command=proc.cmdline()
    if TARGET not in command or 'scripts.research.us_winner_legacy_resume_20261024' not in command:
        return False
    if orchestrator:
        return '--phase' not in command and '--year' not in command
    return all(x in command for x in ['--phase','resume','--kind','1x','--year','2022'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replace-orchestrator-pid',type=int,required=True)
    parser.add_argument('--adopt-worker-pid',type=int,required=True)
    args=parser.parse_args()
    os.environ.update(SSLKEYLOGFILE='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    import psutil
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    old,worker=psutil.Process(args.replace_orchestrator_pid),psutil.Process(args.adopt_worker_pid)
    if not matches(old,orchestrator=True) or not matches(worker,orchestrator=False) or worker.ppid()!=old.pid:
        raise ValueError('Exact original cents parent/2022 child lineage not verified')
    adopted_created=worker.create_time()
    # Install exact OLD engine before any consumer module is imported.
    from scripts.research import us_winner_legacy_resume_20261024 as legacy
    legacy.install_legacy();legacy.prepare();legacy.install_dispatch()
    from scripts.research import us_winner_cent_qualification_20261024 as cent
    base=cent.grid.base
    cent.seal();base.verify(base.read(cent.ROOT/'protocol.json')['sources'])
    base.verify({str(p):h for p,h in base.read(cent.ROOT/'protocol.json')['original_protocols'].items()})
    if not (cent.job_root('1x',2024)/'qualified.json').exists():
        raise ValueError('1x2024 correction not yet qualified')
    if not (cent.job_root('2x',2024)/'request.json').exists():
        raise ValueError('2x2024 incident not registered')
    ROOT.mkdir(parents=True,exist_ok=True)
    if (ROOT/'handoff.json').exists():raise FileExistsError('Priority handoff already recorded')
    now=lambda:datetime.now(timezone.utc).isoformat()
    base.save_new(ROOT/'handoff.json',dict(created_at_utc=now(),old_orchestrator_pid=old.pid,
        adopted_pid=worker.pid,adopted_create_time=adopted_created,
        stopped_replay_workers=False,priority=['1x-2024','2x-2024'],maximum_cents_workers=2,
        old_progress=base.read(cent.ROOT/'progress.json'),
        sources={str(n):base.digest(n) for n in [Path(__file__),Path('tests/test_us_winner_2024_priority_20261025.py'),
            Path('doc/ml/winner_reprise_prioritaire_2024_20261025.md')]},
        economic_rules_changed=False,production_changed=False,SQL_writes=False,provider_calls=0,orders=False))
    # Terminate just the scheduling loop. Its active replay child is explicitly
    # adopted, never killed/replayed. Windows termination is not recursive.
    old.terminate();old.wait(timeout=10)
    if not psutil.pid_exists(worker.pid) or psutil.Process(worker.pid).create_time()!=adopted_created:
        raise RuntimeError('Adopted2022 worker unexpectedly disappeared')
    logging.basicConfig(level=logging.WARNING,force=True)
    import requests
    requests.Session.request=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('No HTTP in legacy priority supervisor'))
    def adopted_alive():
        try:
            proc=psutil.Process(worker.pid)
            alive=proc.create_time()==adopted_created and proc.is_running() and proc.status()!=psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:alive=False
        if not alive and not (cent.job_root('1x',2022)/'resolution.json').exists():
            raise RuntimeError('Adopted2022 terminated without audited resolution; no blind restart')
        return alive
    def next_task(active):
        alive=adopted_alive();jobs=[];folders={}
        for folder in sorted(cent.ROOT.glob('*-20*')):
            if not (folder/'request.json').exists():continue
            folders[folder.name]=folder
            jobs.append(dict(name=folder.name,qualified=(folder/'qualified.json').exists(),
                blocked=(folder/'blocked.json').exists(),resolved=(folder/'resolution.json').exists()))
        selection=choose_job(jobs,active,adopted_alive=alive)
        cent.grid.atomic_json(ROOT/'progress.json',dict(status='RUNNING',adopted_2022_alive=alive,
            adopted_worker_pid=worker.pid,active_new_jobs=list(active),next_job=selection,updated_at_utc=now()))
        if selection is None:return None
        name,phase=selection;folder=folders[name]
        return folder,phase,base.read(folder/'request.json')
    cent.next_task=next_task
    cent.supervise()
    cent.grid.atomic_json(ROOT/'progress.json',dict(status='COMPLETED',updated_at_utc=now()))


if __name__=='__main__':main()
