"""Bounded contextual-protection feasibility; no training, orders or SQL writes.

Unit returns on paired first entries, NOT a portfolio backtest. Current shared
LONG protection primitives and entry-to-session21 expiry, unlike old grid J+H.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, replace
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
from sqlalchemy import bindparam, text

from backtesting.winner_campaign_replay import atomic_json
from common.winner_pyramiding import (WinnerPyramidingConfig, new_campaign, add_fill,
    confirmed_breakout, resolve_bar_exit, observe_completed_bar)
from scripts.research.us_concentrated_historical_tapes import digest, verify_hashes
from scripts.research.us_top10_intraday_breakout import qualify_day

REFERENCE=Path('artifacts/research/us_intraday_protection_grid/20261021-1x-risk-dd15-v1')
PRICE=Path('artifacts/research/us_h10_price_readiness/20261019-v1/qualification-final-v4/research-prices.parquet')
OUTPUT=Path('artifacts/research/us_winner_context_headroom/20261021-v1')
END=pd.Timestamp('2026-09-30')
BASE=WinnerPyramidingConfig(enabled=True,stop_loss_pct=.07,trailing_stop_pct=.15,
    take_profit_pct=None,horizon_sessions=20,initial_position_fraction=.5,reinforcement_enabled=False)
PROFILES=dict(REFERENCE=BASE,SL5=replace(BASE,stop_loss_pct=.05),
    TRAIL10=replace(BASE,trailing_stop_pct=.10),TRAIL20=replace(BASE,trailing_stop_pct=.20),
    HOLD15=replace(BASE,horizon_sessions=15),TP10=replace(BASE,take_profit_pct=.10))
GROUPS=['market_regime','atr_bucket','relative_momentum','volatility_expansion','entry_delay']
READ=lambda path:json.loads(Path(path).read_text(encoding='utf-8'))


def calendar_frame():
    return mcal.get_calendar('NYSE').schedule(start_date='2024-01-01',end_date='2026-12-31').reset_index(names='date')


class ArchiveCalendar:
    def __init__(self,schedule):self.schedule=schedule
    def sessions(self,start,end):
        g=self.schedule[self.schedule.date.between(pd.Timestamp(start),pd.Timestamp(end))]
        return [SimpleNamespace(session_date=r.date.date(),is_open=True,
                open_at_utc=r.market_open.to_pydatetime()) for r in g.itertuples()]


def prepare(root):
    if root.exists():raise ValueError('Fresh immutable output required')
    review=READ(REFERENCE/'final-review.json')
    verify_hashes(REFERENCE,review['files'])
    ready=READ(REFERENCE/'prepared.json');verify_hashes(REFERENCE,ready['files'])
    root.mkdir(parents=True)
    sources=[Path(__file__),Path('tests/test_us_winner_context_headroom.py'),PRICE,
        Path('common/winner_pyramiding.py'),Path('backtesting/winner_campaign_replay.py'),
        Path('scripts/research/us_top10_intraday_breakout.py'),REFERENCE/'candidates.parquet',
        REFERENCE/'prepared.json',REFERENCE/'final-review.json']
    atomic_json(root/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources={str(p):digest(p) for p in sources},profiles={k:asdict(v) for k,v in PROFILES.items()},
        selection='All213 archived research CatBoost PATH_H20 TOP10 LONG campaigns BEFORE new profile outcomes. '
            'Recompute first current-runtime fresh two-close breakout within20sessions; no capital admission or replacement.',
        entry='Current confirmed_breakout requires3same-session completed bars; next contiguous5m open. '
            'Prior raw-session high, common entry all6profiles. No reinforcement or daily profile change.',
        outcome='Unit notional,8bps each leg (stress25). Shared rounded-cent SL/TP and trailing from PRIOR completed5m bar. '
            'Holding20sessions ENTRY INCLUDED, exit OPEN21; common maturity barrier maximum20 regardless of early exits.',
        coverage='DB-enforced READ ONLY snapshot, original raw SIP regular5m/unfilled plus receipts. '
            'Require common full sessions throughopen21 and no known corporate action. '
            'Missing bars/immaturity always reserved for ALL profiles even if a tighter stop exited earlier.',
        primary_factors=dict(market_regime='prior SPY close versus SMA50/200: BULL/CORRECTION/REBOUND/SLIDE',
            atr_bucket='prior stock ATR20/close >=5% vs below5%',
            relative_momentum='prior20session stock return minus SPY >=0 vs negative',
            volatility_expansion='prior stock return vol20/vol60 >=1 vs below1',
            entry_delay='entry<=5officialsessions after Oracle vs later'),
        macro_sector='Snapshot coverage only. Macro vintage/PIT unproven and current sector non-PIT: '
            'not primary factors and no causal claims from these records.',
        independent_sample='Earliest-first per symbol, block through commonopen21, NOT actual chosen exit. '
            'Counts not certified independent across symbols or overlapping market periods.',
        confirmation='Exploratory2025 development,2026 confirmation already seen. Select ONE constant overall '
            'and ONE constant per fixed factor state on2025 only, labels available before2026. '
            'Freeze before2026 outcome comparison; missing/rare states fallback to2025overall constant. '
            'No training, threshold search, profile search or best-year profile in forward rows.',
        criteria=dict(min_nonoverlap_per_year=30,min_nonoverlap_per_state_year=12,
            min_hindsight_headroom_pp=.5,min_confirmation_gain_pp=.25,
            robust_to_cost25=True,positive_confirmation_both_halves=True,
            distinct_selected_profiles_at_least=2,monthly_cluster_bootstrap_lower95_gt_zero=True,
            bootstrap_draws=2000,bootstrap_seed=731,minimum_confirmation_months=6),
        decision='All gates necessary to justify a later SMALL model experiment, not sufficient for promotion. '
            'Otherwise stop NO_GO/INSUFFICIENT. No model fit or economic backtest in this GO.',
        limitations=['Inherited original213full-future-path cohort, survivor/coverage bias; NOT all historical TOP10.',
            'New common future-window exclusions add conditional coverage bias; report every reason.',
            'Only2025/2026toSept30; no2024intraday, no untouched holdout or multiple-testing certification.',
            'Unit return not portfolio capital/sizing/B4/leverage/reinvestment or annual drawdown.',
            'OHLC execution/8bps assumptions, not broker quotes, queue, tick order or live parity.',
            'Price histories revised, present SQL snapshot not original historical receipt.'],
        sql_writes=False,provider_calls=False,llm_calls=False,training=False,orders=False,production_changes=False))
    c=pd.read_parquet(REFERENCE/'candidates.parquet')
    c=c[c.side.eq('buy')].sort_values(['oracle_date','rank','symbol','pair_id']).reset_index(drop=True)
    if len(c)!=213 or c.pair_id.duplicated().any():raise ValueError('Frozen213cohort changed')
    c.to_parquet(root/'campaigns.parquet',index=False)
    calendar_frame().to_parquet(root/'calendar.parquet',index=False)
    atomic_json(root/'prepared.json',dict(files={name:digest(root/name) for name in ['campaigns.parquet','calendar.parquet']}))
    atomic_json(root/'progress.json',dict(status='PREPARED',total=213,completed=0))


def needed_days(campaigns,schedule):
    days=pd.DatetimeIndex(schedule.date);needed={}
    for r in campaigns.itertuples():
        i=days.get_loc(r.oracle_date)
        for d in days[i:min(i+41,len(days))]:
            if d<=END:needed.setdefault(r.symbol,set()).add(d.date())
    return needed


def snapshot(root):
    from database.connection import get_sqlalchemy_engine
    verify_hashes(Path('.'),READ(root/'protocol.json')['sources'])
    verify_hashes(root,READ(root/'prepared.json')['files'])
    if (root/'snapshot.json').exists():raise ValueError('Snapshot already sealed')
    c=pd.read_parquet(root/'campaigns.parquet');s=pd.read_parquet(root/'calendar.parquet')
    needed=needed_days(c,s);engine=get_sqlalchemy_engine()
    files={};receipts=[]
    with engine.connect() as conn,conn.begin():
        conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        if conn.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':raise ValueError('US DB only')
        for index,(symbol,days) in enumerate(sorted(needed.items()),1):
            query=text('''SELECT symbol,trade_date,bar_timestamp,bar_end_timestamp,open,high,low,close,
                volume,provider,data_source,market_code,interval_code,session_tag,data_adjustment,is_filled,payload_hash
                FROM stock_bars_intraday WHERE symbol=:symbol AND trade_date IN :days
                AND interval_code='5m' AND provider='alpaca' AND data_source='alpaca_sip'
                AND market_code='US_EQ' AND session_tag='regular' AND data_adjustment='raw' AND is_filled=0
                ORDER BY trade_date,bar_timestamp''').bindparams(bindparam('days',expanding=True))
            frame=pd.read_sql(query,conn,params=dict(symbol=symbol,days=sorted(days)))
            if not frame.empty:
                if frame.payload_hash.isna().any():raise ValueError('Unproven intraday payload')
                for col in ('bar_timestamp','bar_end_timestamp'):frame[col]=pd.to_datetime(frame[col],utc=True)
                frame['trade_date']=pd.to_datetime(frame.trade_date)
            name=f'bars-{index:03d}.parquet';frame.to_parquet(root/name,index=False);files[name]=digest(root/name)
            receipts.append(dict(symbol=symbol,requested_sessions=len(days),rows=len(frame),file=name))
            atomic_json(root/'progress.json',dict(status='SNAPSHOT',completed=index,total=len(needed),last=symbol))
        syms=sorted(needed)
        sec=pd.read_sql(text('SELECT symbol,sector FROM stock_metadata WHERE symbol IN :symbols').bindparams(
            bindparam('symbols',expanding=True)),conn,params={'symbols':syms})
        ca=pd.read_sql(text('SELECT symbol,ca_type,ex_date FROM corporate_actions_events '
            'WHERE symbol IN :symbols AND ex_date BETWEEN :start AND :end').bindparams(
            bindparam('symbols',expanding=True)),conn,params=dict(symbols=syms,start='2025-01-01',end=str(END.date())))
        columns={r[0] for r in conn.execute(text('SHOW COLUMNS FROM stock_macro_indicators_daily'))}
        wanted=[k for k in ['trade_date','date','vix','vxn','vix3m','move','ten_y','sentiment_score'] if k in columns]
        key=next((k for k in ['trade_date','date'] if k in columns),None)
        macro=pd.read_sql(text('SELECT '+','.join(f'`{k}`' for k in wanted)+' FROM stock_macro_indicators_daily '
            f'WHERE `{key}` BETWEEN :start AND :end ORDER BY `{key}`'),conn,
            params=dict(start='2025-01-01',end=str(END.date()))) if key else pd.DataFrame()
        for name,f in [('current-sectors.parquet',sec),('corporate-actions.parquet',ca),('macro-unqualified.parquet',macro)]:
            f.to_parquet(root/name,index=False);files[name]=digest(root/name)
    atomic_json(root/'snapshot.json',dict(files=files,receipts=receipts,observed_at_utc=datetime.now(timezone.utc).isoformat(),
        current_metadata_not_historical_pit=True,macro_used_as_predictor=False))


def daily_features(daily,days):
    result={}
    for symbol,g in daily.groupby('symbol'):
        g=g.set_index('date').reindex(days)
        fields=['open','high','low','close','volume']
        ok=(np.isfinite(g[fields]).all(axis=1)&g[fields].gt(0).all(axis=1)&g.is_filled.eq(0)
            &g.data_adjustment.eq('split')&g.high.ge(g[['open','close']].max(axis=1))&g.low.le(g[['open','close']].min(axis=1)))
        p=g.close.where(ok);ret=p.pct_change(fill_method=None)
        tr=pd.concat([g.high-g.low,(g.high-p.shift()).abs(),(g.low-p.shift()).abs()],axis=1).max(axis=1).where(ok&p.shift().notna())
        result[symbol]=pd.DataFrame(dict(close=p,sma50=p.rolling(50).mean(),sma200=p.rolling(200).mean(),
            ret20=p/p.shift(20)-1,atr_pct=tr.rolling(20).mean()/p,
            vol_ratio=ret.rolling(20).std()/ret.rolling(60).std()))
    return result


def context(features,symbol,source,delay):
    if symbol not in features or 'SPY' not in features:return None
    a,b=features[symbol].loc[source],features['SPY'].loc[source]
    values=[a.atr_pct,a.ret20,a.vol_ratio,b.close,b.sma50,b.sma200,b.ret20]
    if not np.isfinite(values).all():return None
    regime=('BULL' if b.close>b.sma50 else 'CORRECTION') if b.close>b.sma200 else ('REBOUND' if b.close>b.sma50 else 'SLIDE')
    return dict(source_date=source,market_regime=regime,atr_bucket='HIGH_GE5' if a.atr_pct>=.05 else 'LOW_LT5',
        relative_momentum='POSITIVE' if a.ret20-b.ret20>=0 else 'NEGATIVE',
        volatility_expansion='EXPANDING' if a.vol_ratio>=1 else 'CONTRACTING',
        entry_delay='EARLY_LE5' if delay<=5 else 'LATE_GT5',atr_pct=float(a.atr_pct),
        relative_return20=float(a.ret20-b.ret20),volatility_ratio=float(a.vol_ratio))


def first_entry(r,groups,schedule):
    days=pd.DatetimeIndex(schedule.date);i=days.get_loc(r.oracle_date)
    for j in range(i+1,min(i+21,len(days))):
        d,prior=days[j],days[j-1]
        if d>END:return None,'ENTRY_WINDOW_CENSORED'
        current,prev=groups.get((r.symbol,d)),groups.get((r.symbol,prior))
        if current is None or prev is None:return None,'ENTRY_SCAN_MISSING_SESSION'
        hi=float(prev.high.max());cl=current.close.to_numpy(float)
        for k in range(2,len(current)-1):
            if cl[k-2]<=hi and cl[k-1]>hi and cl[k]>hi:
                stamp=current.bar_timestamp.iloc[k+1]
                bars=[dict(timestamp=q.bar_timestamp.to_pydatetime(),close=q.close,session_tag='regular')
                      for q in current.iloc[k-2:k+1].itertuples()]
                if not confirmed_breakout(bars,hi,BASE,now=stamp.to_pydatetime()):
                    raise ValueError('Shared entry predicate mismatch')
                return dict(date=d,timestamp=stamp,delay=j-i,price=float(current.open.iloc[k+1])),None
    return None,'NO_CURRENT_RUNTIME_SIGNAL'


def unit_outcome(path,entry,policy,cal,fee=.0008):
    state=new_campaign('unit','UNIT',1,1,100000.,policy)
    add_fill(state,parent_id='entry',quantity=1,price=float(entry['price']),filled_at=entry['timestamp'].to_pydatetime(),calendar=cal)
    due=pd.Timestamp(state['due_open']);lot=state['lots'][0]
    if path.empty or path.bar_timestamp.max()<due:raise ValueError('Common horizon immature')
    for r in path[path.bar_timestamp.between(entry['timestamp'],due)].itertuples():
        bar=dict(open=r.open,high=r.high,low=r.low)
        hit=resolve_bar_exit(lot,bar,at_deadline=r.bar_timestamp==due)
        if hit:
            price,reason,phase=hit
            return dict(net_pct=100*((price-entry['price'])/entry['price']-fee*(1+price/entry['price'])),
                exit_price=float(price),reason=reason,exit_time=r.bar_timestamp if phase=='OPEN' else r.bar_end_timestamp,
                phase=phase,due_open=due)
        observe_completed_bar(lot,float(r.high),policy)
    raise ValueError('Expected horizon exit not reached')


def spaced(frame):
    kept=[];blocked={}
    for r in frame.sort_values(['entry_time','rank','symbol','pair_id']).itertuples():
        if r.symbol in blocked and r.entry_time<blocked[r.symbol]:continue
        kept.append(r.Index);blocked[r.symbol]=r.label_available
    return frame.loc[kept].copy()


def summary(frame,columns):
    if frame.empty:return dict(n=0)
    a=frame[columns].to_numpy(float)
    means=a.mean(axis=0);best=int(np.argmax(means));ceiling=a.max(axis=1)
    return dict(n=len(frame),symbols=int(frame.symbol.nunique()),best_constant=columns[best],
        means={k:float(v) for k,v in zip(columns,means)},
        hindsight_headroom_pp=float(ceiling.mean()-means[best]),
        all_profiles_lose_pct=float(100*(a.max(axis=1)<0).mean()),
        profiles_differ_pct=float(100*(np.ptp(a,axis=1)>1e-8).mean()))


def monthly_interval(dates,gains):
    clusters=pd.DataFrame(dict(month=pd.to_datetime(dates,utc=True).dt.strftime('%Y-%m'),gain=gains)).groupby('month').gain.agg(['sum','size'])
    rng=np.random.default_rng(731)
    selected=rng.integers(0,len(clusters),size=(2000,len(clusters)))
    draws=clusters['sum'].to_numpy()[selected].sum(axis=1)/clusters['size'].to_numpy()[selected].sum(axis=1)
    return dict(months=len(clusters),lower95=float(np.quantile(draws,.025)),upper95=float(np.quantile(draws,.975)))


def contextual_checks(frame):
    # No model fit. Freeze choices solely on fully mature2025 labels.
    train=frame[(frame.year==2025)&(frame.label_available<pd.Timestamp('2026-01-01',tz='UTC'))]
    test=frame[frame.year==2026].copy();cols=list(PROFILES)
    if train.empty or test.empty:return [],dict(status='INSUFFICIENT_TEMPORAL_SAMPLE')
    baseline=train[cols].mean().idxmax();rows=[];frozen={}
    for factor in GROUPS:
        choices={};counts={}
        for state,g in train.groupby(factor):
            counts[state]=len(g)
            choices[state]=g[cols].mean().idxmax() if len(g)>=12 else baseline
        frozen[factor]=dict(choices=choices,counts=counts)
        selected=test[factor].map(choices).fillna(baseline)
        gains=np.array([getattr(r,p)-getattr(r,baseline) for r,p in zip(test.itertuples(),selected)])
        stressed=np.array([getattr(r,p+'_cost25')-getattr(r,baseline+'_cost25') for r,p in zip(test.itertuples(),selected)])
        half=pd.to_datetime(test.entry_time,utc=True).dt.month.le(6).to_numpy()
        sufficient=(len(train)>=30 and len(test)>=30 and all(
            counts.get(state,0)>=12 and int(test[factor].eq(state).sum())>=12 for state in test[factor].unique()))
        halves=[float(gains[mask].mean()) if mask.any() else None for mask in (half,~half)]
        interval=monthly_interval(test.entry_time,gains)
        distinct=int(selected.nunique())
        passed=bool(sufficient and distinct>=2 and gains.mean()>=.25 and stressed.mean()>0
            and all(v is not None and v>0 for v in halves) and interval['months']>=6 and interval['lower95']>0)
        rows.append(dict(factor=factor,train_n=len(train),test_n=len(test),baseline=baseline,
            selections=selected.value_counts().to_dict(),gain_pp=float(gains.mean()),gain_cost25_pp=float(stressed.mean()),
            half_year_gains_pp=halves,monthly_interval=interval,distinct_profiles=distinct,
            sufficient_states=sufficient,passes_context_gate=passed))
    return rows,dict(baseline=baseline,training_cutoff='2026-01-01',frozen=frozen)


def analyze(root):
    if (root/'report.json').exists():raise ValueError('Analysis already sealed')
    verify_hashes(Path('.'),READ(root/'protocol.json')['sources'])
    verify_hashes(root,READ(root/'prepared.json')['files'])
    snap=READ(root/'snapshot.json');verify_hashes(root,snap['files'])
    campaigns=pd.read_parquet(root/'campaigns.parquet');schedule=pd.read_parquet(root/'calendar.parquet')
    days=pd.DatetimeIndex(schedule.date);sch=schedule.set_index('date');cal=ArchiveCalendar(schedule)
    groups={};session_status=[]
    for name in snap['files']:
        if not name.startswith('bars-'):continue
        f=pd.read_parquet(root/name)
        for (symbol,day),g in f.groupby(['symbol','trade_date']):
            qualified,why=qualify_day(g,*sch.loc[day,['market_open','market_close']])
            session_status.append(dict(symbol=symbol,date=day,status=why))
            if qualified is not None:groups[symbol,day]=qualified
    daily=pd.read_parquet(PRICE);daily['date']=pd.to_datetime(daily.date)
    syms=set(campaigns.symbol)|{'SPY'};daily=daily[daily.symbol.isin(syms)]
    history=mcal.get_calendar('NYSE').schedule(start_date=daily.date.min(),end_date=END).index
    features=daily_features(daily,history)
    actions=pd.read_parquet(root/'corporate-actions.parquet')
    if not actions.empty:actions['ex_date']=pd.to_datetime(actions.ex_date)
    rows=[];reserved=[]
    for done,r in enumerate(campaigns.itertuples(),1):
        entry,why=first_entry(r,groups,schedule)
        if entry:
            i=days.get_loc(entry['date']);end=days[i+20]
            if end>END:why='COMMON_H20_IMMATURE'
            elif any((r.symbol,d) not in groups for d in days[i:i+21]):why='COMMON_H20_5M_MISSING'
            elif not actions.empty and ((actions.symbol==r.symbol)&actions.ex_date.between(entry['date'],end)).any():why='CORPORATE_ACTION_RESERVED'
            context_row=context(features,r.symbol,days[i-1],entry['delay']) if why is None else None
            if why is None and context_row is None:why='MISSING_PRIOR_CONTEXT'
            if why is None:
                path=pd.concat([groups[r.symbol,d] for d in days[i:i+21]],ignore_index=True)
                row=dict(pair_id=int(r.pair_id),symbol=r.symbol,rank=int(r.rank),year=entry['date'].year,
                    oracle_date=r.oracle_date,entry_time=entry['timestamp'],entry_price=entry['price'],
                    label_available=sch.loc[end,'market_close'],**context_row)
                for name,policy in PROFILES.items():
                    out=unit_outcome(path,entry,policy,cal)
                    row[name]=out['net_pct'];row[name+'_cost25']=unit_outcome(path,entry,policy,cal,.0025)['net_pct']
                    row[name+'_exit']=out['exit_time'];row[name+'_reason']=out['reason']
                rows.append(row)
        if why:reserved.append(dict(pair_id=int(r.pair_id),symbol=r.symbol,reason=why))
        atomic_json(root/'progress.json',dict(status='ANALYZING',completed=done,total=len(campaigns),qualified=len(rows)))
    frame=pd.DataFrame(rows);frame.to_parquet(root/'unit-results.parquet',index=False)
    pd.DataFrame(reserved).to_parquet(root/'reservations.parquet',index=False)
    pd.DataFrame(session_status).to_parquet(root/'session-quality.parquet',index=False)
    if frame.empty:
        report=dict(status='INSUFFICIENT_QUALIFIED_SAMPLE',qualified=0,reservations=dict(Counter(r['reason'] for r in reserved)))
    else:
        independent=spaced(frame);independent.to_parquet(root/'nonoverlap.parquet',index=False)
        states=[]
        for factor in GROUPS:
            for (year,state),g in independent.groupby(['year',factor]):
                states.append(dict(factor=factor,year=int(year),state=state,**summary(g,list(PROFILES))))
        atomic_json(root/'factor-state-summary.json',states)
        checks,frozen=contextual_checks(independent)
        atomic_json(root/'frozen-2025-policy.json',frozen)
        atomic_json(root/'context-checks.json',checks)
        annual={str(y):summary(g,list(PROFILES)) for y,g in frame.groupby('year')}
        nonoverlap={str(y):summary(g,list(PROFILES)) for y,g in independent.groupby('year')}
        sufficient=all(nonoverlap.get(str(y),{}).get('n',0)>=30 for y in [2025,2026])
        headroom=all(nonoverlap.get(str(y),{}).get('hindsight_headroom_pp',0)>=.5 for y in [2025,2026])
        go=sufficient and headroom and any(r['passes_context_gate'] for r in checks)
        report=dict(status='EXPLORATORY_CONTEXT_WORTH_MODEL_PROTOCOL' if go else 'NO_GO_CONTEXT_NOT_CONFIRMED',
            qualified=len(frame),nonoverlap=len(independent),annual=annual,nonoverlap_annual=nonoverlap,
            reservations=dict(Counter(r['reason'] for r in reserved)),context_checks=checks,
            sufficient_sample=sufficient,material_hindsight_headroom=headroom,
            model_trained=False,economic_portfolio_test=False,
            macro_rows_unqualified=len(pd.read_parquet(root/'macro-unqualified.parquet')),
            current_sector_rows_non_pit=len(pd.read_parquet(root/'current-sectors.parquet')))
    report.update(files={p.name:digest(p) for p in root.iterdir() if p.is_file() and p.name not in ['report.json','progress.json']})
    atomic_json(root/'report.json',report);atomic_json(root/'progress.json',dict(status=report['status'],completed=len(campaigns),total=len(campaigns)))
    print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=2,default=str))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=['prepare','snapshot','analyze'],required=True)
    parser.add_argument('--output-dir',type=Path,default=OUTPUT);args=parser.parse_args()
    try:
        {'prepare':prepare,'snapshot':snapshot,'analyze':analyze}[args.phase](args.output_dir)
    except Exception as exc:
        if args.output_dir.exists() and not (args.output_dir/'report.json').exists():
            atomic_json(args.output_dir/'progress.json',dict(status='FAILED',phase=args.phase,
                error_type=type(exc).__name__,error=str(exc)))
        raise
