"""Offline, pre-registered H20 amplitude reranking; no SQL or serving writes."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

ROOT = Path('artifacts/research/us_concentrated_replay')
HISTORY = ROOT / 'oracle-h20-numeric-effect-20261007-v1'
EXTERNAL = ROOT / 'oracle-h20-numeric-external-20261007-v1'
FEATURES = [
    'daily_return', 'intraday_range', 'overnight_gap', 'volume_ratio_20',
    'rolling_volatility_20', 'rolling_volatility_60', 'rsi_14', 'atr_14_norm',
    'sma20_distance', 'sma50_distance', 'sma100_distance', 'sma200_distance',
    'momentum_10', 'momentum_20', 'momentum_60', 'momentum_120',
    'vol_ratio_20_60', 'range_position_20', 'market_return_20',
    'market_volatility_20', 'market_trend_strength_50', 'relative_strength_20',
    'relative_strength_60', 'adx_14', 'atr_ratio_5_20', 'volume_zscore_20',
    'beta_252', 'alpha_252', 'r_squared_252', 'momentum_252_vs_market',
]
INPUTS = ['score', 'atr20_pct'] + FEATURES
PARAMS = dict(objective='lambdarank', n_estimators=200, learning_rate=.03,
    max_depth=4, num_leaves=15, min_child_samples=150,
    reg_alpha=.1, reg_lambda=1., random_state=42, verbosity=-1,
    deterministic=True, force_col_wise=True, label_gain=list(range(10)))
LOG = logging.getLogger(__name__)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def checked(path, expected):
    if digest(path) != expected:
        raise ValueError(f'Archive checksum mismatch: {path}')


def pool(frame):
    """Select using observables before considering any future label."""
    if frame.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate prediction keys')
    result = []
    for day, group in frame.groupby('date', sort=True):
        group = group[np.isfinite(group.score) & np.isfinite(group.atr20_pct)]
        if len(group) < 20:
            continue
        n = int(np.ceil(.2 * len(group)))
        oracle = group.sort_values(['score', 'symbol'], ascending=[False, True]).head(n)
        atr = group.sort_values(['atr20_pct', 'symbol'], ascending=[False, True]).head(n)
        selected = oracle[oracle.symbol.isin(atr.symbol)].copy()
        selected['pool_size'] = len(selected)
        selected['universe_size'] = len(group)
        result.append(selected)
    if not result:
        raise ValueError('Empty observable intersection')
    return pd.concat(result, ignore_index=True)


def eligible_training(data, cutoff):
    valid = (data.date.lt(cutoff) & data.oracle_available_date.lt(cutoff)
             & data.oracle_available_date.gt(data.date)
             & data.target_quality_valid.eq(1) & np.isfinite(data.future_return)
             & data.oracle_extreme10.isin([0, 1]))
    return data.loc[valid].sort_values(['date', 'symbol']).copy()


def relevance(data):
    # Absolute, sign-symmetric target. Ties share the same ordinal relevance.
    ranks = data.future_return.abs().groupby(data.date).rank(method='average', pct=True)
    return np.minimum(9, np.floor(ranks * 10)).astype(int)


def load_source(root, historical, output):
    if historical:
        protocol = read(root / 'protocol.json')
        parts = []
        for fold in protocol['expected_fold_starts']:
            directory = root / 'corrected' / fold
            checked(directory / 'predictions.parquet', read(directory / 'done.json')['predictions.parquet'])
            parts.append(pd.read_parquet(directory / 'predictions.parquet'))
        predictions = pd.concat(parts, ignore_index=True)
        feature_root = Path(protocol['after'])
        files = sorted(feature_root.glob('features-*.parquet'))
    else:
        # Reuse the published external comparison's file checksums.
        from scripts.research.us_oracle_numeric_top10 import load_pair
        frames, _ = load_pair(root, 'external_frozen')
        predictions = frames['corrected']
        feature_root = root
        files = sorted(root.glob('corrected-features-*.parquet'))
    selected = pool(predictions)
    labels_path = root / 'labels.parquet'
    checked(labels_path, read(root / 'labels.json')['sha256'])
    labels = pd.read_parquet(labels_path, columns=['date', 'symbol',
        'oracle_available_date', 'target_quality_valid'])
    selected = selected.merge(labels, on=['date', 'symbol'], how='left', validate='one_to_one')
    keys = selected[['date', 'symbol']]
    parts = []
    for i, path in enumerate(files):
        atomic_json(output / 'progress.json', dict(status='RUNNING', phase='load_features',
            source='historical_oof' if historical else 'external', shard=i + 1, shards=len(files)))
        if historical:
            expected = read(path.with_suffix('.json'))['sha256']
        else:
            marker = root / path.name.replace('corrected-features-', 'features-').replace('.parquet', '.json')
            expected = read(marker)[path.name]
        checked(path, expected)
        frame = pd.read_parquet(path, columns=['date', 'symbol'] + FEATURES)
        parts.append(keys.merge(frame, on=['date', 'symbol'], how='inner', validate='one_to_one'))
    features = pd.concat(parts, ignore_index=True)
    result = selected.merge(features, on=['date', 'symbol'], how='left', validate='one_to_one', indicator=True)
    if not result._merge.eq('both').all():
        raise ValueError('Missing feature rows in selected pool')
    result = result.drop(columns='_merge')
    if not np.isfinite(result[INPUTS].to_numpy(dtype=float)).all():
        raise ValueError('Unqualified nonfinite input features')
    return result


def selections(data):
    output = []
    for name, column in [('ORACLE', 'score'), ('ATR', 'atr20_pct'), ('AMPLITUDE', 'amplitude_score')]:
        ordered = data.sort_values(['date', column, 'symbol'], ascending=[True, False, True]).copy()
        ordered['selection_rank'] = ordered.groupby('date').cumcount() + 1
        for k in (10, 20):
            rows = ordered[ordered.selection_rank.le(k)].copy()
            rows['policy'], rows['top_n'] = name, k
            output.append(rows)
    return pd.concat(output, ignore_index=True)


def metrics(selected):
    output = []
    for (day, policy, k), rows in selected.groupby(['date', 'policy', 'top_n']):
        valid = (rows.target_quality_valid.eq(1) & np.isfinite(rows.future_return)
                 & rows.oracle_extreme10.isin([0, 1]))
        good = rows[valid]
        full = len(rows) == k and valid.all()
        amplitude = good.future_return.abs()
        output.append(dict(date=day, policy=policy, top_n=int(k), selected=len(rows),
            evaluated=len(good), missing=int((~valid).sum()), full=bool(full),
            precision=float(good.oracle_extreme10.mean()) if full else np.nan,
            mean_abs=float(amplitude.mean()) if full else np.nan,
            median_abs=float(amplitude.median()) if full else np.nan,
            abs_ge20=float(amplitude.ge(.2).mean()) if full else np.nan,
            abs_ge50=float(amplitude.ge(.5).mean()) if full else np.nan))
    return pd.DataFrame(output)


def run(args):
    import lightgbm as lgb
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    protocol = dict(target='absolute signed H20 close-to-close return; ordinal daily decile in intersection',
        inputs=INPUTS, params=PARAMS, threads=args.threads, pool='Oracle TOP20 percent intersect ATR TOP20 percent',
        top_n=[10, 20], minimum_train_sessions=504, test_sessions=126,
        purge='oracle_available_date strictly before test start', seed=42,
        selection='score descending then symbol ascending; no future-based replacements',
        primary_metrics=['precision', 'mean_abs'], secondary_metrics=['median_abs', 'abs_ge20', 'abs_ge50'],
        comparison='paired common fully evaluated sessions only',
        training_history=str(HISTORY), external=str(EXTERNAL),
        source_protocol_hashes=[digest(p / 'protocol.json') for p in (HISTORY, EXTERNAL)],
        code_sha256=digest(__file__), sql_writes=False, serving_modified=False,
        limitations=['2026 already examined, not virgin holdout', 'Current cleaned universe, not certified historical PIT universe',
            'No direction, no portfolio PnL', 'Historical OOF stops 2024-07-09; no synthetic second-half-2024',
            'H20 is signal close to future close, not twenty sessions after entry',
            'Overlapping returns and universe survivorship; archive lineage not independent price certification'],
        promotion='No automatic promotion. Both primary metrics must improve versus both baselines in each external year and majority historical blocks for follow-up.')
    if (output / 'protocol.json').exists() and read(output / 'protocol.json') != protocol:
        raise ValueError('Resume protocol mismatch')
    atomic_json(output / 'protocol.json', protocol)
    all_daily = []
    history = load_source(HISTORY, True, output)
    dates = sorted(history.date.unique())
    tasks = [('historical_oof', pd.Timestamp(dates[i]), pd.Timestamp(dates[min(i + 125, len(dates) - 1)]))
             for i in range(504, len(dates), 126)]
    external = load_source(EXTERNAL, False, output)
    tasks.append(('external_frozen', external.date.min(), external.date.max()))
    for i, (source, start, end) in enumerate(tasks):
        directory = output / f'{source}-{start:%Y%m%d}'
        directory.mkdir(exist_ok=True)
        marker = directory / 'done.json'
        atomic_json(output / 'progress.json', dict(status='RUNNING', phase='train_reranker',
            source=source, test_start=start, test_end=end, completed=i, total=len(tasks)))
        if marker.exists():
            for name, sha in read(marker).items():
                checked(directory / name, sha)
        else:
            train = eligible_training(history, start)
            if train.date.nunique() < 480:
                raise ValueError('Insufficient mature training history')
            model = lgb.LGBMRanker(**PARAMS, n_jobs=args.threads)
            LOG.info('Fit %s start=%s train=%d mature_days=%d', source, start, len(train), train.date.nunique())
            model.fit(train[INPUTS], relevance(train), group=train.groupby('date', sort=True).size().to_numpy())
            test = (history if source == 'historical_oof' else external)
            test = test[test.date.between(start, end)].copy()
            test['amplitude_score'] = model.predict(test[INPUTS])
            picked = selections(test)
            daily = metrics(picked)
            picked.to_parquet(directory / 'selected.parquet', index=False)
            daily.to_parquet(directory / 'daily.parquet', index=False)
            model.booster_.save_model(str(directory / 'model.txt'))
            atomic_json(directory / 'training.json', dict(train_rows=len(train),
                train_max_date=train.date.max(), train_max_available=train.oracle_available_date.max(), test_start=start))
            atomic_json(marker, {name: digest(directory / name) for name in
                ('selected.parquet', 'daily.parquet', 'model.txt', 'training.json')})
        daily = pd.read_parquet(directory / 'daily.parquet')
        daily['source'], daily['block'] = source, str(start.date())
        all_daily.append(daily)
    daily = pd.concat(all_daily, ignore_index=True)
    daily['year'] = daily.date.dt.year
    daily.to_parquet(output / 'daily.parquet', index=False)
    common = daily.groupby(['source', 'date', 'top_n']).full.transform('all')
    paired = daily[common].copy()
    summary = paired.groupby(['source', 'year', 'policy', 'top_n']).agg(
        days=('date', 'size'), precision=('precision', 'mean'), mean_abs=('mean_abs', 'mean'),
        median_abs=('median_abs', 'mean'), abs_ge20=('abs_ge20', 'mean'), abs_ge50=('abs_ge50', 'mean')).reset_index()
    summary.to_parquet(output / 'annual.parquet', index=False)
    comparison = []
    for (source, k), group in paired.groupby(['source', 'top_n']):
        wide = group.pivot(index='date', columns='policy', values=['precision', 'mean_abs'])
        for baseline in ('ORACLE', 'ATR'):
            deltas = wide['precision']['AMPLITUDE'] - wide['precision'][baseline]
            rng = np.random.default_rng(42)
            n, block = len(deltas), min(20, len(deltas))
            values = deltas.to_numpy()
            boot = [values[(rng.integers(0, n-block+1, size=int(np.ceil(n/block)))[:, None]
                     + np.arange(block)).ravel()[:n]].mean() for _ in range(1000)]
            comparison.append(dict(source=source, top_n=int(k), baseline=baseline, days=n,
                delta_precision_pp=float(deltas.mean()*100),
                descriptive_block20_ci_pp=[float(x*100) for x in np.quantile(boot, [.025,.975])],
                delta_mean_abs_pp=float((wide['mean_abs']['AMPLITUDE']-wide['mean_abs'][baseline]).mean()*100)))
    atomic_json(output / 'report.json', dict(status='COMPLETED_RESEARCH_ONLY',
        annual=json.loads(summary.to_json(orient='records')), paired=comparison,
        all_policy_days=len(daily), excluded_incomplete_policy_days=int((~common).sum()),
        limitations=protocol['limitations'], serving_modified=False, sql_writes=False))
    atomic_json(output / 'progress.json', dict(status='COMPLETED', completed=len(tasks), total=len(tasks)))
    LOG.info('Amplitude reranking completed: %s', output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        run(args)
    except Exception as exc:
        if args.output.exists():
            atomic_json(args.output / 'progress.json', dict(status='FAILED', error=str(exc)))
        raise


if __name__ == '__main__':
    main()
