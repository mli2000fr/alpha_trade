"""Bounded parallel supervisor for the eight isolated, resumable research runs."""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_weak_topn_2020_2024_experiments import digest,write

ROOT=Path('artifacts/research/us_weak_topn_2020_2024/20261029-v1')
WORKERS=2


def verified_completed(folder):
    report=json.loads((folder/'report.json').read_text(encoding='utf-8'))
    seal=json.loads((folder/'seal.json').read_text(encoding='utf-8'))
    if digest(folder/'report.json')!=seal['report_sha256']:raise ValueError('Altered report')
    for name,sha in seal['files'].items():
        if digest(folder/name)!=sha:raise ValueError('Altered output '+name)
    for path,sha in seal['input_sha256'].items():
        if digest(path)!=sha:raise ValueError('Altered experiment input '+path)
    return report['status']


def run(root=ROOT):
    root=Path(root)
    label_report=json.loads((root/'labels/report.json').read_text(encoding='utf-8'))
    if label_report['status']!='COMPLETED_LABELS':raise ValueError('Completed labels required')
    if digest(root/'labels/panel.parquet')!=label_report['files']['panel.parquet']:
        raise ValueError('Label panel checksum mismatch')
    control=root/'campaign';control.mkdir(exist_ok=True)
    tasks=[dict(method=method,top=top,key=f'{method}-TOP{top}',status='PENDING')
        for top in (20,50) for method in ('VOL60','E2','E3','PMATH0')]
    active={}
    started=datetime.now(timezone.utc).isoformat()
    def save(status):
        write(control/'progress.json',dict(status=status,started_at_utc=started,
            updated_at_utc=datetime.now(timezone.utc).isoformat(),max_parallel_workers=WORKERS,
            completed=sum(t['status']=='COMPLETED_EXPLORATORY' for t in tasks),
            partial=sum(t['status']=='PARTIAL_INSUFFICIENT_TRAINING' for t in tasks),
            failed=sum(t['status']=='FAILED' for t in tasks),total=len(tasks),tasks=tasks))
    with exclusive_run(control):
        for task in tasks:
            folder=root/'experiments'/task['key']
            if (folder/'report.json').exists():
                task['status']=verified_completed(folder)
        save('RUNNING')
        try:
            while any(t['status']=='PENDING' for t in tasks) or active:
                for task in tasks:
                    if len(active)>=WORKERS:break
                    if task['status']!='PENDING':continue
                    logdir=control/task['key'];logdir.mkdir(exist_ok=True)
                    stdout=(logdir/'stdout.log').open('a',encoding='utf-8')
                    stderr=(logdir/'stderr.log').open('a',encoding='utf-8')
                    command=[sys.executable,'-u','-m','scripts.research.us_weak_topn_2020_2024_experiments',
                        '--root',str(root),'--method',task['method'],'--top',str(task['top'])]
                    env=dict(os.environ,OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2',
                        NUMEXPR_NUM_THREADS='2')
                    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
                    try:
                        child=subprocess.Popen(command,cwd=Path(__file__).resolve().parents[2],env=env,
                            stdout=stdout,stderr=stderr,stdin=subprocess.DEVNULL,creationflags=flags)
                    finally:
                        stdout.close();stderr.close()
                    task.update(status='RUNNING',pid=child.pid,command=command)
                    active[task['key']]=child
                    print('Started '+task['key']+' pid='+str(child.pid),flush=True)
                for task in tasks:
                    child=active.get(task['key'])
                    if child is None:continue
                    code=child.poll()
                    if code is None:continue
                    task['exit_code']=code
                    try:
                        if code!=0:raise RuntimeError(f'Child exit={code}; inspect {control/task["key"]}')
                        task['status']=verified_completed(root/'experiments'/task['key'])
                    except Exception as error:
                        task.update(status='FAILED',error=str(error))
                    del active[task['key']]
                    print('Finished '+task['key']+' '+task['status'],flush=True)
                save('RUNNING')
                if active:time.sleep(2)
        except BaseException:
            # Preserve live children for explicit review; no double launch on restart.
            save('SUPERVISOR_INTERRUPTED')
            raise
        status='COMPLETED_EXPLORATORY'
        if any(t['status']=='FAILED' for t in tasks):status='PARTIAL_FAILED'
        elif any(t['status']=='PARTIAL_INSUFFICIENT_TRAINING' for t in tasks):status='PARTIAL_INSUFFICIENT_TRAINING'
        save(status)
        print(status,flush=True)
    return tasks


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    run(parser.parse_args().root)
