"""Reconstructed weak-signal research on the original Oracle TOP20/TOP50.

No SQL/provider/broker calls and no production model changes. Targets retain
their separate contracts: E2 terminal H3, corrected causal E3 lifecycle, and
global terminal H20 deciles for VOL60/P-MATH. This is not an exact replay of
the deleted historical directional models or an untouched confirmation set.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from threadpoolctl import threadpool_limits

from modelFactory import oracle_separability_pmath0 as pmath
from scripts.research.oracle_path_confirmation import exclusive_run

LOG = logging.getLogger(__name__)
PROFILE = Path('config/features/shared_direction/shared.json')
PMATH_CONFIG = Path('config/research/pmath0_separability.json')
CAMPAIGN_CONFIG = Path('config/research/us_weak_topn_2020_2024_20261029.json')
ROOT = Path('artifacts/research/us_weak_topn_2020_2024/20261029-v1')
METHODS = ('VOL60', 'E2', 'E3', 'PMATH0')
YEARS = (2020, 2021, 2022, 2023, 2024)
TASKS = ('D1_VS_D10', 'D10_VS_REST', 'D1_VS_REST')
POLICY = dict(min_train_dates=252, validation_dates=63, catboost_iterations=600,
    catboost_depth=6, catboost_learning_rate=.03, catboost_l2_leaf_reg=5.,
    catboost_random_seed=42, catboost_early_stopping_rounds=60,
    threads=2, selection_fraction=.10, daily_min_per_class=2,
    test_years=list(YEARS), statistical_alpha=.01, already_observed_periods=True,
    exact_original_replication=False, research_only=True, no_pnl=True,
    no_sql=True, no_provider_calls=True, no_broker_calls=True)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024*1024), b''):
            result.update(part)
    return result.hexdigest()


def clean(value):
    if isinstance(value, dict): return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [clean(v) for v in value]
    if isinstance(value, np.generic): return clean(value.item())
    if isinstance(value, (float,int)) and not np.isfinite(value): return None
    if isinstance(value, (pd.Timestamp,datetime,Path)): return str(value)
    return value


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(clean(value),indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    temporary.replace(path)


def task_target(frame, task):
    decile = pd.to_numeric(frame.oracle_decile,errors='coerce')
    if not decile.dropna().isin(range(1,11)).all():
        raise ValueError('Global integer H20 deciles required')
    if task=='D1_VS_D10':
        return decile.eq(10).astype(float).where(decile.isin([1,10]))
    if task not in ('D10_VS_REST','D1_VS_REST'):
        raise ValueError('Unknown task')
    return decile.eq(10 if task=='D10_VS_REST' else 1).astype(float).where(decile.notna())


def select_top(frame, top):
    """Freeze the original membership before inspecting future target coverage."""
    if top not in (20,50): raise ValueError('TOP must be 20 or 50 titles')
    if frame[['date','symbol','oracle_rank']].isna().any().any():
        raise ValueError('Missing Oracle candidate key')
    if frame.duplicated(['date','symbol']).any() or frame.duplicated(['date','oracle_rank']).any():
        raise ValueError('Duplicate Oracle candidate key/rank')
    result=frame.loc[frame.oracle_rank.le(top)].copy()
    counts=result.groupby('date').oracle_rank.agg(['size','min','max'])
    if counts.empty or not (counts['size'].eq(top)&counts['min'].eq(1)&counts['max'].eq(top)).all():
        raise ValueError('Incomplete original TOP membership; do not replace missing ranks')
    if not result.oracle_rank.eq(result.oracle_rank.astype(int)).all():
        raise ValueError('Integer original ranks required')
    return result.sort_values(['date','oracle_rank']).reset_index(drop=True)


def causal_split(frame, year, target, available, policy=POLICY):
    """Both early-stopping and final refit may use only labels known beforehand."""
    cutoff=pd.Timestamp(f'{year}-01-01')
    maturity=pd.to_datetime(frame[available],errors='coerce')
    good=frame.date.lt(cutoff)&maturity.lt(cutoff)&frame[target].notna()
    mature=frame.loc[good].sort_values(['date','symbol']).copy()
    dates=pd.DatetimeIndex(mature.date.unique()).sort_values()
    if len(dates)<policy['validation_dates']+policy['min_train_dates']:
        raise ValueError('Insufficient mature training dates for frozen annual split')
    validation_start=dates[-policy['validation_dates']]
    train=mature.loc[mature.date.lt(validation_start)&pd.to_datetime(mature[available]).lt(validation_start)].copy()
    valid=mature.loc[mature.date.ge(validation_start)].copy()
    if train.date.nunique()<policy['min_train_dates']:
        raise ValueError('Insufficient training dates after label-availability purge')
    if train[target].nunique()!=2 or valid[target].nunique()!=2 or mature[target].nunique()!=2:
        raise ValueError('Both target classes required in training and validation')
    proof=dict(test_start=str(cutoff.date()),validation_start=str(validation_start.date()),
        train_rows=len(train),train_dates=int(train.date.nunique()),
        train_available_max=str(pd.to_datetime(train[available]).max()),
        validation_rows=len(valid),validation_dates=int(valid.date.nunique()),
        validation_available_max=str(pd.to_datetime(valid[available]).max()),
        refit_rows=len(mature),refit_dates=int(mature.date.nunique()),
        refit_available_max=str(pd.to_datetime(mature[available]).max()))
    return train,valid,mature,proof


def attach_method_targets(frame,method):
    """Keep the requested experiment's target and estimator route explicit."""
    result=frame.copy()
    if method=='E2':
        value=pd.to_numeric(result.terminal_return_h3,errors='coerce')
        result['target']=value.ge(.03).astype(float).where(value.notna()&np.isfinite(value))
        return result,[('LONG_H3','available_h3',3)]
    if method=='E3':
        result['target']=pd.to_numeric(result.e3_long_target,errors='coerce')
        return result,[('LONG_NET_POSITIVE','available_e3',20)]
    if method in ('VOL60','PMATH0'):
        return result,[(task,'available_h20',20) for task in TASKS]
    raise ValueError('Unknown method')


