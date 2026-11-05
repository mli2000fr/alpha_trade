"""Oracle TOP20 -> annual independent per-symbol P(LONG) -> TOP5.

Re-infer archived causal annual models on all decision-date features, never only
on matured-label prediction caches. No fitting, SQL, provider, or broker calls.
"""
from pathlib import Path
from datetime import datetime,timezone
import json
import logging
import numpy as np
import pandas as pd
import joblib

from scripts.research.us_selected_universe_oracle_20261104 import (
    ROOT,BASE,OUT as ORACLE,CASES,END,INPUTS,digest,save)

OUT=ROOT/'artifacts/research/us_selected_universe_per_symbol/20261104-v1'
PREVIOUS=ROOT/'artifacts/research/us_selected_universe_oracle/20261104-winner-dd15-v1'
LOG=logging.getLogger(__name__)


def select(scores,pool=20,count=5):
    """Rank amplitude first, freeze pool, then P(LONG); do not refill rank21+."""
    if scores.duplicated(['date','symbol']).any():raise ValueError('Duplicate decision identity')
    if not scores.score.between(0,1).all():raise ValueError('Invalid Oracle score')
    a=scores.sort_values(['date','score','symbol'],ascending=[True,False,True]).copy()
    a['oracle_amplitude_rank']=a.groupby('date').cumcount()+1
    a=a[a.oracle_amplitude_rank.le(pool)].copy()
    if not a.groupby('date').size().eq(pool).all():raise ValueError('Incomplete Oracle TOP20 pool')
    if not a.long_probability.between(0,1).all():raise ValueError('Missing/invalid per-symbol probability within frozen Oracle pool')
    a=a.sort_values(['date','long_probability','oracle_amplitude_rank','symbol'],ascending=[True,False,True,True])
    a['long_rank']=a.groupby('date').cumcount()+1
    a['selected_long_top5']=a.long_rank.le(count)
    chosen=a[a.selected_long_top5].copy()
    # Legacy replay field is execution priority, not a rewritten amplitude rank.
    chosen['oracle_rank']=chosen.long_rank
    return a,chosen


