"""Independent block-statistic recomputation; reads existing sealed results only."""
from pathlib import Path
import math
import numpy as np
import pandas as pd
from scipy.stats import rankdata
from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.us_oracle_path_trend_ranking_20261022 import read, digest, verify, save

ROOT=Path('artifacts/research/us_oracle_path_trend_ranking/20261022-v2')


def run():
    p,r=read(ROOT/'protocol.json'),read(ROOT/'report.json')
    verify(p['sources']);verify({str(ROOT/k):v for k,v in r['files'].items()})
    a=pd.read_parquet(ROOT/'dataset.parquet')
    a=a[a.complete_date & a.period.eq('DISCOVERY')]
    rules=p['rules']; names=p['primary_family']
    calendar=nyse_sessions('2018-07-05','2021-12-31')
    positions={day:i for i,day in enumerate(calendar)}
    daily=[]
    for day,g in a.groupby('date',sort=True):
        y=rankdata(g.long_area_pct);y=y-y.mean()
        row=[]
        for name in names:
            x=rankdata(g[name]);x=x-x.mean()
            den=math.sqrt(float(x@x)*float(y@y))
            row.append(float(x@y)/den if den else np.nan)
        daily.append((positions[day]//rules['block'],row))
    frame=pd.DataFrame([x[1] for x in daily],columns=names)
    block=np.array([x[0] for x in daily])
    matrix=[]
    for k in sorted(set(block)):
        part=frame[block==k]
        matrix.append([part[c].mean() if part[c].count()>=rules['min_block_dates'] else np.nan for c in names])
    matrix=np.array(matrix);n=np.isfinite(matrix).sum(axis=0)
    def t(x):
        vals=[]
        for i in range(len(names)):
            v=x[:,i];v=v[np.isfinite(v)]
            vals.append(abs(v.mean())/(max(v.std(ddof=1),1e-12)/math.sqrt(len(v))))
        return np.array(vals)
    obs=t(matrix);eligible=n>=rules['min_blocks'];rng=np.random.default_rng(rules['seed'])
    maxima=[]
    for _ in range(rules['replications']):
        signs=rng.choice([-1.,1.],size=len(matrix))
        maxima.append(max(t(matrix*signs[:,None])[eligible]))
    records={x['feature']:x for x in r['features']}
    for i,name in enumerate(names):
        value=(1+sum(v>=obs[i] for v in maxima))/(1+len(maxima))
        if n[i]!=records[name]['blocks'] or not math.isclose(value,records[name]['p_maxT'],abs_tol=1e-12):
            raise AssertionError('maxT mismatch '+name)
    # Recompute path-area CIs for every period and both sizes of the discovery-best probe.
    best=records[r['best_discovery_diagnostic_only']];ci_checks=0
    frame=pd.read_parquet(ROOT/'dataset.parquet')
    for period,stats in best['periods'].items():
        g=frame[frame.complete_date & frame.period.eq(period)]
        for size,policy in stats['policies'].items():
            nsize=int(size)
            chosen=g.assign(priority=g[best['feature']]*best['orientation_frozen_discovery']).sort_values(
                ['date','priority','symbol'],ascending=[True,False,True]).groupby('date').head(nsize)
            d=(chosen.groupby('date').long_area_pct.mean()-g[g.oracle_rank<=nsize].groupby('date').long_area_pct.mean()).to_numpy()
            expected=policy['metrics']['area_pct']['delta_oracle_ci63']
            if len(d)<2*rules['block']:
                if expected is not None:raise AssertionError('Sparse CI not reserved')
                continue
            rng=np.random.default_rng(rules['seed']);b=rules['block'];means=[]
            starts=rng.integers(0,len(d)-b+1,size=(rules['replications'],math.ceil(len(d)/b)))
            for row in starts:
                sample=[d[j] for k in row for j in range(k,k+b)][:len(d)]
                means.append(math.fsum(sample)/len(sample))
            if not np.allclose(np.quantile(means,[.025,.975]),expected,rtol=1e-10,atol=1e-10):
                raise AssertionError('CI mismatch '+period+'/'+size)
            ci_checks+=1
    result=dict(status='PASS_INDEPENDENT_MAXT_AND_DISCOVERY_BEST_AREA_CI',
        family_tests=len(names),maxT_replications=rules['replications'],paired_area_CIs=ci_checks,
        independent_human_review=False,report_sha256=digest(ROOT/'report.json'),
        auditor_sha256=digest(__file__))
    save(ROOT/'statistics-audit.json',result)
    return result


if __name__=='__main__':
    print(run())