def daily_auc(frame):
    f=frame.loc[frame.target.notna()&np.isfinite(frame.score)].copy()
    rank=f.groupby('date').score.rank(method='average')
    positive=f.target.eq(1)
    n1=positive.groupby(f.date).sum();n0=(~positive).groupby(f.date).sum()
    sums=rank.where(positive,0.).groupby(f.date).sum()
    result=(sums-n1*(n1+1)/2)/(n1*n0)
    return result.where(n1.ge(POLICY['daily_min_per_class'])&n0.ge(POLICY['daily_min_per_class']))


def metrics(frame, *, prior=None, probability=True, horizon=20, calendar=None):
    known=frame.loc[frame.target.notna()&np.isfinite(frame.score)].copy()
    if not known.target.dropna().isin([0,1]).all(): raise ValueError('Binary metrics target required')
    daily=daily_auc(frame)
    y=known.target.to_numpy(float);p=known.score.to_numpy(float)
    auc=float(roc_auc_score(y,p)) if len(np.unique(y))==2 else None
    if probability and ((p<0).any() or (p>1).any()): raise ValueError('Invalid probability')
    fraction=POLICY['selection_fraction']
    # Rank all original candidates before looking up realised outcomes.
    ranked=frame.sort_values(['date','score','oracle_rank'],ascending=[True,False,True],na_position='last')
    size=ranked.groupby('date').date.transform('size')
    chosen=ranked.loc[ranked.groupby('date').cumcount().lt(np.ceil(size*fraction))]
    selected_known=chosen.loc[chosen.target.notna()&np.isfinite(chosen.score)]
    selected_rate=float(selected_known.target.mean()) if len(selected_known) else None
    reference=(known.groupby('date').target.mean()).mean() if len(known) else None
    dates=pd.DatetimeIndex(calendar if calendar is not None else sorted(frame.date.unique()))
    spaced=dates[::horizon]
    spaced_auc=daily.reindex(spaced).dropna()
    return dict(rows=len(frame),dates=int(frame.date.nunique()),known_rows=len(known),
        target_coverage=len(known)/len(frame) if len(frame) else None,
        positives=int((y==1).sum()),negatives=int((y==0).sum()),
        base_rate=float(y.mean()) if len(y) else None,
        auc_pooled_descriptive=auc,auc_daily_mean=float(daily.mean()) if daily.notna().any() else None,
        auc_daily_median=float(daily.median()) if daily.notna().any() else None,
        auc_daily_dates=int(daily.notna().sum()),
        fraction_daily_auc_above_half=float(daily.dropna().gt(.5).mean()) if daily.notna().any() else None,
        auc_h_spaced_mean=float(spaced_auc.mean()) if len(spaced_auc) else None,
        auc_h_spaced_dates=len(spaced_auc),h_spaced_fixed_global_calendar=True,
        brier=float(np.mean((p-y)**2)) if probability and len(y) else None,
        brier_train_prior=float(np.mean((prior-y)**2)) if prior is not None and len(y) else None,
        probability_calibrated=False,
        selected_original_rows=len(chosen),selected_known_rows=len(selected_known),
        selected_target_rate=selected_rate,reference_equal_date_rate=float(reference) if reference is not None else None,
        selected_rate_is_not_portfolio_win_rate=True)


