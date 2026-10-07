"""Frozen 2025/2026 confirmation of the paired H20 numerical experiment.

Old formulas execute in private namespaces from an immutable local Git commit;
no monkeypatch, rollback, SQL write, serving replacement or retraining.
"""
from __future__ import annotations

import argparse
import ast
import gc
import hashlib
import inspect
import logging
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd
from sqlalchemy import event, text

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle import dataset as oracle_dataset
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest
from scripts.research.us_oracle_h20_dataset_audit import readonly_begin, restore_ranks
from scripts.research.us_oracle_numeric_effect import (
    CHANGED_FEATURES, daily_metrics, merge_targets, paired_summary, read_json,
)

LOG = logging.getLogger(__name__)


class PrivateImports(ast.NodeTransformer):
    def __init__(self, module, namespace):
        self.module, self.namespace = module, namespace

    def visit_ImportFrom(self, node):
        if node.module != self.module:
            return node
        if any(item.name == '*' for item in node.names):
            raise ValueError('Wildcard private binding prohibited')
        return [ast.copy_location(ast.Assign(
            targets=[ast.Name(id=item.asname or item.name, ctx=ast.Store())],
            value=ast.Subscript(value=ast.Name(id=self.namespace, ctx=ast.Load()),
                                slice=ast.Constant(item.name), ctx=ast.Load())), node)
                for item in node.names]


def legacy_compute(commit):
    """Read trusted repository source, never modify production module globals."""
    sources = {name: subprocess.check_output(['git', 'show', f'{commit}:modelFactory/{name}.py'])
               for name in ('features', 'factor_features')}
    if b'_positive_denominator_ratio' in sources['features']:
        raise ValueError('Legacy commit already contains the ratio correction')
    factor_ns = dict(__name__='modelFactory._research_old_factors', __package__='modelFactory',
                     __file__='modelFactory/factor_features.py')
    exec(compile(sources['factor_features'], '<archived-factor-features>', 'exec'), factor_ns)
    features_ns = dict(__name__='modelFactory._research_old_features', __package__='modelFactory',
                       __file__='modelFactory/features.py', _private_factors=factor_ns)
    tree = PrivateImports('modelFactory.factor_features', '_private_factors').visit(
        ast.parse(sources['features']))
    exec(compile(ast.fix_missing_locations(tree), '<archived-features>', 'exec'), features_ns)
    hashes = {name: hashlib.sha256(source).hexdigest() for name, source in sources.items()}
    return features_ns['compute_features'], hashes


def paired_builders(old_compute):
    """Both arms get copies of precisely the same loaded bars/selector frames."""
    from modelFactory import data_loader

    cache = {}
    def cached(name):
        original = getattr(data_loader, name)
        def load(*args, **kwargs):
            key = (name, repr(args[1:] if args and hasattr(args[0], 'connect') else args), repr(kwargs))
            if key not in cache:
                cache[key] = original(*args, **kwargs)
            return cache[key].copy()
        return load

    imports = {name: cached(name) for name in (
        'load_universe_bars', 'load_benchmark_bars', 'load_symbols_selector_context',
        'load_symbols_sentiment')}
    tree = PrivateImports('modelFactory.data_loader', '_private_loaders').visit(
        ast.parse(inspect.getsource(oracle_dataset.build_feature_matrix)))
    code = compile(ast.fix_missing_locations(tree), '<paired-oracle-builder>', 'exec')
    result = {}
    for arm, compute in [('legacy', old_compute), ('corrected', oracle_dataset.compute_features)]:
        namespace = {**oracle_dataset.__dict__, **imports, '_private_loaders': imports,
                     'compute_features': compute}
        exec(code, namespace)
        result[arm] = namespace['build_feature_matrix']
    return result, cache


def compare_external_features(old, new):
    unchanged = [column for column in old if column not in CHANGED_FEATURES]
    if list(old.columns) != list(new.columns) or not old[unchanged].equals(new[unchanged]):
        raise ValueError('External paired keys or untreated features differ')


