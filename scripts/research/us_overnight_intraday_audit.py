"""Second scalar checks on frozen decomposition and outcome files; no external I/O."""
import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_overnight_intraday_pilot import PRICE, READ
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes


def audit(root):
    if (root/'audit.json').exists(): raise ValueError('Immutable audit')
    p=READ(root/'protocol.json'); report=READ(root/'report.json')
    verify_hashes(Path('.'),p['sources']); verify_hashes(root,report['files'])
    f=pd.read_parquet(root/'candidates.parquet'); out=pd.read_parquet(root/'outcomes.parquet')
    days=pd.DatetimeIndex(pd.read_parquet(root/'sessions.parquet').date)
    if f.duplicated(['date','symbol']).any(): raise ValueError('Duplicate members')
    if not f[f.top10].groupby('date').size().eq(10).all(): raise ValueError('TOP10 replaced/lost')
    # Admission checked without reading outcome values, including unknown rows.
    count=0
    for scope,flag in [('TOP10','top10'),('TOP20PCT','top20')]:
        for _,g in f[f[flag]].groupby('symbol'):
            next_pos=-1
            for r in g.sort_values('pos').to_dict('records'):
                expected=r['pos']>=next_pos
                if bool(r['independent_'+scope])!=expected: raise ValueError('Nonoverlap uses future data')
                if expected: next_pos=r['pos']+20
                count+=1
    # Deterministic250 history-qualified member sample, before scalar future check.
    sample=f[f.history_good].sort_values(['date','symbol']).iloc[::max(1,int(f.history_good.sum())//250)].head(250)
    prices=pd.read_parquet(PRICE,filters=[('symbol','in',sample.symbol.unique().tolist())])
    groups={s:g.set_index('date').reindex(days) for s,g in prices.groupby('symbol')}
    checked=0; outcomes_checked=0; max_error=0.
    for r in sample.to_dict('records'):
        g=groups[r['symbol']]; j=r['pos']; w=g.iloc[j-20:j+1]
        ratio=w.adj_close.to_numpy(float)/w.close.to_numpy(float)
        closes=w.close.to_numpy(float)*ratio; opens=w.open.to_numpy(float)*ratio
        intra=sum(math.log(float(closes[k]/opens[k])) for k in range(1,21))
        night=sum(math.log(float(opens[k]/closes[k-1])) for k in range(1,21))
        for actual,expected in [(r['intraday20'],intra),(r['overnight20'],night),(r['close20'],math.log(closes[-1]/closes[0]))]:
            err=abs(actual-expected); max_error=max(max_error,err)
            if err>1e-10: raise ValueError('Scalar decomposition mismatch')
        checked+=1
        for h in [5,10,20]:
            stored=r[f'return_h{h}']
            if pd.isna(stored): continue
            a=g.iloc[j+1]; b=g.iloc[j+h]
            entry=float(a.open)*float(a.adj_close)/float(a.close)
            exit=float(b.close)*float(b.adj_close)/float(b.close)
            expected=exit/entry-1
            if abs(stored-expected)>1e-10: raise ValueError('Scalar endpoint mismatch')
            outcomes_checked+=1
    # All rows cost/sign/endpoint-scope checks, no averaging of summaries.
    keys=['scope','admission','horizon','policy','date','symbol']
    if out.duplicated(keys).any(): raise ValueError('Duplicate trade occasion')
    entry=days.take(out.pos.to_numpy(int)+1); exit=days.take(out.pos.to_numpy(int)+out.horizon.to_numpy(int))
    borrow=np.where(out.side.to_numpy()<0,.003*(exit-entry).days.to_numpy()/365,0.)
    gross=out.side.to_numpy()*out['return'].to_numpy()
    expected=gross-.001*(2+out['return'].to_numpy())-borrow
    errors=np.abs(out.net.to_numpy()-expected)
    if errors.max(initial=0)>1e-10: raise ValueError('All-row cost arithmetic')
    long=out['return'].to_numpy()-.001*(2+out['return'].to_numpy())
    if not np.allclose(out.incremental_vs_long,out.net-long,atol=1e-12,rtol=0): raise ValueError('Paired baseline changed')
    if not out[out.policy=='ALWAYS_LONG'].side.eq(1).all(): raise ValueError('Always-long reference changed')
    annual=pd.read_csv(root/'annual-summary.csv')
    cols=['scope','admission','horizon','policy','year']
    for k,g in out.groupby(cols):
        a=annual
        for name,v in zip(cols,k): a=a[a[name]==v]
        if len(a)!=1 or int(a.iloc[0]['n'])!=len(g) or abs(a.iloc[0].mean_net-g.net.mean())>1e-10:
            raise ValueError('Summary reproduction')
    result=dict(status='PASS_OFFLINE_EXPLORATORY_ONLY',selection_admissions_checked=count,
        scalar_histories_checked=checked,scalar_endpoints_checked=outcomes_checked,max_scalar_error=max_error,
        all_outcome_rows_checked=len(out),max_cost_error=float(errors.max(initial=0)),
        report_sha256=digest(root/'report.json'),same_assistant_not_human_independent_review=True,
        no_training_sql_provider_order=True)
    atomic_json(root/'audit.json',result);print(result,flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    audit(a.parse_args().output)