def catboost_fit(train,valid,mature,test,features,folder,target,policy=POLICY):
    from catboost import CatBoostClassifier
    def x(frame):
        return frame[features].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)
    common=dict(iterations=policy['catboost_iterations'],depth=policy['catboost_depth'],
        learning_rate=policy['catboost_learning_rate'],l2_leaf_reg=policy['catboost_l2_leaf_reg'],
        random_seed=policy['catboost_random_seed'],random_strength=1.,bootstrap_type='Bayesian',
        bagging_temperature=1.,allow_writing_files=False,verbose=False,thread_count=policy['threads'],
        loss_function='Logloss',eval_metric='AUC')
    selector=CatBoostClassifier(**common)
    selector.fit(x(train),train[target].astype(int),eval_set=(x(valid),valid[target].astype(int)),
        early_stopping_rounds=policy['catboost_early_stopping_rounds'],use_best_model=True)
    iterations=max(1,int(selector.get_best_iteration())+1)
    selector.save_model(str(folder/'validation_model.cbm'))
    final=CatBoostClassifier(**{**common,'iterations':iterations})
    final.fit(x(mature),mature[target].astype(int))
    final.save_model(str(folder/'model.cbm'))
    score=final.predict_proba(x(test))[:,1]
    return score,dict(iterations_selected_on_past_validation=iterations,
        validation_best_score=selector.get_best_score(),refit_on_all_mature_history=True)


def logistic_fit(mature,test,features,folder,target,seed):
    balanced=pmath.balanced_by_date(mature.rename(columns={target:pmath.TARGET}),
        max_per_class=30000,seed=seed)
    if balanced[pmath.TARGET].nunique()!=2: raise ValueError('Balanced training lacks classes')
    prep=pmath.fit_preprocessor(balanced,features,lower_q=.01,upper_q=.99,max_missing_rate=.5)
    train_x=pmath.transform(balanced,prep);test_x=pmath.transform(test,prep)
    model=LogisticRegression(C=1.,max_iter=500,solver='lbfgs',random_state=seed)
    model.fit(train_x,balanced[pmath.TARGET].astype(int))
    import joblib
    joblib.dump(dict(preprocessor=prep,classifier=model),folder/'logistic.joblib')
    return model.predict_proba(test_x)[:,1],dict(features_used=list(prep.features),
        balanced_training_rows=len(balanced),balanced_training_prior=float(balanced[pmath.TARGET].mean()))


