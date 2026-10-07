"""Paired H20 retraining on immutable pre/post numerical-audit caches.

Research artifacts only. Never call persist_oos, build_labels or serving. SQL
connections are read-only. Cross-sectional ranks precede future-label filtering.
"""
from __future__ import annotations

import argparse
import gc
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import event, text

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.train import roc_auc
from modelFactory.oracle.walk_forward import build_folds_adaptive
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest
from scripts.research.us_oracle_h20_dataset_audit import readonly_begin, restore_ranks

LOG = logging.getLogger(__name__)
CHANGED_FEATURES = {
    'beta_252', 'alpha_252', 'r_squared_252', 'momentum_252_vs_market',
    'momentum_20_div_vol_20', 'momentum_60_div_vol_60',
    'rsi_14_div_volatility_20', 'intraday_range_div_atr_14',
    'log_return_div_intraday_range', 'relative_strength_60_div_market_volatility',
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def validate_pair(before, after):
    old, new = read_json(before / 'protocol.json'), read_json(after / 'protocol.json')
    for key in ('batch_id', 'horizon', 'start', 'end', 'universe_sha256',
                'symbols', 'features', 'chunk_size', 'profile_sha256', 'metadata_sha256'):
        if old[key] != new[key]:
            raise ValueError(f'Paired audit mismatch: {key}')
    if new['horizon'] != 20:
        raise ValueError('H20 required')
    manifests = {}
    for name, root in [('legacy', before), ('corrected', after)]:
        report = read_json(root / 'report.json')
        if report['status'] != 'COMPLETED_READ_ONLY_AUDIT':
            raise ValueError('Completed audits required')
        if report['missing_symbols'] or any(y['nonfinite_features'] for y in report['yearly']):
            raise ValueError('Missing symbols or nonfinite audited features')
        if any(v['current_universe'] for y in report['yearly']
               for v in y['labels']['checks'].values()):
            raise ValueError('Label audit violations')
        paths = sorted(root.glob('features-*.parquet'))
        expected = (new['symbols'] + new['chunk_size'] - 1) // new['chunk_size']
        if len(paths) != expected:
            raise ValueError('Incomplete feature shards')
        manifests[name] = []
        for path in paths:
            checksum = digest(path)
            if read_json(path.with_suffix('.json'))['sha256'] != checksum:
                raise ValueError(f'Feature hash mismatch: {path}')
            manifests[name].append({'file': path.name, 'sha256': checksum})
    # The treatment may alter ONLY the ten corrected base features. Check every
    # unmodified value, not merely the row count, before any training starts.
    for item in manifests['legacy']:
        previous = pd.read_parquet(before / item['file'])
        current = pd.read_parquet(after / item['file'])
        unchanged = [c for c in previous if c not in CHANGED_FEATURES]
        if list(previous.columns) != list(current.columns) or not previous[unchanged].equals(current[unchanged]):
            raise ValueError(f'Unexpected paired data change: {item["file"]}')
    return new, manifests


def merge_targets(features, labels):
    """Features/ranks see the entire observable pool, including invalid outcomes."""
    if labels.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate labels')
    data = features.merge(labels, on=['date', 'symbol'], how='left', validate='one_to_one')
    valid = (data.target_quality_valid.eq(1) & data.oracle_available_date.gt(data.date)
             & data.oracle_extreme10.isin([0, 1])
             & data.oracle_decile.between(1, 10)
             & np.isfinite(pd.to_numeric(data.future_return, errors='coerce')))
    for column in ('oracle_extreme10', 'future_return', 'oracle_decile'):
        data[column] = data[column].where(valid)
    return data.sort_values(['date', 'symbol']).reset_index(drop=True)


def partition_indices(data, fold):
    labeled = data.oracle_extreme10.notna()
    train = (data.date.isin(fold['train_dates']) & labeled
             & data.oracle_available_date.lt(pd.Timestamp(fold['val_start'])))
    val = (data.date.isin(fold['val_dates']) & labeled
           & data.oracle_available_date.lt(pd.Timestamp(fold['t_start'])))
    test = data.date.isin(fold['test_dates'])
    if (data.loc[train, 'date'].max() >= pd.Timestamp(fold['val_start'])
            or data.loc[val, 'date'].max() >= pd.Timestamp(fold['t_start'])):
        raise ValueError('Temporal overlap')
    if not train.any() or not val.any() or not test.any():
        raise ValueError('Empty partition')
    return tuple(np.flatnonzero(mask.to_numpy()) for mask in (train, val, test))


def daily_metrics(predictions):
    """TOP20 is ranked before checking future outcome availability. Ties: symbol."""
    result = []
    for day, group in predictions.groupby('date', sort=True):
        n = len(group)
        if n < 20:
            raise ValueError('Daily research pool smaller than 20')
        count = max(1, int(np.ceil(.20 * n)))
        oracle = group.sort_values(['score', 'symbol'], ascending=[False, True]).head(count)
        atr = group.sort_values(['atr20_pct', 'symbol'], ascending=[False, True]).head(count)
        intersection = oracle[oracle.symbol.isin(atr.symbol)]
        for policy, selected in [('ORACLE_TOP20', oracle), ('ATR_TOP20', atr),
                                 ('ORACLE_AND_ATR_TOP20', intersection)]:
            evaluated = selected.dropna(subset=['oracle_extreme10', 'future_return', 'oracle_decile'])
            result.append(dict(date=day, fold_start=group.fold_start.iloc[0], policy=policy,
                pool_count=n, selected_count=len(selected), evaluated_count=len(evaluated),
                coverage=len(evaluated) / len(selected) if len(selected) else None,
                precision=float(evaluated.oracle_extreme10.mean()) if len(evaluated) else None,
                d1_pct=float(evaluated.oracle_decile.eq(1).mean()) if len(evaluated) else None,
                d10_pct=float(evaluated.oracle_decile.eq(10).mean()) if len(evaluated) else None,
                mean_abs_return=float(evaluated.future_return.abs().mean()) if len(evaluated) else None,
                mean_return=float(evaluated.future_return.mean()) if len(evaluated) else None))
    return pd.DataFrame(result)


def paired_summary(legacy, corrected, repetitions=1000):
    keys = ['date', 'policy']
    if legacy.duplicated(keys).any() or corrected.duplicated(keys).any():
        raise ValueError('Overlapping OOF test dates')
    pair = legacy.merge(corrected, on=keys, suffixes=('_legacy', '_corrected'),
                        how='outer', indicator=True, validate='one_to_one')
    if not pair._merge.eq('both').all():
        raise ValueError('Unpaired OOF dates')
    rows = []
    for policy, group in pair.groupby('policy'):
        group = group.sort_values('date')
        delta = (group.precision_corrected - group.precision_legacy).dropna().to_numpy()
        rng = np.random.default_rng(42)
        # Moving blocks of 20 sessions: H20 adjacent outcomes overlap strongly.
        boot = []
        if len(delta):
            block = min(20, len(delta))
            offsets = np.arange(block)
            for _ in range(repetitions):
                starts = rng.integers(0, len(delta) - block + 1,
                                      size=int(np.ceil(len(delta) / block)))
                sample = delta[(starts[:, None] + offsets).ravel()[:len(delta)]]
                boot.append(float(sample.mean()))
        rows.append(dict(policy=policy, days=len(group),
            precision_legacy=float(group.precision_legacy.mean()),
            precision_corrected=float(group.precision_corrected.mean()),
            delta_precision_pp=float(delta.mean() * 100) if len(delta) else None,
            descriptive_block20_ci_pp=[float(x * 100) for x in np.quantile(boot, [.025, .975])] if boot else None,
            mean_abs_return_legacy=float(group.mean_abs_return_legacy.mean()),
            mean_abs_return_corrected=float(group.mean_abs_return_corrected.mean()),
            coverage_legacy=float(group.coverage_legacy.mean()),
            coverage_corrected=float(group.coverage_corrected.mean())))
    pair = pair.drop(columns='_merge')
    pair['year'] = pd.to_datetime(pair.date).dt.year
    pair['delta_precision_pp'] = (pair.precision_corrected - pair.precision_legacy) * 100
    annual = pair.groupby(['year', 'policy']).agg(
        days=('date', 'size'), precision_legacy=('precision_legacy', 'mean'),
        precision_corrected=('precision_corrected', 'mean'),
        delta_precision_pp=('delta_precision_pp', 'mean')).reset_index()
    return rows, annual, pair


def fit_pair_member(data, columns, fold, threads):
    import lightgbm as lgb

    train, val, test = partition_indices(data, fold)
    y = data.oracle_extreme10.iloc[train].astype(int)
    if y.nunique() < 2 or data.oracle_extreme10.iloc[val].nunique() < 2:
        raise ValueError('Constant train/validation target')
    # Same effective Oracle trainer, NOT CLI Per-Symbol LightGBM parameters.
    params = dict(objective='binary', metric='auc', verbosity=-1,
        learning_rate=.05, num_leaves=31, min_data_in_leaf=50,
        feature_fraction=.8, bagging_fraction=.8, bagging_freq=1,
        scale_pos_weight=float(y.eq(0).sum() / max(1, y.eq(1).sum())),
        seed=42, num_threads=threads)
    dtrain = lgb.Dataset(data.iloc[train][columns].astype(float), label=y)
    dvalid = lgb.Dataset(data.iloc[val][columns].astype(float),
                         label=data.oracle_extreme10.iloc[val].astype(int), reference=dtrain)
    model = lgb.train(params, dtrain, num_boost_round=400, valid_sets=[dvalid],
        callbacks=[lgb.early_stopping(20, verbose=False)])
    prediction = data.iloc[test][['date', 'symbol', 'oracle_extreme10', 'oracle_decile',
                                 'future_return', 'atr20_pct']].copy()
    prediction['score'] = model.predict(data.iloc[test][columns].astype(float), num_threads=threads)
    prediction['fold_start'] = fold['t_start']
    valid = prediction.dropna(subset=['oracle_extreme10'])
    metrics = dict(fold_start=fold['t_start'], fold_end=fold['t_end'], val_start=fold['val_start'],
        train_rows=len(train), val_rows=len(val), test_rows=len(test),
        train_max_available=str(data.oracle_available_date.iloc[train].max()),
        val_max_available=str(data.oracle_available_date.iloc[val].max()),
        best_iteration=model.best_iteration,
        auc=roc_auc(valid.oracle_extreme10.to_numpy(), valid.score.to_numpy()))
    return model, prediction, metrics


def run(args):
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / 'progress.json', dict(status='RUNNING', phase='validate_cached_pair'))
    audit, manifests = validate_pair(args.before, args.after)
    bid = audit['batch_id']
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    if engine.url.database != 'alpha_trade':
        raise ValueError('US database required')
    event.listen(engine, 'begin', readonly_begin)
    with engine.connect() as conn:
        metadata = conn.execute(text('SELECT metadata_json FROM model_training_batch WHERE batch_id=:bid'),
                                dict(bid=bid)).scalar_one()
    cli = json.loads(metadata)['cli_options']
    settings = {key: cli[key] for key in ('training_start_date', 'training_end_date',
        'wf_min_train_size', 'wf_val_size', 'wf_test_size', 'wf_step_size', 'wf_max_splits')}
    if (settings['training_start_date'], settings['training_end_date']) != (audit['start'], audit['end']):
        raise ValueError('Audit/training period mismatch')
    champions = Path('artifacts/models/oracle/champions') / bid / 'oracle_champions.json'
    expected_starts = [f['t_start'] for f in read_json(champions)]
    protocol = dict(reference_batch=bid, horizon=20, before=str(args.before), after=str(args.after),
        universe_sha256=audit['universe_sha256'], symbols=audit['symbols'], features=audit['features'],
        audit_protocol_hashes=[digest(root / 'protocol.json') for root in (args.before, args.after)],
        manifests=manifests, settings=settings, expected_fold_starts=expected_starts,
        trainer=dict(seed=42, rounds=400, early_stopping=20, threads=args.threads,
                     learning_rate=.05, num_leaves=31, min_data_in_leaf=50,
                     feature_fraction=.8, bagging_fraction=.8, bagging_freq=1),
        code_sha256=digest(__file__), sql_writes=False, serving_modified=False,
        calibration='none', selection_pct=.20, atr='atr20_pct', label_universe='original_batch_unchanged',
        limitations=['Historical OOF, not virgin holdout or PnL',
            'Current cleaned universe and current price history, not historical universe PIT certification',
            '2025/2026 external confirmation is a separate pending phase'])
    path = output / 'protocol.json'
    if path.exists() and read_json(path) != protocol:
        raise ValueError('Resume protocol mismatch')
    atomic_json(path, protocol)
    labels_path = output / 'labels.parquet'
    labels_marker = output / 'labels.json'
    if labels_marker.exists():
        if digest(labels_path) != read_json(labels_marker)['sha256']:
            raise ValueError('Label cache mismatch')
        labels = pd.read_parquet(labels_path)
    else:
        with engine.connect() as conn:
            labels = pd.read_sql(text('''SELECT prediction_date AS date,symbol,
                oracle_available_date,oracle_extreme10,oracle_decile,future_return,target_quality_valid
                FROM global_oracle_labels WHERE batch_id=:bid AND horizon=20
                AND prediction_date BETWEEN :start AND :end'''), conn,
                params=dict(bid=bid, start=audit['start'], end=audit['end']),
                parse_dates=['date', 'oracle_available_date'])
        labels.to_parquet(labels_path, index=False)
        atomic_json(labels_marker, dict(sha256=digest(labels_path), rows=len(labels)))
    engine.dispose()
    total = len(expected_starts) * 2
    completed = 0
    for arm, root in [('legacy', args.before), ('corrected', args.after)]:
        atomic_json(output / 'progress.json', dict(status='RUNNING', phase='load_features', arm=arm,
                                                  completed=completed, total=total))
        parts = [pd.read_parquet(root / item['file']) for item in manifests[arm]]
        frame = pd.concat(parts, ignore_index=True)
        del parts
        frame = restore_ranks(frame, audit['features'])
        data = merge_targets(frame, labels)
        del frame
        gc.collect()
        labeled = data[data.oracle_extreme10.notna()][['date', 'oracle_available_date']]
        folds = build_folds_adaptive(labeled,
            min_train_dates=settings['wf_min_train_size'], val_dates=settings['wf_val_size'],
            test_dates=settings['wf_test_size'], step_dates=settings['wf_step_size'],
            max_splits=settings['wf_max_splits'], forecast_horizon=20, materialize=False)
        if [f['t_start'] for f in folds] != expected_starts:
            raise ValueError('Fold boundaries differ from reference; do not silently compare')
        del labeled
        for fold in folds:
            directory = output / arm / fold['t_start']
            directory.mkdir(parents=True, exist_ok=True)
            marker = directory / 'done.json'
            if marker.exists():
                if any(digest(directory / name) != checksum for name, checksum in read_json(marker).items()):
                    raise ValueError('Fold artifact hash mismatch')
            else:
                atomic_json(output / 'progress.json', dict(status='RUNNING', phase='train_fold',
                    arm=arm, fold_start=fold['t_start'], completed=completed, total=total))
                LOG.info('Training %s fold=%s (%d/%d)', arm, fold['t_start'], completed, total)
                model, predictions, metrics = fit_pair_member(data, audit['features'], fold, args.threads)
                model.save_model(str(directory / 'model.txt'))
                predictions.to_parquet(directory / 'predictions.parquet', index=False)
                daily_metrics(predictions).to_parquet(directory / 'daily.parquet', index=False)
                atomic_json(directory / 'metrics.json', metrics)
                atomic_json(marker, {name: digest(directory / name) for name in
                    ('model.txt', 'predictions.parquet', 'daily.parquet', 'metrics.json')})
                LOG.info('Completed %s fold=%s AUC=%s iterations=%s', arm, fold['t_start'],
                         metrics['auc'], metrics['best_iteration'])
                del model, predictions
                gc.collect()
            completed += 1
        del data
        gc.collect()
    daily = {arm: pd.concat([pd.read_parquet(output / arm / start / 'daily.parquet')
                             for start in expected_starts], ignore_index=True)
             for arm in ('legacy', 'corrected')}
    overall, annual, paired = paired_summary(daily['legacy'], daily['corrected'])
    annual.to_parquet(output / 'annual.parquet', index=False)
    paired.to_parquet(output / 'paired_daily.parquet', index=False)
    fold_metrics = {arm: [read_json(output / arm / start / 'metrics.json') for start in expected_starts]
                    for arm in ('legacy', 'corrected')}
    report = dict(status='COMPLETED_PAIRED_HISTORICAL_OOF', overall=overall,
                  annual=json.loads(annual.to_json(orient='records')),
                  folds=fold_metrics, limitations=protocol['limitations'])
    atomic_json(output / 'report.json', report)
    atomic_json(output / 'progress.json', dict(status='COMPLETED', phase='historical_oof',
                                               completed=completed, total=total))
    LOG.info('Paired numerical correction effect complete: %s', output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--threads', type=int, default=6)
    args = parser.parse_args()
    if args.threads < 1:
        parser.error('Positive thread count required')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    try:
        run(args)
    except Exception as exc:
        if args.output.is_dir():
            atomic_json(args.output / 'progress.json', dict(status='FAILED', error_type=type(exc).__name__,
                error=str(exc) if isinstance(exc, (ValueError, KeyError)) else 'See stderr.log'))
        raise


if __name__ == '__main__':
    main()
