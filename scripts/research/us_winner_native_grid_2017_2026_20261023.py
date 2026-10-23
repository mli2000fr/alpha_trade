"""Resumable native LONG Winner grid. SQL snapshots READ ONLY, no provider/broker."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from itertools import product
from pathlib import Path
import logging
import math
import time

import numpy as np
import pandas as pd
from sqlalchemy import text, bindparam

from scripts.research import us_winner_bottom_rank_filter_20261022 as base
from scripts.research import us_winner_bottom_rank_filter_whole_shares_20261022 as whole
from scripts.research.us_winner_sl3_tp7_tr3_open11_audit_20261023 import scalar_exit, near
from scripts.research.us_winner_bottom_rank_filter_audit_20261022 import event_cash
from backtesting.winner_campaign_replay import atomic_json, metrics
import backtesting.winner_intraday as native
from service.market.intraday_backfill import run_lock

ROOT = Path('artifacts/research/us_winner_native_grid_2017_2026/20261023-v1')
SCORES = Path('artifacts/research/us_winner_grid_scores_2017_2026/20261023-v2')
REFERENCE = Path('artifacts/research/us_winner_bottom_rank_filter/20261022-v2/protocol.json')
DOC = Path('doc/ml/winner_grille_native_2017_2026_protocole_20261023.md')
BACKFILL = Path('artifacts/intraday_backfill/intraday-5dfcdc71cfaf4819ed1b/progress.json')
YEARS = [2017, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026, 2018]
LOG = logging.getLogger(__name__)


def profiles():
    result = []
    for sl, tr, horizon, tp in product([.03, .05, .07], [None, .03, .10, .15, .20],
                                      [5, 10, 15, 20], [None, .07, .10, .15, .20]):
        label = lambda x: 'OFF' if x is None else str(round(100*x))
        result.append(dict(name=f'SL{label(sl)}_TR{label(tr)}_H{horizon}_TP{label(tp)}',
            stop_loss_pct=sl, trailing_stop_pct=tr, horizon_sessions=horizon, take_profit_pct=tp))
    return result


def bounds(year):
    return max(date(year, 1, 1), date(2017, 6, 2)), min(date(year, 12, 31), date(2026, 9, 30))


def calendar():
    return base.get_market_calendar('US_EQ', allow_us_weekday_fallback=False)


def annual_scores(year):
    start, end = bounds(year)
    seed = max(s.session_date for s in calendar().sessions(start-timedelta(days=14), start)
               if s.is_open and s.session_date < start)
    f = pd.read_parquet(SCORES/'causal-top10.parquet')
    return f[f.date.between(pd.Timestamp(seed), pd.Timestamp(end))].copy(), seed


def prepare(root):
    root.mkdir(parents=True, exist_ok=True)
    if (root/'protocol.json').exists():
        p = base.read(root/'protocol.json'); base.verify(p['sources']); return p
    q = base.read(SCORES/'report.json')
    if q['missing_score_dates'] or q['status'] != 'SCORES_AVAILABLE_INTRADAY_QUALIFICATION_PENDING':
        raise ValueError('Qualified causal scores required')
    base.verify({str(SCORES/n):sha for n, sha in q['files'].items()})
    base.verify(q['inputs'])
    old = base.read(REFERENCE)
    paths = [Path(__file__), DOC, REFERENCE, SCORES/'report.json', SCORES/'causal-top10.parquet',
             Path('tests/test_us_winner_native_grid_2017_2026_20261023.py'),
             Path(base.__file__), Path(whole.__file__), Path(native.__file__),
             Path('backtesting/simulator.py'), Path('backtesting/winner_campaign_replay.py'),
             Path('scripts/research/us_winner_sl3_tp7_tr3_open11_audit_20261023.py'),
             Path('scripts/research/us_winner_bottom_rank_filter_audit_20261022.py'),
             Path('common/trading_costs.py'), Path('common/market_calendar.py')]
    for folder, pattern in [('common','winner*.py'), ('execution_engine','winner*.py'),
                            ('risk_management','*.py')]:
        paths.extend(Path(folder).glob(pattern))
    p = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), start='2017-06-02', end='2026-09-30',
        sources={str(n):base.digest(n) for n in paths}, reference_config=old,
        profiles=profiles(), years=YEARS, total_runs=3000, initial_equity=4000., annual_reset=True,
        fee_per_leg=.0008, allowed_leverage=2., effective_gross_cap=old['effective_gross_cap'],
        risk_policy=old['risk']['policy'], risk_drawdown_pct=old['risk']['max_portfolio_drawdown_pct'],
        fixed_winner_policy=old['winner_policy'], TOP=10, half_position=True, reinforcement=False,
        common_cohort_max_future_sessions=40, full_live_parity=False, production_changed=False,
        training=False, SQL_writes=False, provider_calls=0, broker_calls=0,
        ranking='Discovery 2017-2023 only: median annual return / max(5,worst annual DD magnitude); '
                'tie positive-year count, worst annual return, profile name. Report 2024-2026 unchanged.',
        limitations=['OHLC execution assumptions, not bid/ask/fills; stops not guaranteed.',
            'Static survivor universe, current non-PIT sectors, revised daily history.',
            'Future coverage/CA eligibility bias identical across arms; no reranking after exclusion.',
            'Factor overlay disabled as in reference; no qualified historical factor tape.',
            'Current corporate-action table is not guaranteed exhaustive.',
            'Annual reset and end-of-year mark-to-market; open holdings not forced out.',
            'Previously inspected years are not an independent untouched holdout.'])
    if old['winner_policy']['initial_position_fraction'] != .5 or old['winner_policy']['reinforcement_enabled']:
        raise ValueError('Frozen HALF/no-add reference required')
    base.save_new(root/'protocol.json', p)
    atomic_json(root/'progress.json', dict(status='PREPARED', completed_runs=0, total_runs=p['total_runs']))
    return p


def backfill_ready():
    p = base.read(BACKFILL)
    return p.get('status') == 'COMPLETED' and p.get('failed_tasks') == 0 and p.get('completed_tasks') == p.get('total_tasks')


def snapshot(root, year):
    folder = root/'inputs'/str(year); folder.mkdir(parents=True, exist_ok=True)
    if (folder/'snapshot.json').exists():
        manifest = base.read(folder/'snapshot.json')
        base.verify({str(folder/n):v for n,v in manifest['files'].items()}); return
    if year == 2018 and not backfill_ready():
        raise ValueError('2018 backfill unfinished: snapshot refused, no incomplete cohort silently frozen')
    from database.connection import get_sqlalchemy_engine
    scores, seed = annual_scores(year); _, end = bounds(year)
    symbols = sorted(scores.symbol.unique()); files={}; receipts=[]
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    try:
        with engine.connect() as conn, conn.begin():
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=30000'))
            conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':raise ValueError('US only')
            for i, symbol in enumerate(symbols):
                file = folder/f'sip-{i:03}.parquet'; marker = file.with_suffix('.json')
                if marker.exists():
                    r=base.read(marker); base.verify({str(file):r['sha256']})
                    if r['symbol'] != symbol:raise ValueError('Snapshot symbol changed')
                else:
                    query=text("SELECT symbol,trade_date,bar_timestamp,bar_end_timestamp,open,high,low,close,volume,payload_hash "
                        "FROM stock_bars_intraday FORCE INDEX(PRIMARY) WHERE symbol=:symbol AND bar_timestamp>=:start "
                        "AND bar_timestamp<:end AND provider='alpaca' AND data_source='alpaca_sip' AND interval_code='5m' "
                        "AND market_code='US_EQ' AND session_tag='regular' AND data_adjustment='raw' AND is_filled=0 ORDER BY bar_timestamp")
                    f=pd.read_sql(query,conn,params=dict(symbol=symbol,start=str(seed),end=str(end+timedelta(days=1))))
                    for k in ['bar_timestamp','bar_end_timestamp']:f[k]=pd.to_datetime(f[k],utc=True)
                    f['trade_date']=pd.to_datetime(f.trade_date)
                    f.to_parquet(file,index=False)
                    r=dict(symbol=symbol,file=file.name,rows=len(f),sha256=base.digest(file),observed_at_utc=datetime.now(timezone.utc).isoformat())
                    base.save_new(marker,r)
                receipts.append(r);files[file.name]=r['sha256'];files[marker.name]=base.digest(marker)
                atomic_json(root/'progress.json',dict(status='SNAPSHOT_READ_ONLY',year=year,symbol=symbol,
                    completed_symbols=i+1,total_symbols=len(symbols),total_runs=3000,
                    completed_runs=len(list((root/'cases').glob('*/report.json'))) if (root/'cases').exists() else 0))
            queries={
                'daily.parquet':("SELECT symbol,date,open,high,low,close,volume,data_source,data_adjustment,is_filled "
                    "FROM stock_bars_daily FORCE INDEX(PRIMARY) WHERE symbol IN :symbols AND date BETWEEN :start AND :end",
                    dict(symbols=symbols+['SPY'],start=seed-timedelta(days=650),end=end)),
                'sectors.parquet':('SELECT symbol,sector FROM stock_metadata WHERE symbol IN :symbols',dict(symbols=symbols)),
                'actions.parquet':('SELECT symbol,ca_type,ex_date,payable_date,amount_per_share,currency FROM corporate_actions_events '
                    'WHERE symbol IN :symbols AND ex_date BETWEEN :start AND :end',dict(symbols=symbols,start=seed,end=end))}
            for name,(sql,args) in queries.items():
                file=folder/name;marker=file.with_suffix('.json')
                if marker.exists():
                    r=base.read(marker);base.verify({str(file):r['sha256']})
                else:
                    f=pd.read_sql(text(sql).bindparams(bindparam('symbols',expanding=True)),conn,params=args)
                    f.to_parquet(file,index=False);r=dict(sha256=base.digest(file),rows=len(f))
                    base.save_new(marker,r)
                files[name]=r['sha256'];files[marker.name]=base.digest(marker)
    finally:engine.dispose()
    scores.to_parquet(folder/'signals.parquet',index=False);files['signals.parquet']=base.digest(folder/'signals.parquet')
    base.save_new(folder/'snapshot.json',dict(year=year,receipts=receipts,files=files,
        SQL_reads_only=True,provider_calls=0,resumed_symbol_receipts_possible=True,metadata_current_non_PIT=True))


def qualify_cohort(signals, groups, actions, sectors, days):
    indices={d:i for i,d in enumerate(days)};rows=[]
    for row in signals.itertuples():
        d=pd.Timestamp(row.date).date();i=indices[d];window=days[i:min(i+41,len(days))]
        reason=''
        if not sectors.get(row.symbol):reason='CURRENT_SECTOR_MISSING'
        elif any((row.symbol,x) not in groups for x in window):reason='COMMON_MAX_WAIT_HOLD_SIP_WINDOW_MISSING'
        elif not actions.empty and ((actions.symbol==row.symbol)&actions.ex_date.between(pd.Timestamp(window[0]),pd.Timestamp(window[-1]))).any():
            reason='CORPORATE_ACTION_LIFECYCLE_RESERVED'
        rows.append(dict(date=row.date,symbol=row.symbol,selected=not reason,coverage_reason=reason,window_end=window[-1]))
    return signals.merge(pd.DataFrame(rows),on=['date','symbol'],validate='one_to_one')


def load_year(root, year):
    folder=root/'inputs'/str(year);m=base.read(folder/'snapshot.json')
    base.verify({str(folder/n):v for n,v in m['files'].items()})
    signals=pd.read_parquet(folder/'signals.parquet');start,end=bounds(year)
    sessions=[s for s in calendar().sessions(start-timedelta(days=14),end+timedelta(days=100)) if s.is_open]
    schedule={s.session_date:s for s in sessions};groups={};raw={};quality=[]
    for receipt in m['receipts']:
        f=pd.read_parquet(folder/receipt['file']);f['session_close']=f.trade_date.map({pd.Timestamp(d):s.close_at_utc for d,s in schedule.items()})
        raw[receipt['symbol']]=f
        for day,g in f.groupby('trade_date',sort=True):
            d=pd.Timestamp(day).date();s=schedule.get(d)
            good=s is not None and base.qualify_session(g,s)
            quality.append(dict(symbol=receipt['symbol'],date=d,qualified=bool(good),rows=len(g)))
            if good:groups[receipt['symbol'],d]=g.rename(columns={'bar_timestamp':'timestamp'}).copy()
    sectors={str(x.symbol):str(x.sector) for x in pd.read_parquet(folder/'sectors.parquet').dropna().itertuples()}
    actions=pd.read_parquet(folder/'actions.parquet');actions['ex_date']=pd.to_datetime(actions.ex_date)
    actions['payable_date']=pd.to_datetime(actions.payable_date).dt.date
    cohort=qualify_cohort(signals,groups,actions,sectors,[d for d in schedule if d<=end])
    for name,f in [('qualified-signals.parquet',cohort),('session-quality.parquet',pd.DataFrame(quality))]:
        target=folder/name
        if target.exists():pd.testing.assert_frame_equal(pd.read_parquet(target),f,check_exact=True)
        else:f.to_parquet(target,index=False)
    counts=cohort.groupby('coverage_reason').size().to_dict()
    coverage=dict(original=len(cohort),eligible=int(cohort.selected.sum()),reasons=counts,
                  future_coverage_selection_bias=True)
    if not (folder/'cohort.json').exists():base.save_new(folder/'cohort.json',coverage)
    if not cohort.selected.any():raise ValueError('No covered TOP10 candidates: no meaningful annual grid')
    daily=pd.read_parquet(folder/'daily.parquet');daily['date']=pd.to_datetime(daily.date)
    if daily.duplicated(['symbol','date']).any():raise ValueError('Ambiguous daily')
    n=daily[['open','high','low','close','volume']].to_numpy(float)
    valid=np.isfinite(n).all(axis=1)&(n>0).all(axis=1)&daily.is_filled.eq(0)&daily.data_adjustment.eq('split')&~daily.data_source.str.contains('iex',case=False,na=True)
    daily.loc[~valid,['open','high','low','close','volume']]=np.nan
    pivots={k:daily.pivot(index='date',columns='symbol',values=k).astype(float) for k in ['open','high','low','close','volume']}
    return cohort,groups,raw,actions,sectors,pivots,sessions


def configuration(protocol, year, profile, smoke=False):
    cfg=base.engine_config(protocol['reference_config'],2025)
    start,end=bounds(year)
    if smoke:end=[s.session_date for s in calendar().sessions(start,start+timedelta(days=50)) if s.is_open][19]
    wp=replace(cfg.exec_config.winner_pyramiding,**{k:v for k,v in profile.items() if k!='name'})
    return replace(cfg,start_date=start,end_date=end,cost_round_trip_bps=16.,
                   exec_config=replace(cfg.exec_config,winner_pyramiding=wp))


@contextmanager
def runtime_adapter(year, name):
    stage,cal=native.stage_targets,native.get_market_calendar
    old_case,old_refusals=whole.CURRENT_CASE,whole.REFUSALS
    cached=whole.CachedCalendar(cal('US_EQ',allow_us_weekday_fallback=False))
    whole.CURRENT_CASE=dict(year=year,arm=name);whole.REFUSALS=[]
    native.stage_targets=whole.stage_whole_shares;native.get_market_calendar=lambda *a,**k:cached
    try:yield whole.REFUSALS
    finally:
        native.stage_targets=stage;native.get_market_calendar=cal
        whole.CURRENT_CASE=old_case;whole.REFUSALS=old_refusals


def audit_result(result, summary, profile, cohort, raw, sessions):
    events=result.trade_events_df;events=events[events.event.notna()]
    cash,fees,held=event_cash(events)
    near(cash,summary['settled_cash']);near(fees,summary['costs'])
    if held!={x['symbol']:x['qty'] for x in summary['open_positions']}:raise AssertionError('Positions/cash mismatch')
    near(summary['final_equity'],cash+sum(x['qty']*x['mark'] for x in summary['open_positions']))
    if summary['dividends_accrued'] or summary['unsettled_cash']:raise AssertionError('Reserved lifecycle unexpectedly active')
    ds=[s.session_date for s in sessions];idx={d:i for i,d in enumerate(ds)}
    wins=[];losses=[];exit_checks=buy_checks=0
    for t in result.closed_trades_df.itertuples():
        entry=pd.Timestamp(t.entry_date);day=entry.tz_convert('America/New_York').date()
        due=pd.Timestamp(sessions[idx[day]+profile['horizon_sessions']].open_at_utc)
        got=scalar_exit(raw[t.symbol],entry,t.entry_price,due,sl=profile['stop_loss_pct'],tp=profile['take_profit_pct'],trail=profile['trailing_stop_pct'])
        if got is None or got[0]!=t.exit_date or got[2]!=t.exit_reason:raise AssertionError(f'Scalar lifecycle mismatch {t.symbol}: {got}')
        near(got[1],t.exit_price);near(t.pnl,t.quantity*(t.exit_price-t.entry_price)-t.entry_fees-t.exit_fees+t.dividends)
        count=idx[pd.Timestamp(t.exit_date).tz_convert('America/New_York').date()]-idx[day]+1
        (wins if t.pnl>0 else losses).append(count);exit_checks+=1
    for b in events[events.event.eq('BUY_FILL')].itertuples():
        stamp=pd.Timestamp(b.time);day=stamp.tz_convert('America/New_York').date();f=raw[b.symbol]
        g=f[f.trade_date.eq(pd.Timestamp(day))].reset_index(drop=True);indices=np.flatnonzero(g.bar_timestamp.eq(stamp))
        if len(indices)!=1 or indices[0]<3:raise AssertionError('No completed entry confirmation')
        i=int(indices[0]);prior=f[f.trade_date.eq(pd.Timestamp(ds[idx[day]-1]))];level=prior.high.max()
        if not (g.close.iloc[i-3]<=level and g.close.iloc[i-2]>level and g.close.iloc[i-1]>level):raise AssertionError('False breakout')
        near(b.price,g.open.iloc[i]);near(b.costs,b.price*b.quantity*.0008)
        c=cohort[cohort.symbol.eq(b.symbol)&cohort.selected]
        if not any(1<=idx[day]-idx[pd.Timestamp(d).date()]<=20 for d in c.date):raise AssertionError('No causal eligible signal')
        buy_checks+=1
    curve=result.intraday_equity_curve;eq=np.r_[4000.,curve.equity.to_numpy()]
    near(summary['max_drawdown_pct'],100*np.min(eq/np.maximum.accumulate(eq)-1))
    return dict(status='PASS_SCALAR_EXITS_CASH_FEES_AND_ENTRIES',buy_checks=buy_checks,scalar_exit_checks=exit_checks,
        average_winning_holding_sessions=float(np.mean(wins)) if wins else None,
        average_losing_holding_sessions=float(np.mean(losses)) if losses else None)


def worker(root,year,smoke=False):
    root=Path(root);p=base.read(root/'protocol.json');base.verify(p['sources'])
    logging.basicConfig(level=logging.ERROR,force=True)
    import requests
    def forbidden(*a,**k):raise RuntimeError('No HTTP/provider/broker in grid worker')
    requests.Session.request=forbidden
    cohort,groups,raw,actions,sectors,pivots,sessions=load_year(root,year)
    def bars(day,symbols):
        parts=[groups[s,day] for s in symbols if (s,day) in groups]
        return pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()
    chosen=[x for x in p['profiles'] if x['name']=='SL3_TR3_H10_TP15'] if smoke else p['profiles']
    reports=[];started=time.monotonic();state=root/f'year-{year}.json'
    for profile in chosen:
        folder=root/('smoke' if smoke else 'cases')/f"{year}-{profile['name']}"
        if (folder/'report.json').exists():
            r=base.read(folder/'report.json');base.verify({str(folder/k):v for k,v in r['files'].items()})
            if r['audit']['status']!='PASS_SCALAR_EXITS_CASH_FEES_AND_ENTRIES':raise ValueError('Prior case not audited')
            reports.append(r);continue
        folder.mkdir(parents=True,exist_ok=True)
        selected=cohort[['date','symbol','rank','selected']].rename(columns={'date':'trade_date'}).copy();selected['side']='long'
        def progress(done,total,day):
            atomic_json(state,dict(status='RUNNING',year=year,profile=profile['name'],completed_runs=len(reports),
                total_runs=len(chosen),completed_sessions=done,total_sessions=total,last_date=day,
                elapsed_seconds=time.monotonic()-started,smoke=smoke))
        try:
            cfg=configuration(p,year,profile,smoke=smoke)
            with runtime_adapter(year,profile['name']) as refusals:
                result=base.BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],
                    low=pivots['low'],volume=pivots['volume'],signals_df=selected,sector_map=sectors,
                    intraday_source=bars,winner_research_assumptions=True,winner_progress=progress,
                    winner_corporate_actions=actions.to_dict('records'))
                atomic_json(folder/'whole-share-refusals.json',refusals)
            summary=metrics(result,4000.)
            if summary['status']!='COMPLETED_EXPLORATORY':raise ValueError('Coverage incomplete: '+str(summary['coverage_gaps'][:5]))
            audit=audit_result(result,summary,profile,cohort,raw,sessions)
            result.closed_trades_df.to_parquet(folder/'trades.parquet',index=False)
            result.trade_events_df.to_csv(folder/'events.csv',index=False)
            result.intraday_equity_curve.to_parquet(folder/'equity-5m.parquet',index=False)
            result.equity_curve.to_frame().to_parquet(folder/'equity-daily.parquet')
            result.drawdown_breaker_df.to_parquet(folder/'breaker.parquet',index=False)
            summary.update(year=year,profile=profile['name'],parameters=profile,audit=audit,
                smoke=smoke,end_date=str(cfg.end_date),eligible_signals=int(cohort.selected.sum()),
                effective_gross_cap=p['effective_gross_cap'],
                average_winning_holding_sessions=audit['average_winning_holding_sessions'],
                average_losing_holding_sessions=audit['average_losing_holding_sessions'],
                files={x.name:base.digest(x) for x in folder.iterdir() if x.is_file() and x.name!='failure.json'})
            base.save_new(folder/'report.json',summary);reports.append(summary)
            pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,(dict,list))} for r in reports]).to_csv(root/f'annual-{year}.csv',index=False)
        except Exception as exc:
            atomic_json(folder/'failure.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
            atomic_json(state,dict(status='FAILED',year=year,profile=profile['name'],completed_runs=len(reports),error=str(exc)))
            raise
    base.verify(p['sources'])
    atomic_json(state,dict(status='COMPLETED_AUDITED_TECHNICAL_SMOKE' if smoke else 'COMPLETED_AUDITED_EXPLORATORY',
        year=year,completed_runs=len(reports),total_runs=len(chosen),elapsed_seconds=time.monotonic()-started))
    return dict(year=year,cases=len(reports))


def aggregate(root):
    reports=[]
    for f in sorted((root/'cases').glob('*/report.json')):
        r=base.read(f);base.verify({str(f.parent/k):v for k,v in r['files'].items()})
        reports.append(r)
    rows=[{k:v for k,v in r.items() if not isinstance(v,(dict,list))} for r in reports]
    frame=pd.DataFrame(rows);frame.to_csv(root/'annual-summary.partial.csv',index=False)
    if len(reports)!=3000:return None
    if frame.duplicated(['year','profile']).any():raise ValueError('Duplicate annual case')
    ranked=[]
    for name,g in frame.groupby('profile'):
        train=g[g.year.le(2023)];confirm=g[g.year.ge(2024)]
        dd=float((-train.max_drawdown_pct).max());median=float(train.return_pct.median())
        ranked.append(dict(profile=name,discovery_score=median/max(5.,dd),discovery_median_return=median,
            discovery_worst_dd=dd,discovery_positive_years=int(train.return_pct.gt(0).sum()),
            discovery_worst_return=float(train.return_pct.min()),confirmation_median_return=float(confirm.return_pct.median()),
            confirmation_worst_dd=float((-confirm.max_drawdown_pct).max()),
            positive_years=int(g.return_pct.gt(0).sum()),full_period_median_return=float(g.return_pct.median())))
    ranking=pd.DataFrame(ranked).sort_values(['discovery_score','discovery_positive_years','discovery_worst_return','profile'],ascending=[False,False,False,True])
    ranking.to_csv(root/'profile-ranking.csv',index=False);frame.to_csv(root/'annual-summary.csv',index=False)
    # Neighbours are diagnostics only; do not rerank on the later confirmation outcomes.
    params={x['name']:x for x in profiles()};neighbours=[]
    for chosen in ranking.profile.head(3):
        a=params[chosen]
        for other,b in params.items():
            changed=[k for k in a if k!='name' and a[k]!=b[k]]
            if len(changed)==1:
                row=ranking[ranking.profile.eq(other)].iloc[0].to_dict()
                neighbours.append(dict(chosen=chosen,changed_parameter=changed[0],**row))
    pd.DataFrame(neighbours).to_csv(root/'top3-one-parameter-neighbours.csv',index=False)
    base.save_new(root/'report.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',cases=len(reports),
        top3=ranking.head(3).to_dict('records'),independent_holdout=False,full_live_parity=False,
        files={n:base.digest(root/n) for n in ['annual-summary.csv','profile-ranking.csv','top3-one-parameter-neighbours.csv']}))
    return ranking.head(3).to_dict('records')


def run(root,workers=2,smoke=False):
    p=prepare(root)
    if (root/'report.json').exists():raise FileExistsError('Grid already complete')
    if smoke:
        snapshot(root,2017);return worker(root,2017,smoke=True)
    smoke_state=root/'year-2017.json'
    if not smoke_state.exists() or base.read(smoke_state).get('status')!='COMPLETED_AUDITED_TECHNICAL_SMOKE':
        # Existing real cases on resume supersede the technical-smoke marker.
        if not list((root/'cases').glob('*/report.json')):raise ValueError('Audited smoke required before full grid')
    errors=[];futures={};pending=list(YEARS);started=time.monotonic()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        while pending or futures:
            while pending and len(futures)<workers:
                year=pending[0]
                if year==2018 and not backfill_ready():break
                pending.pop(0)
                try:snapshot(root,year)
                except Exception as exc:
                    errors.append(dict(year=year,phase='SNAPSHOT',error=str(exc)));continue
                futures[pool.submit(worker,str(root),year)]=year
            done,_=wait(futures,timeout=5,return_when=FIRST_COMPLETED) if futures else (set(),set())
            for future in done:
                year=futures.pop(future)
                try:future.result()
                except Exception as exc:errors.append(dict(year=year,phase='REPLAY',error=str(exc)))
            states=[base.read(root/f'year-{y}.json') for y in YEARS if (root/f'year-{y}.json').exists()]
            count=len(list((root/'cases').glob('*/report.json')))
            if pending==[2018] and not backfill_ready():
                state=base.read(BACKFILL)
                if state.get('status') not in ('RUNNING',):
                    errors.append(dict(year=2018,phase='WAIT_INPUT',error='2018 collection terminal but incomplete'));pending=[]
            status='WAITING_2018_BACKFILL' if pending==[2018] and not futures else 'RUNNING'
            atomic_json(root/'progress.json',dict(status=status,completed_runs=count,total_runs=3000,
                elapsed_seconds=time.monotonic()-started,years=states,pending_years=pending,errors=errors))
            if not futures and pending:time.sleep(5)
    top3=aggregate(root)
    atomic_json(root/'progress.json',dict(status='PARTIAL_FAILED' if errors else 'COMPLETED_AUDITED_EXPLORATORY',
        completed_runs=len(list((root/'cases').glob('*/report.json'))),total_runs=3000,errors=errors,top3=top3,
        elapsed_seconds=time.monotonic()-started))
    if errors:raise RuntimeError('Incomplete annual grid; see progress.json. No complete TOP3.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT);parser.add_argument('--workers',type=int,choices=[1,2],default=2)
    parser.add_argument('--phase',choices=['prepare','smoke','run'],default='run');args=parser.parse_args()
    logging.basicConfig(level=logging.WARNING,format='%(asctime)s %(levelname)s %(message)s')
    args.output.mkdir(parents=True,exist_ok=True)
    with run_lock(args.output):
        if args.phase=='prepare':prepare(args.output)
        else:run(args.output,workers=args.workers,smoke=args.phase=='smoke')


if __name__=='__main__':main()