def protocol(panel_path,manifest_path,method,top,output,policy=POLICY):
    if method not in METHODS: raise ValueError('Unknown method')
    manifest=json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    if manifest.get('status')!='COMPLETED_LABELS' or manifest.get('files',{}).get(Path(panel_path).name)!=digest(panel_path):
        raise ValueError('Completed label manifest with matching panel hash required')
    campaign=json.loads(CAMPAIGN_CONFIG.read_text(encoding='utf-8'))
    if (campaign['years']!=policy['test_years'] or campaign['min_train_dates']!=policy['min_train_dates']
            or campaign['validation_dates']!=policy['validation_dates']):
        raise ValueError('Campaign/model temporal policy mismatch')
    inputs={str(p):digest(p) for p in (Path(panel_path),Path(manifest_path),PROFILE,PMATH_CONFIG,CAMPAIGN_CONFIG,Path(__file__),
        Path('modelFactory/oracle_separability_pmath0.py'))}
    value=dict(method=method,top_titles=top,policy=policy,input_sha256=inputs,
        dataset_manifest=manifest,campaign_protocol=campaign,
        feature_profile=str(PROFILE),target_contracts=dict(
            VOL60='global terminal H20 D1/D10; increasing volatility fixed before results',
            E2='adjusted close(J+3)/close(J)-1 >=0.03; not path and not next-open return',
            E3='CAUSAL_CORRECTED LONG net-positive; ATR14 at J; entry open J+1; all20 held sessions monitored',
            PMATH0='three global terminal H20 decile tasks, not TOPN-local deciles'),
        original_min_train504_val126_replaced_explicitly=True,
        oracle_score_features_forbidden=True,current_history_and_universe_bias_retained=True,
        no_automatic_promotion=True,annual_tests_already_observed=True)
    marker=output/'protocol.json'
    if marker.exists() and json.loads(marker.read_text(encoding='utf-8'))!=clean(value):
        raise ValueError('Protocol/input changed; new output directory required')
    if not marker.exists(): write(marker,value)
    return value


