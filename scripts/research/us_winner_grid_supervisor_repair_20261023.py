"""Execution-only repair: bounded JSON retries and independent annual subprocesses.

Reuse original sealed protocols, workers, snapshots, reports and metrics unchanged.
No ProcessPoolExecutor shutdown wait; report orchestration exceptions immediately.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
import json
import logging
import os
import subprocess
import sys
import time

from scripts.research import us_winner_native_grid_2017_2026_20261023 as grid
from scripts.research import us_winner_native_grid_2x_2017_2026_20261023 as lever

DOC=Path('doc/ml/winner_grilles_reparation_pilotage_20261023.md')
TEST=Path('tests/test_us_winner_grid_supervisor_repair_20261023.py')
ORIGINAL_READ=grid.base.read


def read_json(path,*,attempts=12,pause=.05):
    """Readers may race a Windows atomic replace. Never accept corrupt final JSON."""
    for attempt in range(attempts):
        try:return json.loads(Path(path).read_text(encoding='utf-8'))
        except (PermissionError,FileNotFoundError,json.JSONDecodeError):
            if attempt+1==attempts:raise
            time.sleep(min(.25,pause*(attempt+1)))


@contextmanager
def safe_reads():
    old=grid.base.read;grid.base.read=read_json
    try:yield
    finally:grid.base.read=old


def resolved_root(kind):
    return grid.ROOT if kind=='1x' else lever.ROOT


def completed_records(root,protocol,*,verify_files=False):
    profiles={p['name']:p for p in protocol['profiles']};records={};by_year={}
    for folder in sorted((root/'cases').glob('*')):
        file=folder/'report.json'
        if not file.exists():continue
        r=read_json(file);year=r.get('year');name=r.get('profile')
        if year not in protocol['years'] or name not in profiles or folder.name!=f'{year}-{name}':
            raise ValueError('Foreign/unexpected case: '+str(folder))
        if (r.get('status')!='COMPLETED_EXPLORATORY' or r.get('smoke') is not False
                or r.get('parameters')!=profiles[name]
                or r.get('audit',{}).get('status')!='PASS_SCALAR_EXITS_CASH_FEES_AND_ENTRIES'
                or r.get('effective_gross_cap')!=protocol['effective_gross_cap']):
            raise ValueError('Unqualified prior case: '+str(folder))
        if verify_files:grid.base.verify({str(folder/n):sha for n,sha in r['files'].items()})
        records[folder.name]=dict(report_sha256=grid.base.digest(file),files=r['files'])
        by_year[year]=by_year.get(year,0)+1
    return records,by_year


def next_ready(pending,completed,active,ready,profiles_per_year):
    for year in pending:
        if completed.get(year,0)<profiles_per_year and year not in active and ready(year):return year
    return None


def status_read(path,last,warnings):
    if not Path(path).exists():return last
    try:return read_json(path)
    except FileNotFoundError:return last
    except (OSError,json.JSONDecodeError) as exc:
        warnings.append(dict(file=str(path),error_type=type(exc).__name__,error=str(exc)))
        return last


def amendment(root,kind):
    folder=root/'supervisor-v2';folder.mkdir(exist_ok=True)
    p=read_json(root/'protocol.json');grid.base.verify(p['sources'])
    path=folder/'amendment.json'
    sources={str(n):grid.base.digest(n) for n in [Path(__file__),DOC,TEST]}
    if path.exists():
        old=read_json(path);grid.base.verify(old['sources'])
        if old['protocol_sha256']!=grid.base.digest(root/'protocol.json') or old['kind']!=kind:
            raise ValueError('Execution amendment drift')
    else:
        # Preserve the stale global summary as evidence, never alter original protocol/results.
        old_progress=root/'progress.json'
        if old_progress.exists():
            grid.atomic_json(folder/'original-progress.json',read_json(old_progress))
        grid.base.save_new(path,dict(created_at_utc=datetime.now(timezone.utc).isoformat(),kind=kind,
            protocol_sha256=grid.base.digest(root/'protocol.json'),sources=sources,
            cause='PermissionError reading year-2017.json; exception deferred inside ProcessPoolExecutor.shutdown(wait=True).',
            changes=['Bounded retry of JSON reads during Windows replace.',
                'Annual subprocesses polled independently, no pool shutdown join.',
                'Skip all verified completed cases/years; fresh progress and immediate errors.'],
            economic_rules_changed=False,original_sources_edited=False,original_protocol_edited=False,
            provider_calls=0,SQL_writes=False,orders=False,maximum_workers=2))
    return p,folder


def annual_command(root,kind,year,attempt):
    return [sys.executable,'-u','-m','scripts.research.us_winner_grid_supervisor_repair_20261023',
        '--phase','year','--kind',kind,'--year',str(year),'--attempt',str(attempt),'--output',str(root)]


def run_year(root,kind,year,attempt):
    p=read_json(root/'protocol.json');grid.base.verify(p['sources'])
    journal=root/'supervisor-v2';journal.mkdir(exist_ok=True)
    result=journal/f'year-{year}-attempt-{attempt}.json'
    lock=journal/'locks'/str(year);lock.mkdir(parents=True,exist_ok=True)
    try:
        with grid.run_lock(lock),safe_reads():
            if kind=='2x':value=lever.leveraged_worker(str(root),year)
            else:value=grid.worker(str(root),year)
        grid.atomic_json(result,dict(status='COMPLETED',year=year,result=value,
            completed_at_utc=datetime.now(timezone.utc).isoformat()))
    except BaseException as exc:
        grid.atomic_json(result,dict(status='FAILED',year=year,error_type=type(exc).__name__,error=str(exc),
            transient_IO=isinstance(exc,PermissionError),failed_at_utc=datetime.now(timezone.utc).isoformat()))
        raise


def supervise(root,kind,workers):
    p,journal=amendment(root,kind);total=len(p['profiles'])*len(p['years'])
    if (root/'report.json').exists():raise FileExistsError('Final grid already sealed')
    grid.atomic_json(root/'progress.json',dict(status='RESTART_AUDIT',total_runs=total,
        updated_at_utc=datetime.now(timezone.utc).isoformat()))
    records,counts=completed_records(root,p,verify_files=True)
    receipt=journal/'preserved-completed.json'
    if not receipt.exists():grid.base.save_new(receipt,dict(records=records,counts=counts,
        verified_at_utc=datetime.now(timezone.utc).isoformat(),completed_before_restart=len(records)))
    preserved=read_json(receipt)['records']
    for name,r in preserved.items():
        if records.get(name)!=r:raise ValueError('A preserved completed case changed: '+name)
    pending=[y for y in p['years'] if counts.get(y,0)<len(p['profiles'])]
    active={};attempts={};errors=[];last_states={};started=time.monotonic();last_scan=0.;scan_warnings=[]
    def ready(year):
        if kind=='1x':
            return year!=2018 or grid.backfill_ready()
        return (lever.REFERENCE/'inputs'/str(year)/'snapshot.json').exists()
    try:
        while pending or active:
            while len(active)<workers:
                year=next_ready(pending,counts,active,ready,len(p['profiles']))
                if year is None:break
                grid.atomic_json(root/'progress.json',dict(status='SNAPSHOT_OR_REUSE',year=year,
                    completed_runs=sum(counts.values()),total_runs=total,supervisor='v2',
                    active_years=list(active),updated_at_utc=datetime.now(timezone.utc).isoformat()))
                try:
                    with safe_reads():
                        if kind=='2x':lever.snapshot_from_reference(root,year)
                        else:grid.snapshot(root,year)
                except Exception as exc:
                    errors.append(dict(year=year,phase='SNAPSHOT',error_type=type(exc).__name__,error=str(exc)))
                    pending.remove(year);continue
                attempt=attempts.get(year,0)+1;attempts[year]=attempt
                out=journal/f'year-{year}-attempt-{attempt}.stdout.log'
                err=journal/f'year-{year}-attempt-{attempt}.stderr.log'
                environment=dict(os.environ,SSLKEYLOGFILE='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
                with out.open('wb') as stdout,err.open('wb') as stderr:
                    proc=subprocess.Popen(annual_command(root,kind,year,attempt),cwd=Path.cwd(),
                        env=environment,stdout=stdout,stderr=stderr,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                active[year]=dict(process=proc,attempt=attempt,pid=proc.pid)
                pending.remove(year)
            for year,job in list(active.items()):
                code=job['process'].poll()
                if code is None:continue
                del active[year]
                file=journal/f'year-{year}-attempt-{job["attempt"]}.json'
                result=status_read(file,None,scan_warnings) if file.exists() else None
                if code!=0 or not result or result.get('status')!='COMPLETED':
                    if result and result.get('transient_IO') and job['attempt']<3:
                        pending.insert(0,year)
                    else:errors.append(dict(year=year,phase='REPLAY',exit_code=code,details=result))
                # Completion is established from actual sealed reports, never just a status word.
                records,counts=completed_records(root,p,verify_files=False)
                last_scan=time.monotonic()
                if code==0 and counts.get(year,0)!=len(p['profiles']):
                    errors.append(dict(year=year,phase='RESULT_COUNT',error='Annual subprocess returned without all profiles'))
            if time.monotonic()-last_scan>5:
                try:records,counts=completed_records(root,p,verify_files=False);scan_warnings=[]
                except (OSError,json.JSONDecodeError) as exc:
                    scan_warnings.append(dict(phase='COUNTER_READ',error=str(exc)))
                last_scan=time.monotonic()
            for year in p['years']:
                value=status_read(root/f'year-{year}.json',last_states.get(year),scan_warnings)
                if value:last_states[year]=value
            if not active and pending and not any(ready(y) for y in pending):
                if kind=='1x':
                    b=read_json(grid.BACKFILL)
                    if b.get('status')!='RUNNING':
                        errors.append(dict(phase='INPUT',pending=pending,error='2018 catchup not complete'));pending=[]
                else:
                    ref=status_read(lever.REFERENCE/'progress.json',{},scan_warnings)
                    if ref.get('status') in ('FAILED','PARTIAL_FAILED','COMPLETED_AUDITED_EXPLORATORY'):
                        errors.append(dict(phase='INPUT',pending=pending,error='Reference ended before required snapshots'));pending=[]
            grid.atomic_json(root/'progress.json',dict(status='RUNNING' if active else 'WAITING_INPUTS' if pending else 'AGGREGATING',
                supervisor='v2',kind=kind,completed_runs=sum(counts.values()),total_runs=total,
                preserved_completed_runs=len(preserved),completed_by_year=counts,
                active_years={y:dict(pid=j['pid'],attempt=j['attempt']) for y,j in active.items()},
                pending_years=pending,years=list(last_states.values()),errors=errors,
                monitor_warnings=scan_warnings[-20:],elapsed_since_restart_seconds=time.monotonic()-started,
                updated_at_utc=datetime.now(timezone.utc).isoformat()))
            if pending or active:time.sleep(2)
        records,counts=completed_records(root,p,verify_files=True)
        for name,r in preserved.items():
            if records.get(name)!=r:raise ValueError('Preserved case drift at completion: '+name)
        if errors or len(records)!=total:
            grid.atomic_json(root/'progress.json',dict(status='PARTIAL_FAILED',supervisor='v2',
                completed_runs=len(records),total_runs=total,errors=errors,updated_at_utc=datetime.now(timezone.utc).isoformat()))
            raise RuntimeError('Incomplete grid; valid completed cases remain preserved')
        with safe_reads():
            top3=lever.aggregate_2x(root) if kind=='2x' else grid.aggregate(root)
        grid.atomic_json(root/'progress.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',supervisor='v2',
            completed_runs=len(records),total_runs=total,top3=top3,errors=[],updated_at_utc=datetime.now(timezone.utc).isoformat()))
    except BaseException as exc:
        # Unlike ProcessPoolExecutor.__exit__, no wait on year-long tasks before exposing an error.
        for job in active.values():
            proc=job['process']
            if proc.poll() is None:proc.terminate()
        for job in active.values():
            try:job['process'].wait(timeout=5)
            except subprocess.TimeoutExpired:job['process'].kill()
        grid.atomic_json(journal/'supervisor-error.json',dict(error_type=type(exc).__name__,error=str(exc),
            occurred_at_utc=datetime.now(timezone.utc).isoformat(),completed_cases_preserved=True))
        if not isinstance(exc,RuntimeError) or not errors:
            grid.atomic_json(root/'progress.json',dict(status='FAILED_SUPERVISOR',supervisor='v2',
                completed_runs=sum(counts.values()),total_runs=total,error_type=type(exc).__name__,error=str(exc),
                updated_at_utc=datetime.now(timezone.utc).isoformat()))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind',choices=['1x','2x'],required=True)
    parser.add_argument('--phase',choices=['supervise','year'],default='supervise')
    parser.add_argument('--output',type=Path);parser.add_argument('--workers',type=int,choices=[1,2],default=2)
    parser.add_argument('--year',type=int);parser.add_argument('--attempt',type=int,default=1)
    a=parser.parse_args();root=a.output or resolved_root(a.kind)
    if root.resolve()!=resolved_root(a.kind).resolve():raise ValueError('Only exact existing research grid roots may be repaired')
    logging.basicConfig(level=logging.WARNING,format='%(asctime)s %(levelname)s %(message)s')
    if a.phase=='year':
        if a.year not in grid.YEARS:raise ValueError('Unexpected year')
        run_year(root,a.kind,a.year,a.attempt)
    else:
        try:
            with grid.run_lock(root),safe_reads():supervise(root,a.kind,a.workers)
        except BaseException as exc:
            # Also expose failures during the initial immutable-input audit.
            if not (root/'report.json').exists():
                current=status_read(root/'progress.json',{},[])
                if current.get('status') not in ('FAILED_SUPERVISOR','PARTIAL_FAILED'):
                    grid.atomic_json(root/'progress.json',dict(status='FAILED_SUPERVISOR',supervisor='v2',
                        error_type=type(exc).__name__,error=str(exc),updated_at_utc=datetime.now(timezone.utc).isoformat()))
            raise


if __name__=='__main__':main()