def main():
    if (OUT/'selection-report.json').exists():raise FileExistsError('Frozen selection already exists')
    OUT.mkdir(parents=True,exist_ok=True)
    old=json.loads((ORACLE/'report.json').read_text())
    sources={};models=[];cases={};wanted=set();expected_models=0
    for case,(horizon,count) in CASES.items():
        folder=OUT/case;folder.mkdir(exist_ok=False)
        universe=old['cases'][case]['universe']
        assert len(universe)==count
        oracle_path=ORACLE/case/'all-scores.parquet'
        oracle=pd.read_parquet(oracle_path)
        sources[str(oracle_path)]=digest(oracle_path)
        predictions=[]
        for symbol in universe:
            p=BASE/'symbols'/symbol
            receipt=json.loads((p/'result.json').read_text())
            feature_path=p/f'{case}-panel.parquet'
            frame=pd.read_parquet(feature_path)[['date',*INPUTS]]
            assert frame.date.is_unique
            saved=pd.read_parquet(p/f'{case}-predictions.parquet')
            sources[str(feature_path)]=digest(feature_path)
            sources[str(p/'result.json')]=digest(p/'result.json')
            sources[str(p/f'{case}-predictions.parquet')]=digest(p/f'{case}-predictions.parquet')
            for year in (2024,2025,2026):
                fit=next(r for r in receipt['targets'][case]['fits'] if r['year']==year)
                assert fit['status']=='FITTED'
                assert pd.Timestamp(fit['fit_label_available_max'])<pd.Timestamp(f'{year-1}-01-01')
                assert pd.Timestamp(fit['calibration_label_available_max'])<pd.Timestamp(f'{year}-01-01')
                path=p/f'{case}-{year}.joblib'
                assert digest(path)==fit['model_sha256']
                sources[str(path)]=digest(path)
                model=joblib.load(path)
                assert model['features']==INPUTS and model['year']==year and model['target']==case
                test=frame[frame.date.dt.year.eq(year)&frame.date.le(END)].copy()
                matrix=test[INPUTS].replace([np.inf,-np.inf],np.nan).clip(model['lo'],model['hi'],axis=1)
                raw=np.clip(model['model'].predict_proba(matrix)[:,1],1e-6,1-1e-6)
                probabilities=model['calibrator'].predict_proba(np.log(raw/(1-raw)).reshape(-1,1))[:,1]
                inferred=pd.DataFrame(dict(date=test.date,symbol=symbol,long_probability=probabilities,model_year=year,
                    model_sha256=fit['model_sha256'],target=case))
                expected=saved[saved.year.eq(year)&saved.date.le(END)][['date','probability']]
                overlap=inferred.merge(expected,on='date',validate='one_to_one')
                assert len(overlap)==len(expected)
                assert np.allclose(overlap.long_probability,overlap.probability,rtol=0,atol=1e-12)
                models.append(dict(case=case,symbol=symbol,year=year,model=str(path),model_sha256=fit['model_sha256'],
                    fit_label_available_max=fit['fit_label_available_max'],
                    calibration_label_available_max=fit['calibration_label_available_max'],
                    inferred_rows=len(inferred),cached_matured_rows_reproduced=len(overlap)))
                predictions.append(inferred)
                expected_models+=1
        probabilities=pd.concat(predictions,ignore_index=True)
        assert not probabilities.duplicated(['date','symbol']).any()
        probabilities.to_parquet(folder/'per-symbol-long-scores.parquet',index=False)
        joined=oracle.merge(probabilities,on=['date','symbol'],how='left',validate='one_to_one',suffixes=('','_per_symbol'))
        pool,chosen=select(joined)
        pool.to_parquet(folder/'oracle-top20-long-ranking.parquet',index=False)
        chosen.to_csv(folder/'daily-top5.csv',index=False)
        old_top=pd.read_csv(ORACLE/case/'daily-top5.csv',parse_dates=['date'])
        before=set(zip(old_top.date,old_top.symbol));after=set(zip(chosen.date,chosen.symbol))
        cases[case]=dict(universe=universe,horizon=horizon,oracle_pool=20,long_top=5,
            decisions=len(chosen),decision_dates=chosen.date.nunique(),selected_symbols=sorted(chosen.symbol.unique()),
            overlap_with_original_oracle_top5=len(before&after),changed_signals=len(after-before),
            long_probability_min=float(chosen.long_probability.min()),long_probability_max=float(chosen.long_probability.max()))
        wanted.update(chosen.symbol)
        # Input reader must also keep predecessor comparison symbols, for matched sources.
        cohort=OUT/'input-cohort'/case;cohort.mkdir(parents=True)
        pd.concat([chosen[['date','symbol']],old_top[['date','symbol']]]).drop_duplicates().to_csv(cohort/'daily-top5.csv',index=False)
        LOG.info('%s selected=%s symbols=%s changed=%s',case,len(chosen),len(cases[case]['selected_symbols']),len(after-before))
    assert expected_models==207
    assert all(digest(p)==h for p,h in sources.items())
    save(OUT/'models-reused.json',dict(models=models,count=len(models),new_fits=0))
    save(OUT/'report.json',dict(status='SELECTION_READY',cases=cases))
    save(OUT/'selection-report.json',dict(status='COMPLETED',cases=cases,models=len(models),
        new_fits=0,inferred_rows=sum(m['inferred_rows'] for m in models),
        cached_predictions_reproduced=sum(m['cached_matured_rows_reproduced'] for m in models),
        source_hashes=sources,script_sha256=digest(__file__),
        pool='Oracle amplitude TOP20 frozen before directional scores',
        execution_priority='TOP5 descending calibrated per-symbol LONG probability; ties Oracle amplitude rank then symbol',
        probability_threshold=None,minimum_probability_not_enforced=True,
        targets={'winner_h10':'Positive net LONG with SL5/open11',
            'parcours_h20':'Upward peak dominates absolute downward peak across H20; not TP-before-SL profitability'},
        universe_selection_uses_2026=True,sql_writes=False,provider_calls=0,orders=0,
        created_at_utc=datetime.now(timezone.utc).isoformat()))
    print(json.dumps(dict(status='SELECTION_READY',models=len(models),symbols=len(wanted),cases=cases),default=str))


if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    main()
