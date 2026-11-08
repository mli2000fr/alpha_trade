"""Two-worker supervisor, including the already-started 2024 pilot."""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import subprocess
import sys
import time

import pandas as pd

from scripts.research.us_winner_per_symbol_long_20261103 import ROOT,YEARS,ARMS,read
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def main():
    control=ROOT/'campaign';control.mkdir(exist_ok=False)
    tasks=[dict(year=y,arm=a,key=f'{y}-{a}',status='PENDING') for y in YEARS
           for a in ('PER_SYMBOL_TOP10','ORACLE_TOP20','ORACLE_TOP10')]
    tasks[0]['status']='EXTERNAL_RUNNING'
    active={};started=time.monotonic();last=None
    def files(task):
        folder=ROOT/'runs'/task['key']
        return folder/'artifacts/report.json',folder/'isolation.json',folder/'artifacts/progress.json'
    def completion(task):
        report,isolation,progress=files(task)
        if report.exists() and isolation.exists() and read(isolation).get('status')=='COMPLETED':
            value=read(report)
            if not str(value.get('status','')).startswith(('COMPLETED','INCOMPLETE')):
                raise ValueError('Unqualified terminal report')
            task.update(status='COMPLETED',coverage_status=value['status'])
            return True
        if progress.exists() and read(progress).get('status')=='FAILED':
            task.update(status='FAILED',error=read(progress))
            return True
        return False
    while any(t['status'] in ('PENDING','RUNNING','EXTERNAL_RUNNING') for t in tasks):
        for task in tasks:
            if task['status']=='EXTERNAL_RUNNING':completion(task)
        for key,child in list(active.items()):
            code=child.poll()
            if code is None:continue
            task=next(t for t in tasks if t['key']==key)
            task['exit_code']=code
            if code!=0 or not completion(task):
                task.update(status='FAILED',error=f'exit={code}; see campaign/{key}.stderr.log')
            del active[key]
        external=sum(t['status']=='EXTERNAL_RUNNING' for t in tasks)
        for task in tasks:
            if len(active)+external>=2:break
            if task['status']!='PENDING':continue
            command=[sys.executable,'-X','utf8','-u','-m','scripts.research.us_winner_per_symbol_long_replay_20261103',
                '--year',str(task['year']),'--arm',task['arm']]
            env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
            with (control/(task['key']+'.stdout.log')).open('x',encoding='utf-8') as out, (
                control/(task['key']+'.stderr.log')).open('x',encoding='utf-8') as err:
                child=subprocess.Popen(command,cwd=Path(__file__).resolve().parents[2],env=env,
                    stdin=subprocess.DEVNULL,stdout=out,stderr=err,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            active[task['key']]=child;task.update(status='RUNNING',pid=child.pid)
        snapshot=dict(status='RUNNING',completed=sum(t['status']=='COMPLETED' for t in tasks),
            failed=sum(t['status']=='FAILED' for t in tasks),total=len(tasks),tasks=tasks,
            elapsed_seconds=time.monotonic()-started,updated_at_utc=datetime.now(timezone.utc).isoformat())
        atomic_json(control/'progress.json',snapshot)
        key=tuple((t['key'],t['status']) for t in tasks)
        if key!=last:print(json.dumps(snapshot,default=str),flush=True);last=key
        if active or external:time.sleep(2)
    rows=[]
    for task in tasks:
        report_path,isolation,_=files(task)
        if task['status']=='COMPLETED':
            report=read(report_path)
            rows.append(dict(year=task['year'],arm=task['arm'],**{k:v for k,v in report.items()
                if k in ['initial_equity','final_equity','return_pct','max_drawdown_pct','closed_lot_trades',
                    'winners','losers','win_pct','gross_winning_pnl','gross_losing_pnl','average_winning_pnl',
                    'average_losing_pnl','average_winning_holding_days','average_losing_holding_days',
                    'average_gross_capital','maximum_gross_capital','average_gross_equity_ratio','status']},
                report_sha256=digest(report_path),isolation_sha256=digest(isolation)))
        else:rows.append(dict(year=task['year'],arm=task['arm'],status='FAILED'))
    pd.DataFrame(rows).to_csv(ROOT/'annual-summary.csv',index=False)
    report=dict(status='COMPLETED_EXPLORATORY' if all(t['status']=='COMPLETED' for t in tasks) else 'PARTIAL_FAILED',
        cases=rows,tasks=tasks,elapsed_seconds=time.monotonic()-started,
        annual_models=read(ROOT/'training-report.json'),provider_calls=0,llm_calls=0,broker_calls=0,sql_writes=False,
        full_live_parity=False,coverage_limitations='Per-entry post-hoc intraday availability; statuses explicitly retained')
    atomic_json(ROOT/'report.json',report)
    atomic_json(control/'progress.json',dict(snapshot,status=report['status']))
    print(json.dumps(dict(status=report['status'],completed=len([t for t in tasks if t['status']=='COMPLETED']))),flush=True)


if __name__=='__main__':main()
