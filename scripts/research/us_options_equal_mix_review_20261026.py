"""Independent arithmetic review of frozen US options results; no database."""
from pathlib import Path
from decimal import Decimal
import json
import hashlib
import numpy as np
import pandas as pd

ROOT=Path('artifacts/research/us_options_equal_mix/20261026-v2')
OUT=Path('artifacts/research/us_options_equal_mix/20261026-v2-review')


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def excursion(path,side):
    entry=float(path[0]['open']);best=0.;sgn=1 if side=='LONG' else -1
    stop=float(Decimal(str(entry))*(Decimal('.9') if side=='LONG' else Decimal('1.1')))
    for p in path:
        o,hi,lo=map(float,[p['open'],p['high'],p['low']])
        if (o<=stop if sgn==1 else o>=stop):return 100*best,100*best
        move=max(0.,hi/entry-1 if sgn==1 else 1-lo/entry)
        if (lo<=stop if sgn==1 else hi>=stop):return 100*best,100*max(best,move)
        best=max(best,move)
    return 100*best,100*best


def run():
    OUT.mkdir(parents=True,exist_ok=False)
    seal=json.loads((ROOT/'seal.json').read_text(encoding='utf-8'))
    for name,sha in seal['files'].items():assert digest(ROOT/name)==sha,name
    for name,sha in seal['sources'].items():assert digest(name)==sha,name
    protocol=json.loads((ROOT/'protocol.json').read_text(encoding='utf-8'))
    cutoff=pd.Timestamp(protocol['cutoff']);cal=pd.read_parquet(ROOT/'calendar.parquet')
    prices=pd.read_parquet(ROOT/'prices.parquet');prices['date']=pd.to_datetime(prices.date)
    summary=json.loads((ROOT/'report.json').read_text(encoding='utf-8'))
    checked=dict(paths=0,aucs=0,asof_scores=0,archives={},cohorts={})
    for source in ['eodhd_eod','alpaca_sip']:
        root=ROOT/source;f=pd.read_parquet(root/'features.parquet');scored=pd.read_parquet(root/'asof-scores.parquet')
        labels=pd.read_parquet(root/'protected-paths.parquet')
        assert not scored.duplicated(['entry_day','symbol']).any()
        assert pd.to_datetime(scored.feature_available_at,utc=True).lt(pd.to_datetime(scored.decision_at,utc=True)).all()
        assert (f.volume_expiry==f.oi_expiry).all()
        for day,g in scored.groupby('entry_day'):
            n=len(g)
            a=(g.volume_call_minus_put_log.rank(method='average')-.5)/n
            o=(g.oi_call_minus_put_log.rank(method='average')-.5)/n
            np.testing.assert_allclose(g.volume_score,a,rtol=0,atol=1e-14)
            np.testing.assert_allclose(g.oi_score,o,rtol=0,atol=1e-14)
            np.testing.assert_allclose(g.combined_score,(a+o)/2,rtol=0,atol=1e-14)
        checked['asof_scores']+=len(scored)
        px=prices[prices.data_source.eq(source)]
        paths={sym:g.set_index('date') for sym,g in px.groupby('symbol')}
        for r in labels[labels.status.isin(['LABEL','AMBIGUOUS_PATH'])].to_dict('records'):
            i=cal.index[cal.day.eq(pd.Timestamp(r['entry_day']))][0]
            window=cal.iloc[i:i+int(r['horizon'])]
            assert len(window)==int(r['horizon']) and window.closed.lt(cutoff).all()
            path=paths[r['symbol']].reindex(window.day)
            assert path.instrument_id.notna().all() and path.instrument_id.nunique()==1
            rows=path.to_dict('records');lo,lu=excursion(rows,'LONG');so,su=excursion(rows,'SHORT')
            np.testing.assert_allclose([r['long_lower_pct'],r['long_upper_pct'],r['short_lower_pct'],r['short_upper_pct']],
                                      [lo,lu,so,su],rtol=0,atol=1e-10)
            direction='LONG' if lo>su+1e-9 else 'SHORT' if so>lu+1e-9 else 'AMBIGUOUS_OR_TIE'
            assert direction==r['dominant_direction']
            checked['paths']+=1
        for h,d in summary['sources'][source]['horizons'].items():
            valid=labels[labels.horizon.eq(int(h))&labels.status.eq('LABEL')]
            key=source+'/'+h
            checked['cohorts'][key]=dict(n=len(valid),symbols=int(valid.symbol.nunique()),dates=int(valid.entry_day.nunique()))
            for daily in d['all']['daily']:
                g=valid[valid.entry_day.eq(daily['day'])];y=g.dominant_direction.eq('LONG');n1=int(y.sum());n0=int((~y).sum())
                assert n1>0 and n0>0 and len(g)==daily['n']
                for score in ['volume_score','oi_score','combined_score']:
                    auc=(g[score].rank(method='average')[y].sum()-n1*(n1+1)/2)/(n1*n0)
                    assert abs(auc-daily[score])<1e-12
                    checked['aucs']+=1
        if source=='eodhd_eod':
            old=pd.read_parquet('artifacts/research/us_prospective_directional_audit/20261010-v1/prospective_features.parquet')
            z=old.merge(f,on=['symbol','day'],suffixes=('_old','_new'))
            for name in ['volume_call_minus_put_log','oi_call_minus_put_log']:
                q=z.dropna(subset=[name+'_old',name+'_new'])
                np.testing.assert_allclose(q[name+'_old'],q[name+'_new'],atol=0,rtol=0)
                checked['archives'][name]=dict(n=len(q),maximum_difference=0)
    for name,sha in seal['files'].items():assert digest(ROOT/name)==sha,name
    result=dict(status='PASS_EXPLORATORY_ARITHMETIC_REVIEW',same_assistant_not_independent_human=True,
        source_seal_sha256=digest(ROOT/'seal.json'),review_script_sha256=digest(__file__),**checked)
    (OUT/'report.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':run()
