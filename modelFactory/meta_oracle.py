"""Research-only Meta Oracle, stages A/B. Never loads the shadow holdout."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.dataset import build_feature_matrix, load_oracle_targets
from modelFactory.oracle_opening_volume_ablation import E20CConfig, build_folds

LOG = logging.getLogger(__name__)
SCORES = ['directional_oracle_proba_extreme', 'directional_oracle_extreme_pct']


@dataclass(frozen=True)
class MetaConfig:
    horizon: int = 20
    minimum_train_sessions: int = 504
    test_sessions: int = 126
    maximum_folds: int = 12
    seed: int = 20260914
    threads: int = 4
    iterations: int = 300
    bootstrap_samples: int = 2000


def assemble(gate: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """Admission OOF precedes label-quality filtering; target is never rebuilt."""
    gate = gate.copy()
    gate['date'] = pd.to_datetime(gate['date']).dt.normalize()
    gate['symbol'] = gate['symbol'].astype(str).str.upper()
    if gate.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate Oracle observations')
    admitted = gate[gate.directional_oracle_oof_available.fillna(False)].copy()
    labels = labels.rename(columns={'prediction_date': 'date'}).copy()
    labels['date'] = pd.to_datetime(labels['date']).dt.normalize()
    labels['oracle_available_date'] = pd.to_datetime(labels['oracle_available_date'])
    labels = labels[labels.target_quality_valid.eq(1)]
    panel = admitted.merge(labels, on=['date', 'symbol'], validate='one_to_one')
    if not panel.oracle_extreme10.isin([0, 1]).all():
        raise ValueError('Invalid authoritative target')
    return panel


def training_rows(panel, train_dates, test_start):
    return panel[panel.date.isin(train_dates) & panel.oracle_available_date.lt(test_start)]


def keep_quota(panel: pd.DataFrame, score: str, quotas: pd.Series) -> pd.DataFrame:
    """Stable symbol tie-break; floor(0.8*N) is shared by every comparator."""
    ordered = panel.sort_values(['date', score, 'symbol'], ascending=[True, False, True])
    rank = ordered.groupby('date').cumcount()
    return ordered[rank.lt(ordered.date.map(quotas))]


def precision(frame):
    return float(frame.groupby('date').oracle_extreme10.mean().mean())


def bootstrap_delta(values, config):
    clean = values.dropna().to_numpy(float)
    if len(clean) < 2:
        return [None, None]
    rng = np.random.default_rng(config.seed)
    # Moving blocks retain dependence induced by overlapping H20 labels.
    block = min(config.horizon + 1, len(clean))
    samples = []
    for _ in range(config.bootstrap_samples):
        starts = rng.integers(len(clean), size=int(np.ceil(len(clean) / block)))
        indices = np.concatenate([(s + np.arange(block)) % len(clean) for s in starts])[:len(clean)]
        samples.append(clean[indices].mean())
    return list(map(float, np.quantile(samples, [.025, .975])))


def evaluate(panel, feature_columns, config):
    fold_config = E20CConfig(
        minimum_train_sessions=config.minimum_train_sessions,
        test_sessions=config.test_sessions, step_sessions=config.test_sessions,
        embargo_sessions=config.horizon, maximum_folds=config.maximum_folds,
    )
    folds = build_folds(panel.date, fold_config)
    outputs, metrics = [], []
    rng = np.random.default_rng(config.seed)
    for fold in folds:
        train_all = training_rows(panel, fold['train_dates'], fold['test_start'])
        train = train_all[train_all.directional_oracle_eligible.fillna(False)]
        test_all = panel[panel.date.isin(fold['test_dates'])].copy()
        test = test_all[test_all.directional_oracle_eligible.fillna(False)].copy()
        if len(train) < 2000 or train.oracle_extreme10.nunique() != 2:
            continue
        assert train.oracle_available_date.max() < fold['test_start']
        test['fold'] = fold['fold']
        families = [('f0', SCORES)]
        if feature_columns:
            families.append(('f1', SCORES + feature_columns))
        for family, columns in families:
            for kind in ['logistic', 'catboost']:
                name = f'{family}_{kind}'
                models = {
                    'logistic': make_pipeline(SimpleImputer(strategy='median', add_indicator=True),
                                             StandardScaler(), LogisticRegression(max_iter=1000, C=1)),
                    'catboost': CatBoostClassifier(iterations=config.iterations, depth=5,
                        learning_rate=.03, verbose=False, random_seed=config.seed,
                        thread_count=config.threads, allow_writing_files=False),
                }
                x = train[columns].replace([np.inf, -np.inf], np.nan)
                xt = test[columns].replace([np.inf, -np.inf], np.nan)
                model = models[kind]
                y = train.oracle_extreme10.astype(int)
                weights = 1 / train.groupby('date').date.transform('size')
                weights = weights / weights.mean()
                if kind == 'catboost':
                    medians = x.median().fillna(0)
                    model.fit(x.fillna(medians), y, sample_weight=weights)
                    p = model.predict_proba(xt.fillna(medians))[:, 1]
                else:
                    model.fit(x, y, logisticregression__sample_weight=weights)
                    p = model.predict_proba(xt)[:, 1]
                test[name] = p
                metrics.append({'fold': fold['fold'], 'model': name,
                    'train_end': str(train.date.max()), 'available_end': str(train.oracle_available_date.max()),
                    'test_start': str(fold['test_start']), 'test_end': str(fold['test_end']),
                    'train_rows': len(train), 'test_rows': len(test),
                    'auc': roc_auc_score(test.oracle_extreme10, p),
                    'pr_auc': average_precision_score(test.oracle_extreme10, p),
                    'brier': brier_score_loss(test.oracle_extreme10, p),
                    'log_loss': log_loss(test.oracle_extreme10, p)})
        test['random_score'] = rng.random(len(test))
        placebo_y = train.groupby('date').oracle_extreme10.transform(
            lambda values: rng.permutation(values.to_numpy()))
        placebo = make_pipeline(SimpleImputer(strategy='median', add_indicator=True),
                                StandardScaler(), LogisticRegression(max_iter=1000, C=1))
        placebo.fit(train[SCORES], placebo_y)
        test['placebo_shuffle'] = placebo.predict_proba(test[SCORES])[:, 1]
        if feature_columns:
            inverse = CatBoostClassifier(iterations=config.iterations, depth=5,
                learning_rate=.03, verbose=False, random_seed=config.seed,
                thread_count=config.threads, allow_writing_files=False)
            x = train_all[feature_columns].replace([np.inf, -np.inf], np.nan)
            medians = x.median().fillna(0)
            inverse.fit(x.fillna(medians), 1 - train_all.oracle_extreme10.astype(int))
            test['inverse_control'] = 1 - inverse.predict_proba(
                test[feature_columns].replace([np.inf, -np.inf], np.nan).fillna(medians))[:, 1]
        # TOP16 comparator uses the complete admitted OOF universe, not a rebuilt TOP20.
        quotas = (test.groupby('date').size() * .8).astype(int)
        direct = keep_quota(test_all, SCORES[0], quotas)
        direct_daily = direct.groupby('date').oracle_extreme10.mean()
        test['direct_top16_precision'] = test.date.map(direct_daily)
        outputs.append(test)
        LOG.info('meta fold=%s train=%s test=%s complete', fold['fold'], len(train), len(test))
    if not outputs:
        raise ValueError('No trainable Meta Oracle folds')
    return pd.concat(outputs, ignore_index=True), pd.DataFrame(metrics)


def selection_policies(scored):
    policies = {'oracle_score_keep80': SCORES[0], 'random_keep80': 'random_score'}
    policies.update({c: c for c in scored if c.startswith(('f0_', 'f1_'))})
    policies['placebo_shuffle'] = 'placebo_shuffle'
    if 'inverse_control' in scored:
        policies['inverse_control'] = 'inverse_control'
    return policies


ORACLE_BAND_LABELS = ['80-85%', '85-90%', '90-95%', '95-100%']


def oracle_band_ids(percentiles):
    """Fixed universe percentiles, left-inclusive; percentile 1 belongs to band 3."""
    values = pd.to_numeric(percentiles, errors='coerce')
    if not values.between(.8, 1).all():
        raise ValueError('Oracle TOP20 band diagnostic requires finite percentiles in [0.8, 1.0]')
    return pd.cut(values, [.8, .85, .9, .95, np.nextafter(1., np.inf)],
                  labels=[0, 1, 2, 3], right=False).astype('int64')


def oracle_band_diagnostics(scored):
    work = scored.assign(oracle_band=oracle_band_ids(scored[SCORES[1]]))
    rows = []
    for name, score in selection_policies(scored).items():
        for band, group in work.groupby('oracle_band'):
            two_classes = group.oracle_extreme10.nunique() == 2
            rows.append({'variant': name, 'oracle_band': int(band),
                'oracle_band_label': ORACLE_BAND_LABELS[int(band)],
                'events': len(group), 'dates': group.date.nunique(),
                'true_extremes': int(group.oracle_extreme10.sum()),
                'precision_equal_date': precision(group),
                'auc_valid': bool(two_classes),
                'auc': roc_auc_score(group.oracle_extreme10, group[score]) if two_classes else np.nan})
    return pd.DataFrame(rows)


def refresh_oracle_bands(run_path):
    """Refresh only derived bands; never train, load DB or rewrite primary reports."""
    run_path = Path(run_path)
    candidate_path = run_path / 'candidates.parquet'
    scored = pd.read_parquet(candidate_path)
    scored['date'] = pd.to_datetime(scored.date)
    bands = oracle_band_diagnostics(scored)
    bands.to_csv(run_path / 'oracle_band_metrics.csv', index=False)
    metadata = {'diagnostic_version': 2, 'refreshed_at': datetime.now(UTC).isoformat(),
        'candidates_sha256': hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
        'bands': ORACLE_BAND_LABELS, 'intervals': '[0.80,0.85), [0.85,0.90), [0.90,0.95), [0.95,1.00]',
        'primary_reports_unchanged': True, 'retrained': False}
    (run_path / 'oracle_band_diagnostics.json').write_text(
        json.dumps(metadata, indent=2), encoding='utf-8')
    return bands


def report_selections(scored, config):
    quotas = (scored.groupby('date').size() * .8).astype(int)
    policies = selection_policies(scored)
    baseline = keep_quota(scored, SCORES[0], quotas)
    baseline_daily = baseline.groupby('date').oracle_extreme10.mean()
    rows, periods, buckets = [], [], []
    for name, score in policies.items():
        selected = keep_quota(scored, score, quotas)
        daily = selected.groupby('date').oracle_extreme10.mean()
        delta = daily - baseline_daily
        removed = scored.drop(selected.index)
        fp = int(removed.oracle_extreme10.eq(0).sum())
        tp = int(removed.oracle_extreme10.eq(1).sum())
        ci = bootstrap_delta(delta, config)
        rows.append({'variant': name, 'retention': len(selected) / len(scored),
            'precision_equal_date': precision(selected),
            'precision_observation': float(selected.oracle_extreme10.mean()),
            'd1': float(selected.oracle_decile.eq(1).mean()),
            'd10': float(selected.oracle_decile.eq(10).mean()),
            'lift_vs_oracle_keep80': float(delta.mean()), 'ci95_low': ci[0], 'ci95_high': ci[1],
            'lift_vs_direct_top16': float((daily - scored.groupby('date').direct_top16_precision.first()).mean()),
            'fp_removed': fp, 'tp_removed': tp, 'removal_efficiency': fp / tp if tp else None,
            'true_extremes_retained': float(selected.oracle_extreme10.sum() / scored.oracle_extreme10.sum()),
            'mean_abs_return': float(selected.future_return.abs().mean()),
            'candidates_per_date': float(selected.groupby('date').size().mean()),
            'unique_symbols': selected.symbol.nunique(),
            'symbol_hhi': float((selected.symbol.value_counts(normalize=True) ** 2).sum())})
        for grouping in ['fold', 'year']:
            for key, group in scored.assign(year=scored.date.dt.year).groupby(grouping):
                dates = group.date.unique()
                lift = delta.reindex(dates).mean()
                periods.append({'variant': name, 'grouping': grouping, 'period': key, 'lift': lift})
        rank = scored.groupby('date')[score].rank(method='first', pct=True)
        work = scored.assign(bucket=np.ceil(rank * 10).astype(int))
        for bucket, group in work.groupby('bucket'):
            buckets.append({'variant': name, 'bucket': bucket, 'precision': precision(group), 'events': len(group)})
    return pd.DataFrame(rows), pd.DataFrame(periods), pd.DataFrame(buckets), oracle_band_diagnostics(scored)


def decide(comparisons, periods, buckets, stage):
    if stage == 'a':
        return {'verdict': 'CONTROL_ONLY', 'promotion_authorized': False}
    primary = comparisons.set_index('variant').loc['f1_catboost']
    random = comparisons.set_index('variant').loc['random_keep80']
    stability = periods[periods.variant.eq('f1_catboost')]
    curve = buckets[buckets.variant.eq('f1_catboost')].sort_values('bucket')
    gates = {
        'positive_incremental_lift': primary.lift_vs_oracle_keep80 > 0,
        'significant_incremental_lift': pd.notna(primary.ci95_low) and primary.ci95_low > 0,
        'beats_direct_top16': primary.lift_vs_direct_top16 > 0,
        'beats_random': primary.precision_equal_date > random.precision_equal_date,
        'positive_fold_ratio': float(stability[stability.grouping.eq('fold')].lift.gt(0).mean()) >= .6,
        'positive_year_ratio': float(stability[stability.grouping.eq('year')].lift.gt(0).mean()) >= .6,
        'bucket_monotonicity': float(curve.precision.diff().dropna().ge(0).mean()) >= .7,
    }
    gates = {key: bool(value) for key, value in gates.items()}
    verdict = 'GO_RESEARCH' if all(gates.values()) else (
        'WEAK_SIGNAL' if gates['positive_incremental_lift'] else 'NO_GO')
    return {'verdict': verdict, 'gates': gates, 'promotion_authorized': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-id', default='model-factory-20260909051302-323684')
    parser.add_argument('--stage', choices=['a', 'b'], default='a')
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--output-root', type=Path, default=Path('artifacts/research/meta_oracle'))
    parser.add_argument('--refresh-bands', type=Path, help='Recompute bands from an existing run without training')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.refresh_bands:
        bands = refresh_oracle_bands(args.refresh_bands)
        print(f'Oracle band diagnostics refreshed: {args.refresh_bands} ({len(bands)} rows)')
        return
    root = Path('artifacts/models') / args.batch_id
    gate_path = root / '_oracle_oof_gate.parquet'
    gate = pd.read_parquet(gate_path)
    engine = get_sqlalchemy_engine()
    panel = assemble(gate, load_oracle_targets(engine, args.batch_id, 20))
    columns = []
    if args.stage == 'b':
        profile = json.loads((root / 'oracle/feature_profile.json').read_text(encoding='utf-8'))
        columns = profile['feature_columns']
        membership = gate[['date', 'symbol']].copy()
        features = build_feature_matrix(engine, sorted(membership.symbol.unique()),
            start_date=str(pd.to_datetime(gate.date).min().date()),
            end_date=str(pd.to_datetime(gate.date).max().date()), feature_set=profile['feature_set'],
            generator_options=profile['generator_options'], membership=membership)
        panel = panel.merge(features[['date', 'symbol'] + columns],
                            on=['date', 'symbol'], validate='one_to_one')
    config = MetaConfig(threads=args.threads)
    scored, metrics = evaluate(panel, columns, config)
    comparisons, periods, buckets, bands = report_selections(scored, config)
    out = args.output_root / f'meta-oracle-{args.stage}-{datetime.now(UTC):%Y%m%d%H%M%S}'
    out.mkdir(parents=True, exist_ok=False)
    scored.to_parquet(out / 'candidates.parquet', index=False)
    for name, frame in [('fold_metrics', metrics), ('veto_comparison', comparisons),
                        ('yearly_metrics', periods), ('meta_decile_metrics', buckets), ('oracle_band_metrics', bands)]:
        frame.to_csv(out / f'{name}.csv', index=False)
    report = {'research_only': True, 'production_change': False, 'stage': args.stage,
        'batch_id': args.batch_id, 'config': asdict(config), 'features': columns,
        'gate_sha256': hashlib.sha256(gate_path.read_bytes()).hexdigest(),
        'holdout_loaded': False, **decide(comparisons, periods, buckets, args.stage),
        'comparisons': comparisons.to_dict('records'),
        'deferred': ['F2 dedicated features', 'M3 weighting', 'M6 nested calibration', 'M8 absolute target', 'F3 new sources'],
        'quota_rounding': 'floor(0.8 * quality-valid TOP20 count)',
        'direct_top16_note': 'matched daily count on full quality-valid OOF universe'}
    (out / 'report.json').write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
    (out / 'report.md').write_text('# Meta Oracle\n\nResearch only; no promotion.\n\n' + comparisons.to_string(index=False), encoding='utf-8')
    print(f'Meta Oracle terminé: {out}')


if __name__ == '__main__':
    main()
