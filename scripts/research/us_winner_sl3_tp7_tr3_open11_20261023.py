"""One frozen SL3/TP7/TR3/open11 variant, native Winner, existing offline inputs."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from dataclasses import replace
from datetime import date,datetime,timezone
from pathlib import Path
import logging
import time

import numpy as np
import pandas as pd
from scripts.research import us_winner_bottom_rank_filter_20261022 as source
from scripts.research import us_winner_bottom_rank_filter_whole_shares_20261022 as adapter
from backtesting.winner_campaign_replay import atomic_json,metrics
import backtesting.winner_intraday as native

PARENT=Path('artifacts/research/us_winner_bottom_rank_filter/20261022-v2')
ROOT=Path('artifacts/research/us_winner_sl3_tp7_tr3_open11/20261023-v1')
DOC=Path('doc/ml/winner_sl3_tp7_tr3_open11_protocole_20261023.md')
ARM='SL3_TP7_TR3_OPEN11'
RULE=dict(stop_loss_pct=.03,take_profit_pct=.07,trailing_stop_pct=.03,horizon_sessions=10)
LOG=logging.getLogger(__name__)


def variant_config(protocol,year,*,smoke=False):
    cfg=source.engine_config(protocol,year)
    wp=replace(cfg.exec_config.winner_pyramiding,**RULE)
    cfg=replace(cfg,exec_config=replace(cfg.exec_config,winner_pyramiding=wp))
    if smoke:
        cal=source.get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
        fifth=[s for s in cal.sessions(date(year,1,1),date(year,2,1)) if s.is_open][4].session_date
        cfg=replace(cfg,end_date=fifth)
    return cfg


def prepare(root,*,smoke=False):
    if root.exists():raise FileExistsError('Fresh output required')
    old=source.read(PARENT/'protocol.json');source.verify(old['sources'])
    report=source.read(PARENT/'report.json');audit=source.read(PARENT/'final-audit.json')
    if audit['report_sha256']!=source.digest(PARENT/'report.json'):raise ValueError('Reference cash audit changed')
    source.verify({str(PARENT/k):v for k,v in report['files'].items()})
    snap=source.read(PARENT/'snapshot.json');source.verify({str(PARENT/k):v for k,v in snap['files'].items()})
    inputs=[Path(__file__),DOC,Path('scripts/research/us_winner_sl3_tp7_tr3_open11_audit_20261023.py'),
        Path('tests/test_us_winner_sl3_tp7_tr3_open11_20261023.py'),PARENT/'protocol.json',PARENT/'report.json',
        PARENT/'final-audit.json',PARENT/'snapshot.json',PARENT/'qualified-signals.parquet',PARENT/'session-quality.parquet']
    for y in (2025,2026):
        c=source.read(PARENT/f'{y}-WINNER_ONLY/report.json')
        source.verify({str(PARENT/f'{y}-WINNER_ONLY'/k):v for k,v in c['files'].items()})
        inputs.extend([PARENT/f'{y}-WINNER_ONLY'/k for k in ['report.json',*c['files']]])
    sources={**old['sources'],**{str(x):source.digest(x) for x in inputs},**{str(PARENT/k):v for k,v in snap['files'].items()}}
    root.mkdir(parents=True)
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,parent=str(PARENT),
        reference_protocol=old,rule=RULE,arm=ARM,smoke=smoke,years=[2025] if smoke else [2025,2026],
        same_sizing_formula_not_quantity=True,entry_wait_sessions_unchanged=20,
        effective_gross_cap=old['effective_gross_cap'],baseline='Reuse existing audited native WINNER_ONLY annual accounts',
        training=False,SQL_reads=0,SQL_writes=False,provider_calls=0,broker_calls=0,production_changed=False,
        independent_holdout=False,full_live_parity=False)
    source.save_new(root/'protocol.json',p)
    atomic_json(root/'progress.json',dict(status='PREPARED',completed_runs=0,total_runs=len(p['years'])))
    return p


def load_inputs():
    snap=source.read(PARENT/'snapshot.json')
    cal=source.get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    schedule={s.session_date:s for s in cal.sessions(date(2024,12,30),date(2026,9,30)) if s.is_open}
    groups={}
    for n,item in enumerate(snap['receipts']):
        f=pd.read_parquet(PARENT/item['file'])
        for day,g in f.groupby('trade_date',sort=True):
            d=pd.Timestamp(day).date();s=schedule.get(d)
            if s is not None and source.qualify_session(g,s):
                groups[item['symbol'],d]=g.rename(columns={'bar_timestamp':'timestamp'}).copy()
        if n%30==0:LOG.info('Qualified SIP %d/%d',n+1,len(snap['receipts']))
    meta=pd.read_parquet(PARENT/'sectors.parquet')
    sectors={str(x.symbol):str(x.sector) for x in meta.dropna().itertuples()}
    actions=pd.read_parquet(PARENT/'actions.parquet');actions['ex_date']=pd.to_datetime(actions.ex_date)
    actions['payable_date']=pd.to_datetime(actions.payable_date).dt.date
    observed=source.common_cohort(pd.read_parquet(PARENT/'frozen-signals.parquet'),groups,actions,sectors)
    frozen=pd.read_parquet(PARENT/'qualified-signals.parquet')
    pd.testing.assert_frame_equal(observed,frozen,check_exact=True)
    symbols=set(frozen.symbol)|{'SPY'}
    daily=pd.read_parquet(source.DAILY,filters=[('symbol','in',list(symbols))])
    if daily.duplicated(['symbol','date']).any():raise ValueError('Duplicate daily')
    numeric=daily[['open','high','low','close','volume']]
    valid=np.isfinite(numeric).all(axis=1)&numeric.gt(0).all(axis=1)&daily.is_filled.eq(0)&daily.data_adjustment.eq('split')
    daily=daily.copy();daily.loc[~valid,['open','high','low','close','volume']]=np.nan
    pivots={k:daily.pivot(index='date',columns='symbol',values=k).astype(float) for k in ('open','high','low','close','volume')}
    return frozen,groups,actions,sectors,pivots


@contextmanager
def native_adapters(year):
    stage,calendar=native.stage_targets,native.get_market_calendar
    old_case,old_refusals=adapter.CURRENT_CASE,adapter.REFUSALS
    cache=adapter.CachedCalendar(calendar('US_EQ',allow_us_weekday_fallback=False))
    adapter.CURRENT_CASE=dict(year=year,arm=ARM);adapter.REFUSALS=[]
    native.stage_targets=adapter.stage_whole_shares;native.get_market_calendar=lambda *a,**k:cache
    try:yield adapter.REFUSALS
    finally:
        native.stage_targets=stage;native.get_market_calendar=calendar
        adapter.CURRENT_CASE=old_case;adapter.REFUSALS=old_refusals


def run(root):
    p=source.read(root/'protocol.json');source.verify(p['sources'])
    if (root/'report.json').exists():raise FileExistsError('Already sealed')
    signals,groups,actions,sectors,pivots=load_inputs();started=time.monotonic();cases=[]
    def bars(day,symbols):
        parts=[groups[s,day] for s in symbols if (s,day) in groups]
        return pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()
    try:
        for year in p['years']:
            folder=root/f'{year}-{ARM}'
            if (folder/'report.json').exists():
                old=source.read(folder/'report.json')
                if old['status']!='COMPLETED_EXPLORATORY':raise ValueError('Prior case not completed')
                source.verify({str(folder/k):v for k,v in old['files'].items()});cases.append(old);continue
            folder.mkdir(exist_ok=False)
            annual=signals[signals.year.eq(year)]
            selected=annual[['date','symbol','oracle_rank']].rename(columns={'date':'trade_date','oracle_rank':'rank'}).copy()
            selected['selected']=(annual.common_eligible&annual.WINNER_ONLY).to_numpy();selected['side']='long'
            def progress(done,total,day):
                elapsed=time.monotonic()-started
                atomic_json(root/'progress.json',dict(status='RUNNING',year=year,arm=ARM,completed_runs=len(cases),
                    total_runs=len(p['years']),completed_sessions=done,total_sessions=total,last_date=day,
                    elapsed_seconds=elapsed,remaining_case_seconds_estimate=elapsed*(total-done)/done))
            cfg=variant_config(p['reference_protocol'],year,smoke=p['smoke'])
            with native_adapters(year) as refusals:
                result=source.BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],
                    high=pivots['high'],low=pivots['low'],volume=pivots['volume'],signals_df=selected,
                    sector_map=sectors,intraday_source=bars,winner_research_assumptions=True,
                    winner_progress=progress,winner_corporate_actions=actions.to_dict('records'))
                source.save_new(folder/'whole-share-refusals.json',refusals)
            summary=metrics(result,4000.)
            if summary['status']!='COMPLETED_EXPLORATORY':raise ValueError('Variant coverage incomplete: '+str(summary))
            result.closed_trades_df.to_parquet(folder/'trades.parquet',index=False)
            result.trade_events_df.to_csv(folder/'events.csv',index=False)
            result.intraday_equity_curve.to_parquet(folder/'equity-5m.parquet',index=False)
            result.equity_curve.to_frame().to_parquet(folder/'equity-daily.parquet')
            result.drawdown_breaker_df.to_parquet(folder/'breaker.parquet',index=False)
            summary.update(year=year,arm=ARM,smoke=p['smoke'],end_date=str(cfg.end_date),
                files={x.name:source.digest(x) for x in folder.iterdir() if x.is_file()})
            source.save_new(folder/'report.json',summary);cases.append(summary)
            LOG.info('Completed %s variant: return=%s win=%s DD=%s',year,summary['return_pct'],summary['win_pct'],summary['max_drawdown_pct'])
            pd.DataFrame([{k:v for k,v in c.items() if not isinstance(v,(dict,list))} for c in cases]).to_csv(root/'annual-summary.partial.csv',index=False)
        references=[]
        if not p['smoke']:
            for year in p['years']:
                c=source.read(PARENT/f'{year}-WINNER_ONLY/report.json');c['reused_audited_reference']=True;references.append(c)
        source.verify(p['sources'])
        rows=[{k:v for k,v in c.items() if not isinstance(v,(dict,list))} for c in references+cases]
        pd.DataFrame(rows).to_csv(root/'annual-summary.csv',index=False)
        source.save_new(root/'report.json',dict(status='COMPLETED_TECHNICAL_SMOKE' if p['smoke'] else 'COMPLETED_EXPLORATORY_PENDING_AUDIT',
            cases=cases,references=references,baseline_reused_not_replayed=True,common_cohort_exact=True,
            full_live_parity=False,SQL_reads=0,provider_calls=0,production_changed=False,
            files={x.name:source.digest(x) for x in root.iterdir() if x.is_file() and x.name!='progress.json'}))
        atomic_json(root/'progress.json',dict(status='AUDITING',completed_runs=len(cases),total_runs=len(p['years'])))
        from scripts.research.us_winner_sl3_tp7_tr3_open11_audit_20261023 import audit
        audit(root)
        atomic_json(root/'progress.json',dict(status='COMPLETED_AUDITED_TECHNICAL_SMOKE' if p['smoke'] else 'COMPLETED_AUDITED_EXPLORATORY',
            completed_runs=len(cases),total_runs=len(p['years'])))
    except Exception as exc:
        atomic_json(root/'progress.json',dict(status='FAILED',completed_runs=len(cases),total_runs=len(p['years']),
            error_type=type(exc).__name__,error=str(exc)))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=['prepare','run','all'],default='all')
    parser.add_argument('--output',type=Path,default=ROOT);parser.add_argument('--smoke',action='store_true');a=parser.parse_args()
    logging.basicConfig(level=logging.WARNING,format='%(asctime)s %(levelname)s %(message)s')
    import requests
    def forbidden(*a,**k):raise RuntimeError('Offline research; HTTP forbidden')
    requests.Session.request=forbidden
    if a.phase in ('prepare','all'):prepare(a.output,smoke=a.smoke)
    if a.phase in ('run','all'):run(a.output)
