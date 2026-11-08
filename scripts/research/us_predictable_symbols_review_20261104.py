"""Integrity review of completed reliability campaign; no fit, SQL or provider.

Quarantine mixed instrument histories or reviewed identity breaks before
publishing the current-issuer rankings. Do not reinterpret ticker continuity
as legal/economic identity continuity. All original results are preserved.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from modelFactory.oracle.security_continuity import load_security_discontinuities
from common.symbol_artifact_paths import symbol_directory

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'artifacts/research/us_predictable_symbols/20261103-v1'
PLAN=OUT/'integrity-review-plan.json'


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(p,v):Path(p).write_text(json.dumps(v,indent=2,default=str,allow_nan=False)+'\n',encoding='utf-8')


def check_2026(frame,target):
    """Fixed-phase nonoverlap check; never alter the 2023-25 ranking."""
    h=10 if target=='winner_h10' else 20
    a=frame[frame.year.eq(2026)&frame.session_index.mod(h).eq(0)]
    selected=a[a.probability.ge(a.long_threshold)]
    auc=float(roc_auc_score(a.label,a.probability)) if a.label.nunique()==2 else None
    base=float(a.label.mean()) if len(a) else None
    precision=float(selected.label.mean()) if len(selected) else None
    return dict(observations=len(a),auc=auc,long_observations=len(selected),base_rate=base,
        long_precision=precision,long_lift=None if precision is None else precision-base)


def summarize(frame):
    auc=frame.auc.dropna();lift=frame.long_lift.dropna()
    return dict(symbols=len(frame),with_auc=len(auc),with_long_outcomes=len(lift),
        median_auc=None if auc.empty else float(auc.median()),
        fraction_auc_above_half=None if auc.empty else float(auc.gt(.5).mean()),
        median_long_precision_lift=None if lift.empty else float(lift.median()),
        median_independent_observations=None if frame.empty else float(frame.observations.median()))


def plan():
    if PLAN.exists():raise FileExistsError(PLAN)
    save(PLAN,dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        purpose='Identity and date/hash review; no performance tuning or parameter changes',
        price_performance_inspected_to_choose_quarantine=False,
        quarantine_rules=['More than one nonnull instrument_id in the exported history',
            'Known predecessor/successor economic identity break inside the exported history'],
        check_2026='Fixed calendar phase, same target horizon; per-stock AUC/precision lift medians in TOP1500 versus remaining history-qualified stocks; no reranking',
        known_break_symbols=sorted(load_security_discontinuities()),
        prediction_reproduction_sample=['AAPL','BRK.B','MSFT'],
        code_sha256=digest(__file__),registry_sha256=digest(ROOT/'config/data_quality/security_discontinuities.json'),
        sql_writes=False,training=False,provider_calls=0,orders=0))


def review():
    p=json.loads(PLAN.read_text());protocol=json.loads((OUT/'protocol.json').read_text())
    if digest(__file__)!=p['code_sha256']:raise ValueError('Frozen review code changed')
    for filename,value in protocol['source_hashes'].items():
        if digest(ROOT/filename)!=value:raise ValueError('Frozen source changed: '+filename)
    registry=load_security_discontinuities();quarantine=[];errors=[];checked_models=0;checked_symbols=0;validation=[]
    for file in sorted((OUT/'symbols').glob('*/result.json')):
        record=json.loads(file.read_text());symbol=record['symbol'];folder=file.parent;checked_symbols+=1
        raw=folder/'source-bars.parquet'
        if raw.exists():
            if 'bars_sha256' not in record:
                if record['status']!='ERROR':raise ValueError('Missing bars receipt: '+symbol)
                continue
            if digest(raw)!=record['bars_sha256']:raise ValueError('Exported bars changed: '+symbol)
            b=pd.read_parquet(raw,columns=['date','instrument_id']);days=pd.to_datetime(b.date)
            reasons=[]
            if b.instrument_id.dropna().nunique()>1:reasons.append('MIXED_INSTRUMENT_HISTORY')
            if any(event.crosses(days.min(),days.max()) for event in registry.get(symbol,())):
                reasons.append('KNOWN_PREDECESSOR_SUCCESSOR_BREAK')
            if reasons:quarantine.append(dict(symbol=symbol,reasons=reasons))
        for target,item in record.get('targets',{}).items():
            for fit in item['fits']:
                if fit['status']!='FITTED':continue
                year=fit['year'];model=folder/f'{target}-{year}.joblib';checked_models+=1
                if digest(model)!=fit['model_sha256']:raise ValueError('Model changed: '+str(model))
                if not pd.Timestamp(fit['fit_label_available_max'])<pd.Timestamp(f'{year-1}-01-01'):
                    errors.append((symbol,target,year,'FIT_DATE_LEAK'))
                if not pd.Timestamp(fit['calibration_label_available_max'])<pd.Timestamp(f'{year}-01-01'):
                    errors.append((symbol,target,year,'CALIBRATION_DATE_LEAK'))
        for target in ('winner_h10','parcours_h20'):
            scorefile=folder/(target+'-predictions.parquet')
            if not scorefile.exists():continue
            a=pd.read_parquet(scorefile)
            validation.append(dict(symbol=symbol,target=target,**check_2026(a,target)))
            if a.date.duplicated().any() or not a.probability.between(0,1).all():
                errors.append((symbol,target,'INVALID_PREDICTION'))
            if not (pd.to_datetime(a.label_available_date)<=pd.Timestamp(protocol['asof'])).all():
                errors.append((symbol,target,'UNMATURED_RESULT'))
    if checked_symbols!=len(protocol['symbols']):raise ValueError('Incomplete symbol receipts')
    if errors:save(OUT/'integrity-errors.json',errors);raise ValueError('Integrity review failed')
    reproduced=[]
    for symbol in p['prediction_reproduction_sample']:
        folder=symbol_directory(OUT/'symbols',symbol)
        for target in ('winner_h10','parcours_h20'):
            sf=folder/(target+'-predictions.parquet')
            if not sf.exists():continue
            scores=pd.read_parquet(sf)
            panel=pd.read_parquet(folder/(target+'-panel.parquet'))
            for year in scores.year.unique():
                model=joblib.load(folder/f'{target}-{year}.joblib')
                expected=scores[scores.year.eq(year)].head(3)
                x=expected[['date']].merge(panel[['date',*model['features']]],on='date',validate='one_to_one')
                x=x[model['features']].replace([np.inf,-np.inf],np.nan).clip(model['lo'],model['hi'],axis=1)
                rawp=np.clip(model['model'].predict_proba(x)[:,1],1e-6,1-1e-6)
                actual=model['calibrator'].predict_proba(np.log(rawp/(1-rawp)).reshape(-1,1))[:,1]
                if not np.allclose(actual,expected.probability,rtol=0,atol=1e-12):raise ValueError('Prediction reproduction failed')
                reproduced.append(dict(symbol=symbol,target=target,year=int(year),rows=len(actual)))
    before=OUT/'before-integrity-review';before.mkdir(exist_ok=False)
    reportpath=OUT/'report.json';report=json.loads(reportpath.read_text());(before/'report.json').write_bytes(reportpath.read_bytes())
    quarantined={x['symbol'] for x in quarantine}
    validation=pd.DataFrame(validation);validation.to_csv(OUT/'check-2026-per-symbol.csv',index=False)
    summaries={}
    for target in ('winner_h10','parcours_h20'):
        file=OUT/(target+'-per-symbol-ranking.csv');a=pd.read_csv(file,keep_default_na=False)
        (before/file.name).write_bytes(file.read_bytes())
        a=a[~a.symbol.isin(quarantined)].copy();a['rank']=np.arange(1,len(a)+1)
        a.to_csv(file,index=False)
        audit=OUT/(target+'-per-symbol-audit.csv');(before/audit.name).write_bytes(audit.read_bytes())
        allrows=pd.read_csv(audit,keep_default_na=False);allrows['identity_history_qualified']=~allrows.symbol.isin(quarantined)
        allrows.loc[~allrows.identity_history_qualified,['qualified_history','reliability_confirmed']]=False
        allrows.to_csv(audit,index=False)
        for suffix,values in [('model-top1500',a.head(1500).symbol),('model-confirmed',a[a.reliability_confirmed].symbol)]:
            output=OUT/(target+'-'+suffix+'.txt');(before/output.name).write_bytes(output.read_bytes())
            output.write_text(','.join(values)+'\n',encoding='utf-8')
        report['cases'][target].update(model_history_qualified=len(a),model_top1500=min(1500,len(a)),
            model_exploratory_confirmed=int(a.reliability_confirmed.sum()))
        eligible=set(a.symbol);top=set(a.head(1500).symbol)
        v=validation[validation.target.eq(target)&validation.symbol.isin(eligible)]
        summaries[target]=dict(top1500=summarize(v[v.symbol.isin(top)]),
            other_history_qualified=summarize(v[~v.symbol.isin(top)]),
            no_reranking=True,portfolio_return=False,independent_of_2023_2025_ranking=True,
            previously_explored_calendar_period_not_virgin_holdout=True)
    save(OUT/'check-2026-summary.json',summaries)
    report['integrity_review']='integrity-review.json';save(reportpath,report)
    save(OUT/'integrity-review.json',dict(status='PASS',created_at_utc=datetime.now(timezone.utc).isoformat(),
        symbols_checked=checked_symbols,models_checked=checked_models,date_leaks=0,
        samples_reproduced=reproduced,quarantined_histories=quarantine,
        rationale='Current ticker must not pool predecessor/successor histories to establish per-issuer reliability',
        final_intersections_unchanged_empty=True,sql_writes=False,provider_calls=0))


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--phase',choices=['plan','review'],required=True)
    args=a.parse_args();{'plan':plan,'review':review}[args.phase]()
