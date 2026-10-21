"""One fixed CatBoost three-class trial; Oracle TOP10 archives, no SQL/PnL/orders."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import catboost
import numpy as np
import pandas as pd
import sklearn
from catboost import CatBoostClassifier
from sklearn.linear_model import LogisticRegression

from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle_path.train import digest
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, verify_hashes
from scripts.research.us_directional_hierarchy_diagnostic import causal_training, holm_adjust
from scripts.research.us_top10_directional_diagnostic import block_test, top10_only

LOG = logging.getLogger(__name__)
CONFIG = Path('config/research/us_top10_catboost_multiclass_20261018.json')
CAT, LINEAR, OLD, ORACLE = 'CATBOOST_3CLASS', 'LOGISTIC_3CLASS', 'OLD_LOGISTIC_D10', 'ORACLE_ORDER'
RANK_ARMS = (CAT, LINEAR, OLD, ORACLE)
PROB_ARMS = (CAT, LINEAR, 'TRAIN_PRIOR_3CLASS')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def three_classes(decile):
    """Middle outcomes are a real third class; unknowns are never negatives."""
    known = decile.notna()
    if not decile[known].isin(range(1, 11)).all():
        raise ValueError('Only global integer deciles 1..10 allowed')
    return pd.Series(np.where(decile.eq(1), 0., np.where(decile.eq(10), 2., 1.)), index=decile.index).where(known)


def ordered_probabilities(probabilities, classes):
    """Explicit class mapping, no relabel/re-normalisation of invalid responses."""
    values = np.asarray(probabilities, dtype=float)
    keys = np.asarray(classes)
    if keys.shape != (3,) or set(keys.tolist()) != {0, 1, 2}:
        raise ValueError('Exactly classes 0=D1, 1=middle, 2=D10 required')
    if values.ndim != 2 or values.shape[1] != 3:
        raise ValueError('Three probability columns required')
    result = values[:, [int(np.flatnonzero(keys == key)[0]) for key in (0, 1, 2)]]
    if (not np.isfinite(result).all() or (result < 0).any() or (result > 1).any()
            or not np.allclose(result.sum(axis=1), 1., atol=1e-8, rtol=0)):
        raise ValueError('Invalid three-class probabilities')
    return result


def contrast(probabilities):
    p = ordered_probabilities(probabilities, [0, 1, 2])
    return p[:, 2]-p[:, 0]


def preprocess(train, test, columns, cfg):
    """Same train-only transform as the old reference, persisted for replay."""
    a = train[columns].replace([np.inf, -np.inf], np.nan)
    b = test[columns].replace([np.inf, -np.inf], np.nan)
    median = a.median().fillna(0.)
    lo, hi = (a.quantile(q).fillna(median) for q in cfg['winsor_quantiles'])
    a, b = a.fillna(median).clip(lo, hi, axis=1), b.fillna(median).clip(lo, hi, axis=1)
    mean, scale = a.mean(), a.std(ddof=0).replace(0., 1.).fillna(1.)
    record = dict(columns=columns, median=median.to_dict(), lower=lo.to_dict(), upper=hi.to_dict(),
                  mean=mean.to_dict(), scale=scale.to_dict())
    return ((a-mean)/scale).to_numpy(float), ((b-mean)/scale).to_numpy(float), record


def daily_auc(labels, scores, dates):
    """Equal-date AUC, with explicit sparse/single-class dates left unknown."""
    f = pd.DataFrame(dict(date=np.asarray(dates), y=np.asarray(labels), score=np.asarray(scores)))
    f = f.loc[f.y.notna() & np.isfinite(f.score)].copy()
    f['rank'] = f.groupby('date').score.rank(method='average')
    pos = f.y.eq(1)
    n1, n0 = pos.groupby(f.date).sum(), (~pos).groupby(f.date).sum()
    summed = f['rank'].where(pos, 0.).groupby(f.date).sum()
    return ((summed-n1*(n1+1)/2)/(n1*n0)).where(n1.ge(2) & n0.ge(2))


def primary_days(frame):
    # Evaluation mask only. Membership/scores/shortlists do not use this mask.
    return frame.groupby('date').oracle_decile.count().eq(10)


def selection_rows(frame, counts):
    """Pick ranks using only decision scores; never refill an unknown label."""
    if any(type(count) is not int or not 1 <= count <= 10 for count in counts):
        raise ValueError('Fixed integer selection counts 1..10 required')
    complete = primary_days(frame)
    parts = []
    for arm in RANK_ARMS:
        columns, ascending = (['date', 'oracle_rank'], [True, True]) if arm == ORACLE else (
            ['date', arm, 'oracle_rank'], [True, False, True])
        ranked = frame.sort_values(columns, ascending=ascending)
        rank = ranked.groupby('date').cumcount()+1
        for count in counts:
            chosen = ranked.loc[rank.le(count)]
            rows = pd.DataFrame(dict(selected_count=chosen.groupby('date').size(),
                                     known_count=chosen.oracle_decile.notna().groupby(chosen.date).sum(),
                                     d1_count=chosen.oracle_decile.eq(1).groupby(chosen.date).sum(),
                                     d10_count=chosen.oracle_decile.eq(10).groupby(chosen.date).sum()))
            rows['d1'] = rows.d1_count/rows.known_count.replace(0, np.nan)
            rows['d10'] = rows.d10_count/rows.known_count.replace(0, np.nan)
            rows['complete_ten_labels'] = complete.reindex(rows.index)
            rows['selection_count'], rows['arm'] = count, arm
            parts.append(rows.rename_axis('date').reset_index())
    return pd.concat(parts, ignore_index=True)


def probability_metrics(frame):
    known = frame.oracle_decile.notna()
    part = frame.loc[known].copy()
    truth = np.eye(3)[three_classes(part.oracle_decile).to_numpy(int)]
    out = []
    for arm in PROB_ARMS:
        p = part[[f'{arm}_p_d1', f'{arm}_p_middle', f'{arm}_p_d10']].to_numpy(float)
        ordered_probabilities(p, [0, 1, 2])
        row = pd.DataFrame(dict(date=part.date.to_numpy(),
                               brier3=((p-truth)**2).sum(axis=1),
                               logloss3=-(truth*np.log(np.clip(p, 1e-15, 1.))).sum(axis=1),
                               accuracy=(p.argmax(axis=1) == truth.argmax(axis=1)).astype(float)))
        row = row.groupby('date').mean().reset_index()
        row['arm'] = arm
        out.append(row)
    return pd.concat(out, ignore_index=True)


def ranking_metrics(frame):
    out = []
    decile, days = frame.oracle_decile, primary_days(frame)
    for arm in RANK_ARMS:
        score = -frame.oracle_rank if arm == ORACLE else frame[arm]
        up = decile.eq(10).astype(float).where(decile.notna())
        down = decile.eq(1).astype(float).where(decile.notna())
        tails = decile.eq(10).astype(float).where(decile.isin([1, 10]))
        row = pd.DataFrame(dict(auc_d10_rest=daily_auc(up, score, frame.date),
                               auc_d1_rest=daily_auc(down, -score, frame.date),
                               auc_d1_d10=daily_auc(tails, score, frame.date)))
        row['complete_ten_labels'] = days.reindex(row.index)
        row['arm'] = arm
        out.append(row.rename_axis('date').reset_index())
    return pd.concat(out, ignore_index=True)


def fixed_gate(row, cfg):
    required = ('auc_d10_rest', 'auc_gain_vs_linear', 'brier_gain_vs_linear', 'd10_lift_vs_oracle',
                'd1_lift_vs_oracle', 'd10_lift_vs_old', 'd10_lift_vs_linear')
    return bool(all(row.get(key) is not None and np.isfinite(row[key]) for key in required)
                and row['auc_d10_rest'] >= cfg['validation_min_auc']
                and row['auc_gain_vs_linear'] >= cfg['min_auc_gain_vs_multiclass_logistic']
                and row['brier_gain_vs_linear'] > 0
                and row['d10_lift_vs_oracle'] >= cfg['min_d10_lift_vs_oracle']
                and row['d1_lift_vs_oracle'] <= cfg['max_d1_lift_vs_oracle']
                and row['d10_lift_vs_old'] > 0 and row['d10_lift_vs_linear'] > 0
                and row['auc_dates'] >= cfg['min_evaluable_dates'])


def qualify_source(output, cfg, config):
    root = Path(cfg['source'])
    report, old_protocol = read(root/'report.json'), read(root/'protocol.json')
    if report['status'] != 'COMPLETED_EXPLORATORY' or not report['source_hashes_verified_after_calculation']:
        raise ValueError('Completed verified TOP10 source required')
    if digest(root/'protocol.json') != report['protocol_sha256']:
        raise ValueError('TOP10 protocol/report mismatch')
    verify_hashes(Path('.'), old_protocol['source_hashes'])
    parent = Path(old_protocol['config']['source'])
    verify_hashes(Path('.'), read(parent/'protocol.json')['source_hashes'])
    verify_hashes(parent, read(parent/'population-manifest.json')['files'])
    population = top10_only(pd.read_parquet(root/'top10-population.parquet'))
    expected = top10_only(pd.read_parquet(parent/'population.parquet'))
    pd.testing.assert_frame_equal(population, expected)
    if population.date.max() > pd.Timestamp(cfg['decision_end']):
        raise ValueError('Source beyond planned decision end')
    paths = [Path(__file__), config, root/'protocol.json', root/'report.json', root/'top10-population.parquet',
             Path('scripts/research/us_top10_directional_diagnostic.py'),
             Path('scripts/research/us_directional_hierarchy_diagnostic.py'),
             Path('scripts/research/us_concentrated_historical_tapes.py'), Path('scripts/research/oracle_path_confirmation.py')]
    paths.extend(root/f'predictions-{year}-D10_VS_REST.parquet' for year in [cfg['validation_year'], *cfg['confirmation_years']])
    protocol = dict(config=cfg, source_hashes={str(p): digest(p) for p in paths},
                    source_scope='Original causal Oracle ranks 1..10; no membership change',
                    classes={'0': 'D1', '1': 'D2-D9', '2': 'D10'}, score='P(D10)-P(D1)',
                    primary_comparison='Same dates with all original ten labels known; selections frozen before labels',
                    versions=dict(catboost=catboost.__version__, sklearn=sklearn.__version__),
                    automatic_promotion=False, no_sql=True, no_provider_calls=True, no_orders=True,
                    no_pnl=True, no_serving_changes=True, independently_untouched_holdout=False,
                    protocol_selected_after_prior_experiments=True)
    path = output/'protocol.json'
    if path.exists() and read(path) != protocol:
        raise ValueError('Changed source/protocol; new output folder required')
    atomic_json(path, protocol)
    population.to_parquet(output/'population.parquet', index=False)
    return protocol, population


def fit_years(population, output, cfg):
    columns = cfg['base_features'] + [f'{c}_delta_{w}' for c in cfg['base_features'] for w in cfg['trajectory_sessions']]
    if len(columns) != 24 or any(c in columns for c in ('symbol', 'sector', 'oracle_decile', 'terminal_return')):
        raise ValueError('Only the fixed 24 causal numeric features allowed')
    rankings, probabilities, selections, support = [], [], [], []
    for year in [cfg['validation_year'], *cfg['confirmation_years']]:
        atomic_json(output/'progress.json', dict(status='RUNNING', phase='fixed_multiclass_fit', year=year))
        train = causal_training(population, f'{year}-01-01').dropna(subset=['oracle_decile']).reset_index(drop=True)
        test = population.loc[population.date.dt.year.eq(year)].copy().reset_index(drop=True)
        y = three_classes(train.oracle_decile).to_numpy(int)
        if set(y) != {0, 1, 2} or test.empty or not train.oracle_rank.between(1, 10).all():
            raise ValueError('Invalid mature TOP10 train/test classes')
        a, b, transform = preprocess(train, test, columns, cfg)
        weights = 1/train.groupby('date').date.transform('size').to_numpy()
        weights /= weights.mean()
        prior = np.average(np.eye(3)[y], axis=0, weights=weights)
        folder = output/str(year)
        folder.mkdir(exist_ok=True)
        atomic_json(folder/'preprocessing.json', transform)
        old = pd.read_parquet(Path(cfg['source'])/f'predictions-{year}-D10_VS_REST.parquet')
        old = test[['date', 'symbol', 'oracle_decile']].merge(old[['date', 'symbol', 'oracle_decile', 'GLOBAL_PATH']],
                    on=['date', 'symbol'], how='left', suffixes=('', '_old'), validate='one_to_one')
        if not (old.oracle_decile.eq(old.oracle_decile_old) | (old.oracle_decile.isna() & old.oracle_decile_old.isna())).all():
            raise ValueError('Old reference label/key mismatch')
        binary = LogisticRegression(C=cfg['logistic_C'], max_iter=500, solver='lbfgs', random_state=cfg['seed'])
        binary.fit(a, (y == 2).astype(float), sample_weight=weights)
        old_difference = float(np.abs(binary.predict_proba(b)[:, 1]-old.GLOBAL_PATH.to_numpy()).max())
        if not np.isfinite(old_difference) or old_difference > 1e-10:
            raise ValueError('Old logistic reference no longer reproduces')
        pred = test[['date', 'symbol', 'oracle_rank', 'oracle_decile', 'oracle_available_date']].copy()
        pred[OLD] = old.GLOBAL_PATH.to_numpy()
        model = LogisticRegression(C=cfg['logistic_C'], solver='lbfgs', max_iter=1000, random_state=cfg['seed'])
        model.fit(a, y, sample_weight=weights)
        if int(model.n_iter_.max()) >= model.max_iter:
            raise RuntimeError('Multiclass logistic failed to converge')
        linear = ordered_probabilities(model.predict_proba(b), model.classes_)
        atomic_json(folder/'logistic.json', dict(classes=model.classes_.tolist(), intercept=model.intercept_.tolist(),
                                                coefficients=model.coef_.tolist(), research_only=True))
        model = CatBoostClassifier(**cfg['catboost'])
        model.fit(a, y, sample_weight=weights)  # no eval_set, no test labels, no early stopping
        if model.tree_count_ != cfg['catboost']['iterations']:
            raise RuntimeError('Unexpected tree count in fixed CatBoost trial')
        boosted = ordered_probabilities(model.predict_proba(b), model.classes_)
        model.save_model(str(folder/'research-catboost.cbm'))
        for arm, values in [(LINEAR, linear), (CAT, boosted), ('TRAIN_PRIOR_3CLASS', np.tile(prior, (len(test), 1)))]:
            for index, label in enumerate(('d1', 'middle', 'd10')):
                pred[f'{arm}_p_{label}'] = values[:, index]
            if arm != 'TRAIN_PRIOR_3CLASS':
                pred[arm] = contrast(values)
        pred.to_parquet(folder/'predictions.parquet', index=False)
        rank = ranking_metrics(pred)
        probability = probability_metrics(pred)
        selection = selection_rows(pred, [cfg['primary_selection_count'], *cfg['secondary_selection_counts']])
        for rows in (rank, probability, selection):
            rows['year'] = year
        rankings.append(rank)
        probabilities.append(probability)
        selections.append(selection)
        support.append(dict(year=year, train_rows=len(train), train_dates=int(train.date.nunique()), train_symbols=int(train.symbol.nunique()),
                            train_class_counts=np.bincount(y, minlength=3).tolist(), max_train_available=str(train.oracle_available_date.max()),
                            test_rows=len(test), test_dates=int(test.date.nunique()), complete_label_dates=int(primary_days(test).sum()),
                            old_reference_max_difference=old_difference, catboost_trees=model.tree_count_, training_max_rank=int(train.oracle_rank.max())))
        atomic_json(folder/'done.json', dict(files={name: digest(folder/name) for name in
                    ('preprocessing.json', 'logistic.json', 'research-catboost.cbm', 'predictions.parquet')}, **support[-1]))
        LOG.info('Completed %s: %d mature train / %d test; old reference difference %.3g', year, len(train), len(test), old_difference)
    rank, probability, selection = (pd.concat(parts, ignore_index=True) for parts in (rankings, probabilities, selections))
    rank.to_parquet(output/'daily-ranking.parquet', index=False)
    probability.to_parquet(output/'daily-probabilities.parquet', index=False)
    selection.to_parquet(output/'daily-selections.parquet', index=False)
    pd.DataFrame(support).to_json(output/'training-support.json', orient='records', indent=2)
    return rank, probability, selection


def summarize(rank, probability, selection, cfg):
    avg = lambda s: float(s.mean()) if s.notna().any() else None
    primary = selection.loc[selection.selection_count.eq(cfg['primary_selection_count']) & selection.complete_ten_labels]
    rank = rank.loc[rank.complete_ten_labels]
    rows, comparisons = [], []
    for year in [cfg['validation_year'], *cfg['confirmation_years']]:
        annual = primary.loc[primary.year.eq(year)]
        complete = annual.loc[annual.arm.eq(CAT), 'date']
        brier = probability.loc[probability.year.eq(year) & probability.date.isin(complete)].pivot(index='date', columns='arm', values='brier3')
        d10 = annual.pivot(index='date', columns='arm', values='d10')
        d1 = annual.pivot(index='date', columns='arm', values='d1')
        auc = rank.loc[rank.year.eq(year)].pivot(index='date', columns='arm', values='auc_d10_rest')
        for arm in RANK_ARMS:
            annual_rank = rank.loc[rank.year.eq(year) & rank.arm.eq(arm)]
            rows.append(dict(year=year, arm=arm, d10=avg(d10[arm]), d1=avg(d1[arm]), selection_dates=len(d10),
                             auc_d10_rest=avg(annual_rank.auc_d10_rest), auc_d1_rest=avg(annual_rank.auc_d1_rest),
                             auc_d1_d10=avg(annual_rank.auc_d1_d10), auc_dates=int(annual_rank.auc_d10_rest.notna().sum()),
                             brier3=avg(brier[arm]) if arm in brier else None))
        cat = next(row for row in rows if row['year'] == year and row['arm'] == CAT)
        cat.update(dict(auc_gain_vs_linear=avg(auc[CAT]-auc[LINEAR]),
                        brier_gain_vs_linear=avg(brier[LINEAR]-brier[CAT]),
                        d10_lift_vs_oracle=avg(d10[CAT]-d10[ORACLE]), d1_lift_vs_oracle=avg(d1[CAT]-d1[ORACLE]),
                        d10_lift_vs_old=avg(d10[CAT]-d10[OLD]), d10_lift_vs_linear=avg(d10[CAT]-d10[LINEAR])))
        comparisons.append(pd.DataFrame(dict(year=year, brier_gain_vs_linear=brier[LINEAR]-brier[CAT],
                                             d10_lift_vs_oracle=d10[CAT]-d10[ORACLE],
                                             d10_lift_vs_old=d10[CAT]-d10[OLD], d10_lift_vs_linear=d10[CAT]-d10[LINEAR])).rename_axis('date').reset_index())
    paired = pd.concat(comparisons, ignore_index=True)
    confirmations = paired.loc[paired.year.isin(cfg['confirmation_years'])].set_index('date')
    calendar = nyse_sessions('2022-01-01', cfg['decision_end'])
    tests = {key: block_test(confirmations[key], calendar, cfg) for key in
             ('brier_gain_vs_linear', 'd10_lift_vs_oracle', 'd10_lift_vs_old', 'd10_lift_vs_linear')}
    adjusted = holm_adjust({key: value['p_raw'] for key, value in tests.items()})
    for key in tests:
        tests[key]['p_holm'] = adjusted[key]
    val = next(row for row in rows if row['year'] == cfg['validation_year'] and row['arm'] == CAT)
    positive = sum(fixed_gate(row, cfg) for row in rows if row['arm'] == CAT and row['year'] in cfg['confirmation_years'])
    significant = all(t['p_holm'] is not None and t['p_holm'] <= cfg['alpha_holm'] and t['mean_delta'] > 0 for t in tests.values())
    passes = fixed_gate(val, cfg) and positive >= cfg['min_positive_confirmation_periods'] and significant
    return dict(status='COMPLETED_EXPLORATORY', verdict='CATBOOST_TOP10_TO_CONFIRM_NOT_ALPHA' if passes else 'NO_STABLE_CATBOOST_TOP10_DIRECTION',
                summary=rows, validation_pass=fixed_gate(val, cfg), positive_confirmation_periods=positive,
                block_tests=tests, statistical_gate_pass=bool(passes), production_promotion=False,
                sql_access=False, provider_calls=False, broker_calls=False, pnl_calculated=False, serving_changed=False,
                limitations=['Same historically examined years after several research choices; no independent untouched holdout.',
                             'Static current universe and adjusted-price archives not historically vintage certified.',
                             'Primary paired metrics use dates with all original ten terminal deciles known; incomplete dates archived, not replaced.',
                             'D1/D10 terminal H20 ranks, not path direction, barrier profitability or winning trades.',
                             '2023 partial through July 7; 2026 decisions through September 2 with twenty unknown-label dates.',
                             'Overlapping H20 labels, repeated titles and approximate 63-session block inference.',
                             'One fixed CatBoost, no parameter search, no sector/ticker memorisation features or early stopping.'])


def run(output, config=CONFIG):
    output, config = Path(output), Path(config)
    cfg = read(config)
    if cfg['training_top_titles'] != 10 or cfg['evaluation_top_titles'] != 10 or cfg['early_stopping'] or cfg['hyperparameter_search']:
        raise ValueError('Fixed TOP10-only protocol required')
    with exclusive_run(output):
        if (output/'report.json').exists():
            raise ValueError('Completed output immutable; use new folder')
        try:
            atomic_json(output/'progress.json', dict(status='RUNNING', phase='source_integrity'))
            protocol, population = qualify_source(output, cfg, config)
            rank, probability, selection = fit_years(population, output, cfg)
            result = summarize(rank, probability, selection, cfg)
            pd.DataFrame(result['summary']).to_csv(output/'summary.csv', index=False)
            selection.groupby(['year', 'selection_count', 'arm', 'complete_ten_labels'])[['d1', 'd10', 'known_count']].mean().reset_index().to_csv(
                output/'selection-summary.csv', index=False)
            verify_hashes(Path('.'), protocol['source_hashes'])
            verify_hashes(Path('.'), read(Path(cfg['source'])/'protocol.json')['source_hashes'])
            result['source_hashes_verified_after_calculation'] = True
            result['protocol_sha256'] = digest(output/'protocol.json')
            result['files'] = {str(path.relative_to(output)): digest(path) for path in output.rglob('*')
                               if path.is_file() and path.suffix in ('.parquet', '.csv', '.cbm', '.json')
                               and path.name not in ('progress.json', 'report.json')}
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
