"""Bounded qualification/recovery companion for sealed Winner research grids.

Do not change production, original sources, prices, audit tolerances or profiles.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager, nullcontext
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time

import numpy as np
import pandas as pd

from scripts.research import us_winner_native_grid_2017_2026_20261023 as grid
from scripts.research import us_winner_native_grid_2x_2017_2026_20261023 as lever
from scripts.research import us_winner_2020_cent_repair_20261023 as correction
from scripts.research.us_winner_grid_supervisor_repair_20261023 import read_json,safe_reads,completed_records

ROOT=Path('artifacts/research/us_winner_cent_qualification/20261024-v1')
DOC=Path('doc/ml/winner_qualification_centimes_commune_20261024.md')
TEST=Path('tests/test_us_winner_cent_qualification_20261024.py')
RUNS={'1x':grid.ROOT,'2x':lever.ROOT,
    'top20':Path('artifacts/research/us_winner_topn_2017/20261023-v1/top20'),
    'top50':Path('artifacts/research/us_winner_topn_2017/20261023-v1/top50')}
ORIGINAL_WORKER=grid.worker


def now():return datetime.now(timezone.utc).isoformat()


def cent_error(value):
    match=re.fullmatch(r'(-?\d+(?:\.\d+)?) != (-?\d+(?:\.\d+)?)',str(value))
    return bool(match and math.isclose(abs(float(match[1])-float(match[2])),.01,abs_tol=1e-8))


def job_root(kind,year):return ROOT/f'{kind}-{year}'


def seal():
    ROOT.mkdir(parents=True,exist_ok=True)
    sources={str(n):grid.base.digest(n) for n in [Path(__file__),DOC,TEST,Path(correction.__file__)]}
    path=ROOT/'protocol.json'
    if path.exists():
        p=read_json(path);grid.base.verify(p['sources']);return p
    p=dict(created_at_utc=now(),sources=sources,maximum_parallel_workers=2,
        kinds={k:str(v) for k,v in RUNS.items()},correction='FIRST_FULL_FILL_AVERAGE_V1',
        original_protocols={str(v/'protocol.json'):grid.base.digest(v/'protocol.json') for v in RUNS.values()},
        audit_tolerance_changed=False,original_sources_changed=False,
        SQL_reads=False,SQL_writes=False,provider_calls=0,training=False,orders=False)
    grid.base.save_new(path,p);return p


@contextmanager
def annual_lock(kind,year):
    root=RUNS[kind]
    outer=grid.run_lock(root) if kind.startswith('top') else nullcontext()
    folder=root/'supervisor-v2/locks'/str(year);folder.mkdir(parents=True,exist_ok=True)
    with outer,grid.run_lock(folder):yield


def inventory(kind,year):
    root=RUNS[kind];records={};drifts={};buys=0
    for file in sorted((root/'cases').glob(f'{year}-*/report.json')):
        r=read_json(file);grid.base.verify({str(file.parent/k):v for k,v in r['files'].items()})
        if r['audit']['status']!='PASS_SCALAR_EXITS_CASH_FEES_AND_ENTRIES':raise ValueError('Unqualified previous account')
        records[file.parent.name]=dict(report_sha256=grid.base.digest(file),files=r['files'])
        sl=r['parameters']['stop_loss_pct'];tp=r['parameters']['take_profit_pct']
        with (file.parent/'events.csv').open(encoding='utf-8',newline='') as stream:
            for row in csv.DictReader(stream):
                if row['event']!='BUY_FILL':continue
                a=float(row['price']);q=float(row['quantity']);b=q*a/q;buys+=1
                if round(a*(1-sl),2)!=round(b*(1-sl),2) or tp and round(a*(1+tp),2)!=round(b*(1+tp),2):
                    drifts.setdefault(r['profile'],[]).append(dict(symbol=row['symbol'],time=row['time'],price=a,quantity=q))
    return dict(records=records,completed_cases=len(records),buy_checks=buys,initial_level_drift=drifts,observed_at_utc=now())


def explained(mismatch):
    if not mismatch['same_time_reason'] or not math.isclose(abs(mismatch['scalar_price']-mismatch['actual_price']),.01,abs_tol=1e-8):return False
    key='stop' if mismatch['actual_reason']=='STOP' else 'tp' if mismatch['actual_reason'] in ('TP','TP_GAP_CAPPED') else None
    return bool(key and any(
        x[key] is not None and math.isclose(x[key],mismatch['actual_price'],abs_tol=1e-8)
        and math.isclose(x['canonical_'+key],mismatch['scalar_price'],abs_tol=1e-8)
        and x['native_price']!=float(x['raw_average']) for x in mismatch['fills']))


def replay_profile(kind,year,profile,folder,*,fixed):
    root=RUNS[kind];folder.mkdir(parents=True,exist_ok=True)
    if (folder/'report.json').exists():raise ValueError('Replay output must be a grid folder, not a case')
    p=deepcopy(read_json(root/'protocol.json'));p['profiles']=[x for x in p['profiles'] if x['name']==profile]
    if not p['profiles']:raise ValueError('Unknown profile')
    if not (folder/'protocol.json').exists():grid.base.save_new(folder/'protocol.json',p)
    context=lever.adapter() if kind=='2x' else nullcontext()
    with context:
        load=grid.load_year;audit=grid.audit_result;metrics=grid.metrics
        grid.load_year=lambda unused,y:load(root,y)
        fills=[];book=correction.runtime.WinnerCampaignRuntime.book_buy;add=correction.runtime.add_fill
        def trace_book(self,intent,operation,raw):
            def trace_add(state,**kwargs):
                value=add(state,**kwargs);lot=state['lots'][-1];price=float(raw['filled_avg_price']);policy=state['policy']
                fills.append(dict(symbol=state['symbol'],time=str(kwargs['filled_at']),raw_average=raw['filled_avg_price'],
                    quantity=kwargs['quantity'],native_price=kwargs['price'],stop=lot['stop'],tp=lot['tp'],
                    canonical_stop=round(price*(1-policy['stop_loss_pct']),2),
                    canonical_tp=round(price*(1+policy['take_profit_pct']),2) if policy['take_profit_pct'] else None))
                return value
            correction.runtime.add_fill=trace_add
            try:return book(self,intent,operation,raw)
            finally:correction.runtime.add_fill=add
        def diagnostic(result,summary,rule,cohort,raw,sessions):
            ds=[s.session_date for s in sessions];idx={d:i for i,d in enumerate(ds)};mismatches=[]
            for t in result.closed_trades_df.itertuples():
                day=t.entry_date.tz_convert('America/New_York').date();due=sessions[idx[day]+rule['horizon_sessions']].open_at_utc
                got=grid.scalar_exit(raw[t.symbol],t.entry_date,t.entry_price,due,
                    sl=rule['stop_loss_pct'],tp=rule['take_profit_pct'],trail=rule['trailing_stop_pct'])
                if got is None or abs(got[1]-t.exit_price)>1e-7 or got[0]!=t.exit_date or got[2]!=t.exit_reason:
                    mismatches.append(dict(symbol=t.symbol,entry_time=str(t.entry_date),entry_price=t.entry_price,
                        actual_price=t.exit_price,actual_reason=t.exit_reason,scalar_price=got[1] if got else None,
                        same_time_reason=got is not None and got[0]==t.exit_date and got[2]==t.exit_reason,
                        fills=[x for x in fills if x['symbol']==t.symbol and x['time']==str(t.entry_date.to_pydatetime())]))
            grid.base.save_new(folder/'diagnosis.json',dict(mismatches=mismatches,
                all_explained=bool(mismatches) and all(explained(x) for x in mismatches),fills=fills))
            return audit(result,summary,rule,cohort,raw,sessions)
        if not fixed:
            correction.runtime.WinnerCampaignRuntime.book_buy=trace_book;grid.audit_result=diagnostic
        else:
            def tagged(result,initial):return metrics(result,initial)|dict(fill_price_correction='FIRST_FULL_FILL_AVERAGE_V1',
                correction_amendment_sha256=grid.base.digest(ROOT/'protocol.json'))
            grid.metrics=tagged
        try:
            with correction.corrected_runtime() if fixed else nullcontext():
                try:ORIGINAL_WORKER(folder,year)
                except AssertionError:
                    if fixed or not (folder/'diagnosis.json').exists():raise
                    evidence=read_json(folder/'diagnosis.json')
                    if not evidence['all_explained']:raise
            if not fixed:
                evidence=read_json(folder/'diagnosis.json')
                if not evidence['all_explained']:raise ValueError('Original failure not reproduced/explained')
                return evidence
            case=folder/'cases'/f'{year}-{profile}';r=read_json(case/'report.json')
            grid.base.verify({str(case/k):v for k,v in r['files'].items()})
            return r
        finally:
            grid.load_year=load;grid.audit_result=audit;grid.metrics=metrics
            correction.runtime.WinnerCampaignRuntime.book_buy=book;correction.runtime.add_fill=add


def equivalent_accounts(old_case,new_case):
    old=read_json(old_case/'report.json');new=read_json(new_case/'report.json')
    keys=['final_equity','return_pct','max_drawdown_pct','costs','margin_interest','settled_cash',
        'closed_lot_trades','winners','losers','gross','average_gross_capital']
    for k in keys:
        if not math.isclose(float(old[k]),float(new[k]),abs_tol=1e-7,rel_tol=1e-10):raise ValueError('Completed account materially changes: '+k)
    for file in ['trades.parquet','equity-5m.parquet']:
        pd.testing.assert_frame_equal(pd.read_parquet(old_case/file),pd.read_parquet(new_case/file),check_exact=False,atol=1e-7,rtol=1e-10)
    if old['open_positions']!=new['open_positions']:raise ValueError('Open positions change')
    return dict(status='ECONOMIC_AND_TRANSACTION_PARITY',compared=keys,files=['trades.parquet','equity-5m.parquet'])


def install_validated(kind,year,profile,source):
    target=RUNS[kind]/'cases'/f'{year}-{profile}';target.mkdir(parents=True,exist_ok=True)
    if (target/'report.json').exists():raise FileExistsError('Never replace a completed account')
    report=read_json(source/'report.json');grid.base.verify({str(source/k):v for k,v in report['files'].items()})
    for name,sha in report['files'].items():
        path=target/name
        if path.exists() and grid.base.digest(path)!=sha:
            backup=job_root(kind,year)/'prior-unsealed'/profile;backup.mkdir(parents=True,exist_ok=True)
            if (backup/name).exists():raise FileExistsError('Prior unsealed backup exists')
            shutil.copyfile(path,backup/name)
        shutil.copyfile(source/name,path)
    grid.base.save_new(target/'report.json',report)
    return grid.base.digest(target/'report.json')


def qualify(kind,year):
    root=RUNS[kind];job=job_root(kind,year);request=read_json(job/'request.json');profile=request['profile']
    with annual_lock(kind,year),safe_reads():
        p=read_json(root/'protocol.json');grid.base.verify(p['sources']);grid.base.verify(read_json(ROOT/'protocol.json')['sources'])
        grid.base.verify({str(root/'protocol.json'):request['protocol_sha256']})
        if (job/'qualified.json').exists():return
        inv=inventory(kind,year)
        if not (job/'preserved.json').exists():grid.base.save_new(job/'preserved.json',inv)
        grid.atomic_json(job/'progress.json',dict(status='DIAGNOSING',kind=kind,year=year,profile=profile,updated_at_utc=now()))
        evidence=replay_profile(kind,year,profile,job/'diagnosis',fixed=False)
        grid.atomic_json(job/'progress.json',dict(status='VALIDATING_CORRECTION',kind=kind,year=year,profile=profile,updated_at_utc=now()))
        result=replay_profile(kind,year,profile,job/'validation',fixed=True)
        drift_audits={}
        for name in inv['initial_level_drift']:
            grid.atomic_json(job/'progress.json',dict(status='CHECKING_PRIOR_LEVEL_DRIFT',year=year,profile=name,updated_at_utc=now()))
            replay_profile(kind,year,name,job/'prior-validation'/name,fixed=True)
            drift_audits[name]=equivalent_accounts(root/'cases'/f'{year}-{name}',job/'prior-validation'/name/'cases'/f'{year}-{name}')
        installed=install_validated(kind,year,profile,job/'validation/cases'/f'{year}-{profile}')
        grid.base.save_new(job/'qualified.json',dict(status='QUALIFIED',kind=kind,year=year,profile=profile,
            actual_mismatches=evidence['mismatches'],audit=result['audit'],preserved_cases=inv['completed_cases'],
            prior_buy_checks=inv['buy_checks'],prior_drift_audits=drift_audits,installed_report_sha256=installed,
            original_audit_tolerance_unchanged=True,qualified_at_utc=now()))
        grid.atomic_json(root/f'year-{year}.json',dict(status='QUALIFIED_RESUME_PENDING',year=year,
            completed_runs=inv['completed_cases']+1,total_runs=300,qualification=str(job/'qualified.json')))


def resume(kind,year):
    root=RUNS[kind];job=job_root(kind,year)
    with annual_lock(kind,year),safe_reads():
        q=read_json(job/'qualified.json');grid.base.verify(read_json(ROOT/'protocol.json')['sources'])
        grid.base.verify({str(root/'protocol.json'):read_json(job/'request.json')['protocol_sha256']})
        with lever.adapter() if kind=='2x' else nullcontext():
            metrics=grid.metrics
            grid.metrics=lambda result,initial:metrics(result,initial)|dict(fill_price_correction='FIRST_FULL_FILL_AVERAGE_V1',
                correction_amendment_sha256=grid.base.digest(ROOT/'protocol.json'))
            try:
                grid.atomic_json(job/'progress.json',dict(status='RESUMING',kind=kind,year=year,updated_at_utc=now()))
                with correction.corrected_runtime():
                    for attempt in range(3):
                        try:ORIGINAL_WORKER(root,year);break
                        except PermissionError:
                            if attempt==2:raise
                            time.sleep(1)
            finally:grid.metrics=metrics
        for name,r in read_json(job/'preserved.json')['records'].items():
            file=root/'cases'/name/'report.json'
            if grid.base.digest(file)!=r['report_sha256']:raise ValueError('Completed account changed')
            grid.base.verify({str(file.parent/k):v for k,v in r['files'].items()})
        count=len(list((root/'cases').glob(f'{year}-*/report.json')))
        if count!=300:raise ValueError('Incomplete annual grid')
        grid.base.save_new(job/'resolution.json',dict(status='RESOLVED',kind=kind,year=year,completed_runs=count,
            qualified_sha256=grid.base.digest(job/'qualified.json'),all_prior_reports_unchanged=True,resolved_at_utc=now()))


def discover():
    created=[]
    for kind,root in RUNS.items():
        p=read_json(root/'protocol.json')
        for year in p['years']:
            file=root/f'year-{year}.json'
            if not file.exists():continue
            state=read_json(file)
            if state.get('status')!='FAILED' or not cent_error(state.get('error')):continue
            job=job_root(kind,year);job.mkdir(parents=True,exist_ok=True)
            if not (job/'request.json').exists():
                grid.base.save_new(job/'request.json',dict(kind=kind,year=year,profile=state['profile'],error=state['error'],
                    protocol_sha256=grid.base.digest(root/'protocol.json'),state=state,created_at_utc=now()))
                created.append(job.name)
    return created


def next_task(active):
    for phase in ['qualify','resume']:
        for job in sorted(ROOT.glob('*-20*')):
            if not (job/'request.json').exists() or job.name in active or (job/'blocked.json').exists() or (job/'resolution.json').exists():continue
            qualified=(job/'qualified.json').exists()
            if (phase=='qualify' and not qualified) or (phase=='resume' and qualified):
                q=read_json(job/'request.json');return job,phase,q
    return None


def finalize(kind):
    root=RUNS[kind];p=read_json(root/'protocol.json');expected=len(p['profiles'])*len(p['years'])
    if (root/'report.json').exists():return True
    if any((folder/'blocked.json').exists() for folder in ROOT.glob(kind+'-20*')):return False
    if len(list((root/'cases').glob('*/report.json')))!=expected:return False
    if kind=='2x' and not (RUNS['1x']/'report.json').exists():return False
    # Root lock prevents collision with the original parent or a TOP-N worker.
    try:
        with grid.run_lock(root),safe_reads():
            records,_=completed_records(root,p,verify_files=True)
            if len(records)!=expected:return False
            original=read_json(root/'progress.json')
            receipt=ROOT/f'{kind}-original-final-status.json'
            if not receipt.exists():grid.base.save_new(receipt,original)
            if kind in ('1x','2x'):
                if kind=='1x':grid.aggregate(root)
                else:lever.aggregate_2x(root)
            else:
                from scripts.research.us_winner_topn_2017_comparison_20261023 import aggregate
                aggregate(root)
            grid.atomic_json(root/'progress.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',completed_runs=expected,
                total_runs=expected,errors=[],recovery_protocol=str(ROOT/'protocol.json'),updated_at_utc=now()))
            return True
    except OSError as exc:
        if getattr(exc,'winerror',None) in (32,33,36) or exc.errno in (13,11):return False
        raise


def supervise():
    protocol=seal();grid.base.verify(protocol['original_protocols']);active={};failed=set()
    with grid.run_lock(ROOT),safe_reads():
        while True:
            discover()
            for name,job in list(active.items()):
                code=job['process'].poll()
                if code is None:continue
                del active[name]
                if code:
                    failed.add(name)
                    if not (ROOT/name/'blocked.json').exists():grid.base.save_new(ROOT/name/'blocked.json',dict(status='BLOCKED',exit_code=code,phase=job['phase']))
            while len(active)<2:
                item=next_task(active)
                if item is None:break
                folder,phase,q=item
                command=[sys.executable,'-u','-m','scripts.research.us_winner_cent_qualification_20261024',
                    '--phase',phase,'--kind',q['kind'],'--year',str(q['year'])]
                with (folder/f'{phase}.stdout.log').open('ab') as out,(folder/f'{phase}.stderr.log').open('ab') as err:
                    env=dict(os.environ,SSLKEYLOGFILE='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
                    flags=(subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS) if os.name=='nt' else 0
                    proc=subprocess.Popen(command,env=env,stdout=out,stderr=err,creationflags=flags)
                active[folder.name]=dict(process=proc,phase=phase)
            finalized={k:finalize(k) for k in RUNS}
            states=[]
            for folder in sorted(ROOT.glob('*-20*')):
                if not (folder/'request.json').exists():continue
                q=read_json(folder/'request.json');file=folder/'progress.json'
                state=read_json(file) if file.exists() else dict(status='QUEUED')
                if (folder/'resolution.json').exists():state=read_json(folder/'resolution.json')
                elif (folder/'blocked.json').exists():state=read_json(folder/'blocked.json')
                states.append(dict(kind=q['kind'],year=q['year'],phase=active.get(folder.name,{}).get('phase'),detail=state))
            complete=all(finalized.values())
            grid.atomic_json(ROOT/'progress.json',dict(status='COMPLETED' if complete else 'RUNNING',jobs=states,
                active={k:dict(pid=v['process'].pid,phase=v['phase']) for k,v in active.items()},
                finalized=finalized,blocked=sorted(failed),updated_at_utc=now()))
            if complete:break
            if not active and any((ROOT/n/'blocked.json').exists() for n in failed):
                # Do not endlessly retry real errors or declare a mixed/partial grid complete.
                grid.atomic_json(ROOT/'attention-required.json',dict(status='BLOCKED_CASES',jobs=sorted(failed),at_utc=now()))
            time.sleep(10)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=['supervise','qualify','resume'],default='supervise')
    p.add_argument('--kind',choices=list(RUNS));p.add_argument('--year',type=int);a=p.parse_args()
    try:
        if a.phase=='supervise':supervise()
        else:
            seal();{'qualify':qualify,'resume':resume}[a.phase](a.kind,a.year)
    except BaseException as exc:
        folder=job_root(a.kind,a.year) if a.phase!='supervise' else ROOT;folder.mkdir(parents=True,exist_ok=True)
        grid.atomic_json(folder/'blocked.json',dict(status='BLOCKED',phase=a.phase,error_type=type(exc).__name__,error=str(exc),at_utc=now()))
        raise
