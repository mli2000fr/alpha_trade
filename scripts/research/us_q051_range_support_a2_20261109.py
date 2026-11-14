"""Frozen A2 range-support pilot on Q051 vol20/regime; no providers or orders."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime,timezone,timedelta
from multiprocessing import get_context
from pathlib import Path
import json
import sys
from unittest.mock import patch

import numpy as np
import pandas as pd
import requests

from backtesting.range_support_entry import RangeSupportSettings,aggregate_m15,freeze_range,first_rebound,ScheduledEntries
from scripts.research import us_winner_continuous_q051_q088_20261108 as shared
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_q051_range_support_a2/20261109-v1')
BASE=shared.ROOT
CONTROL=Path('artifacts/research/us_winner_q051_risk_budget/20261109-v1/REGIME_VOL20/result')
CASES=('BASELINE_ALL','BASELINE_COMMON','WAIT_COMMON','A2_COMMON')


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def frozen_day(source,day):
    file=BASE/'inputs/base/intraday'/f'{day}.parquet'
    return source.day(day) if file.exists() else {}


def prepare(root):
    from common.config_loader import replay_market_registry
    from common.market_calendar import get_market_calendar
    root.mkdir(parents=True,exist_ok=False);inputs=root/'inputs';inputs.mkdir()
    settings=RangeSupportSettings();signals=pd.read_parquet(BASE/'inputs/signals-Q051_050.parquet')
    sources=[Path(__file__),Path('backtesting/range_support_entry.py'),Path('backtesting/simulator.py'),
        Path('backtesting/winner_intraday.py'),Path('backtesting/winner_daily_entry.py'),
        Path('backtesting/winner_portfolio_budget.py'),BASE/'inputs/signals-Q051_050.parquet',
        BASE/'inputs/manifest.json',BASE/'protocol.json',CONTROL/'configuration.json',CONTROL/'report.json']
    plan=dict(start='2021-01-01',end='2026-10-01',initial_equity=4000.,annual_reset=False,cases=CASES,
        settings=asdict(settings),range='Last20 complete regular M15 through J close, preceding12 impulse and14 ATR seed; contiguous official slots across overnight session breaks',
        entry='First bullish close above frozen support after touch on J+1; prior close below support-tolerance invalidates; no retry/refill',
        availability='M15 close +930 seconds, next observed5m open; expires at J+1 close',
        controls='Original full baseline; prior-context common baseline; fixed10:30NY wait on common prior-context cohort; A2',
        frequency_gate=dict(min_signals=60,min_symbols=20,min_nonoverlapping=30,min_years_with_five_signals=4),
        frequency_population='Regime-allowed candidates only; no economic outcome or future-path completeness screen',
        reference=str(CONTROL),risk='Exact Q051 vol20/regime, SL5/open11, no TP/trailing/add, full size,1x entry cap',
        costs='8bps/leg and6.5% annual financing; stress25bps/leg after primary replay if frequency sufficient',
        source_hashes={str(p):digest(p) for p in sources},new_SQL_writes=0,provider_calls=0,orders=0,
        retrospective=True,independent_holdout=False,production_changes=False,
        created_at_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(root/'request.json',plan)
    atomic_json(root/'progress.json',dict(status='AUDITING_PAST_CONTEXT_AND_MOTIF_FREQUENCY',completed=0,total=int(signals.trade_date.nunique())))
    pivots,_,_=shared.market_data(BASE);spy=pivots['close']['SPY'];source=shared.FrozenPrices(BASE)
    with replay_market_registry(shared.restore_registry(BASE)):
        calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
        sessions=[s for s in calendar.sessions(pd.Timestamp('2020-12-15').date(),pd.Timestamp('2026-10-01').date()) if s.is_open]
    positions={s.session_date:i for i,s in enumerate(sessions)}
    audit=[];schedule=[];wait=[];common=[];input_hashes={};nonoverlap={}
    for i,(stamp,rows) in enumerate(signals.groupby('trade_date')):
        signal_day=pd.Timestamp(stamp).date();idx=positions[signal_day];day=sessions[idx+1].session_date
        prior_sessions=sessions[max(0,idx-3):idx+1]
        needed=settings.atr_bars+settings.impulse_bars+settings.range_bars
        expected=pd.DatetimeIndex([t for session in prior_sessions for t in pd.date_range(
            session.open_at_utc,session.close_at_utc,freq='15min',inclusive='left')])[-needed:]
        hist=spy.loc[:pd.Timestamp(signal_day)].tail(200)
        regime=len(hist)==200 and np.isfinite(hist).all() and hist.iloc[-1]>.98*hist.mean()
        frozen={}
        for session in [*prior_sessions,sessions[idx+1]]:
            frozen[session.session_date]=frozen_day(source,session.session_date)
            for part in ['base/intraday','extra-intraday']:
                file=BASE/'inputs'/part/f'{session.session_date}.parquet'
                if file.exists() and str(file) not in input_hashes:input_hashes[str(file)]=digest(file)
        for row in rows.to_dict('records'):
            symbol=row['symbol'];parts=[]
            for session in prior_sessions:
                f=frozen[session.session_date].get(symbol,pd.DataFrame())
                parts.append(aggregate_m15(f,session.session_date,known_at=session.close_at_utc))
            parts=[f for f in parts if not f.empty]
            history=pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()
            coverage=(len(history)>=needed and pd.DatetimeIndex(history.timestamp.tail(needed)).equals(expected))
            detail=dict(signal_date=str(signal_day),entry_day=str(day),symbol=symbol,year=day.year,
                regime_allowed=bool(regime),context_qualified=bool(coverage),range_qualified=False,confirmed=False)
            if not coverage:
                detail['reason']='MISSING_PRE_SIGNAL_M15_CONTEXT';audit.append(detail);continue
            common.append(row)
            opening=sessions[idx+1].open_at_utc
            wait.append(dict(signal_date=str(signal_day),symbol=symbol,confirmed_at=(opening+timedelta(minutes=15)).isoformat(),
                available_at=(opening+timedelta(minutes=15,seconds=settings.delay_seconds)).isoformat(),
                execution_at=(opening+timedelta(minutes=60)).isoformat(),setup='FIXED_1030_NY_WAIT'))
            zone,reason=freeze_range(history,settings)
            if zone is None:detail['reason']=reason;audit.append(detail);continue
            detail.update(range_qualified=True,**zone)
            f=frozen[day].get(symbol,pd.DataFrame())
            candles=aggregate_m15(f,day,known_at=sessions[idx+1].close_at_utc)
            # A missing component is not a silent bridge across an invalidation.
            expected_today=pd.date_range(opening,sessions[idx+1].close_at_utc,freq='15min',inclusive='left')
            contiguous=[]
            for t in expected_today:
                q=candles[candles.timestamp.eq(t)]
                if q.empty:break
                contiguous.append(q)
            candles=pd.concat(contiguous,ignore_index=True) if contiguous else candles.iloc[:0]
            event,reason=first_rebound(candles,zone,day,settings)
            detail['reason']=reason
            if event:
                detail.update(confirmed=True,**event)
                schedule.append(dict(signal_date=str(signal_day),symbol=symbol,**event))
            audit.append(detail)
        atomic_json(root/'progress.json',dict(status='AUDITING_PAST_CONTEXT_AND_MOTIF_FREQUENCY',completed=i+1,
            total=int(signals.trade_date.nunique()),last_signal_day=str(signal_day)))
    observations=pd.DataFrame(audit);observations.to_csv(inputs/'coverage-and-motifs.csv',index=False)
    columns=['signal_date','symbol','confirmed_at','available_at','execution_at','setup']
    for name,rows in [('A2',schedule),('WAIT',wait)]:
        pd.DataFrame(rows,columns=columns).to_parquet(inputs/f'schedule-{name}.parquet',index=False)
    pd.DataFrame(common,columns=signals.columns).to_parquet(inputs/'signals-common.parquet',index=False)
    selected=observations[observations.confirmed&observations.regime_allowed]
    for row in selected.sort_values(['signal_date','symbol']).itertuples():
        idx=positions[pd.Timestamp(row.signal_date).date()]
        if idx>=nonoverlap.get(row.symbol,-999)+11:nonoverlap[row.symbol]=idx
    # Independently count every greedily spaced opportunity (not only last one).
    last={};spaced=0
    for row in selected.sort_values(['signal_date','symbol']).itertuples():
        idx=positions[pd.Timestamp(row.signal_date).date()]
        if idx>=last.get(row.symbol,-999)+11:spaced+=1;last[row.symbol]=idx
    per_year=selected.groupby('year').size().to_dict();g=plan['frequency_gate']
    sufficient=(len(selected)>=g['min_signals'] and selected.symbol.nunique()>=g['min_symbols']
        and spaced>=g['min_nonoverlapping'] and sum(n>=5 for n in per_year.values())>=g['min_years_with_five_signals'])
    summary=dict(status='FREQUENCY_PASS' if sufficient else 'INSUFFICIENT_FREQUENCY_NO_BACKTEST',
        candidates=len(observations),context_qualified=int(observations.context_qualified.sum()),
        ranges=int(observations.range_qualified.sum()),confirmed=len(schedule),regime_allowed_signals=len(selected),
        companies=int(selected.symbol.nunique()),nonoverlapping=spaced,by_year=per_year,
        reasons=observations.reason.value_counts().to_dict(),thresholds=g)
    atomic_json(root/'frequency.json',summary)
    atomic_json(inputs/'manifest.json',dict(files={p.name:digest(p) for p in inputs.iterdir() if p.is_file()},
        archived_tapes=input_hashes,provider_calls=0,SQL_writes=0))
    atomic_json(root/'progress.json',summary)
    return sufficient


def replay(root,name,stress=False):
    from backtesting.simulator import BacktestEngine,BacktestResult
    from backtesting.winner_campaign_replay import metrics
    from backtesting.winner_portfolio_budget import replay_protections
    from scripts.research.us_winner_q051_risk_budget_20261109 import daily_metrics,matched_configuration
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry
    root=Path(root);plan=read(root/'request.json')
    for file,sha in plan['source_hashes'].items():
        if digest(Path(file))!=sha:raise ValueError('Changed source since preregistration: '+file)
    for file,sha in read(root/'inputs/manifest.json')['files'].items():
        if digest(root/'inputs'/file)!=sha:raise ValueError('Changed frozen input')
    key=name+('_COST25' if stress else '');folder=root/'cases'/key;out=folder/'result';out.mkdir(parents=True,exist_ok=False)
    source_plan=read(BASE/'protocol.json');saved=read(BASE/'cases/Q051_050/result/configuration.json')
    case,cfg=matched_configuration(source_plan,saved,'REGIME_VOL20')
    if json.loads(json.dumps(asdict(cfg),default=str))!=read(CONTROL/'configuration.json')['portfolio']:
        raise ValueError('Reference portfolio differs')
    if stress:cfg.cost_round_trip_bps=50.
    signals=pd.read_parquet(BASE/'inputs/signals-Q051_050.parquet' if name=='BASELINE_ALL' else root/'inputs/signals-common.parquet')
    timing=None
    if name in ('WAIT_COMMON','A2_COMMON'):
        timing=ScheduledEntries(pd.read_parquet(root/'inputs'/('schedule-A2.parquet' if name=='A2_COMMON' else 'schedule-WAIT.parquet')))
    pivots,sectors,actions=shared.market_data(BASE)
    policy,gate=replay_protections(pivots['close'],daily_entry=True,target=.2,regime=True)
    protocol={**source_plan,'profile':key,'reference':deepcopy(source_plan['reference']),
        'replay_command':[sys.executable,'-m','scripts.research.us_q051_range_support_a2_20261109','--phase','run'],
        'experiment_request_sha256':digest(root/'request.json')}
    protocol['reference']['risk']=asdict(cfg.risk_config)
    atomic_json(folder/'protocol.json',protocol);atomic_json(out/'configuration.json',dict(profile=key,portfolio=asdict(cfg)))
    def no_http(*a,**kw):raise ValueError('No provider calls in A2 pilot')
    with ReadOnlyReplay(folder).install(),replay_market_registry(shared.restore_registry(BASE)),patch.object(requests.Session,'request',no_http):
        def progress(done,total,day):atomic_json(folder/'progress.json',dict(status='RUNNING',completed=done,total=total,last_date=str(day)))
        result=BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],low=pivots['low'],
            volume=pivots['volume'],signals_df=signals,sector_map=sectors.set_index('symbol').sector.to_dict(),
            intraday_source=shared.FrozenPrices(BASE),winner_research_assumptions=True,winner_progress=progress,
            winner_corporate_actions=actions.to_dict('records'),winner_selection_source=gate,
            winner_entry_risk_policy=policy,winner_entry_timing_source=timing)
        result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv');result.intraday_equity_curve.to_parquet(out/'equity-5m.parquet',index=False)
        result.closed_trades_df.to_csv(out/'trades.csv',index=False);result.trade_events_df.to_csv(out/'events.csv',index=False)
        result.drawdown_breaker_df.to_csv(out/'risk-5m.csv',index=False)
        pd.DataFrame(policy.receipts).to_csv(out/'portfolio-risk-decisions.csv',index=False)
        pd.DataFrame(gate.receipts).to_csv(out/'regime-decisions.csv',index=False)
        report=metrics(result,4000.);report.update(daily_metrics(result.equity_curve));annual=[];opening=4000.
        for year in range(2021,2027):
            curve=result.equity_curve[result.equity_curve.index.year==year]
            trades=result.closed_trades_df
            closed=trades[pd.to_datetime(trades.exit_date,utc=True).dt.year.eq(year)] if len(trades) else trades
            marks=result.intraday_equity_curve
            part=BacktestResult(equity_curve=curve,closed_trades_df=closed,
                intraday_equity_curve=marks[pd.to_datetime(marks.timestamp,utc=True).dt.year.eq(year)],
                tracker_snapshot={'winner_replay':dict(status=report['status'],full_live_parity=False)})
            a=metrics(part,opening);a.update(year=year);annual.append(a);opening=float(curve.iloc[-1])
        pd.DataFrame(annual).to_csv(out/'annual-summary.csv',index=False)
        if name=='BASELINE_ALL' and not stress:
            old=pd.read_csv(CONTROL/'equity-daily.csv',index_col=0,parse_dates=True).iloc[:,0]
            if digest(out/'equity-daily.csv')!=digest(CONTROL/'equity-daily.csv'):
                raise ValueError('Reference daily equity CSV changed')
            for metric in ['final_equity','max_drawdown_pct','closed_lot_trades','winners','losers']:
                if report[metric]!=read(CONTROL/'report.json')[metric]:raise ValueError('Reference changed: '+metric)
            report['reference_reproduction']='EXACT_EQUITY_AND_TRADE_COUNTS'
        report.update(profile=key,selected_signals=len(signals),provider_calls=0,SQL_writes=0,orders=0,
            limitations='Partial intraday OHLC; daily fallback after late entry is an adverse bound and can include a pre-entry low',
            finished_at_utc=datetime.now(timezone.utc).isoformat())
        atomic_json(out/'report.json',report)
        atomic_json(folder/'progress.json',dict(status='COMPLETED_EXPLORATORY'))
    from ihm.services.backtesting_import import import_continuous_winner
    record=import_continuous_winner(folder,run_id='20261109_a2_'+key.lower()+'_v1',label='Continu2021–2026 — Q051 vol20/régime — '+key,result_subdir='result')
    atomic_json(folder/'progress.json',dict(status='COMPLETED_EXPLORATORY',ihm_run_id=record['run_id']))
    return dict(profile=key,folder=str(folder),ihm_run_id=record['run_id'])


def run(root):
    root=Path(root)
    if not (root/'frequency.json').exists():prepare(root)
    if read(root/'frequency.json')['status']!='FREQUENCY_PASS':
        atomic_json(root/'report.json',dict(status='INSUFFICIENT_FREQUENCY_NO_BACKTEST',frequency=read(root/'frequency.json')));return
    # Reproduce reference before any economic comparison is accepted.
    results=[replay(root,'BASELINE_ALL')]
    with ProcessPoolExecutor(max_workers=2,mp_context=get_context('spawn')) as pool:
        tasks={pool.submit(replay,str(root),case):case for case in CASES[1:]}
        for task in as_completed(tasks):
            try:results.append(task.result())
            except Exception as exc:
                atomic_json(root/'progress.json',dict(status='FAILED',profile=tasks[task],error=str(exc)));raise
            atomic_json(root/'progress.json',dict(status='REPLAYING_PRIMARY_CASES',completed=len(results),total=4,results=results))
    columns=['profile','final_equity','return_pct','max_drawdown_pct','closed_lot_trades','winners','losers','win_pct','average_gross_capital']
    pd.DataFrame([{k:read(Path(x['folder'])/'result/report.json').get(k) for k in columns} for x in results]).to_csv(root/'comparison.csv',index=False)
    atomic_json(root/'report.json',dict(status='PRIMARY_COMPLETED_EXPLORATORY',imports=results,
        reference_reproduced=True,frequency=read(root/'frequency.json'),stress='PENDING',production_changes=False))
    atomic_json(root/'progress.json',read(root/'report.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=['prepare','run'],default='run')
    parser.add_argument('--output-dir',type=Path,default=ROOT);args=parser.parse_args()
    try:
        if args.phase=='prepare':prepare(args.output_dir)
        else:run(args.output_dir)
    except Exception as exc:
        if args.output_dir.exists():atomic_json(args.output_dir/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
