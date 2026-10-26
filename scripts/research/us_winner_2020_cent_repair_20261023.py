"""Versioned diagnostic/remediation of the 2020 cent-level audit failure."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from datetime import datetime,timezone
import csv
import json
import math
import time

from scripts.research import us_winner_native_grid_2017_2026_20261023 as grid
from scripts.research.us_winner_grid_supervisor_repair_20261023 import read_json,safe_reads
import execution_engine.winner_runtime as runtime

ROOT=Path('artifacts/research/us_winner_2020_cent_repair/20261023-v1')
PROFILE='SL5_TROFF_H5_TP20'
ORIGINAL_BOOK=runtime.WinnerCampaignRuntime.book_buy
DOC=Path('doc/ml/winner_2020_correctif_centime_20261023.md')
TEST=Path('tests/test_us_winner_2020_cent_repair_20261023.py')


def initial_fill_price(raw,parent,intent):
    """Replay IOC is one complete fill: do not manufacture a new average."""
    quantity=float(raw.get('filled_qty') or 0)
    if parent['booked_quantity'] or quantity!=intent.qty:
        raise ValueError('Correction qualified only for a first complete replay fill')
    price=float(raw.get('filled_avg_price') or 0)
    if not math.isfinite(price) or price<=0 or price>intent.limit_price+1e-6:
        raise ValueError('Invalid actual fill price')
    return price


def stable_book_buy(self,intent,operation,raw):
    parent=self.state['parents'][intent.intent_id]
    if float(raw.get('filled_qty') or 0)==parent['booked_quantity']:
        return ORIGINAL_BOOK(self,intent,operation,raw)
    price=initial_fill_price(raw,parent,intent)
    original=runtime.add_fill
    def add(state,**kwargs):
        # Everything else (timestamps, quantity, ID, lot, stops, horizon) stays native.
        kwargs['price']=price
        return original(state,**kwargs)
    runtime.add_fill=add
    try:return ORIGINAL_BOOK(self,intent,operation,raw)
    finally:runtime.add_fill=original


@contextmanager
def corrected_runtime():
    old=runtime.WinnerCampaignRuntime.book_buy
    runtime.WinnerCampaignRuntime.book_buy=stable_book_buy
    try:yield
    finally:runtime.WinnerCampaignRuntime.book_buy=old


def preserve_prior(root):
    """Inventory completed cases, hashes and all actual buys, including open lots."""
    records={};checks=0;drifts=[]
    for file in sorted((root/'cases').glob('2020-*/report.json')):
        r=read_json(file);grid.base.verify({str(file.parent/k):v for k,v in r['files'].items()})
        if r['audit']['status']!='PASS_SCALAR_EXITS_CASH_FEES_AND_ENTRIES':raise ValueError('Prior audit failed')
        records[file.parent.name]=dict(report_sha256=grid.base.digest(file),files=r['files'])
        sl=r['parameters']['stop_loss_pct'];tp=r['parameters']['take_profit_pct']
        with (file.parent/'events.csv').open(encoding='utf-8',newline='') as stream:
            for row in csv.DictReader(stream):
                if row['event']!='BUY_FILL':continue
                a=float(row['price']);q=float(row['quantity']);b=q*a/q;checks+=1
                if round(a*(1-sl),2)!=round(b*(1-sl),2) or tp and round(a*(1+tp),2)!=round(b*(1+tp),2):
                    drifts.append(dict(case=file.parent.name,symbol=row['symbol'],time=row['time']))
    if drifts:raise ValueError('Previously completed accounts need separate recomputation: '+str(drifts[:5]))
    return dict(records=records,completed_cases=len(records),actual_buy_checks=checks,
        changed_protection_levels=drifts,checked_at_utc=datetime.now(timezone.utc).isoformat())


def validate_case():
    """Replay just the failed profile with correction and unchanged strict audit."""
    folder=ROOT/'validation';folder.mkdir(parents=True,exist_ok=True)
    p=deepcopy(read_json(grid.ROOT/'protocol.json'));p['profiles']=[x for x in p['profiles'] if x['name']==PROFILE]
    p['sources'].update({str(n):grid.base.digest(n) for n in [Path(__file__),DOC,TEST]})
    p['runtime_override']='FIRST_FULL_FILL_AVERAGE_V1'
    if not (folder/'protocol.json').exists():grid.base.save_new(folder/'protocol.json',p)
    original=grid.load_year;grid.load_year=lambda root,year:original(grid.ROOT,year)
    try:
        with safe_reads(),corrected_runtime():return grid.worker(folder,2020)
    finally:grid.load_year=original


def resume():
    root=grid.ROOT;ROOT.mkdir(parents=True,exist_ok=True)
    lock=root/'supervisor-v2/locks/2020';lock.mkdir(parents=True,exist_ok=True)
    with grid.run_lock(lock),safe_reads():
        p=read_json(root/'protocol.json');grid.base.verify(p['sources'])
        diagnosis=read_json(ROOT/'diagnosis/diagnosis.json')
        if not diagnosis['mismatches']:raise ValueError('No concrete failed trade diagnosed')
        sources={str(n):grid.base.digest(n) for n in [Path(__file__),DOC,TEST]}
        path=ROOT/'amendment.json'
        if path.exists():
            amendment=read_json(path);grid.base.verify(amendment['sources'])
            grid.base.verify({str(root/'protocol.json'):amendment['protocol_sha256'],
                str(ROOT/'preserved-2020.json'):amendment['preserved_sha256']})
        else:
            prior=preserve_prior(root)
            grid.base.save_new(ROOT/'preserved-2020.json',prior)
            grid.base.save_new(path,dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,
                protocol_sha256=grid.base.digest(root/'protocol.json'),preserved_sha256=grid.base.digest(ROOT/'preserved-2020.json'),
                correction='Use broker first complete fill average unchanged, before native round(x,2) protections.',
                original_sources_changed=False,SQL_writes=False,provider_calls=0,orders=False,
                audit_tolerance_changed=False,completed_cases_preserved=prior['completed_cases']))
        if not (ROOT/'validation/cases'/f'2020-{PROFILE}'/'report.json').exists():validate_case()
        validation=ROOT/'validation/cases'/f'2020-{PROFILE}'/'report.json'
        verified=read_json(validation)
        if verified['audit']['status']!='PASS_SCALAR_EXITS_CASH_FEES_AND_ENTRIES':raise ValueError('Validation audit failed')
        grid.base.verify({str(validation.parent/k):v for k,v in verified['files'].items()})
        if not (ROOT/'validation-passed.json').exists():
            grid.base.save_new(ROOT/'validation-passed.json',dict(status='PASS',report_sha256=grid.base.digest(validation),
                audit=verified['audit'],amendment_sha256=grid.base.digest(path)))
        saved=grid.metrics
        def metrics(result,initial):
            return saved(result,initial)|dict(fill_price_correction='FIRST_FULL_FILL_AVERAGE_V1',
                correction_amendment_sha256=grid.base.digest(path))
        grid.metrics=metrics
        try:
            grid.atomic_json(ROOT/'progress.json',dict(status='RUNNING',year=2020,initial_completed=104,total_runs=300,
                updated_at_utc=datetime.now(timezone.utc).isoformat()))
            with corrected_runtime():
                for attempt in range(3):
                    try:value=grid.worker(root,2020);break
                    except PermissionError:
                        if attempt==2:raise
                        time.sleep(1)
            for name,r in read_json(ROOT/'preserved-2020.json')['records'].items():
                file=root/'cases'/name/'report.json'
                if grid.base.digest(file)!=r['report_sha256']:raise ValueError('Preserved report changed')
                grid.base.verify({str(file.parent/k):v for k,v in r['files'].items()})
            grid.atomic_json(ROOT/'progress.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',year=2020,
                completed_runs=300,total_runs=300,result=value,original_error_resolved=True,
                updated_at_utc=datetime.now(timezone.utc).isoformat()))
            grid.base.save_new(ROOT/'resolution.json',dict(status='RESOLVED',year=2020,original_error='10.73 != 10.74',
                completed_runs=300,all_original_completed_reports_preserved=True,amendment_sha256=grid.base.digest(path)))
        finally:grid.metrics=saved


def diagnose():
    folder=ROOT/'diagnosis';folder.mkdir(parents=True,exist_ok=True)
    if (folder/'diagnosis.json').exists():raise FileExistsError('Diagnosis already sealed')
    p=read_json(grid.ROOT/'protocol.json');grid.base.verify(p['sources'])
    p=deepcopy(p);p['profiles']=[x for x in p['profiles'] if x['name']==PROFILE]
    grid.base.save_new(folder/'protocol.json',p)
    # Read original input archives without copying/modifying them.
    original_load=grid.load_year
    grid.load_year=lambda root,year:original_load(grid.ROOT,year)
    original_book=runtime.WinnerCampaignRuntime.book_buy
    original_add=runtime.add_fill
    fills=[]
    def book(self,intent,operation,raw):
        def add(state,**kwargs):
            result=original_add(state,**kwargs)
            fills.append(dict(symbol=state['symbol'],raw_average=raw.get('filled_avg_price'),
                raw_quantity=raw.get('filled_qty'),reconstructed_price=kwargs['price'],
                stop=state['lots'][-1]['stop'],tp=state['lots'][-1]['tp'],filled_at=str(kwargs['filled_at'])))
            return result
        runtime.add_fill=add
        try:return original_book(self,intent,operation,raw)
        finally:runtime.add_fill=original_add
    original_audit=grid.audit_result
    def audit(result,summary,profile,cohort,raw,sessions):
        ds=[s.session_date for s in sessions];idx={d:i for i,d in enumerate(ds)};mismatches=[]
        for t in result.closed_trades_df.itertuples():
            day=t.entry_date.tz_convert('America/New_York').date()
            due=sessions[idx[day]+profile['horizon_sessions']].open_at_utc
            got=grid.scalar_exit(raw[t.symbol],t.entry_date,t.entry_price,due,
                sl=profile['stop_loss_pct'],tp=profile['take_profit_pct'],trail=profile['trailing_stop_pct'])
            if got is None or abs(got[1]-t.exit_price)>1e-7 or got[0]!=t.exit_date or got[2]!=t.exit_reason:
                mismatches.append(dict(symbol=t.symbol,quantity=t.quantity,entry_price=t.entry_price,
                    entry_time=str(t.entry_date),actual_price=t.exit_price,actual_reason=t.exit_reason,
                    actual_time=str(t.exit_date),scalar=str(got),
                    fills=[x for x in fills if x['symbol']==t.symbol and x['filled_at']==str(t.entry_date.to_pydatetime())]))
        result.closed_trades_df.to_parquet(folder/'diagnostic-trades.parquet',index=False)
        grid.base.save_new(folder/'diagnosis.json',dict(mismatches=mismatches,fills=fills,
            original_protocol_sha256=grid.base.digest(grid.ROOT/'protocol.json'),
            source_sha256=grid.base.digest(__file__),original_sources_modified=False))
        print(json.dumps(mismatches,indent=2),flush=True)
        return original_audit(result,summary,profile,cohort,raw,sessions)
    runtime.WinnerCampaignRuntime.book_buy=book;grid.audit_result=audit
    try:
        with safe_reads():grid.worker(folder,2020)
    finally:
        grid.load_year=original_load;runtime.WinnerCampaignRuntime.book_buy=original_book;grid.audit_result=original_audit


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=['diagnose','validate','resume'],default='diagnose')
    a=p.parse_args()
    try:{'diagnose':diagnose,'validate':validate_case,'resume':resume}[a.phase]()
    except BaseException as exc:
        ROOT.mkdir(parents=True,exist_ok=True)
        grid.atomic_json(ROOT/f'{a.phase}-error.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
