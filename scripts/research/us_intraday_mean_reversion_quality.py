"""Sealed offline causal-signal and daily-price cross-check, no provider/SQL.

The price comparison is an outcome-quality reserve, never a historical feature.
It cannot repair prices or create historical availability/quote/fill evidence.
"""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import logging

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes
from scripts.research.us_intraday_mean_reversion import READ,statistics,PRICE

LOG=logging.getLogger(__name__)


def price_check(raw,daily,tolerance=.01):
    """One constant scale allowed across same-day OHLC, no inferred split repair."""
    a=np.asarray(raw,float); b=np.asarray(daily,float)
    if a.shape!=(4,) or b.shape!=(4,) or not np.isfinite([a,b]).all() or (a<=0).any() or (b<=0).any():
        return 'MISSING_OR_INVALID_REFERENCE',None
    ratio=a/b; spread=float(ratio.max()/ratio.min()-1)
    return ('OK' if spread<=tolerance else 'DAILY_OHLC_DISAGREEMENT'),spread


def causal_arrays(rows,times):
    """Independent dense implementation. Uses only valid completed prefixes."""
    if rows.bar_timestamp.duplicated().any(): return None
    g=rows.set_index('bar_timestamp').reindex(times)
    a=g[['open','high','low','close','volume']].to_numpy(float)
    ok=np.isfinite(a).all(axis=1)&(a>0).all(axis=1)
    ok&=(a[:,1]>=np.max(a[:,:4],axis=1))&(a[:,2]<=np.min(a[:,:4],axis=1))
    for name,value in [('provider','alpaca'),('data_source','alpaca_sip'),('interval_code','5m'),
        ('market_code','US_EQ'),('session_tag','regular'),('data_adjustment','raw'),('is_filled',0)]:
        ok&=g[name].eq(value).to_numpy()
    ok&=pd.DatetimeIndex(g.bar_end_timestamp).asi8==(times+pd.Timedelta(minutes=5)).asi8
    prefix=np.cumprod(ok).astype(bool)
    ret=np.full(len(a),np.nan); vw=np.full(len(a),np.nan)
    if prefix.any():
        n=int(prefix.sum()); ret[:n]=a[:n,3]/a[0,0]-1
        vw[:n]=np.cumsum(a[:n,:4][:,[1,2,3]].mean(axis=1)*a[:n,4])/np.cumsum(a[:n,4])
    return a,ok,prefix,ret,vw


def first_signal(a,ok,ret,vw,benchmark,times,op,cl):
    prev_close=np.r_[np.nan,a[:-1,3]]; prev_low=np.r_[np.nan,a[:-1,2]]; prev_high=np.r_[np.nan,a[:-1,1]]
    excess=ret-benchmark
    eligible=(times+pd.Timedelta(minutes=5)>=op+pd.Timedelta(minutes=30))&(
        times+pd.Timedelta(minutes=5)<=cl-pd.Timedelta(minutes=60))&ok
    long=eligible&(excess<=-.02)&(a[:,3]>prev_close)&(a[:,2]>=prev_low)&(vw>a[:,3])
    short=eligible&(excess>=.02)&(a[:,3]<prev_close)&(a[:,1]<=prev_high)&(vw<a[:,3])
    ix=np.flatnonzero(long|short)
    if not len(ix): return None
    i=int(ix[0]); return i,'LONG' if long[i] else 'SHORT',float(excess[i]),float(vw[i])


def cap_forced_open_target(trades):
    """Conservative TP cap also applies to a favorable gap at forced final open.

    Original replay remains sealed; this explicitly documented implementation
    correction never improves a return or reads the final bar's later prices.
    """
    f=trades.copy()
    sign=np.where(f.side.eq('LONG'),1.,-1.)
    hit=f.outcome.eq('TIME')&(sign*(f.exit_price-f.target)>=0)
    f['final_open_target_corrected']=hit
    f.loc[hit,'exit_price']=f.loc[hit,'target']
    f.loc[hit,'outcome']='TP'
    ratio=f.exit_price/f.entry_price
    f['gross']=sign*(ratio-1)
    f['costs']=.001*(1+ratio)+f.commission+f.borrow
    f['net']=f.gross-f.costs
    f['stress_net']=f.gross-.0025*(1+ratio)-f.commission-f.borrow
    return f


