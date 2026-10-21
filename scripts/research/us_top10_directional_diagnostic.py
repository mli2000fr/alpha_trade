"""TOP10-only directional probes, research archives only; no SQL, PnL or orders."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle_path.train import digest
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, verify_hashes
from scripts.research.us_directional_hierarchy_diagnostic import (
    ARMS, causal_training, daily_metrics, group_corrections, holm_adjust,
    target, transform_train_test,
)

LOG = logging.getLogger(__name__)
CONFIG = Path('config/research/us_top10_directional_20261018.json')
CONSTANT = 'TRAIN_PRIOR'
ORACLE = 'ORACLE_ORDER'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def top10_only(frame):
    """Allow only original ranks 1..10; never replace a missing realised label."""
    result = frame.loc[frame.oracle_rank.le(10)].copy()
    if not result.oracle_rank.isin(range(1, 11)).all():
        raise ValueError('Original integer ranks 1..10 required')
    if result.duplicated(['date', 'symbol']).any() or result.duplicated(['date', 'oracle_rank']).any():
        raise ValueError('Duplicate TOP10 keys/ranks')
    counts = result.groupby('date').oracle_rank.agg(['size', 'min', 'max'])
    if counts.empty or not (counts['size'].eq(10) & counts['min'].eq(1) & counts['max'].eq(10)).all():
        raise ValueError('Exactly the original ten ranks required for every session')
    return result.sort_values(['date', 'oracle_rank']).reset_index(drop=True)


def selection_metrics(frame, counts):
    """Rank all ten first, attach realised deciles second, keep unknowns explicit."""
    if any(type(count) is not int or not 1 <= count <= 10 for count in counts):
        raise ValueError('Selection counts must be integers in 1..10')
    result = []
    for arm in [*ARMS, ORACLE]:
        keys, ascending = (['date', 'oracle_rank'], [True, True]) if arm == ORACLE else (
            ['date', arm, 'oracle_rank'], [True, False, True])
        ranked = frame.sort_values(keys, ascending=ascending)
        position = ranked.groupby('date').cumcount()+1
        for count in counts:
            chosen = ranked.loc[position.le(count)].copy()
            good = chosen.oracle_decile.notna()
            dates = chosen.groupby('date').size().rename('selected_count')
            known = good.groupby(chosen.date).sum().rename('known_count')
            d1 = chosen.oracle_decile.eq(1).groupby(chosen.date).sum()
            d10 = chosen.oracle_decile.eq(10).groupby(chosen.date).sum()
            out = pd.DataFrame(dict(selected_count=dates, known_count=known,
                                    d1=d1/known.replace(0, np.nan), d10=d10/known.replace(0, np.nan),
                                    label_coverage=known/dates,
                                    d1_count=d1, d10_count=d10))
            out['arm'], out['selection_count'] = arm, count
            result.append(out.rename_axis('date').reset_index())
    return pd.concat(result, ignore_index=True)


def reference_metrics(frame, task, prior):
    metrics = daily_metrics(frame, task).drop(columns=['selected_d10', 'selected_d1', 'selected_label_coverage'])
    observed = target(frame, task)
    prior_loss = (observed-prior)**2
    base = prior_loss.groupby(frame.date).mean().rename('brier')
    rows = pd.DataFrame(dict(date=base.index, brier=base.to_numpy(), auc=.5, arm=CONSTANT, task=task))
    # A constant's AUC has the same evaluable dates as the common reference.
    dates = metrics.loc[metrics.arm.eq('GLOBAL_J')].set_index('date').auc
    rows['auc'] = rows.date.map(dates.notna().map({True: .5, False: np.nan}))
    return pd.concat([metrics, rows], ignore_index=True)


def block_test(differences, calendar, cfg):
    """Two-sided paired block sign flips; block means need enough sessions."""
    x = differences.dropna().sort_index()
    order = pd.Series(np.arange(len(calendar)), index=calendar)
    blocks = (order.reindex(x.index)//cfg['block_sessions']).astype(int)
    grouped = x.groupby(blocks.to_numpy())
    block_means = grouped.mean().where(grouped.count().ge(cfg['min_dates_per_block'])).dropna().to_numpy()
    if len(block_means) < cfg['min_blocks']:
        return dict(p_raw=None, blocks=len(block_means), mean_delta=float(x.mean()) if len(x) else None)
    rng = np.random.default_rng(cfg['seed'])
    observed = abs(block_means.mean())
    null = np.abs((rng.choice([-1., 1.], size=(cfg['permutations'], len(block_means))) * block_means).mean(axis=1))
    return dict(p_raw=float((1+(null >= observed-1e-15).sum())/(1+len(null))), blocks=len(block_means), mean_delta=float(x.mean()))


def period_pass(row, cfg):
    """Predeclared research gate, not calibrated trading or economic validation."""
    values = [row.get(k) for k in ('auc', 'auc_gain', 'brier_gain', 'target_lift', 'opposite_lift')]
    return bool(all(v is not None and np.isfinite(v) for v in values)
                and row['auc'] >= cfg['validation_min_auc']
                and row['auc_gain'] >= cfg['min_auc_gain'] and row['brier_gain'] > 0
                and row['target_lift'] >= cfg['min_target_lift']
                and row['opposite_lift'] <= cfg['max_opposite_tail_lift']
                and row['dates'] >= cfg['min_evaluable_dates'])


def protocol_and_source(output, cfg, config):
    root = Path(cfg['source'])
    report = read(root/'report.json')
    if report['status'] != 'COMPLETED_EXPLORATORY' or not report['source_hashes_verified_after_calculation']:
        raise ValueError('Completed and source-verified archive required')
    old = read(root/'protocol.json')
    verify_hashes(Path('.'), old['source_hashes'])
    verify_hashes(root, read(root/'population-manifest.json')['files'])
    if digest(root/'protocol.json') != report['protocol_sha256']:
        raise ValueError('Source protocol differs from its report')
    paths = [Path(__file__), config, Path('scripts/research/us_directional_hierarchy_diagnostic.py'),
             Path('scripts/research/oracle_path_confirmation.py'),
             Path('scripts/research/us_concentrated_historical_tapes.py'),
             root/'report.json', root/'protocol.json', root/'population-manifest.json', root/'population.parquet']
    frozen = dict(config=cfg, source_hashes={str(p): digest(p) for p in paths},
                  training_scope='ORIGINAL_ORACLE_RANK_1_TO_10_ONLY', test_scope='SAME_ORIGINAL_TEN_INCLUDING_MIDDLE_DECILES',
                  no_sql=True, no_provider_calls=True, no_broker_calls=True, no_pnl=True,
                  no_serving_model_changes=True, current_sectors_non_pit=True,
                  already_observed_periods=True, selection_after_previous_TOP20_experiment=True,
                  novel_independent_holdout=False)
    marker = output/'protocol.json'
    if marker.exists() and read(marker) != frozen:
        raise ValueError('Changed sources/protocol: choose a new output directory')
    atomic_json(marker, frozen)
    population = top10_only(pd.read_parquet(root/'population.parquet'))
    if population.date.max() > pd.Timestamp(cfg['decision_end']):
        raise ValueError('Unexpected decision tail')
    population.to_parquet(output/'top10-population.parquet', index=False)
    return frozen, population


def fit_all(population, output, cfg):
    base = cfg['base_features']
    path = base + [f'{c}_delta_{w}' for c in base for w in cfg['trajectory_sessions']]
    counts = [cfg['primary_selection_count'], *cfg['secondary_selection_counts']]
    metrics, selections, evidence, support = [], [], [], []
    tasks = [*cfg['practical_tasks'], cfg['diagnostic_task']]
    for year in [cfg['validation_year'], *cfg['confirmation_years']]:
        train_all = causal_training(population, f'{year}-01-01')
        test = population.loc[population.date.dt.year.eq(year)].reset_index(drop=True)
        if test.empty:
            raise ValueError(f'Missing planned period {year}')
        for task in tasks:
            atomic_json(output/'progress.json', dict(status='RUNNING', phase='top10_training', year=year, task=task))
            train = train_all.assign(_target=target(train_all, task)).dropna(subset=['_target']).reset_index(drop=True)
            if train._target.nunique() != 2 or not train.oracle_rank.le(10).all():
                raise ValueError('Invalid TOP10 training population')
            pred = test[['date', 'symbol', 'oracle_rank', 'oracle_decile', 'oracle_available_date', 'sector']].copy()
            weights = 1/train.groupby('date').date.transform('size').to_numpy()
            weights /= weights.mean()
            prior = float(np.average(train._target, weights=weights))
            for family, columns in [('J', base), ('PATH', path)]:
                a, b = transform_train_test(train, test, columns, cfg)
                model = LogisticRegression(C=cfg['logistic_C'], solver='lbfgs', max_iter=500, random_state=cfg['seed'])
                model.fit(a, train._target, sample_weight=weights)
                if int(model.n_iter_.max()) >= model.max_iter:
                    raise RuntimeError('Reference failed to converge')
                ptr, ptest = model.predict_proba(a)[:, 1], model.predict_proba(b)[:, 1]
                sector, hierarchy, seen_sector, seen_symbol, groups = group_corrections(train, test, a, b, ptr, ptest, cfg)
                pred[f'GLOBAL_{family}'], pred[f'SECTOR_{family}'], pred[f'HIERARCHY_{family}'] = ptest, sector, hierarchy
                for row in groups:
                    evidence.append(dict(year=year, task=task, family=family, **row))
                support.append(dict(year=year, task=task, family=family, train_rows=len(train), train_dates=int(train.date.nunique()),
                                    train_symbols=int(train.symbol.nunique()), max_train_available=str(train.oracle_available_date.max()),
                                    max_train_oracle_rank=int(train.oracle_rank.max()),
                                    sector_correction_fraction=float(seen_sector.mean()), symbol_correction_fraction=float(seen_symbol.mean()),
                                    symbols_corrected=int(test.loc[seen_symbol].symbol.nunique()),
                                    price_feature_missing_fraction=float(train[columns].isna().mean().mean())))
                # Exact diagnostic coefficients, not artifacts discoverable by serving.
                atomic_json(output/f'linear-probe-{year}-{task}-{family}.json', dict(columns=columns, intercept=float(model.intercept_[0]),
                            coefficients=model.coef_[0].tolist(), training_prior=prior, model_is_not_served=True))
            pred.to_parquet(output/f'predictions-{year}-{task}.parquet', index=False)
            met = reference_metrics(pred, task, prior)
            met['year'] = year
            metrics.append(met)
            sel = selection_metrics(pred, counts)
            sel['year'], sel['task'] = year, task
            selections.append(sel)
            LOG.info('TOP10 complete %s %s: %d mature training rows / %d candidates', year, task, len(train), len(test))
    metrics, selections = pd.concat(metrics, ignore_index=True), pd.concat(selections, ignore_index=True)
    metrics.to_parquet(output/'daily-metrics.parquet', index=False)
    selections.to_parquet(output/'daily-selections.parquet', index=False)
    pd.DataFrame(evidence).to_csv(output/'group-evidence.csv', index=False)
    pd.DataFrame(support).to_csv(output/'training-support.csv', index=False)
    return metrics, selections


def summarize(metrics, selections, cfg):
    summary, comparisons = [], []
    avg = lambda x: float(x.mean()) if x.notna().any() else None
    for (task, year, arm), rows in metrics.loc[metrics.arm.isin(ARMS)].groupby(['task', 'year', 'arm']):
        ref_arm = CONSTANT if arm.startswith('GLOBAL_') else f'GLOBAL_{arm.split("_")[-1]}'
        reference = metrics.loc[metrics.task.eq(task) & metrics.year.eq(year) & metrics.arm.eq(ref_arm)].set_index('date')
        joined = rows.set_index('date').join(reference[['auc', 'brier']], rsuffix='_base')
        primary = selections.loc[selections.task.eq(task) & selections.year.eq(year)
                                 & selections.selection_count.eq(cfg['primary_selection_count'])]
        chosen = primary.loc[primary.arm.eq(arm)].set_index('date')
        oracle = primary.loc[primary.arm.eq(ORACLE)].set_index('date')
        paired = chosen.join(oracle[['d1', 'd10']], rsuffix='_oracle')
        target_col, opposite = ('d1', 'd10') if task == 'D1_VS_REST' else ('d10', 'd1')
        target_lift = paired[target_col]-paired[f'{target_col}_oracle']
        opposite_lift = paired[opposite]-paired[f'{opposite}_oracle']
        summary.append(dict(task=task, year=int(year), arm=arm, reference=ref_arm,
                            auc=avg(joined.auc), auc_gain=avg(joined.auc-joined.auc_base),
                            brier=avg(joined.brier), brier_gain=avg(joined.brier_base-joined.brier),
                            dates=int(joined.auc.notna().sum()), d10=avg(chosen.d10), d1=avg(chosen.d1),
                            oracle_first3_d10=avg(oracle.d10), oracle_first3_d1=avg(oracle.d1),
                            target_lift=avg(target_lift), opposite_lift=avg(opposite_lift)))
        if task in cfg['practical_tasks']:
            comparisons.append(pd.DataFrame(dict(date=joined.index, brier_gain=joined.brier_base-joined.brier,
                                                  target_lift=target_lift.reindex(joined.index),
                                                  year=year, task=task, arm=arm)))
    paired = pd.concat(comparisons, ignore_index=True)
    calendar = nyse_sessions('2022-01-01', cfg['decision_end'])
    tests, pvalues = {}, {}
    for (task, arm), sub in paired.loc[paired.year.isin(cfg['confirmation_years'])].groupby(['task', 'arm']):
        for measure in ('brier_gain', 'target_lift'):
            key = f'{task}:{arm}:{measure}'
            test = block_test(sub.set_index('date')[measure], calendar, cfg)
            tests[key], pvalues[key] = test, test['p_raw']
    corrected = holm_adjust(pvalues)  # 24 predeclared practical comparisons
    gates = []
    for task in cfg['practical_tasks']:
        for arm in ARMS:
            rows = [r for r in summary if r['task'] == task and r['arm'] == arm]
            val = next(r for r in rows if r['year'] == cfg['validation_year'])
            confirms = [r for r in rows if r['year'] in cfg['confirmation_years']]
            significant = all(corrected[f'{task}:{arm}:{measure}'] is not None
                              and corrected[f'{task}:{arm}:{measure}'] <= cfg['alpha_holm']
                              and tests[f'{task}:{arm}:{measure}']['mean_delta'] > 0
                              for measure in ('brier_gain', 'target_lift'))
            gates.append(dict(task=task, arm=arm, validation_pass=period_pass(val, cfg),
                              positive_confirmation_periods=sum(period_pass(r, cfg) for r in confirms),
                              block_comparisons_pass=significant,
                              gate_pass=bool(period_pass(val, cfg) and significant and
                                             sum(period_pass(r, cfg) for r in confirms) >= cfg['min_positive_confirmation_periods'])))
    passing = [g for g in gates if g['gate_pass']]
    return dict(status='COMPLETED_EXPLORATORY', verdict='TOP10_SIGNAL_TO_CONFIRM_NOT_ALPHA' if passing else 'NO_STABLE_TOP10_DIRECTION',
                summary=summary, gates=gates, block_tests={k: {**v, 'p_holm': corrected[k]} for k, v in tests.items()},
                primary_selection_count=cfg['primary_selection_count'], independent_holdout=False, serving_changed=False,
                sql_access=False, provider_calls=False, broker_calls=False, pnl_calculated=False,
                limitations=['Current non-PIT sectors and static universe, current adjusted-price archives.',
                             'New scope selected after looking at the previous TOP20 results; not untouched validation.',
                             '2023 and 2026 partial; unknown future returns remain unknown, never replaced.',
                             'H20 terminal deciles, not path direction, barrier outcomes or winning trades.',
                             'Overlapping outcomes and few independent symbol events; fixed strong shrinkage retained.',
                             'Linear global reference, sector ridge and symbol intercepts; not all nonlinear interactions.'])


def run(output, config=CONFIG):
    output, config = Path(output), Path(config)
    cfg = read(config)
    if cfg['training_top_titles'] != 10 or cfg['evaluation_top_titles'] != 10:
        raise ValueError('This protocol exclusively supports ten original candidates')
    with exclusive_run(output):
        if (output/'report.json').exists():
            raise ValueError('Completed output is immutable; use a new folder')
        try:
            atomic_json(output/'progress.json', dict(status='RUNNING', phase='source_qualification'))
            protocol, population = protocol_and_source(output, cfg, config)
            coverage = population.groupby(population.date.dt.year).agg(rows=('symbol', 'size'), dates=('date', 'nunique'),
                         symbols=('symbol', 'nunique'), known_labels=('oracle_decile', 'count')).reset_index(names='year')
            coverage.to_csv(output/'population-coverage.csv', index=False)
            metrics, selections = fit_all(population, output, cfg)
            result = summarize(metrics, selections, cfg)
            result['population_coverage'] = coverage.to_dict('records')
            pd.DataFrame(result['summary']).to_csv(output/'summary.csv', index=False)
            # All counts/arms are exported; the best test year never selects a winner.
            selections.groupby(['task', 'year', 'selection_count', 'arm'])[['d1', 'd10', 'label_coverage']].mean().reset_index().to_csv(
                output/'selection-summary.csv', index=False)
            verify_hashes(Path('.'), protocol['source_hashes'])
            verify_hashes(Path('.'), read(Path(cfg['source'])/'protocol.json')['source_hashes'])
            result['source_hashes_verified_after_calculation'] = True
            result['protocol_sha256'] = digest(output/'protocol.json')
            atomic_json(output/'report.json', result)
            atomic_json(output/'progress.json', dict(status='COMPLETED', verdict=result['verdict']))
            LOG.info('Finished: %s', result['verdict'])
            return result
        except Exception as exc:
            atomic_json(output/'progress.json', dict(status='FAILED', error_type=type(exc).__name__, error=str(exc)))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=CONFIG)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    run(**vars(parser.parse_args()))
