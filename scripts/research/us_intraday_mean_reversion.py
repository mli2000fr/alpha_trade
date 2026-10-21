"""Frozen same-session mean reversion; existing local SIP bars, SQL READ ONLY.

No fit, download, SQL write, production modification, or broker order. Not a
replication of an institutional strategy, and not a capital portfolio backtest.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

PRICE = Path('artifacts/research/us_h10_price_readiness/20261019-v1/qualification-final-v4/research-prices.parquet')
SCORES = Path('artifacts/research/us_h10_h20_frozen_comparison/20261019-v1')
UNIVERSE = Path('config/univers_batch/univers_filtred_tradable.txt')
READ = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
LOG = logging.getLogger(__name__)


def liquidity_pool(prices, schedule, universe):
    """Twenty *prior* consecutive sessions, no current/future bar in admission."""
    days = pd.DatetimeIndex(schedule.date)
    frames = []
    for symbol, f in prices[prices.symbol.isin(universe)].groupby('symbol', sort=True):
        if f.date.duplicated().any():
            raise ValueError('Duplicate reference symbol/date')
        g = f.set_index('date').reindex(days)
        x = g[['open','high','low','close','volume']].apply(pd.to_numeric, errors='coerce')
        valid = (np.isfinite(x).all(axis=1) & x.gt(0).all(axis=1) & g.is_filled.eq(0)
            & x.high.ge(x[['open','close','low']].max(axis=1))
            & x.low.le(x[['open','close','high']].min(axis=1)))
        for name in ['instrument_id','data_source','data_adjustment']:
            known = g[name].notna() & ~g[name].astype(str).str.upper().isin(['','UNKNOWN','NONE','NAN'])
            same = g[name].eq(g[name].shift(1))
            valid &= known
            stable = same.shift(1).rolling(19, min_periods=19).sum().eq(19)
            valid_history = stable if name == 'instrument_id' else valid_history & stable
        good = valid.shift(1).rolling(20, min_periods=20).sum().eq(20) & valid_history
        value = (x.close*x.volume).where(valid).shift(1).rolling(20, min_periods=20).median()
        ok = good & value.ge(20_000_000) & x.close.shift(1).ge(5)
        if ok.any():
            frames.append(pd.DataFrame(dict(date=days[ok], symbol=symbol,
                prior_liquidity=value[ok].to_numpy(), previous_price=x.close.shift(1)[ok].to_numpy())))
    all_rows = pd.concat(frames, ignore_index=True)
    all_rows = all_rows.sort_values(['date','prior_liquidity','symbol'], ascending=[True,False,True])
    all_rows['liquidity_rank'] = all_rows.groupby('date').cumcount()+1
    return all_rows[all_rows.liquidity_rank.le(100)].reset_index(drop=True)


def prepare(root):
    if (root/'protocol.json').exists():
        p = READ(root/'protocol.json'); verify_hashes(Path('.'), p['sources'])
        verify_hashes(root, READ(root/'prepared.json')['files'])
        return p
    if root.exists() and any(root.iterdir()):
        raise ValueError('Fresh empty output directory required')
    source = READ(SCORES/'protocol.json')
    if READ(SCORES/'final-audit.json')['status'] != 'PASS_EXPLORATORY_ONLY':
        raise ValueError('Unqualified Oracle source')
    expected_price = next(v for k,v in source['sources'].items() if Path(k).name==PRICE.name)
    if digest(PRICE)!=expected_price: raise ValueError('Changed source price tape')
    files = [Path(__file__), Path('scripts/research/us_intraday_mean_reversion_audit.py'),
        Path('tests/test_us_intraday_mean_reversion.py'),
        Path('scripts/research/us_concentrated_historical_tapes.py'), PRICE,
        PRICE.parent/'quality-reserves.json', UNIVERSE, SCORES/'protocol.json', SCORES/'final-audit.json']
    for y in (2024,2025,2026):
        name = f'{y}-H20-scores.parquet'
        if digest(SCORES/name) != READ(SCORES/f'{y}-done.json')['files'][name]:
            raise ValueError('Changed annual research scores')
        files.extend([SCORES/name, SCORES/f'{y}-done.json'])
    # Freeze before reading intraday outcomes. No thresholds chosen on this test.
    p = dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources={str(f):digest(f) for f in files}, start='2024-01-03', end='2026-09-02',
        primary='LONG mean reversion on up to100 liquid candidates, no Oracle prerequisite',
        secondary='SHORT is diagnostic only, no historical locate qualification; combined is not an executable recommendation',
        scope=['LIQUID100','ORACLE_TOP20PCT','ORACLE_TOP10'],
        oracle='Annual frozen research CatBoost PATH_H20 rolling OOS ranks at previous NYSE close only. Not current live LightGBM model; never use same-day close scores intraday.',
        ranking='Top100 by median20 prior daily close*volume, >=20M USD proxy, previous close>=5; twenty complete stable metadata sessions. No backfill replacement for missing intraday.',
        liquidity_reserve='Historical vendor split-adjusted OHLC and volume may not share a true as-of raw notional basis. This is a restated liquidity proxy, not certified historical dollar turnover.',
        reference='No SPY or sectorETF SIP5m in local SQL at feasibility check. Cross-sectional median open-to-current-close return of prefix-qualified liquid basket; >=80% of selected basket and >=50 names. Includes own name; no sector neutrality claimed.',
        source='Existing stock_bars_intraday / alpaca / alpaca_sip / 5m / raw / regular / US_EQ only',
        signal='First completed bar ending at least30min after open and at least60min before close: abs(stock return minus basket median)>=2%; long if negative plus close>previous close and low>=previous low; short symmetric. Target is cumulative typical-price volume proxy frozen at signal; target must be beyond signal close in trade direction.',
        execution='Next contiguous bar open, market-order proxy, no fill on signal bar. One trigger per symbol/day; invalid target at next open abstains, no retry. No doubling, no averaging down, no overnight.',
        vwap='Cumulative sum(((high+low+close)/3)*volume)/sum(volume), using completed prefix only; NOT true trade VWAP.',
        stop_pct=.01, take='Frozen signal VWAP proxy, not updated with future bars',
        expiry='Scheduled final5m bar OPEN (15:55 NY normally,12:55 half-day), never assumed closing-auction fill',
        collision='Adverse gap at open, favorable target gap capped at target; intrabar stop first if both touched. Entry on/beyond target abstains.',
        fees_per_leg=.001, stress_fees_per_leg=.0025, commission_per_order=1., notional=1000.,
        costs='Illustrative10bps per executed notional leg plus1USD per order at1000USD initial notional; stress25bps. Short borrow .3%annual charged one day, no locates proven.',
        quality='Prefix grid and positive valid raw SIP bars required before signal, no future filtering of basket. Full remaining execution path required for a qualified outcome even if an earlier exit would work; otherwise UNKNOWN and all policies retained unknown.',
        controls='On same signal timestamp, mean-reversion direction versus reversed direction, alwaysLONG, alwaysSHORT; same target distance magnitude and1%stop. Matched controls not unconditional buy-and-hold.',
        bootstrap='20-session moving blocks over full calendar, fixed seed20261020,1999 draws; descriptive CIs, no fresh holdout',
        admission='At least50 qualified signal-days and100 trades/year for primary LONG. Primary net and paired advantage over matchedSHORT must have lower CI>0 in BOTH2025 and2026 at stress costs. ALWAYS_LONG is identical on LONG subset, so cannot prove incremental selection/direction skill.2024 descriptive only; even a pass is exploratory and no promotion.',
        price_reserves=source['price_reserves'],
        sql_writes=False, downloads=False, fit=False, orders=False, portfolio_pnl=False,
        reserves=['Static current survivor universe, restated historical bars, unknown historical receive time',
            'OHLC only: no NBBO/depth/queue/halts auction proof; next-open market proxy, not live parity',
            'Per-occasion equal-notional returns, not annual compounded portfolio return or drawdown',
            'No guaranteed human independence; audit is another implementation by same assistant',
            'Intraday operation requires machine/broker availability during entry window; no scheduler changed'])
    root.mkdir(parents=True, exist_ok=True)
    atomic_json(root/'protocol.json', p)
    universe = set(UNIVERSE.read_text().replace('\n',',').split(','))-{''}
    prices = pd.read_parquet(PRICE)
    schedule = mcal.get_calendar('NYSE').schedule(start_date='2023-10-01', end_date=p['end'])
    schedule.index.name = 'date'; schedule = schedule.reset_index()
    pool = liquidity_pool(prices, schedule, universe)
    pool = pool[pool.date.ge(p['start']) & pool.date.le(p['end'])].copy()
    dates = pd.DatetimeIndex(schedule.date)
    pool['signal_date'] = [dates[dates.get_loc(d)-1] for d in pool.date]
    sc = pd.concat([pd.read_parquet(SCORES/f'{y}-H20-scores.parquet',
        columns=['date','symbol','score','rank','scored_count']) for y in (2024,2025,2026)], ignore_index=True)
    sc = sc.rename(columns={'date':'signal_date','rank':'oracle_rank'})
    pool = pool.merge(sc,on=['signal_date','symbol'],how='left',validate='many_to_one')
    pool['top10'] = pool.oracle_rank.le(10)
    pool['top20pct'] = pool.oracle_rank.le(np.ceil(.2*pool.scored_count))
    pool['year'] = pool.date.dt.year
    pool.to_parquet(root/'pool.parquet',index=False)
    schedule.to_parquet(root/'sessions.parquet',index=False)
    atomic_json(root/'prepared.json',dict(files={n:digest(root/n) for n in ['pool.parquet','sessions.parquet']},
        pairs=len(pool), symbols=pool.symbol.nunique(), sessions=pool.date.nunique(),
        oracle_matched=int(pool.oracle_rank.notna().sum())))
    LOG.info('Prepared %d pairs / %d symbols',len(pool),pool.symbol.nunique())
    return p


def snapshot(root):
    prepare(root)
    if (root/'snapshot-ready.json').exists():
        verify_hashes(root, READ(root/'snapshot-ready.json')['files']); return
    from database.connection import get_sqlalchemy_engine
    from sqlalchemy import text, bindparam
    pool = pd.read_parquet(root/'pool.parquet')
    # Partial snapshots never silently resume under a later database transaction.
    part = root/'snapshot'; part.mkdir(exist_ok=False)
    engine = get_sqlalchemy_engine(); files = {}; counts = []
    sql = text('''SELECT symbol,trade_date,bar_timestamp,bar_end_timestamp,open,high,low,close,
        volume,is_filled,data_adjustment,session_tag,provider,data_source,market_code,interval_code,
        observed_at,payload_hash,run_id FROM stock_bars_intraday
        WHERE symbol=:symbol AND bar_timestamp>=:start AND bar_timestamp<:end
        AND trade_date IN :dates AND interval_code='5m' AND provider='alpaca'
        AND data_source='alpaca_sip' AND market_code='US_EQ' AND session_tag='regular'
        ORDER BY bar_timestamp''').bindparams(bindparam('dates',expanding=True))
    tasks = list(pool.groupby(['symbol','year'],sort=True))
    start = datetime.now(timezone.utc).isoformat()
    with engine.connect() as conn:
        conn.execute(text('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
        conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
        for i, ((symbol,year),f) in enumerate(tasks):
            dates = sorted(f.date.dt.date.unique())
            rows = pd.read_sql_query(sql,conn,params=dict(symbol=symbol,dates=dates,
                start=pd.Timestamp(dates[0]).to_pydatetime(),
                end=(pd.Timestamp(dates[-1])+pd.Timedelta(days=2)).to_pydatetime()))
            for col in ['bar_timestamp','bar_end_timestamp','observed_at']:
                rows[col] = pd.to_datetime(rows[col],utc=True)
            rows['trade_date'] = pd.to_datetime(rows.trade_date)
            name=f'snapshot/{i:04d}-{symbol}-{year}.parquet'
            rows.to_parquet(root/name,index=False); files[name]=digest(root/name)
            counts.append(dict(symbol=symbol,year=int(year),expected=len(f),
                sessions=int(rows.trade_date.nunique()),rows=len(rows)))
            atomic_json(root/'progress.json',dict(status='SNAPSHOTTING',completed=i+1,total=len(tasks),
                rows=sum(c['rows'] for c in counts),current=symbol))
            if i%20==0: LOG.info('Snapshot %d/%d %s rows=%d',i+1,len(tasks),symbol,len(rows))
        conn.rollback()
    engine.dispose()
    pd.DataFrame(counts).to_csv(root/'snapshot-coverage.csv',index=False)
    atomic_json(root/'snapshot-ready.json',dict(started_at_utc=start,
        finished_at_utc=datetime.now(timezone.utc).isoformat(),
        transaction='REPEATABLE READ / READ ONLY / ROLLBACK',files=files,
        rows=sum(c['rows'] for c in counts),tasks=len(tasks)))


def bar_grid(frame, opening, closing):
    """Expose only prefix validity for decision; future missing bars cannot remove a peer."""
    times = pd.date_range(opening,closing,freq='5min',inclusive='left')
    if frame.bar_timestamp.duplicated().any():
        return None
    f = frame.set_index('bar_timestamp').reindex(times).reset_index(names='bar_timestamp')
    a = f[['open','high','low','close','volume']].apply(pd.to_numeric,errors='coerce').to_numpy(float)
    valid = np.isfinite(a).all(axis=1) & (a>0).all(axis=1)
    valid &= (a[:,1]>=a[:,:4].max(axis=1)) & (a[:,2]<=a[:,:4].min(axis=1))
    for col,value in [('provider','alpaca'),('data_source','alpaca_sip'),('interval_code','5m'),
        ('market_code','US_EQ'),('session_tag','regular'),('data_adjustment','raw'),('is_filled',0)]:
        valid &= f[col].eq(value).to_numpy()
    valid &= f.bar_end_timestamp.eq(times+pd.Timedelta(minutes=5)).to_numpy()
    f['valid'] = valid
    f['prefix_good'] = np.logical_and.accumulate(valid)
    # Invalid bars cannot enter later cumulative statistics.
    typical = (a[:,1]+a[:,2]+a[:,3])/3
    with np.errstate(divide='ignore',invalid='ignore'):
        vwap = np.cumsum(np.where(valid,typical*a[:,4],0))/np.cumsum(np.where(valid,a[:,4],0))
        returns = a[:,3]/a[0,0]-1
    f['vwap_proxy'] = np.where(f.prefix_good,vwap,np.nan)
    f['session_return'] = np.where(f.prefix_good,returns,np.nan)
    return f


def trigger(frame, benchmark, opening, closing):
    """Read completed bars only; first qualifying signal consumes the day's opportunity."""
    a = frame[['close','high','low','vwap_proxy','session_return']].to_numpy(float)
    for i in range(1,len(frame)-2):
        end = frame.bar_timestamp.iloc[i]+pd.Timedelta(minutes=5)
        if end<opening+pd.Timedelta(minutes=30) or end>closing-pd.Timedelta(minutes=60):
            continue
        if not frame.prefix_good.iloc[i] or not np.isfinite(benchmark[i]):
            continue
        residual = a[i,4]-benchmark[i]
        if residual<=-.02 and a[i,0]>a[i-1,0] and a[i,2]>=a[i-1,2] and a[i,3]>a[i,0]:
            return i,'LONG',float(a[i,3]),float(residual)
        if residual>=.02 and a[i,0]<a[i-1,0] and a[i,1]<=a[i-1,1] and a[i,3]<a[i,0]:
            return i,'SHORT',float(a[i,3]),float(residual)
    return None