def run(root,output):
    output.mkdir(exist_ok=False)
    base=READ(root/'protocol.json'); report=READ(root/'report.json')
    verify_hashes(Path('.'),base['sources']); verify_hashes(root,report['files'])
    snap=READ(root/'snapshot-ready.json'); verify_hashes(root,snap['files'])
    verify_hashes(root,READ(root/'prepared.json')['files'])
    files=[Path(__file__),Path('tests/test_us_intraday_mean_reversion_quality.py'),
        Path('scripts/research/us_intraday_mean_reversion.py'),PRICE,
        root/'protocol.json',root/'report.json',root/'snapshot-ready.json',root/'prepared.json']
    atomic_json(output/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources={str(f):digest(f) for f in files},
        rule='Reconstruct every selected prefix, basket median and earliest trigger independently; do not condition earlier basket on future coverage.',
        price_guard='Same-session raw SIP aggregate OHLC divided by daily reference; one constant scale across four fields; ratio-spread<=1%. Fixed data-quality tolerance inherited from earlier intraday research, not selected on returns.',
        effect='Outcomes with unqualified price reference UNKNOWN; original results retained. No price fixes, no rule or parameter retuning.',
        execution_correction='Also cap a favorable target gap at forced last-bar open, to obey the same conservative TP contract as earlier opens. Original replay used uncapped TIME open there. Correct only downward, no strategy retuning.',
        source_supplement='Added before reading trade-result summary; original sealed protocol retained',
        sql=False,downloads=False,fit=False,orders=False))
    pool=pd.read_parquet(root/'pool.parquet'); schedule=pd.read_parquet(root/'sessions.parquet')
    sessions=schedule.set_index('date'); signals=pd.read_parquet(root/'signals.parquet')
    cov=pd.read_parquet(root/'coverage.parquet').set_index(['date','symbol'])
    signal_map=signals.set_index(['date','symbol']) if len(signals) else None
    prices=pd.read_parquet(PRICE).set_index(['symbol','date'])
    raw=pd.concat([f for n in snap['files'] if len(f:=pd.read_parquet(root/n))],ignore_index=True)
    days=dict(tuple(raw.groupby('trade_date',sort=False))); del raw
    basket=pd.read_parquet(root/'basket.parquet').set_index('date')
    checks=[]; checked=0; triggered=0
    for num,(day,selected) in enumerate(pool.groupby('date',sort=True)):
        op,cl=sessions.loc[day,['market_open','market_close']]
        times=pd.date_range(op,cl,freq='5min',inclusive='left')
        source=days.pop(day,pd.DataFrame(columns=['symbol']))
        groups=dict(tuple(source.groupby('symbol',sort=False)))
        arrays={s:causal_arrays(f,times) for s,f in groups.items()}
        matrix=np.array([arrays[s][3] if s in arrays and arrays[s] is not None else np.full(len(times),np.nan)
            for s in selected.symbol])
        count=np.isfinite(matrix).sum(axis=0); need=max(50,int(np.ceil(.8*len(selected))))
        benchmark=np.array([np.median(matrix[np.isfinite(matrix[:,i]),i]) if count[i]>=need else np.nan
            for i in range(len(times))])
        assert int(np.isfinite(benchmark).sum())==basket.loc[day,'usable_bars']
        assert count[0]==basket.loc[day,'opening_valid'] and count[-1]==basket.loc[day,'last_valid']
        for r in selected.itertuples():
            checked+=1; data=arrays.get(r.symbol)
            hit=None if data is None else first_signal(data[0],data[2],data[3],data[4],benchmark,times,op,cl)
            assert bool(hit is not None)==bool(cov.loc[(day,r.symbol),'triggered'])
            if hit is None: continue
            triggered+=1; i,side,excess,vwap=hit; s=signal_map.loc[(day,r.symbol)]
            assert s.trigger_side==side and s.signal_time==times[i]+pd.Timedelta(minutes=5)
            assert np.isclose(s.residual,excess,atol=1e-12,rtol=0)
            assert np.isclose(s.signal_vwap,vwap,atol=1e-10,rtol=0)
            quality='NOT_ORIGINALLY_QUALIFIED'; spread=None
            if s.status=='QUALIFIED':
                a=data[0]
                aggregate=[a[0,0],a[:,1].max(),a[:,2].min(),a[-1,3]]
                reference=prices.loc[(r.symbol,day),['open','high','low','close']].to_numpy(float) if (r.symbol,day) in prices.index else [np.nan]*4
                quality,spread=price_check(aggregate,reference)
            checks.append(dict(pair_id=int(s.pair_id),date=day,symbol=r.symbol,year=day.year,
                original_status=s.status,price_quality=quality,ratio_spread=spread))
        if num%50==0: LOG.info('Causal check %d/669 candidates=%d triggers=%d',num+1,checked,triggered)
    assert checked==len(pool) and triggered==len(signals)
    quality=pd.DataFrame(checks)
    quality.to_parquet(output/'signal-price-quality.parquet',index=False)
    out=pd.read_parquet(root/'trades.parquet')
    out=cap_forced_open_target(out)
    good=set(quality.loc[quality.price_quality.eq('OK'),'pair_id'])
    qualified=out[out.pair_id.isin(good)].copy()
    qualified.to_parquet(output/'qualified-trades.parquet',index=False)
    results,comparisons=statistics(qualified,schedule[schedule.date.between(base['start'],base['end'])])
    pd.DataFrame(results).to_csv(output/'summary.csv',index=False)
    pd.DataFrame(comparisons).to_csv(output/'comparisons.csv',index=False)
    coverage=[]
    for y,f in quality.groupby('year'):
        coverage.append(dict(year=int(y),triggered=len(f),originally_qualified=int(f.original_status.eq('QUALIFIED').sum()),
            price_qualified=int(f.price_quality.eq('OK').sum()),
            price_reserves={str(k):int(v) for k,v in f.loc[f.original_status.eq('QUALIFIED'),'price_quality'].value_counts().items()}))
    gates=[]
    for y in [2025,2026]:
        rows=[r for r in results if r['scope']=='LIQUID100' and r['year']==y and r['policy']=='REVERSION' and r['signal_side']=='LONG']
        failures=[]
        if not rows: failures=['NO_QUALIFIED_PRIMARY_TRADES']
        else:
            r=rows[0]
            if r['n']<100 or r['dates']<50: failures.append('INSUFFICIENT_TRADES_OR_DATES')
            if r['stress_ci95'] is None or r['stress_ci95'][0]<=0: failures.append('STRESS_NET_NOT_CONFIDENTLY_POSITIVE')
            c=[x for x in comparisons if x['scope']=='LIQUID100' and x['year']==y and x['signal_side']=='LONG' and x['control']=='REVERSE']
            if not c or c[0]['stress_ci95'] is None or c[0]['stress_ci95'][0]<=0: failures.append('NO_CONFIDENT_ADVANTAGE_OVER_MATCHED_SHORT')
        gates.append(dict(year=y,passed=not failures,reasons=failures))
    final=dict(status='PASS_OFFLINE_CAUSAL_AND_PRICE_QUALITY_CHECKS',checked_candidates=checked,checked_triggers=triggered,
        final_open_corrections=int(out.final_open_target_corrected.sum()),
        qualified_signals=len(good),coverage=coverage,results=results,comparisons=comparisons,gate=gates,
        verdict='EXPLORATORY_SIGNAL_ONLY_NO_PROMOTION' if all(g['passed'] for g in gates) else 'NO_GO_CURRENT_FROZEN_RULE',
        files={n:digest(output/n) for n in ['signal-price-quality.parquet','qualified-trades.parquet','summary.csv','comparisons.csv']},
        note='Same-assistant cross-check, not independent human review. Unknown outcomes excluded only after recording the original signal; no historical PIT or executable portfolio claim.')
    atomic_json(output/'report.json',final)
    print({k:v for k,v in final.items() if k not in ['results','comparisons','files']})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    run(args.root,args.output)