def run_method(panel_path,output,method,top,*,manifest_path=None,policy=POLICY):
    panel_path=Path(panel_path);output=Path(output)
    manifest_path=Path(manifest_path) if manifest_path else panel_path.with_suffix('.manifest.json')
    with exclusive_run(output),threadpool_limits(limits=policy['threads']):
        frozen=protocol(panel_path,manifest_path,method,top,output,policy)
        frame=pd.read_parquet(panel_path)
        frame['date']=pd.to_datetime(frame.date).dt.normalize()
        # Never let an experiment read 2025/2026 outcome columns.
        frame=frame.loc[frame.date.le('2024-12-31')].copy()
        full=select_top(frame,top)
        features=json.loads(PROFILE.read_text(encoding='utf-8'))['feature_columns']
        if set(features)-set(full.columns): raise ValueError('Missing original numeric features: '+str(sorted(set(features)-set(full.columns))))
        full,tasks=attach_method_targets(full,method)
        global_calendar=pd.DatetimeIndex(sorted(full.date.unique()))
        summaries=[];all_predictions=[];pmath_folds={task:[] for task in TASKS}
        for year in policy['test_years']:
            for task,available,horizon in tasks:
                folder=output/str(year)/task;folder.mkdir(parents=True,exist_ok=True)
                done=folder/'done.json'
                if done.exists():
                    record=json.loads(done.read_text(encoding='utf-8'))
                    for name,expected in record['files'].items():
                        if digest(folder/name)!=expected: raise ValueError('Completed checkpoint altered')
                    summaries.append(record['metrics'])
                    if record.get('nonparametric'): pmath_folds[task].append(record['nonparametric'])
                    if (folder/'predictions.parquet').exists(): all_predictions.append(pd.read_parquet(folder/'predictions.parquet'))
                    continue
                write(output/'progress.json',dict(status='RUNNING',method=method,top=top,year=year,task=task,
                    completed=len(summaries),total=len(policy['test_years'])*len(tasks)))
                work=full.copy()
                if method in ('VOL60','PMATH0'): work['target']=task_target(work,task)
                test=work.loc[work.date.dt.year.eq(year)].copy()
                if test.empty: raise ValueError('Missing planned test year')
                model_proof={};np_result=None;prior=None
                if method=='VOL60':
                    test['score']=pd.to_numeric(test.rolling_volatility_60,errors='coerce')
                else:
                    try:
                        train,valid,mature,model_proof=causal_split(work,year,'target',available,policy)
                    except ValueError as error:
                        value=dict(method=method,top=top,year=year,task=task,status='INSUFFICIENT_TRAINING',error=str(error),
                            candidate_rows=len(test),candidate_dates=int(test.date.nunique()))
                        write(done,dict(metrics=value,files={}))
                        summaries.append(value)
                        continue
                    prior=float(mature.target.mean())
                    if method in ('E2','E3'):
                        test['score'],fit_proof=catboost_fit(train,valid,mature,test,features,folder,'target',policy)
                    else:
                        seed=20260916+year+top
                        test['score'],fit_proof=logistic_fit(mature,test,features,folder,'target',seed)
                        config=json.loads(PMATH_CONFIG.read_text(encoding='utf-8'))
                        before=mature.rename(columns={'target':pmath.TARGET})
                        after=test.loc[test.target.notna()].rename(columns={'target':pmath.TARGET})
                        np_result=pmath.audit_fold(before,after,features,config=config,seed=seed)
                        # Balanced statistical C2ST remains separate from all-candidate daily AUC.
                        pmath_folds[task].append(np_result)
                    model_proof.update(fit_proof)
                test['method']=method;test['task']=task;test['year']=year;test['top']=top
                values=metrics(test,prior=prior,probability=method!='VOL60',horizon=horizon,calendar=global_calendar)
                row=dict(method=method,top=top,year=year,task=task,status='COMPLETED_EXPLORATORY',**values)
                summaries.append(row)
                pred=test[['date','symbol','oracle_rank','method','task','year','top','target','score',available]].copy()
                pred.to_parquet(folder/'predictions.parquet',index=False)
                daily_auc(pred).rename('auc').to_csv(folder/'daily-auc.csv')
                write(folder/'model-proof.json',model_proof)
                files={p.name:digest(p) for p in folder.iterdir() if p.is_file() and p.name!='done.json'}
                write(done,dict(metrics=row,nonparametric=np_result,files=files))
                all_predictions.append(pred)
                LOG.info('%s TOP%d %s %s: daily AUC=%s coverage=%s',method,top,year,task,
                    row['auc_daily_mean'],row['target_coverage'])
        pd.DataFrame(summaries).to_csv(output/'annual-summary.csv',index=False)
        if all_predictions: pd.concat(all_predictions,ignore_index=True).to_parquet(output/'predictions.parquet',index=False)
        tests={}
        if method=='PMATH0':
            cfg=json.loads(PMATH_CONFIG.read_text(encoding='utf-8'))
            tests={task:pmath.summarize_task(rows,cfg['gates']) for task,rows in pmath_folds.items() if rows}
            if tests: pmath.apply_global_gates(tests,cfg['gates'])
        for name,expected in frozen['input_sha256'].items():
            if digest(name)!=expected: raise ValueError('Input changed during experiment')
        incomplete=sum(row['status']!='COMPLETED_EXPLORATORY' for row in summaries)
        report=dict(status='PARTIAL_INSUFFICIENT_TRAINING' if incomplete else 'COMPLETED_EXPLORATORY',method=method,top_titles=top,
            annual=summaries,nonparametric_task_summaries=tests,
            incomplete_tasks=incomplete,
            source_hashes_verified_after_calculation=True,
            no_pnl=True,no_production_changes=True,no_automatic_promotion=True,
            protocol_sha256=digest(output/'protocol.json'),
            files={p.name:digest(p) for p in output.iterdir() if p.is_file() and p.name not in ('run.lock','progress.json','report.json','seal.json')})
        write(output/'report.json',report)
        write(output/'seal.json',dict(report_sha256=digest(output/'report.json'),files=report['files'],input_sha256=frozen['input_sha256']))
        write(output/'progress.json',dict(status=report['status'],method=method,top=top,
            completed=len(summaries),total=len(policy['test_years'])*len(tasks),incomplete_tasks=report['incomplete_tasks']))
        return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--panel',type=Path)
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--method',required=True,choices=METHODS)
    parser.add_argument('--top',required=True,type=int,choices=[20,50])
    args=parser.parse_args()
    args.panel=args.panel or args.root/'labels/panel.parquet'
    args.manifest=args.manifest or args.root/'labels/report.json'
    args.output=args.output or args.root/f'experiments/{args.method}-TOP{args.top}'
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    try:
        report=run_method(args.panel,args.output,args.method,args.top,manifest_path=args.manifest)
    except BaseException as error:
        if args.output.exists(): write(args.output/'progress.json',dict(status='FAILED',error_type=type(error).__name__,error=str(error)))
        raise
    print(json.dumps(dict(status=report['status'],method=args.method,top=args.top,incomplete_tasks=report['incomplete_tasks'])))


if __name__=='__main__': main()