def execute(path, side, target, stop_pct=.01):
    """Last row is forced exit at OPEN; its later high/low/close are never read."""
    sign = 1 if side=='LONG' else -1
    if side not in ['LONG','SHORT'] or len(path)<2 or not path.valid.all():
        raise ValueError('Complete executable path required')
    entry=float(path.open.iloc[0])
    if sign*(target-entry)<=0: return None
    stop=entry*(1-sign*stop_pct); exit_price=float(path.open.iloc[-1]); reason='TIME'
    idx=len(path)-1; collision=False; gap=False
    for i,r in enumerate(path.iloc[:-1].itertuples()):
        if sign*(r.open-stop)<=abs(stop)*1e-12:
            exit_price=float(r.open); reason='SL'; idx=i; gap=True; break
        if sign*(r.open-target)>=-abs(target)*1e-12:
            exit_price=target; reason='TP'; idx=i; break
        hs=r.low<=stop+abs(stop)*1e-12 if sign==1 else r.high>=stop-abs(stop)*1e-12
        ht=r.high>=target-abs(target)*1e-12 if sign==1 else r.low<=target+abs(target)*1e-12
        if hs: exit_price=stop; reason='SL'; idx=i; collision=bool(ht); break
        if ht: exit_price=target; reason='TP'; idx=i; break
    # Forced exit at final open includes adverse gap, but no imaginary final-bar TP.
    if reason=='TIME' and sign*(exit_price-stop)<=0: reason='SL'; gap=True
    ratio=exit_price/entry; gross=sign*(ratio-1)
    commission=.002; borrow=.003/365 if sign==-1 else 0.
    return dict(side=side,entry_price=entry,exit_price=exit_price,target=target,stop=stop,
        entry_time=path.bar_timestamp.iloc[0],exit_bar_start=path.bar_timestamp.iloc[idx],
        exit_time=path.bar_timestamp.iloc[idx]+(pd.Timedelta(0) if reason=='TIME' or gap or idx==len(path)-1 else pd.Timedelta(minutes=5)),
        outcome=reason,collision=collision,gap_stop=gap,gross=gross,
        costs=.001*(1+ratio)+commission+borrow,net=gross-.001*(1+ratio)-commission-borrow,
        stress_net=gross-.0025*(1+ratio)-commission-borrow,
        commission=commission,borrow=borrow,exit_bar=idx)


