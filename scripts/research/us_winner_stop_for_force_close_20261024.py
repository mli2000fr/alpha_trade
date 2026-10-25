"""User-authorized stop of exact research workers; preserve all completed results."""
from pathlib import Path
from datetime import datetime,timezone
import json
import os
import time

import psutil

ROOT=Path(__file__).resolve().parents[2]
MODULES={
    'scripts.research.us_winner_grid_supervisor_repair_20261023',
    'scripts.research.us_winner_topn_2017_comparison_20261023',
    'scripts.research.us_winner_cent_qualification_20261024',
    'scripts.research.us_winner_monthly_scope_repair_20261024',
}
RUNS=[
    'artifacts/research/us_winner_native_grid_2017_2026/20261023-v1',
    'artifacts/research/us_winner_native_grid_2017_2026/20261023-2x-v1',
    'artifacts/research/us_winner_topn_2017/20261023-v1',
    'artifacts/research/us_winner_cent_qualification/20261024-v1',
    'artifacts/research/us_winner_monthly_selector/20261024-v1',
]


def atomic(path,value):
    temporary=path.with_name(path.name+'.stop-tmp')
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
    os.replace(temporary,path)


def main():
    folder=ROOT/'artifacts/operations/winner-force-close-stop-20261024-v1'
    folder.mkdir(parents=True,exist_ok=False)
    records=[]
    for p in psutil.process_iter(['pid','ppid','cmdline','create_time']):
        try:
            cmd=p.info['cmdline'] or []
            if '-m' not in cmd or cmd[cmd.index('-m')+1] not in MODULES:
                continue
            if not any('F:\\projets\\.venv\\Scripts\\python.exe'.lower() in str(c).lower() for c in cmd):
                raise RuntimeError('Unexpected interpreter for selected research process')
            records.append(dict(pid=p.pid,ppid=p.ppid(),cmdline=cmd,created=p.create_time()))
        except (psutil.NoSuchProcess,psutil.AccessDenied):
            continue
    stamp=datetime.now(timezone.utc).isoformat()
    atomic(folder/'processes-before-stop.json',dict(at_utc=stamp,processes=records))
    progress={}
    for name in RUNS:
        path=ROOT/name/'progress.json'
        if path.exists():
            progress[name]=json.loads(path.read_text(encoding='utf-8'))
    atomic(folder/'progress-before-stop.json',progress)
    # Stop supervisors before workers so no new task can be dispatched.
    records.sort(key=lambda r:('--phase' in r['cmdline'],r['created']))
    targets=[]
    for row in records:
        try:
            p=psutil.Process(row['pid'])
            if p.create_time()!=row['created']:
                raise RuntimeError('PID reused before stop')
            p.terminate();targets.append(p)
        except psutil.NoSuchProcess:
            pass
    _,alive=psutil.wait_procs(targets,timeout=8)
    if alive:
        raise RuntimeError('Selected research processes did not stop: '+str([p.pid for p in alive]))
    for name,previous in progress.items():
        if previous.get('status','').startswith('COMPLETED'):
            continue
        atomic(ROOT/name/'progress.json',dict(previous,status='STOPPED_BY_USER',
            stopped_at_utc=stamp,stop_receipt=str(folder.relative_to(ROOT)),
            stop_reason='User requested stop before global drawdown liquidation qualification; completed artifacts preserved'))
    atomic(folder/'report.json',dict(status='STOPPED_BY_USER',stopped_processes=len(records),
        processes=records,production_or_downloads_touched=False,completed_results_preserved=True,at_utc=stamp))
    print(json.dumps(dict(status='STOPPED_BY_USER',processes=len(records),receipt=str(folder))))


if __name__=='__main__':main()
