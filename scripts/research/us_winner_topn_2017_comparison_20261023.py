"""Separate TOP20/TOP50 2017 grids; preserve sealed TOP10 economics and runs."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import time

import pandas as pd
from sqlalchemy import bindparam, text

from scripts.research import us_winner_native_grid_2017_2026_20261023 as grid
from scripts.research.us_winner_grid_supervisor_repair_20261023 import read_json, safe_reads, completed_records

ROOT = Path('artifacts/research/us_winner_topn_2017/20261023-v1')
REFERENCE = grid.ROOT
SCORE_ROOT = Path('artifacts/research/us_winner_global_selector/20261023-v1')
DOC = Path('doc/ml/winner_top20_top50_2017_protocole_20261023.md')
TEST = Path('tests/test_us_winner_topn_2017_comparison_20261023.py')


def select_scores(frame, top_n, reference):
    if top_n not in (20, 50):
        raise ValueError('Only the authorized TOP20 and TOP50')
    f = frame[frame.date.dt.year.eq(2017) & frame['rank'].le(top_n)].copy()
    if f.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate score keys')
    if not f.groupby('date')['rank'].apply(lambda s: sorted(s) == list(range(1, top_n+1))).all():
        raise ValueError('Incomplete original ranking')
    columns = list(reference.columns)
    a = f[f['rank'].le(10)][columns].sort_values(['date', 'rank']).reset_index(drop=True)
    b = reference.sort_values(['date', 'rank']).reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b, check_exact=True)
    if not (pd.to_datetime(f.model_available_date) < f.date).all():
        raise ValueError('Noncausal model')
    return f[columns].sort_values(['date', 'rank']).reset_index(drop=True)


def seal_frame(folder, name, frame):
    path = folder/name
    frame.to_parquet(path, index=False)
    marker = dict(sha256=grid.base.digest(path), rows=len(frame))
    grid.base.save_new(path.with_suffix('.json'), marker)
    return {name: marker['sha256'], path.with_suffix('.json').name: grid.base.digest(path.with_suffix('.json'))}


def prepare():
    ROOT.mkdir(parents=True, exist_ok=True)
    path = ROOT/'protocol.json'
    if path.exists():
        p = read_json(path); grid.base.verify(p['sources']); return p
    old = read_json(REFERENCE/'protocol.json'); grid.base.verify(old['sources'])
    score_meta = read_json(SCORE_ROOT/'scores.json')
    grid.base.verify({str(SCORE_ROOT/'top100.parquet'): score_meta['sha256']})
    grid.base.verify(score_meta['inputs'])
    ref_folder = REFERENCE/'inputs/2017'
    m = read_json(ref_folder/'snapshot.json')
    grid.base.verify({str(ref_folder/n): v for n,v in m['files'].items()})
    reference = pd.read_parquet(ref_folder/'signals.parquet')
    source = pd.read_parquet(SCORE_ROOT/'top100.parquet')
    sources = dict(old['sources'])
    sources.update({str(n): grid.base.digest(n) for n in [Path(__file__), DOC, TEST,
        REFERENCE/'protocol.json', ref_folder/'snapshot.json', SCORE_ROOT/'scores.json', SCORE_ROOT/'top100.parquet',
        Path('scripts/research/us_winner_grid_supervisor_repair_20261023.py')]})
    p = deepcopy(old)
    p.update(created_at_utc=datetime.now(timezone.utc).isoformat(), sources=sources, years=[2017],
        end='2017-12-31', total_runs=600, top_values=[20,50], reference_root=str(REFERENCE),
        score_archive=str(SCORE_ROOT), economic_rules_changed=False, effective_gross_cap=1.,
        ranking='Descriptive 2017 only, matched profile deltas vs TOP10; no deployable champion selection.',
        input_policy='Original TOP10 raw/daily/sectors/actions frozen; SQL READ ONLY for added symbols only.',
        common_quality_rule='Same J..J+40 complete-window gate for all TOP-N; no replacement after exclusion.',
        notes=['Two independent 4000 USD accounts, HALF/no reinforcement, max 8 positions.',
               'Effective exposure cap 1x as reference, not forced investment; same original margin/settlement config.',
               '2017 only and already observed; static universe/current sector and future coverage selection bias.'])
    for n in p['top_values']:
        root = ROOT/f'top{n}'; folder = root/'inputs/2017'; folder.mkdir(parents=True, exist_ok=True)
        scores = select_scores(source, n, reference)
        scores.to_parquet(folder/'signals.parquet', index=False)
        q = deepcopy(p); q.update(TOP=n, total_runs=300, top_values=[n])
        q['signal_sha256'] = grid.base.digest(folder/'signals.parquet')
        grid.base.save_new(root/'protocol.json', q)
        grid.atomic_json(root/'progress.json', dict(status='PREPARED', top_n=n, completed_runs=0, total_runs=300))
    grid.base.save_new(path, p)
    return p


def combined_frame(original, added, name):
    if name == 'daily.parquet':
        result = pd.concat([original, added], ignore_index=True)
        if result.duplicated(['symbol','date']).any(): raise ValueError('Duplicate daily merge')
    elif name == 'sectors.parquet':
        result = pd.concat([original, added], ignore_index=True)
        if result.symbol.duplicated().any(): raise ValueError('Duplicate sector merge')
    else:
        result = pd.concat([original, added], ignore_index=True)
    return result


def snapshot_expanded():
    """Freeze one TOP50 superset, reused byte-for-byte by TOP20 where relevant."""
    root = ROOT/'top50'; folder = root/'inputs/2017'; manifest = folder/'snapshot.json'
    if manifest.exists():
        m = read_json(manifest); grid.base.verify({str(folder/n):v for n,v in m['files'].items()}); return
    ref = REFERENCE/'inputs/2017'; prior = read_json(ref/'snapshot.json')
    scores = pd.read_parquet(folder/'signals.parquet')
    known = {r['symbol']:r for r in prior['receipts']}
    symbols = sorted(scores.symbol.unique()); added = sorted(set(symbols)-set(known))
    seed = min(pd.read_parquet(ref/'daily.parquet')['date'])
    raw_start = min(pd.read_parquet(ref/'signals.parquet').date).date()
    files = {}; receipts = []
    from database.connection import get_sqlalchemy_engine
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    try:
        with engine.connect() as conn, conn.begin():
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=30000'))
            conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade': raise ValueError('US only')
            for i,symbol in enumerate(symbols):
                file = folder/f'sip-{i:03}.parquet'; marker = file.with_suffix('.json')
                if marker.exists():
                    r = read_json(marker); grid.base.verify({str(file): r['sha256']})
                    if r['symbol'] != symbol: raise ValueError('Snapshot symbol drift')
                elif symbol in known:
                    r0 = known[symbol]; shutil.copyfile(ref/r0['file'], file)
                    r = dict(r0, file=file.name, copied_frozen_reference=True)
                    grid.base.save_new(marker, r)
                else:
                    q = text("SELECT symbol,trade_date,bar_timestamp,bar_end_timestamp,open,high,low,close,volume,payload_hash "
                        "FROM stock_bars_intraday FORCE INDEX(PRIMARY) WHERE symbol=:symbol AND bar_timestamp>=:start "
                        "AND bar_timestamp<:end AND provider='alpaca' AND data_source='alpaca_sip' AND interval_code='5m' "
                        "AND market_code='US_EQ' AND session_tag='regular' AND data_adjustment='raw' AND is_filled=0 ORDER BY bar_timestamp")
                    f = pd.read_sql(q, conn, params=dict(symbol=symbol, start=str(raw_start), end='2018-01-01'))
                    for k in ['bar_timestamp','bar_end_timestamp']: f[k] = pd.to_datetime(f[k], utc=True)
                    f['trade_date'] = pd.to_datetime(f.trade_date); f.to_parquet(file, index=False)
                    r = dict(symbol=symbol,file=file.name,rows=len(f),sha256=grid.base.digest(file),
                             observed_at_utc=datetime.now(timezone.utc).isoformat())
                    grid.base.save_new(marker,r)
                receipts.append(r); files[file.name]=r['sha256']; files[marker.name]=grid.base.digest(marker)
                grid.atomic_json(ROOT/'progress.json',dict(status='SNAPSHOT_READ_ONLY',symbol=symbol,
                    completed_symbols=i+1,total_symbols=len(symbols),added_symbols=len(added),completed_runs=0,total_runs=600))
            queries = {
                'daily.parquet': ('SELECT symbol,date,open,high,low,close,volume,data_source,data_adjustment,is_filled '
                    'FROM stock_bars_daily FORCE INDEX(PRIMARY) WHERE symbol IN :symbols AND date BETWEEN :start AND :end',
                    dict(symbols=added,start=str(pd.Timestamp(seed).date()),end='2017-12-31')),
                'sectors.parquet': ('SELECT symbol,sector FROM stock_metadata WHERE symbol IN :symbols', dict(symbols=added)),
                'actions.parquet': ('SELECT symbol,ca_type,ex_date,payable_date,amount_per_share,currency FROM corporate_actions_events '
                    'WHERE symbol IN :symbols AND ex_date BETWEEN :start AND :end',dict(symbols=added,start=str(raw_start),end='2017-12-31'))}
            for name,(sql,params) in queries.items():
                marker = (folder/name).with_suffix('.json')
                if marker.exists():
                    r = read_json(marker); grid.base.verify({str(folder/name):r['sha256']})
                    files.update({name:r['sha256'],marker.name:grid.base.digest(marker)}); continue
                old = pd.read_parquet(ref/name)
                fresh = pd.read_sql(text(sql).bindparams(bindparam('symbols',expanding=True)),conn,params=params) if added else old.iloc[:0]
                files.update(seal_frame(folder,name,combined_frame(old,fresh,name)))
    finally: engine.dispose()
    files['signals.parquet']=grid.base.digest(folder/'signals.parquet')
    grid.base.save_new(manifest,dict(year=2017,receipts=receipts,files=files,SQL_reads_only=True,SQL_writes=False,
        provider_calls=0,metadata_current_non_PIT=True,frozen_TOP10_inputs_preserved=True))


def snapshot_top20():
    source=ROOT/'top50/inputs/2017'; folder=ROOT/'top20/inputs/2017'
    if (folder/'snapshot.json').exists():
        m=read_json(folder/'snapshot.json'); grid.base.verify({str(folder/n):v for n,v in m['files'].items()}); return
    m=read_json(source/'snapshot.json'); files={}
    for name,sha in m['files'].items():
        if name=='signals.parquet': continue
        shutil.copyfile(source/name,folder/name); files[name]=sha
    files['signals.parquet']=grid.base.digest(folder/'signals.parquet')
    grid.base.save_new(folder/'snapshot.json',dict(m,files=files,paired_TOP50_snapshot=True))


@contextmanager
def observed_metrics():
    old=grid.metrics
    def measured(result,initial):
        r=old(result,initial);f=result.intraday_equity_curve;active=f.gross.gt(0)
        r.update(fraction_flat_5m=float((~active).mean()),
            average_gross_capital_when_invested=float(f.loc[active,'gross'].mean()) if active.any() else 0.,
            average_gross_equity_ratio_when_invested=float((f.loc[active,'gross']/f.loc[active,'equity']).mean()) if active.any() else 0.,
            maximum_gross_equity_ratio=float((f.gross/f.equity).max()))
        return r
    grid.metrics=measured
    try: yield
    finally: grid.metrics=old


def aggregate(root):
    p=read_json(root/'protocol.json'); records,_=completed_records(root,p,verify_files=True)
    if len(records)!=300: raise ValueError('All 300 cases required')
    rows=[]
    for name in records:
        r=read_json(root/'cases'/name/'report.json'); ref=read_json(REFERENCE/'cases'/name/'report.json')
        rows.append(dict(top_n=p['TOP'],**{k:v for k,v in r.items() if not isinstance(v,(dict,list))},
            top10_return_pct=ref['return_pct'],return_delta_pp=r['return_pct']-ref['return_pct'],
            top10_dd_pct=ref['max_drawdown_pct'],top10_mean_capital=ref['average_gross_capital']))
    f=pd.DataFrame(rows);f.to_csv(root/'comparison-vs-top10.csv',index=False)
    grid.base.save_new(root/'report.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',cases=300,top_n=p['TOP'],
        best_2017_descriptive_only=f.sort_values('return_pct',ascending=False).head(3).to_dict('records'),
        full_live_parity=False,independent_holdout=False,future_coverage_selection_bias=True,
        files={'comparison-vs-top10.csv':grid.base.digest(root/'comparison-vs-top10.csv')}))


def run_one(top_n):
    root=ROOT/f'top{top_n}'
    if top_n not in (20,50): raise ValueError('Unauthorized TOP-N')
    try:
        with grid.run_lock(root),safe_reads(),observed_metrics():
            p=read_json(root/'protocol.json'); grid.base.verify(p['sources'])
            if (root/'report.json').exists(): return
            if not list((root/'cases').glob('*/report.json')):
                grid.worker(root,2017,smoke=True)
                grid.atomic_json(root/'smoke-passed.json',read_json(root/'year-2017.json'))
            for attempt in range(3):
                try: grid.worker(root,2017); break
                except PermissionError:
                    if attempt==2: raise
                    time.sleep(1)
            aggregate(root)
    except BaseException as exc:
        grid.atomic_json(root/'error.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise


def supervise():
    ROOT.mkdir(parents=True,exist_ok=True)
    jobs={};started=time.monotonic()
    try:
        with grid.run_lock(ROOT),safe_reads():
            prepare(); snapshot_expanded(); snapshot_top20()
            for n in (20,50):
                if (ROOT/f'top{n}/report.json').exists(): continue
                command=[sys.executable,'-u','-m','scripts.research.us_winner_topn_2017_comparison_20261023','--phase','year','--top',str(n)]
                env=dict(os.environ,SSLKEYLOGFILE='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
                with (ROOT/f'top{n}.stdout.log').open('ab') as out,(ROOT/f'top{n}.stderr.log').open('ab') as err:
                    flags=(subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS) if os.name=='nt' else 0
                    jobs[n]=subprocess.Popen(command,stdout=out,stderr=err,env=env,creationflags=flags)
            while True:
                states=[];errors=[];total=0
                for n in (20,50):
                    root=ROOT/f'top{n}'; reports=list((root/'cases').glob('*/report.json'));total+=len(reports)
                    state=read_json(root/'year-2017.json') if (root/'year-2017.json').exists() else {}
                    done=(root/'report.json').exists();code=jobs[n].poll() if n in jobs else 0
                    states.append(dict(top_n=n,completed_runs=len(reports),total_runs=300,
                        status='COMPLETED_AUDITED_EXPLORATORY' if done else 'FAILED' if code is not None else 'RUNNING',
                        pid=jobs[n].pid if n in jobs else None,detail=state))
                    if code is not None and not done:errors.append(dict(top_n=n,exit_code=code))
                running=any(j.poll() is None for j in jobs.values())
                status='RUNNING' if running else 'PARTIAL_FAILED' if errors else 'COMPLETED_AUDITED_EXPLORATORY'
                grid.atomic_json(ROOT/'progress.json',dict(status=status,completed_runs=total,total_runs=600,grids=states,
                    errors=errors,elapsed_seconds=time.monotonic()-started,updated_at_utc=datetime.now(timezone.utc).isoformat()))
                if not running: break
                time.sleep(3)
            if errors: raise RuntimeError('One or more TOP-N grids failed; preserved completed cases')
    except BaseException as exc:
        grid.atomic_json(ROOT/'error.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=['supervise','year'],default='supervise')
    p.add_argument('--top',type=int,choices=[20,50]);a=p.parse_args()
    if a.phase=='year':run_one(a.top)
    else:supervise()
