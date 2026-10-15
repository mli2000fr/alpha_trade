"""One frozen net-profit classifier after path Oracle; no recent-year replay.

Only 2018-2021 fit, 2022 early stopping, untouched partial 2023 control.
Failures of preregistered gates stop the campaign without threshold tuning.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from scripts.research import us_oracle_path_profit_tp15_sl7_dataset as data


DEFAULT_DATA = Path('artifacts/research/us_oracle_path_profit_filter/20261015-tp15-sl7-dataset-v2')
LOG=logging.getLogger(__name__)


def equal_date_weights(frame):
    weights=1/frame.groupby('date').date.transform('size').astype(float)
    return (weights/weights.mean()).to_numpy()


def block_interval(daily_lift, *, seed=20261015, repetitions=999, width=63):
    """Calendar blocks, not iid candidate resampling; no-acceptance dates unknown."""
    values=np.asarray(daily_lift,dtype=float)
    if not np.isfinite(values).any():return dict(low=None,high=None,valid_draws=0,blocks=0)
    blocks=[values[i:i+width] for i in range(0,len(values),width)]
    rng=np.random.default_rng(seed);samples=[]
    for _ in range(repetitions):
        sample=np.concatenate([blocks[k] for k in rng.integers(0,len(blocks),size=len(blocks))])
        if np.isfinite(sample).any():samples.append(float(np.nanmean(sample)))
    return dict(low=float(np.quantile(samples,.025)),high=float(np.quantile(samples,.975)),
        valid_draws=len(samples),blocks=len(blocks),method='63_session_blocks_exploratory_not_iid')


def metrics(frame, probability, baseline, spec):
    p=np.asarray(probability,dtype=float);work=frame.copy()
    if p.shape!=(len(frame),) or not np.isfinite(p).all() or ((p<0)|(p>1)).any():
        raise ValueError('Invalid probability vector')
    work['probability']=p;work['accepted']=p>=spec['learner']['threshold']
    y=work.label.to_numpy(float);w=equal_date_weights(work)
    brier=float(np.average((p-y)**2,weights=w))
    constant_brier=float(np.average((baseline-y)**2,weights=w))
    daily=[]
    for _,part in work.groupby('date'):
        if min(part.label.value_counts().get(0.,0),part.label.value_counts().get(1.,0))>=2:
            daily.append(float(roc_auc_score(part.label,part.probability)))
    pool=work.groupby('date').net_return.mean()
    accepted=work[work.accepted].groupby('date').net_return.mean()
    # Dates are equally weighted; no acceptance is missing, never a fabricated zero-return trade.
    lifts=(accepted-pool).reindex(pool.index)
    calendar=data.nyse_sessions(pool.index.min(),pool.index.max())
    lift_calendar=lifts.reindex(calendar)
    g=spec['gates_before_external_replay']
    interval=block_interval(lift_calendar,seed=g['bootstrap_seed'],repetitions=g['bootstrap_repetitions'],
        width=g['bootstrap_block_sessions'])
    auc_daily=float(np.mean(daily)) if daily else None
    lift=float(lifts.mean()) if lifts.notna().any() else None
    fraction=float(work.accepted.mean());lo,hi=g['validation_accepted_fraction_between']
    checks=dict(mean_daily_auc=auc_daily is not None and auc_daily>=g['validation_mean_daily_auc_gte'],
        minimum_auc_dates=len(daily)>=g['minimum_validation_dates_with_two_of_each_class'],
        brier_better_than_constant=brier<constant_brier,
        accepted_fraction=lo<=fraction<=hi,
        date_matched_lift=lift is not None and lift>g['validation_date_matched_net_lift_gt'],
        lift_lower_interval=interval['low'] is not None and interval['low']>g['date_matched_lift_block_bootstrap_lower_95pct_gt'])
    return dict(rows=len(work),dates=int(work.date.nunique()),base_rate=float(np.average(y,weights=w)),
        pooled_auc=float(roc_auc_score(y,p)) if len(np.unique(y))==2 else None,
        mean_daily_auc=auc_daily,auc_dates=len(daily),brier=brier,constant_brier=constant_brier,
        minimum_probability=float(p.min()),maximum_probability=float(p.max()),mean_probability=float(np.average(p,weights=w)),
        accepted_rows=int(work.accepted.sum()),accepted_fraction=fraction,
        accepted_dates=int(work.loc[work.accepted,'date'].nunique()),
        no_acceptance_dates=int(work.date.nunique()-work.loc[work.accepted,'date'].nunique()),
        accepted_date_matched_net_lift=lift,lift_block_interval=interval,
        pool_equal_date_mean_net_return=float(pool.mean()),
        selected_equal_date_mean_net_return=float(accepted.mean()) if len(accepted) else None,
        checks=checks,all_gates_pass=all(checks.values()),portfolio_pnl=False)


def freeze(root, dataset):
    marker=root/'protocol.json'
    if marker.exists():
        p=data.read(marker)
        if Path(p['dataset'])!=dataset:raise ValueError('Different dataset for existing fit')
        for name,expected in p['sources'].items():data.plan.original.require_hash(name,expected)
        return p
    report=data.read(dataset/'report.json')
    if report['verdict']!='READY_FOR_SINGLE_FIT':raise ValueError('Dataset qualification gates did not pass')
    audit=data.read(dataset/'completion-audit.json')
    if audit['status']!='AUDITED_NATIVE_TP15_SL7_DATASET':raise ValueError('Independent native dataset audit required')
    data.plan.original.require_hash('scripts/research/us_oracle_path_profit_tp15_sl7_audit.py',audit['audit_source_sha256'])
    data.plan.original.require_hash(dataset/'report.json',audit['source_report_sha256'])
    data.plan.original.require_hash(dataset/'dataset.parquet',audit['source_dataset_sha256'])
    for name,expected in report['files'].items():data.plan.original.require_hash(dataset/name,expected)
    old=data.read(dataset/'protocol.json');sources=dict(old['sources'])
    for name,expected in sources.items():data.plan.original.require_hash(name,expected)
    for path in [dataset/'report.json',dataset/'dataset.parquet',dataset/'protocol.json',dataset/'completion-audit.json',
                 dataset/'native-parity.json',Path(__file__),Path('tests/test_us_oracle_path_profit_tp15_sl7_fit.py')]:
        sources[str(path)]=data.digest(path)
    p=dict(specification=old['specification'],dataset=str(dataset),sources=sources,
        authorization='user_continue_after_TP15_SL7_preparation',
        model_fits_planned=1,threshold_selection=False,recent_predictions_planned=False,
        no_automatic_production_promotion=True,external_years_already_observed=True)
    data.atomic_json(marker,p);return p


def run(root,dataset):
    root=Path(root);dataset=Path(dataset);root.mkdir(parents=True,exist_ok=True)
    p=freeze(root,dataset);spec=p['specification']
    if (root/'report.json').exists():
        report=data.read(root/'report.json')
        for name,expected in report['files'].items():data.plan.original.require_hash(root/name,expected)
        return report
    full=pd.read_parquet(dataset/'dataset.parquet')
    parts={name:full[full.reason.eq('') & full.split.eq(name)].copy() for name in ('FIT','VALIDATION','CONTROL')}
    columns=spec['features']
    for name,frame in parts.items():
        if frame.empty or not np.isfinite(frame[columns+['label','net_return']]).all().all():
            raise ValueError('Invalid fit partition '+name)
        rule=spec['splits'][name.lower()]
        if not frame.date.between(rule['decision_start'],rule['decision_end']).all() or not frame.label_available.lt(rule['label_before']).all():
            raise ValueError('Target availability leakage '+name)
    fit,valid=parts['FIT'],parts['VALIDATION']
    baseline=float(np.average(fit.label,weights=equal_date_weights(fit)))
    marker=root/'fit.json'
    if not marker.exists():
        options=spec['learner']
        params={k:options[k] for k in ('objective','metric','max_depth','num_leaves','min_data_in_leaf',
            'learning_rate','lambda_l1','lambda_l2','seed','num_threads','deterministic','force_col_wise','feature_fraction')}
        params['verbosity']=-1
        train=lgb.Dataset(fit[columns].astype(np.float32),label=fit.label,weight=equal_date_weights(fit))
        val=lgb.Dataset(valid[columns].astype(np.float32),label=valid.label,weight=equal_date_weights(valid))
        data.atomic_json(root/'progress.json',dict(status='FITTING_ONE_MODEL',fit_rows=len(fit),validation_rows=len(valid)))
        model=lgb.train(params,train,num_boost_round=options['num_boost_round'],valid_sets=[val],
            callbacks=[lgb.early_stopping(options['early_stopping_rounds'],verbose=False)])
        model.save_model(str(root/'model.txt'),num_iteration=model.best_iteration)
        data.atomic_json(marker,dict(best_iteration=model.best_iteration,parameters=params,
            fit_rows=len(fit),fit_dates=int(fit.date.nunique()),validation_rows=len(valid),
            fit_labels_available_max=str(fit.label_available.max()),
            validation_labels_available_max=str(valid.label_available.max()),baseline_probability=baseline,
            files={'model.txt':data.digest(root/'model.txt')}))
    trained=data.read(marker)
    for name,expected in trained['files'].items():data.plan.original.require_hash(root/name,expected)
    model=lgb.Booster(model_file=str(root/'model.txt'))
    if model.feature_name()!=columns:raise ValueError('Model feature order mismatch')
    scores=[];summaries={}
    for name in ('VALIDATION','CONTROL'):
        frame=parts[name]
        predicted=model.predict(frame[columns].astype(np.float32),num_threads=3)
        summaries[name]=metrics(frame,predicted,baseline,spec)
        selected=frame[['date','symbol','oracle_rank','label','net_return','label_available']].copy()
        selected['probability']=predicted;selected['accepted']=predicted>=spec['learner']['threshold'];selected['split']=name
        scores.append(selected)
    pd.concat(scores,ignore_index=True).to_parquet(root/'validation-control-predictions.parquet',index=False)
    passed=all(m['all_gates_pass'] for m in summaries.values())
    for name,expected in p['sources'].items():data.plan.original.require_hash(name,expected)
    report=dict(status='COMPLETED_SINGLE_FIT_EXPLORATORY',
        verdict='READY_FOR_SEPARATE_MATCHED_TP15_SL7_REPLAY' if passed else 'NO_GO_CONDITIONAL_NET_PROFIT_FILTER',
        model_fits=1,threshold=spec['learner']['threshold'],threshold_retuned=False,
        best_iteration=trained['best_iteration'],baseline_probability=baseline,metrics=summaries,
        recent_year_predictions=0,portfolio_runs=0,sql_reads=0,sql_writes=0,API_calls=0,broker_calls=0,
        production_promotion=False,independent_holdout=False,
        next_action='new matched TP15SL7 baseline/filter replay only on new GO' if passed else
                    'stop: no recent-year inference or replay, no new threshold',
        files={name:data.digest(root/name) for name in ('protocol.json','fit.json','model.txt','validation-control-predictions.parquet')})
    data.atomic_json(root/'report.json',report)
    data.atomic_json(root/'progress.json',{k:v for k,v in report.items() if k not in ('files','metrics')})
    LOG.info('Single conditional filter completed: %s',report['verdict']);return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--dataset',type=Path,default=DEFAULT_DATA);args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    import requests
    def forbidden(*args,**kwargs):raise RuntimeError('Network forbidden in single profit filter fit')
    requests.Session.request=forbidden
    with data.plan.original.exclusive_run(args.output):
        try:print(json.dumps(run(args.output,args.dataset),default=str))
        except Exception as exc:
            data.atomic_json(args.output/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise
