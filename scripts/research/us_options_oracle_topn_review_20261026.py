"""Offline arithmetic/cohort audit, no source changes or SQL."""
from pathlib import Path
import json
import hashlib
import numpy as np
import pandas as pd

ROOT=Path('artifacts/research/us_options_oracle_topn/20261026-v1')
PARENT=Path('artifacts/research/us_options_equal_mix/20261026-v2')
OUT=Path('artifacts/research/us_options_oracle_topn/20261026-v1-review')


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run():
    OUT.mkdir(exist_ok=False,parents=True)
    seal=json.loads((ROOT/'seal.json').read_text(encoding='utf-8'))
    for n,sha in seal['files'].items():assert digest(ROOT/n)==sha,n
    for n,sha in seal['sources'].items():assert digest(n)==sha,n
    raw=pd.read_parquet(ROOT/'oracle-scores.parquet')
    ranked=pd.read_parquet(ROOT/'oracle-ranked.parquet')
    report=json.loads((ROOT/'report.json').read_text(encoding='utf-8'))
    days=pd.read_parquet(PARENT/'calendar.parquet')
    result=dict(status='PASS_EXPLORATORY_CONDITIONAL_REVIEW',same_assistant_not_independent_human=True,
        aucs=0,asof_scores=0,paths=0,cohorts={},single_horizon_model='H20 only')
    for day,g in ranked.groupby('signal_day'):
        original=raw[raw.signal_day.eq(day.date())&raw.batch_id.eq(g.batch_id.iloc[0])&raw.symbol.isin(ranked.symbol)]
        # The saved universe rather than the observed TOPN determines full coverage.
        original=raw[pd.to_datetime(raw.signal_day).eq(day)&raw.batch_id.eq(g.batch_id.iloc[0])]
        universe=json.loads((PARENT/'protocol.json').read_text(encoding='utf-8'))['symbols']
        original=original[original.symbol.isin(universe)].sort_values(['proba_extreme','symbol'],ascending=[False,True])
        assert g.sort_values('oracle_rank').symbol.tolist()==original.symbol.tolist()
    for source,group in report['source_results'].items():
        parent=pd.read_parquet(PARENT/source/'protected-paths.parquet').set_index(['symbol','entry_day','horizon'])
        for n,item in group.items():
            selected=pd.read_parquet(ROOT/f'oracle-top{n}.parquet')
            scored=pd.read_parquet(ROOT/f'{source}-top{n}-asof-scores.parquet')
            paths=pd.read_parquet(ROOT/f'{source}-top{n}-paths.parquet')
            assert selected.oracle_rank.le(int(n)).all() and not selected.duplicated(['symbol','entry_day']).any()
            assert len(selected)==int(n)*selected.entry_day.nunique()
            assert len(scored)==item['covered_asof'] and len(paths)==3*len(scored)
            assert scored.oracle_rank.le(int(n)).all()
            for day,g in scored.groupby('entry_day'):
                a=(g.volume_call_minus_put_log.rank()-.5)/len(g);o=(g.oi_call_minus_put_log.rank()-.5)/len(g)
                np.testing.assert_allclose(g.volume_score,a,rtol=0,atol=1e-14)
                np.testing.assert_allclose(g.oi_score,o,rtol=0,atol=1e-14)
                np.testing.assert_allclose(g.combined_score,(a+o)/2,rtol=0,atol=1e-14)
            result['asof_scores']+=len(scored);result['paths']+=len(paths)
            x=paths.set_index(['symbol','entry_day','horizon']);ref=parent.reindex(x.index)
            for col in ['status','dominant_direction','long_lower_pct','long_upper_pct','short_lower_pct','short_upper_pct']:
                pd.testing.assert_series_equal(x[col],ref[col],check_names=False)
            for h,study in item['horizons'].items():
                f=paths[paths.horizon.eq(int(h))&paths.status.eq('LABEL')]
                auc_dates=study['all']['daily'];two_days=[r['day'] for r in auc_dates]
                result['cohorts'][source+'/'+n+'/'+h]=dict(valid_n=len(f),symbols=int(f.symbol.nunique()),
                    valid_dates=int(f.entry_day.nunique()),long_n=int(f.dominant_direction.eq('LONG').sum()),
                    short_n=int(f.dominant_direction.eq('SHORT').sum()),
                    daily_auc_n=int(f.entry_day.isin(two_days).sum()),daily_auc_dates=len(two_days))
                for row in auc_dates:
                    g=f[f.entry_day.eq(row['day'])];y=g.dominant_direction.eq('LONG');n1=int(y.sum());n0=len(g)-n1
                    assert len(g)==row['n'] and n1>0 and n0>0
                    for col in ['volume_score','oi_score','combined_score']:
                        auc=(g[col].rank()[y].sum()-n1*(n1+1)/2)/(n1*n0)
                        assert abs(auc-row[col])<1e-12
                        result['aucs']+=1
    result.update(source_seal_sha256=digest(ROOT/'seal.json'),review_script_sha256=digest(__file__))
    (OUT/'report.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':run()
