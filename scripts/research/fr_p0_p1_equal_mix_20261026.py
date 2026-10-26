"""Offline equal-weight FR signal mix, no training or parameter search.

Ranks use ALL feature-complete candidates observed before each entry open,
including not-yet-mature/ambiguous outcomes. Outcome status cannot affect ranks.
"""
from datetime import datetime,timezone
from pathlib import Path
import json,hashlib

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

PARENT=Path('artifacts/fr/research/p0_p1_directional/20261026-v1-reviewed')
OUTPUT=Path('artifacts/fr/research/p0_p1_equal_mix/20261026-v1')
FEATURES=['momentum_5','momentum_20','amf_common_holder_change_score']
KEY=['symbol','entry_day']
SCORES=['price_score','amf_score','combined_score']
DOC=Path('doc/fr/p0_p1_combinaison_egale_protocole_20261026.md')
TEST=Path('tests/test_fr_p0_p1_equal_mix_20261026.py')


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path,payload):Path(path).write_text(json.dumps(payload,indent=2,ensure_ascii=False,allow_nan=False,default=str),encoding='utf-8')


def verify_seal(root):
    seal=read(root/'seal.json')
    for name,expected in seal['files'].items():
        if Path(name).name!=name:raise ValueError('Unsafe manifest member')
        if digest(root/name)!=expected:raise ValueError('Frozen source changed: '+name)
    return {str(root/name):sha for name,sha in seal['files'].items()}


def centered_rank(values):
    if values.empty:return values.astype(float)
    if not np.isfinite(values.to_numpy(float)).all():raise ValueError('Finite complete features required')
    return (values.rank(method='average')-.5)/len(values)


def score_asof_candidates(frame):
    # Deliberately discard target, horizon and status columns before scoring.
    data=frame[KEY+FEATURES+['feature_available_at','entry_at']].copy()
    if data.groupby(KEY)[FEATURES+['feature_available_at','entry_at']].nunique(dropna=False).gt(1).any().any():
        raise ValueError('Horizon-dependent input feature or provenance')
    data=data.drop_duplicates(KEY)
    if not pd.to_datetime(data.feature_available_at,utc=True).lt(pd.to_datetime(data.entry_at,utc=True)).all():
        raise ValueError('Future source observation')
    complete=np.isfinite(data[FEATURES].to_numpy(float)).all(axis=1)
    coverage=data.assign(complete_features=complete).groupby('entry_day').agg(
        candidate_symbols=('symbol','size'),complete_symbols=('complete_features','sum')).reset_index()
    data=data.loc[complete].copy()
    for column in FEATURES:
        data['rank_'+column]=data.groupby('entry_day')[column].transform(centered_rank)
    data['price_score']=.5*data.rank_momentum_5+.5*data.rank_momentum_20
    data['amf_score']=data.rank_amf_common_holder_change_score
    data['combined_score']=.5*data.price_score+.5*data.amf_score
    data=data.sort_values(KEY).reset_index(drop=True)
    return data,coverage


def metrics(sample):
    summaries={name:dict(daily=[],pooled_auc=None) for name in SCORES}
    if sample.empty:return dict(n=0,symbols=0,dates=0,long_count=0,short_count=0,scores=summaries,paired=[])
    labels=sample.dominant_direction.eq('LONG')
    for name in SCORES:
        # A constant score is a chance ranking (0.5), not a dropped date.
        if labels.nunique()==2:summaries[name]['pooled_auc']=float(roc_auc_score(labels,sample[name]))
    paired=[]
    for day,g in sample.groupby('entry_day',sort=True):
        y=g.dominant_direction.eq('LONG')
        if y.nunique()!=2:continue
        values={name:float(roc_auc_score(y,g[name])) for name in SCORES}
        paired.append(dict(day=day,n=len(g),**values,
            combined_minus_price=values['combined_score']-values['price_score'],
            combined_minus_amf=values['combined_score']-values['amf_score']))
        for name,value in values.items():summaries[name]['daily'].append(dict(day=day,n=len(g),auc=value))
    for name in SCORES:
        values=[r['auc'] for r in summaries[name]['daily']]
        summaries[name].update(mean_daily_auc=float(np.mean(values)) if values else None,informative_dates=len(values))
    deltas=[r['combined_minus_price'] for r in paired]
    return dict(n=len(sample),symbols=int(sample.symbol.nunique()),dates=int(sample.entry_day.nunique()),
        long_count=int(labels.sum()),short_count=int((~labels).sum()),scores=summaries,paired=paired,
        combined_minus_price_mean=float(np.mean(deltas)) if deltas else None,
        combined_better_dates=sum(d>1e-12 for d in deltas),combined_worse_dates=sum(d< -1e-12 for d in deltas),
        tied_dates=sum(abs(d)<=1e-12 for d in deltas))


def nonoverlap_dates(days,horizon,calendar_days):
    index={str(d):i for i,d in enumerate(calendar_days)}
    result=[];last=None
    for day in sorted(set(days)):
        position=index[day]
        if last is None or position-last>=horizon:result.append(day);last=position
    return result