def interval(frame, days, value):
    if frame.empty or frame.date.nunique()<20: return None
    g=frame.groupby('date')[value].agg(['sum','count']).reindex(days,fill_value=0)
    sums=g['sum'].to_numpy(); counts=g['count'].to_numpy(); n=len(g); block=min(20,n)
    rng=np.random.default_rng(20261020); vals=[]
    for _ in range(1999):
        starts=rng.integers(0,n-block+1,size=int(np.ceil(n/block)))
        ix=(starts[:,None]+np.arange(block)).ravel()[:n]
        if counts[ix].sum(): vals.append(sums[ix].sum()/counts[ix].sum())
    return [float(x) for x in np.quantile(vals,[.025,.975])] if vals else None


def statistics(trades, schedule):
    results=[]; comparisons=[]
    if trades.empty: return results,comparisons
    for scope in ['LIQUID100','ORACLE_TOP20PCT','ORACLE_TOP10']:
        subset=trades if scope=='LIQUID100' else trades[trades['top20pct' if scope=='ORACLE_TOP20PCT' else 'top10']]
        for (year,policy),f in subset.groupby(['year','policy']):
            days=pd.DatetimeIndex(schedule.loc[schedule.date.dt.year.eq(year),'date'])
            for side in ['ALL','LONG','SHORT']:
                g=f if side=='ALL' else f[f.trigger_side.eq(side)]
                results.append(dict(scope=scope,year=int(year),policy=policy,signal_side=side,n=len(g),
                    dates=g.date.nunique(),symbols=g.symbol.nunique(),
                    gross=float(g.gross.mean()) if len(g) else None,
                    net=float(g.net.mean()) if len(g) else None,
                    stress_net=float(g.stress_net.mean()) if len(g) else None,
                    win_rate=float(g.net.gt(0).mean()) if len(g) else None,
                    median=float(g.net.median()) if len(g) else None,
                    ci95=interval(g,days,'net'),stress_ci95=interval(g,days,'stress_net'),
                    outcomes={str(k):int(v) for k,v in g.outcome.value_counts().items()}))
        base=subset[subset.policy.eq('REVERSION')]
        for control in ['REVERSE','ALWAYS_LONG','ALWAYS_SHORT']:
            merged=base.merge(subset[subset.policy.eq(control)][['pair_id','net','stress_net']],
                on='pair_id',suffixes=('','_control'),validate='one_to_one')
            merged['delta']=merged.net-merged.net_control
            merged['stress_delta']=merged.stress_net-merged.stress_net_control
            for year,f in merged.groupby('year'):
                days=pd.DatetimeIndex(schedule.loc[schedule.date.dt.year.eq(year),'date'])
                for side in ['ALL','LONG','SHORT']:
                    g=f if side=='ALL' else f[f.trigger_side.eq(side)]
                    comparisons.append(dict(scope=scope,year=int(year),signal_side=side,control=control,n=len(g),
                        delta=float(g.delta.mean()) if len(g) else None,ci95=interval(g,days,'delta'),
                        stress_delta=float(g.stress_delta.mean()) if len(g) else None,
                        stress_ci95=interval(g,days,'stress_delta')))
    return results,comparisons


