"""Offline independent vector barrier cross-check and paired frozen controls."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_top10_intraday_breakout import READ


def vector_exit(path, side):
    a = path[['open','high','low','close']].to_numpy(dtype=float)
    sign = 1 if side=='LONG' else -1
    entry = a[0,0]; stop = entry*(1-sign*.05); take = entry*(1+sign*.10)
    st = abs(stop)*1e-12; tt = abs(take)*1e-12
    gs = sign*(a[:,0]-stop)<=st
    gt = sign*(a[:,0]-take)>=-tt
    hs = a[:,2]<=stop+st if sign==1 else a[:,1]>=stop-st
    ht = a[:,1]>=take-tt if sign==1 else a[:,2]<=take+tt
    hits = np.flatnonzero(gs|gt|hs|ht)
    if not len(hits):
        return len(a)-1, a[-1,3], 'TIMEOUT', False, False
    i = int(hits[0])
    if gs[i]: return i, a[i,0], 'SL', True, False
    if gt[i]: return i, take, 'TP', False, False
    if hs[i]: return i, stop, 'SL', False, bool(ht[i])
    return i, take, 'TP', False, False


def interval(frame, days):
    blocks = days.get_indexer(pd.to_datetime(frame.date))//20
    totals = pd.DataFrame(dict(block=blocks, delta=frame.delta.to_numpy(), n=1)).groupby('block')[['delta','n']].sum()
    ci = [None,None]
    if len(totals)>=5:
        rng=np.random.default_rng(20261019)
        values=totals.to_numpy()[rng.integers(0,len(totals),size=(2000,len(totals)))].sum(axis=1)
        ci=[float(x) for x in np.quantile(values[:,0]/values[:,1],[.025,.975])]
    return dict(n=len(frame), mean_delta=float(frame.delta.mean()), ci95=ci, blocks=len(totals))


def audit(root):
    p=READ(root/'protocol.json'); report=READ(root/'report.json')
    verify_hashes(Path('.'),p['sources'])
    verify_hashes(root,report['files'])
    verify_hashes(root,READ(root/'prepared.json')['files'])
    snap=READ(root/'snapshot-ready.json'); verify_hashes(root,snap['files'])
    selected=pd.read_parquet(root/'selected-at-j.parquet').reset_index(drop=True)
    cov=pd.read_parquet(root/'coverage.parquet')
    trades=pd.read_parquet(root/'trades.parquet')
    schedule=pd.read_parquet(root/'sessions.parquet').set_index('date'); days=pd.DatetimeIndex(schedule.index)
    assert len(selected)==len(cov)==6690
    assert len(trades)==2*report['qualified_pairs']+4*report['triggered_pairs']
    assert not trades.duplicated(['pair_id','policy']).any()
    data=pd.concat([f for name in snap['files'] if len(f:=pd.read_parquet(root/name))],ignore_index=True)
    data=data.sort_values(['symbol','bar_timestamp'])
    byday=dict(tuple(data.groupby(['symbol','trade_date'],sort=False)))
    covered=cov[cov.status.eq('OK')]
    paths={}; triggers={}; checks=0
    for r in covered.itertuples():
        source=selected.iloc[r.pair_id]
        assert source.symbol==r.symbol and source.date==r.date and source['rank']==r.rank
        i=days.get_indexer([r.date])[0]; window=days[i:i+11]
        for d in window:
            f=byday[r.symbol,d]
            op,cl=schedule.loc[d,['market_open','market_close']]
            expected=pd.date_range(op,cl,freq='5min',inclusive='left')
            assert pd.DatetimeIndex(f.bar_timestamp).equals(expected)
            assert pd.DatetimeIndex(f.bar_end_timestamp).equals(expected+pd.Timedelta(minutes=5))
        prev=byday[r.symbol,window[0]]; first=byday[r.symbol,window[1]]
        signs=np.where(first.close.to_numpy()>prev.high.max(),1,np.where(first.close.to_numpy()<prev.low.min(),-1,0))
        hit=np.flatnonzero(signs[:-1]); triggers[r.pair_id]=(int(hit[0])+1,'LONG' if signs[hit[0]]==1 else 'SHORT') if len(hit) else None
        assert bool(len(hit))==r.triggered
        paths[r.pair_id]=pd.concat([byday[r.symbol,d] for d in window[1:]],ignore_index=True)
    for r in trades.itertuples():
        path=paths[r.pair_id]
        if not r.policy.startswith('OPEN_'):
            start,side=triggers[r.pair_id]
            assert r.signal_time==path.bar_end_timestamp.iloc[start-1]
            assert r.signal_time<=r.entry_time
            assert r.entry_time==path.bar_timestamp.iloc[start]
            if r.policy=='BREAKOUT': assert r.side==side
            if r.policy=='MATCHED_REVERSE': assert r.side!=side
            path=path.iloc[start:].reset_index(drop=True)
        else:
            assert r.entry_time==path.bar_timestamp.iloc[0]
        idx,price,outcome,gap,collision=vector_exit(path,r.side)
        assert idx==r.exit_bar and outcome==r.outcome and gap==r.gap_stop and collision==r.collision
        assert np.isclose(price,r.exit_price,rtol=0,atol=1e-10)
        entry=float(path.open.iloc[0]); sign=1 if r.side=='LONG' else -1
        borrow=.003*max(1,(r.exit_time.date()-r.entry_time.date()).days)/365 if sign==-1 else 0.
        net=sign*(price/entry-1)-.0008*(1+price/entry)-borrow
        assert np.isclose(r.net,net,rtol=0,atol=1e-12)
        assert r.entry_time<=r.exit_time<=path.bar_end_timestamp.iloc[-1]
        checks+=1
    # Same no-overlap membership for all matched controls, blocked by full horizon.
    for policies in [['BREAKOUT','MATCHED_REVERSE','MATCHED_LONG','MATCHED_SHORT'],['OPEN_LONG','OPEN_SHORT']]:
        ids=None
        for policy in policies:
            f=trades[trades.policy.eq(policy)&trades.independent]
            current=set(f.pair_id)
            assert ids is None or ids==current
            ids=current
            for _,g in f.sort_values('entry_date').groupby('symbol'):
                assert all(g.entry_date.iloc[k]>g.last_path_date.iloc[k-1] for k in range(1,len(g)))
    base=trades[trades.policy.eq('BREAKOUT')]
    comparisons=[]
    for policy in ['MATCHED_REVERSE','MATCHED_LONG','MATCHED_SHORT','OPEN_LONG','OPEN_SHORT']:
        control=trades[trades.policy.eq(policy)][['pair_id','net']].rename(columns={'net':'control_net'})
        merged=base.merge(control,on='pair_id',validate='one_to_one')
        merged['delta']=merged.net-merged.control_net
        assert len(merged)==len(base)
        for year,f in merged.groupby('year'):
            for cohort,g in [('ALL',f),('NON_OVERLAP',f[f.independent])]:
                comparisons.append(dict(year=int(year),control=policy,cohort=cohort,**interval(g,days)))
    pd.DataFrame(comparisons).to_csv(root/'paired-control-comparisons.csv',index=False)
    annual=[]
    for (year,month),f in base.groupby([base.year,base.date.dt.month]):
        annual.append(dict(year=int(year),month=int(month),n=len(f),mean_net=float(f.net.mean()),
            long_n=int(f.side.eq('LONG').sum()),short_n=int(f.side.eq('SHORT').sum())))
    pd.DataFrame(annual).to_csv(root/'monthly-breakout.csv',index=False)
    result=dict(status='PASS_EXPLORATORY_PARTIAL_COVERAGE',checked_trades=checks,
        checked_windows=len(covered),report_sha256=digest(root/'report.json'),
        comparisons=comparisons, files={f:digest(root/f) for f in ['paired-control-comparisons.csv','monthly-breakout.csv']},
        note='Independent implementation cross-check by same assistant, not independent human review. Partial data, research-only, no promotion.')
    atomic_json(root/'final-audit.json',result)
    print({k:v for k,v in result.items() if k not in ['comparisons','files']})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    audit(parser.parse_args().output)
