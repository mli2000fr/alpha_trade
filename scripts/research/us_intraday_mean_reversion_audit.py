"""Offline cross-check by another implementation, not independent human review."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes
from scripts.research.us_intraday_mean_reversion import READ


def vector_exit(path,side,target):
    sign=1 if side=='LONG' else -1
    a=path[['open','high','low','close']].to_numpy(float)
    stop=a[0,0]*(1-sign*.01)
    gs=sign*(a[:-1,0]-stop)<=abs(stop)*1e-12
    gt=sign*(a[:-1,0]-target)>=-abs(target)*1e-12
    hs=a[:-1,2]<=stop+abs(stop)*1e-12 if sign==1 else a[:-1,1]>=stop-abs(stop)*1e-12
    ht=a[:-1,1]>=target-abs(target)*1e-12 if sign==1 else a[:-1,2]<=target+abs(target)*1e-12
    hits=np.flatnonzero(gs|gt|hs|ht)
    if not len(hits):
        gap=bool(sign*(a[-1,0]-stop)<=0)
        return len(a)-1,float(a[-1,0]),'SL' if gap else 'TIME',gap,False
    i=int(hits[0])
    if gs[i]: return i,float(a[i,0]),'SL',True,False
    if gt[i]: return i,target,'TP',False,False
    if hs[i]: return i,stop,'SL',False,bool(ht[i])
    return i,target,'TP',False,False


def audit(root):
    p=READ(root/'protocol.json'); report=READ(root/'report.json')
    verify_hashes(Path('.'),p['sources']); verify_hashes(root,report['files'])
    verify_hashes(root,READ(root/'prepared.json')['files'])
    snap=READ(root/'snapshot-ready.json'); verify_hashes(root,snap['files'])
    pool=pd.read_parquet(root/'pool.parquet'); cov=pd.read_parquet(root/'coverage.parquet')
    sig=pd.read_parquet(root/'signals.parquet'); trades=pd.read_parquet(root/'trades.parquet')
    sched=pd.read_parquet(root/'sessions.parquet').set_index('date')
    assert len(pool)==len(cov) and not cov.duplicated(['date','symbol']).any()
    assert pool.groupby('date').size().le(100).all()
    assert pool.signal_date.lt(pool.date).all()
    assert pool.top10.eq(pool.oracle_rank.le(10)).all()
    assert pool.top20pct.eq(pool.oracle_rank.le(np.ceil(.2*pool.scored_count))).all()
    assert len(trades)==4*int(sig.status.eq('QUALIFIED').sum()) if len(sig) else len(trades)==0
    assert len(cov[cov.triggered])==len(sig)
    raw=pd.concat([pd.read_parquet(root/n) for n in snap['files']],ignore_index=True)
    groups=dict(tuple(raw.groupby(['symbol','trade_date'],sort=False))); del raw
    checked=0; signal_checked=0
    if len(sig):
        for s in sig.itertuples():
            f=groups[s.symbol,s.date].sort_values('bar_timestamp')
            op,cl=sched.loc[s.date,['market_open','market_close']]
            prefix=f[f.bar_end_timestamp.le(s.signal_time)]
            expected=pd.date_range(op,s.signal_time,freq='5min',inclusive='left')
            assert pd.DatetimeIndex(prefix.bar_timestamp).equals(expected)
            assert s.signal_time>=op+pd.Timedelta(minutes=30) and s.signal_time<=cl-pd.Timedelta(minutes=60)
            assert s.entry_time==s.signal_time
            proxy=np.sum((prefix.high+prefix.low+prefix.close)/3*prefix.volume)/prefix.volume.sum()
            assert np.isclose(proxy,s.signal_vwap,atol=1e-10,rtol=0)
            if s.trigger_side=='LONG':
                assert s.residual<=-.02 and prefix.close.iloc[-1]>prefix.close.iloc[-2]
                assert prefix.low.iloc[-1]>=prefix.low.iloc[-2] and proxy>prefix.close.iloc[-1]
            else:
                assert s.residual>=.02 and prefix.close.iloc[-1]<prefix.close.iloc[-2]
                assert prefix.high.iloc[-1]<=prefix.high.iloc[-2] and proxy<prefix.close.iloc[-1]
            signal_checked+=1
    if len(trades):
        assert not trades.duplicated(['pair_id','policy']).any()
        assert trades.groupby('pair_id').size().eq(4).all()
        for r in trades.itertuples():
            f=groups[r.symbol,r.date].sort_values('bar_timestamp')
            op,cl=sched.loc[r.date,['market_open','market_close']]
            path=f[f.bar_timestamp.ge(r.entry_time)].reset_index(drop=True)
            assert pd.DatetimeIndex(path.bar_timestamp).equals(pd.date_range(r.entry_time,cl,freq='5min',inclusive='left'))
            assert r.entry_time>=op and r.exit_time<=cl-pd.Timedelta(minutes=5)
            idx,price,outcome,gap,collision=vector_exit(path,r.side,r.target)
            assert r.exit_bar==idx and r.outcome==outcome and r.gap_stop==gap and r.collision==collision
            assert np.isclose(r.exit_price,price,atol=1e-10,rtol=0)
            ratio=price/path.open.iloc[0]; sign=1 if r.side=='LONG' else -1
            borrow=.003/365 if sign==-1 else 0.
            expected=sign*(ratio-1)-.001*(1+ratio)-.002-borrow
            assert np.isclose(expected,r.net,atol=1e-12,rtol=0)
            assert r.stress_net<=r.net
            checked+=1
        for _,f in trades.groupby('pair_id'):
            assert f.entry_time.nunique()==1 and f.signal_time.nunique()==1
            base=f.set_index('policy')
            assert base.loc['REVERSION','side']!=base.loc['REVERSE','side']
            assert np.allclose(abs(f.target-f.entry_price),abs(base.loc['REVERSION','target']-base.loc['REVERSION','entry_price']))
    gate=[]
    for y in [2025,2026]:
        rows=[r for r in report['results'] if r['scope']=='LIQUID100' and r['year']==y
              and r['policy']=='REVERSION' and r['signal_side']=='LONG']
        if not rows: gate.append(dict(year=y,passed=False,reason='NO_QUALIFIED_PRIMARY_TRADES')); continue
        r=rows[0]
        reasons=[]
        if r['n']<100 or r['dates']<50: reasons.append('INSUFFICIENT_INDEPENDENT_DATES_OR_TRADES')
        if r['stress_ci95'] is None or r['stress_ci95'][0]<=0: reasons.append('STRESS_NET_NOT_POSITIVE_CONFIDENTLY')
        # ALWAYS_LONG equals long reversion on the long subset by definition.
        # Its paired delta is identically zero: it cannot establish incremental
        # direction skill on this subset. It is reported, not a valid primary gate.
        paired=[v for v in report['comparisons'] if v['scope']=='LIQUID100' and v['year']==y
                and v['signal_side']=='LONG' and v['control']=='REVERSE']
        if not paired or paired[0]['stress_ci95'] is None or paired[0]['stress_ci95'][0]<=0:
            reasons.append('NO_CONFIDENT_ADVANTAGE_OVER_MATCHED_SHORT')
        gate.append(dict(year=y,passed=not reasons,reasons=reasons,n=r['n'],dates=r['dates']))
    result=dict(status='PASS_EXPLORATORY_DATA_AND_EXECUTION_CHECKS',checked_trades=checked,
        checked_signals=signal_checked,source_snapshot_rows=snap['rows'],primary_gate=gate,
        verdict='EXPLORATORY_SIGNAL_ONLY_NO_PROMOTION' if all(x['passed'] for x in gate) else 'NO_GO_CURRENT_FROZEN_RULE',
        report_sha256=digest(root/'report.json'),
        reserves=['Same assistant, no independent human review',
            'LONG subset ALWAYS_LONG is identical and cannot prove incremental direction skill',
            'Neither NBBO nor historical short locates nor fully as-of liquidity certified'])
    atomic_json(root/'final-audit.json',result)
    print(result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    audit(parser.parse_args().output)