def replay(root):
    p=prepare(root)
    if (root/'report.json').exists(): raise ValueError('Immutable report already exists')
    snap=READ(root/'snapshot-ready.json'); verify_hashes(root,snap['files'])
    pool=pd.read_parquet(root/'pool.parquet'); schedule=pd.read_parquet(root/'sessions.parquet')
    sessions=schedule.set_index('date')
    # A few million selected rows, not the entire60M+ production table.
    raw=pd.concat([pd.read_parquet(root/n) for n in snap['files']],ignore_index=True)
    byday=dict(tuple(raw.groupby('trade_date',sort=False))); del raw
    coverage=[]; signals=[]; trades=[]; basket=[]; pair=0
    daily_groups=list(pool.groupby('date',sort=True))
    for num,(day,selected) in enumerate(daily_groups):
        op,cl=sessions.loc[day,['market_open','market_close']]
        times=pd.date_range(op,cl,freq='5min',inclusive='left')
        groups=dict(tuple(byday.pop(day,pd.DataFrame(columns=['symbol'])).groupby('symbol',sort=False)))
        frames={}; returns=[]
        for row in selected.itertuples():
            f=groups.get(row.symbol)
            g=bar_grid(f,op,cl) if f is not None else None
            frames[row.symbol]=g
            returns.append(g.session_return.to_numpy() if g is not None else np.full(len(times),np.nan))
        a=np.array(returns); count=np.isfinite(a).sum(axis=0); required=max(50,int(np.ceil(.8*len(selected))))
        bench=np.full(len(times),np.nan)
        for k in range(len(times)):
            if count[k]>=required: bench[k]=np.nanmedian(a[:,k])
        basket.append(dict(date=day,selected=len(selected),required=required,
            opening_valid=int(count[0]),last_valid=int(count[-1]),usable_bars=int(np.isfinite(bench).sum())))
        for row in selected.itertuples():
            g=frames[row.symbol]; base=dict(pair_id=pair,date=day,year=day.year,symbol=row.symbol,
                oracle_rank=row.oracle_rank,top10=row.top10,top20pct=row.top20pct,liquidity_rank=row.liquidity_rank)
            pair+=1
            status='MISSING_SESSION' if g is None else ('COMPLETE' if g.valid.all() else 'INCOMPLETE_SESSION')
            cov=dict(**base,status=status,triggered=False)
            coverage.append(cov)
            if g is None: continue
            found=trigger(g,bench,op,cl)
            if found is None: continue
            i,side,target,residual=found
            cov['triggered']=True
            signal=dict(**base,trigger_side=side,signal_time=times[i]+pd.Timedelta(minutes=5),
                residual=residual,signal_vwap=target,entry_time=times[i+1],status='QUALIFIED')
            signals.append(signal)
            path=g.iloc[i+1:].reset_index(drop=True)
            if not path.valid.all(): signal['status']='UNKNOWN_EXECUTION_PATH'; continue
            for symbol,reserve in p['price_reserves'].items():
                if row.symbol==symbol and day>=pd.Timestamp(reserve['start']): signal['status']='RESERVED_PRICE_BASIS'
            if signal['status']!='QUALIFIED': continue
            entry=float(path.open.iloc[0]); direction=1 if side=='LONG' else -1
            distance=direction*(target-entry)
            if distance<=0: signal['status']='ABSTAIN_ENTRY_PAST_TARGET'; continue
            if entry-distance<=0: signal['status']='INVALID_CONTROL_TARGET'; continue
            for policy,trade_side in [('REVERSION',side),('REVERSE','SHORT' if side=='LONG' else 'LONG'),
                ('ALWAYS_LONG','LONG'),('ALWAYS_SHORT','SHORT')]:
                goal=entry+(distance if trade_side=='LONG' else -distance)
                result=execute(path,trade_side,goal)
                trades.append(dict(**base,trigger_side=side,signal_time=signal['signal_time'],policy=policy,**result))
        if num%25==0:
            LOG.info('Replay %d/%d signals=%d qualified=%d',num+1,len(daily_groups),len(signals),len(trades)//4)
            atomic_json(root/'progress.json',dict(status='REPLAYING',completed=num+1,total=len(daily_groups),signals=len(signals)))
    cov=pd.DataFrame(coverage); sig=pd.DataFrame(signals); out=pd.DataFrame(trades); b=pd.DataFrame(basket)
    for name,f in [('coverage',cov),('signals',sig),('trades',out),('basket',b)]:
        f.to_parquet(root/f'{name}.parquet',index=False)
    results,comparisons=statistics(out,schedule[schedule.date.between(p['start'],p['end'])])
    pd.DataFrame(results).to_csv(root/'summary.csv',index=False)
    pd.DataFrame(comparisons).to_csv(root/'comparisons.csv',index=False)
    monthly=[]
    if len(out):
        for (year,month,side),f in out[out.policy.eq('REVERSION')].groupby([out.year,out.date.dt.month,out.trigger_side]):
            monthly.append(dict(year=int(year),month=int(month),side=side,n=len(f),net=float(f.net.mean()),stress_net=float(f.stress_net.mean())))
    pd.DataFrame(monthly).to_csv(root/'monthly.csv',index=False)
    annual_coverage=[]
    for y,f in cov.groupby('year'):
        fs=sig[sig.year.eq(y)] if len(sig) else sig
        annual_coverage.append(dict(year=int(y),expected=len(f),complete=int(f.status.eq('COMPLETE').sum()),
            triggered=int(f.triggered.sum()),signals={str(k):int(v) for k,v in fs.status.value_counts().items()} if len(fs) else {}))
    report=dict(status='EXPLORATORY_PARTIAL_COVERAGE' if len(out) else 'BLOCKED_NO_QUALIFIED_TRADES',
        created_at_utc=datetime.now(timezone.utc).isoformat(),coverage=annual_coverage,rows=snap['rows'],
        opportunities=len(cov),signals=len(sig),qualified_signals=len(out)//4,results=results,comparisons=comparisons,
        monthly=monthly,verdict='NO_PROMOTION_PENDING_AUDIT',
        files={n:digest(root/n) for n in ['coverage.parquet','signals.parquet','trades.parquet','basket.parquet','summary.csv','comparisons.csv','monthly.csv']})
    atomic_json(root/'report.json',report)
    atomic_json(root/'progress.json',dict(status='COMPLETED',signals=len(sig),qualified_signals=len(out)//4))
    LOG.info('Completed signals=%d qualified=%d',len(sig),len(out)//4)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['prepare','snapshot','replay'],required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    {'prepare':prepare,'snapshot':snapshot,'replay':replay}[args.phase](args.output)


if __name__=='__main__': main()
