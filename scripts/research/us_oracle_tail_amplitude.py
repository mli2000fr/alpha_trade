"""Frozen two-stage H20 tail-amplitude research. Offline; no SQL or serving."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_oracle_amplitude_rerank import (
    EXTERNAL, HISTORY, INPUTS, checked, eligible_training, load_source, metrics, read,
)
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

THRESHOLD = .20
PARAMS = dict(n_estimators=200, learning_rate=.03, max_depth=4, num_leaves=15,
    min_child_samples=150, reg_alpha=.1, reg_lambda=1., random_state=42,
    verbosity=-1, deterministic=True, force_col_wise=True)
LOG = logging.getLogger(__name__)


def tail_target(returns):
    values = np.asarray(returns, dtype=float)
    if not np.isfinite(values).all():
        raise ValueError('Nonfinite training target')
    return np.abs(values) >= THRESHOLD


def tail_score(probability, conditional_mean):
    """Expected tail contribution, NOT full E[abs(return)] or signed return."""
    p, mean = np.asarray(probability), np.asarray(conditional_mean)
    if p.shape != mean.shape or not np.isfinite(p).all() or not np.isfinite(mean).all():
        raise ValueError('Invalid model outputs')
    if ((p < 0) | (p > 1)).any():
        raise ValueError('Probability outside [0,1]')
    # A conditional mean on the >=20% branch cannot logically be below 20%.
    return p * np.maximum(THRESHOLD, mean)


def select(data):
    parts = []
    for policy, column in [('ORACLE', 'score'), ('ATR', 'atr20_pct'), ('TAIL_TWO_STAGE', 'tail_score')]:
        rows = data.sort_values(['date', column, 'symbol'], ascending=[True, False, True]).copy()
        rows['selection_rank'] = rows.groupby('date').cumcount()+1
        for k in (10, 20):
            chosen = rows[rows.selection_rank.le(k)].copy()
            chosen['policy'], chosen['top_n'] = policy, k
            parts.append(chosen)
    return pd.concat(parts, ignore_index=True)


def source_hashes():
    paths = [HISTORY/'protocol.json', EXTERNAL/'protocol.json',
             HISTORY/'labels.parquet', EXTERNAL/'labels.parquet',
             EXTERNAL/'corrected-predictions.parquet']
    historical = read(HISTORY/'protocol.json')
    paths += [HISTORY/'corrected'/start/'predictions.parquet'
              for start in historical['expected_fold_starts']]
    paths += sorted(Path(historical['after']).glob('features-*.json'))
    paths += sorted(EXTERNAL.glob('features-*.json'))
    return {str(path): digest(path) for path in paths}


def fit_predict(train, test, threads):
    import lightgbm as lgb
    target = tail_target(train.future_return)
    if np.unique(target).size != 2 or target.sum() < 1000:
        raise ValueError('Insufficient tail examples or constant classifier target')
    classifier = lgb.LGBMClassifier(**PARAMS, objective='binary', n_jobs=threads)
    # No class weights: retain natural prevalence rather than distorted probabilities.
    classifier.fit(train[INPUTS], target.astype(int))
    regressor = lgb.LGBMRegressor(**PARAMS, objective='regression', n_jobs=threads)
    regressor.fit(train.loc[target, INPUTS], train.loc[target, 'future_return'].abs())
    result = test.copy()
    result['tail_probability'] = classifier.predict_proba(test[INPUTS])[:, 1]
    result['tail_conditional_mean'] = np.maximum(THRESHOLD, regressor.predict(test[INPUTS]))
    result['tail_score'] = tail_score(result.tail_probability, result.tail_conditional_mean)
    return classifier, regressor, result


def paired_summary(daily):
    required = {'ORACLE', 'ATR', 'TAIL_TWO_STAGE'}
    groups = daily.groupby(['source', 'date', 'top_n'])
    if not groups.policy.agg(lambda x: set(x) == required and len(x) == 3).all():
        raise ValueError('Unpaired policies')
    common = groups.full.transform('all')
    paired = daily[common].copy()
    if paired.empty:
        raise ValueError('No fully evaluated common sessions')
    annual = paired.groupby(['source', 'year', 'policy', 'top_n']).agg(
        days=('date', 'size'), precision=('precision', 'mean'), mean_abs=('mean_abs', 'mean'),
        median_abs=('median_abs', 'mean'), abs_ge20=('abs_ge20', 'mean'),
        abs_ge50=('abs_ge50', 'mean')).reset_index()
    comparisons = []
    for (source, k), group in paired.groupby(['source', 'top_n']):
        wide = group.pivot(index='date', columns='policy', values=['abs_ge20', 'mean_abs', 'precision', 'abs_ge50'])
        for baseline in ('ORACLE', 'ATR'):
            item = dict(source=source, top_n=int(k), baseline=baseline, days=len(wide))
            for metric in ('abs_ge20', 'mean_abs', 'precision', 'abs_ge50'):
                values = (wide[metric]['TAIL_TWO_STAGE']-wide[metric][baseline]).to_numpy()
                rng = np.random.default_rng(42)
                n, block = len(values), min(20, len(values))
                boot = [values[(rng.integers(0, n-block+1, size=int(np.ceil(n/block)))[:, None]
                    + np.arange(block)).ravel()[:n]].mean() for _ in range(1000)]
                item[f'delta_{metric}_pp'] = float(values.mean()*100)
                item[f'descriptive_block20_{metric}_ci_pp'] = [float(x*100) for x in np.quantile(boot, [.025,.975])]
            comparisons.append(item)
    blocks = paired[paired.source.eq('historical_oof')].groupby(['block','policy','top_n'])[
        ['abs_ge20','mean_abs']].mean().reset_index()
    stability, verdicts = [], {}
    for k in (10, 20):
        wide = blocks[blocks.top_n.eq(k)].pivot(index='block', columns='policy', values=['abs_ge20','mean_abs'])
        wins = np.ones(len(wide), dtype=bool)
        for baseline in ('ORACLE', 'ATR'):
            for metric in ('abs_ge20', 'mean_abs'):
                wins &= (wide[metric]['TAIL_TWO_STAGE'] > wide[metric][baseline]).to_numpy()
        ext = annual[annual.source.eq('external_frozen') & annual.top_n.eq(k)].pivot(
            index='year', columns='policy', values=['abs_ge20','mean_abs'])
        confirmed = set(ext.index) == {2025, 2026}
        for baseline in ('ORACLE','ATR'):
            for metric in ('abs_ge20','mean_abs'):
                confirmed &= bool((ext[metric]['TAIL_TWO_STAGE'] > ext[metric][baseline]).all())
        stability.append(dict(top_n=k, blocks=len(wide), all_primary_baseline_wins=int(wins.sum())))
        verdicts[str(k)] = ('RESEARCH_FOLLOWUP_ONLY' if confirmed and wins.sum() > len(wide)/2
                           else 'NO_GO_STABLE_TAIL_RERANK')
    return annual, blocks, dict(annual=json.loads(annual.to_json(orient='records')),
        paired=comparisons, block_stability=stability, verdicts=verdicts,
        excluded_date_topn_pairs=int((~common).sum()/3))


def run(args):
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output/'progress.json', dict(status='RUNNING', phase='freeze_protocol'))
    protocol = dict(threshold=THRESHOLD, primary_metrics=['abs_ge20', 'mean_abs'],
        secondary_metrics=['precision','median_abs','abs_ge50'], inputs=INPUTS,
        classifier='LightGBM binary, no weighting or post-test calibration',
        regressor='LightGBM squared-error conditional mean abs(return) on >=20% cases only',
        score='P(abs(R)>=0.20) * max(0.20,E[abs(R)|abs(R)>=0.20])',
        score_semantics='Expected tail contribution; NOT full expected amplitude or direction',
        params=PARAMS, threads=args.threads, top_n=[10,20],
        pool='Frozen Oracle TOP20% intersect ATR TOP20%', min_train_dates=480,
        initial_oof_history_dates=504, test_dates=126,
        purge='Maturity date strictly earlier than test start',
        baseline='ORACLE and ATR ordering within same pool, common complete sessions',
        promotion='Both primary metrics strictly improve vs BOTH baselines in each external year AND majority historical blocks; research follow-up only',
        code_sha256=digest(__file__), helpers_sha256=digest('scripts/research/us_oracle_amplitude_rerank.py'),
        sources=source_hashes(), sql_writes=False, serving_modified=False,
        limitations=['2026 and previous rerank results already examined; not virgin holdout',
            'Current archived 1790-symbol universe, not historical PIT universe certification',
            'Historical test Jul2020-Jul2024; missing second half 2024',
            'H20 signal-close to future-close, not entry+20 sessions',
            'Overlapping outcomes; bootstrap descriptive, no portfolio PnL',
            'Probability not formally calibrated; no probability threshold for trading'])
    if (output/'protocol.json').exists() and read(output/'protocol.json') != protocol:
        raise ValueError('Resume protocol mismatch')
    atomic_json(output/'protocol.json', protocol)
    history = load_source(HISTORY, True, output)
    external = load_source(EXTERNAL, False, output)
    dates = sorted(history.date.unique())
    tasks = [('historical_oof', pd.Timestamp(dates[i]), pd.Timestamp(dates[min(i+125,len(dates)-1)]))
             for i in range(504,len(dates),126)]
    tasks += [('external_frozen', external.date.min(), external.date.max())]
    daily_parts = []
    for i, (source, start, end) in enumerate(tasks):
        directory = output/f'{source}-{start:%Y%m%d}'
        directory.mkdir(exist_ok=True)
        atomic_json(output/'progress.json',dict(status='RUNNING',phase='fit_two_stage',
            source=source,test_start=start,test_end=end,completed=i,total=len(tasks)))
        marker = directory/'done.json'
        if marker.exists():
            for name, sha in read(marker).items():
                checked(directory/name,sha)
        else:
            train = eligible_training(history,start)
            if train.date.nunique()<480:
                raise ValueError('Insufficient mature training sessions')
            source_frame = history if source=='historical_oof' else external
            test = source_frame[source_frame.date.between(start,end)].copy()
            LOG.info('Fit %s %s training=%d tail=%d test=%d',source,start,len(train),tail_target(train.future_return).sum(),len(test))
            classifier,regressor,predicted = fit_predict(train,test,args.threads)
            predicted.to_parquet(directory/'predictions.parquet',index=False)
            selected = select(predicted)
            selected.to_parquet(directory/'selected.parquet',index=False)
            metrics(selected).to_parquet(directory/'daily.parquet',index=False)
            classifier.booster_.save_model(str(directory/'classifier.txt'))
            regressor.booster_.save_model(str(directory/'conditional_mean.txt'))
            valid = eligible_training(predicted, pd.Timestamp('2100-01-01'))
            from sklearn.metrics import roc_auc_score, brier_score_loss
            y = tail_target(valid.future_return)
            atomic_json(directory/'training.json',dict(train_rows=len(train),tail_rows=int(tail_target(train.future_return).sum()),
                train_max_date=train.date.max(),train_max_available=train.oracle_available_date.max(),test_start=start,
                pool_evaluation_rows=len(valid),tail_auc=float(roc_auc_score(y,valid.tail_probability)) if np.unique(y).size==2 else None,
                brier=float(brier_score_loss(y,valid.tail_probability)) if len(valid) else None))
            names=['predictions.parquet','selected.parquet','daily.parquet','classifier.txt','conditional_mean.txt','training.json']
            atomic_json(marker,{name:digest(directory/name) for name in names})
        daily=pd.read_parquet(directory/'daily.parquet')
        daily['source'],daily['block']=source,str(start.date())
        daily_parts.append(daily)
    daily=pd.concat(daily_parts,ignore_index=True)
    daily['year']=daily.date.dt.year
    daily.to_parquet(output/'daily.parquet',index=False)
    annual,blocks,report=paired_summary(daily)
    annual.to_parquet(output/'annual.parquet',index=False)
    blocks.to_parquet(output/'blocks.parquet',index=False)
    report.update(status='COMPLETED_RESEARCH_ONLY',limitations=protocol['limitations'],sql_writes=False,serving_modified=False)
    atomic_json(output/'report.json',report)
    atomic_json(output/'progress.json',dict(status='COMPLETED',completed=len(tasks),total=len(tasks),verdicts=report['verdicts']))
    LOG.info('Two-stage tail experiment completed: %s %s',output,report['verdicts'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--threads',type=int,default=4)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    try:
        run(args)
    except Exception as exc:
        if args.output.exists():
            atomic_json(args.output/'progress.json',dict(status='FAILED',error=str(exc)))
        raise


if __name__=='__main__':
    main()