def evaluate(frame,scored,calendar_days):
    if frame.duplicated(KEY+['horizon']).any():raise ValueError('Duplicate outcome')
    merged=frame.merge(scored[KEY+SCORES],on=KEY,how='inner',validate='many_to_one')
    outputs={}
    for horizon in [5,10,20]:
        whole=frame[frame.horizon.eq(horizon)]
        joined=merged[merged.horizon.eq(horizon)]
        sample=joined[joined.status.eq('DIAGNOSTIC_LABEL')].copy()
        if not sample.dominant_direction.isin(['LONG','SHORT']).all():raise ValueError('Ambiguous target entered evaluation')
        result=dict(primary_horizon=horizon==20,all_source_rows=len(whole),
            feature_complete_rows=len(joined),status_counts=joined.status.value_counts().to_dict(),
            matched_cohort=metrics(sample),
            correlated_or_overlapping_rows_are_not_independent=True,independent_holdout=False)
        selected=nonoverlap_dates(sample.entry_day,horizon,calendar_days)
        result['nonoverlap_calendar_dates']=selected
        result['nonoverlap_calendar_control']=metrics(sample[sample.entry_day.isin(selected)])
        first=sample.sort_values(['entry_day','symbol']).drop_duplicates('symbol')
        result['first_observation_per_symbol']=metrics(first)
        paired=result['matched_cohort']['paired']
        result['leave_one_date_out_mean_delta']=[dict(excluded=row['day'],
            delta=float(np.mean([r['combined_minus_price'] for r in paired if r['day']!=row['day']])))
            for row in paired] if len(paired)>1 else []
        if sample.empty:result['status']='NO_MATURE_H20_LABELS' if horizon==20 else 'NO_ELIGIBLE_LABELS'
        else:result['status']='DESCRIPTIVE_MATCHED_COHORT_NOT_VALIDATION'
        outputs[str(horizon)]=result
    return outputs,merged


def main():
    sources=verify_seal(PARENT)
    sources.update({str(p):digest(p) for p in [Path(__file__),DOC,TEST]})
    if OUTPUT.exists():raise FileExistsError('Immutable new output required')
    OUTPUT.mkdir(parents=True)
    # Persist exact, untrained rule BEFORE calculating any combined-score outcome.
    write(OUTPUT/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,
        primary_horizon=20,secondary_horizons=[5,10],target='Existing maximum favorable excursion before side-specific SL10, not terminal H20 or economic PnL',
        complete_features=FEATURES,rank_rule='(average tied rank -0.5)/N among all as-of feature-complete candidates, not future label-qualified subset',
        weights=dict(momentum_5=.25,momentum_20=.25,amf_common_holder_change_score=.50),
        comparisons=SCORES,training=False,weight_search=False,threshold_search=False,sign_flip=False,
        source_prior_outcomes_already_seen=True,independent_holdout=False,
        level_AMF_excluded='Not one of the favorable weak signals; no additional post-hoc combination',
        DILA_excluded='No qualified directional event content',consensus_excluded='P3 outside source cohort',
        production_changed=False,SQL_reads=0,SQL_writes=0,provider_calls=0,LLM_calls=0,orders=False))
    frame=pd.read_parquet(PARENT/'protected-path-diagnostics.parquet')
    scored,coverage=score_asof_candidates(frame)
    from common.market_calendar import get_market_calendar
    from datetime import date
    days=get_market_calendar('FR_EQ',allow_us_weekday_fallback=False).session_dates(date(2026,9,1),date(2026,12,15))
    results,merged=evaluate(frame,scored,days)
    scored.to_parquet(OUTPUT/'asof-scores.parquet',index=False)
    merged.to_parquet(OUTPUT/'scored-diagnostics.parquet',index=False)
    write(OUTPUT/'report.json',dict(status='EXPLORATORY_COMPARISON_COMPLETE_H20_UNAVAILABLE',
        scored_symbol_dates=len(scored),symbols=int(scored.symbol.nunique()),dates=int(scored.entry_day.nunique()),
        coverage=coverage.to_dict('records'),horizons=results,
        score_is_probability=False,no_economic_backtest=True,training=False,no_weight_optimization=True,
        verdict='No H20 validation or live promotion; H5/H10 comparisons descriptive only'))
    sources_after=verify_seal(PARENT)
    if any(sources[k]!=v for k,v in sources_after.items()):raise ValueError('Input mutated during calculation')
    write(OUTPUT/'seal.json',dict(at_utc=datetime.now(timezone.utc).isoformat(),
        files={p.name:digest(p) for p in OUTPUT.iterdir() if p.is_file()}))
    print(json.dumps(dict(output=str(OUTPUT),horizons={h:dict(status=r['status'],
        n=r['matched_cohort']['n'],symbols=r['matched_cohort']['symbols'],dates=r['matched_cohort']['dates'],
        AUC={n:s.get('mean_daily_auc') for n,s in r['matched_cohort']['scores'].items()},
        delta=r['matched_cohort'].get('combined_minus_price_mean')) for h,r in results.items()})))


if __name__=='__main__':main()