def run(args):
    import lightgbm as lgb

    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    progress = lambda **kwargs: atomic_json(output / 'progress.json', dict(status='RUNNING', **kwargs))
    historical = read_json(args.training_root / 'protocol.json')
    audit = read_json(Path(historical['after']) / 'protocol.json')
    if pd.Timestamp(args.start) <= pd.Timestamp(audit['end']):
        raise ValueError('External period must follow the historical feature period')
    if pd.Timestamp(args.end) > pd.Timestamp(args.as_of) or pd.Timestamp(args.start) > pd.Timestamp(args.end):
        raise ValueError('Invalid external period/as_of')
    old_compute, old_hashes = legacy_compute(args.legacy_commit)
    symbols = sorted({symbol for path in Path(historical['after']).glob('features-*.json')
                      for symbol in read_json(path)['symbols']})
    protocol = dict(training_protocol_sha256=digest(args.training_root / 'protocol.json'),
        legacy_commit=args.legacy_commit, legacy_source_hashes=old_hashes,
        corrected_features_sha256=digest('modelFactory/features.py'),
        corrected_factors_sha256=digest('modelFactory/factor_features.py'),
        builder_sha256=digest(oracle_dataset.__file__), code_sha256=digest(__file__),
        symbols=symbols, start=args.start, end=args.end, as_of=args.as_of,
        horizon=20, frozen_fold=historical['expected_fold_starts'][-1],
        score_calibration='none', sql_writes=False, serving_modified=False,
        external_is_virgin_holdout=False, baseline_atr='atr20_pct')
    path = output / 'protocol.json'
    if path.exists() and read_json(path) != protocol:
        raise ValueError('External resume protocol mismatch')
    atomic_json(path, protocol)
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    if engine.url.database != 'alpha_trade':
        raise ValueError('US database required')
    event.listen(engine, 'begin', readonly_begin)
    builders, cache = paired_builders(old_compute)
    columns = historical['features']
    needed = list(dict.fromkeys([c for c in columns if not c.endswith('_xs_rank')]
        + [c[:-len('_xs_rank')] for c in columns if c.endswith('_xs_rank')]))
    options = {**audit['generator_options'], 'enable_cross_sectional_ranks': False}
    total = (len(symbols) + 24) // 25
    for index, offset in enumerate(range(0, len(symbols), 25)):
        marker = output / f'features-{index:03d}.json'
        if marker.exists():
            if any(digest(output / name) != checksum for name, checksum in read_json(marker).items()):
                raise ValueError('External cached feature hash mismatch')
            continue
        progress(phase='paired_external_features', completed=index, total=total)
        parts = {}
        for arm, builder in builders.items():
            # Same historical warm-up origin as training. Retain only external
            # dates after feature construction; no reset of rolling histories.
            frame = builder(engine, symbols[offset:offset+25], start_date=audit['start'],
                            end_date=args.end, generator_options=options)
            parts[arm] = frame.loc[frame.date.between(pd.Timestamp(args.start), pd.Timestamp(args.end)),
                                  ['date', 'symbol', *needed]].reset_index(drop=True)
        compare_external_features(parts['legacy'], parts['corrected'])
        hashes = {}
        for arm, frame in parts.items():
            destination = output / f'{arm}-features-{index:03d}.parquet'
            frame.to_parquet(destination, index=False)
            hashes[destination.name] = digest(destination)
        atomic_json(marker, hashes)
        LOG.info('External feature chunks %d/%d rows=%d', index+1, total, len(frame))
        del frame, parts
        cache.clear()
        gc.collect()
    labels_path = output / 'labels.parquet'
    marker = output / 'labels.json'
    if marker.exists():
        if digest(labels_path) != read_json(marker)['sha256']:
            raise ValueError('External label snapshot hash mismatch')
        labels = pd.read_parquet(labels_path)
    else:
        with engine.connect() as conn:
            labels = pd.read_sql(text('''SELECT prediction_date AS date,symbol,
                oracle_available_date,oracle_extreme10,oracle_decile,future_return,target_quality_valid
                FROM global_oracle_labels WHERE batch_id=:bid AND horizon=20
                AND prediction_date BETWEEN :start AND :end'''), conn,
                params=dict(bid=historical['reference_batch'], start=args.start, end=args.end),
                parse_dates=['date', 'oracle_available_date'])
        if labels.empty:
            raise ValueError('External labels absent; never synthesize them silently')
        labels.loc[labels.oracle_available_date.gt(pd.Timestamp(args.as_of)), 'target_quality_valid'] = 0
        labels.to_parquet(labels_path, index=False)
        atomic_json(marker, dict(sha256=digest(labels_path), rows=len(labels)))
    engine.dispose()
    # Feature preparation can run alongside training. Stop cleanly if the final
    # models are not ready; resume this exact command, no long polling daemon.
    frozen_start = historical['expected_fold_starts'][-1]
    if not all((args.training_root / arm / frozen_start / 'done.json').exists()
               for arm in ('legacy', 'corrected')):
        atomic_json(output / 'progress.json', dict(status='READY_FEATURES_WAITING_MODELS',
                                                   completed=total, total=total))
        return
    model_hashes = {}
    for arm in ('legacy', 'corrected'):
        directory = args.training_root / arm / frozen_start
        hashes = read_json(directory / 'done.json')
        model_path = directory / 'model.txt'
        if digest(model_path) != hashes['model.txt']:
            raise ValueError('Frozen model hash mismatch')
        model_hashes[arm] = hashes['model.txt']
        progress(phase='frozen_external_prediction', arm=arm)
        frame = pd.concat([pd.read_parquet(path) for path in sorted(output.glob(f'{arm}-features-*.parquet'))],
                          ignore_index=True)
        data = merge_targets(restore_ranks(frame, columns), labels)
        del frame
        if data.empty:
            raise ValueError('Empty external feature dataset')
        model = lgb.Booster(model_file=str(model_path))
        if model.feature_name() != columns:
            raise ValueError('Frozen model column mismatch')
        data['score'] = np.nan
        for offset in range(0, len(data), 50000):
            index = data.index[offset:offset+50000]
            data.loc[index, 'score'] = model.predict(data.loc[index, columns], num_threads=args.threads)
        predictions = data[['date', 'symbol', 'oracle_extreme10', 'oracle_decile',
                            'future_return', 'atr20_pct', 'score']].copy()
        predictions['fold_start'] = frozen_start
        predictions.to_parquet(output / f'{arm}-predictions.parquet', index=False)
        daily_metrics(predictions).to_parquet(output / f'{arm}-daily.parquet', index=False)
        del model, data, predictions
        gc.collect()
    overall, annual, pair = paired_summary(pd.read_parquet(output / 'legacy-daily.parquet'),
                                          pd.read_parquet(output / 'corrected-daily.parquet'))
    pair.to_parquet(output / 'paired_daily.parquet', index=False)
    annual.to_parquet(output / 'annual.parquet', index=False)
    report = dict(status='COMPLETED_FROZEN_EXTERNAL_CONFIRMATION', overall=overall,
        annual=annual.to_dict('records'), model_hashes=model_hashes,
        limitations=['2026 already inspected, not virgin holdout',
                     'Current universe/history reconstruction, not exhaustive PIT certification',
                     'No PnL or direction inference', 'Existing original-batch label universe unchanged'])
    atomic_json(output / 'report.json', report)
    atomic_json(output / 'progress.json', dict(status='COMPLETED', phase='frozen_external_confirmation'))
    LOG.info('Frozen external confirmation complete: %s', output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--training-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--legacy-commit', required=True)
    parser.add_argument('--start', default='2025-01-01')
    parser.add_argument('--end', default='2026-09-03')
    parser.add_argument('--as-of', default='2026-10-07')
    parser.add_argument('--threads', type=int, default=6)
    args = parser.parse_args()
    if args.threads < 1:
        parser.error('Positive thread count required')
    # Resolve aliases now, never use a movable HEAD when resuming.
    args.legacy_commit = subprocess.check_output(['git', 'rev-parse', args.legacy_commit], text=True).strip()
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
