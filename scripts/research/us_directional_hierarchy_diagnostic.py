"""Bounded offline diagnostic; never train/replace a serving model or compute PnL.

Compare one shared linear reference with ridge-shrunk sector responses and
symbol offsets. J-only versus fixed 5/10-session trajectories, three targets.
The small research regressions are diagnostic probes, not promoted specialists.
"""
from __future__ import annotations

import argparse
import gc
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.linear_model import LogisticRegression

from modelFactory.cross_sectional import _map_to_gics_sector
from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle_path.train import restore_ranks, digest
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, verify_hashes

LOG = logging.getLogger(__name__)
CONFIG = Path('config/research/us_directional_hierarchy_20261018.json')
HISTORY = Path('artifacts/research/oracle_path_comparison/20261013-v1/models/oracle-path-comparison/oracle_path')
EXTERNAL = Path('artifacts/research/oracle_path_confirmation/20261013-v1')
SECTORS = Path('artifacts/research/us_concentrated_replay/live-parity-preflight-current-sectors-20261007-v1/current-sector-mapping.parquet')
ARMS = ('GLOBAL_J', 'SECTOR_J', 'HIERARCHY_J', 'GLOBAL_PATH', 'SECTOR_PATH', 'HIERARCHY_PATH')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def trajectory_features(frame, calendar, columns, windows):
    """Missing sessions stay missing; never shift along sparse Oracle events."""
    result = frame.copy()
    if result.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate feature keys')
    index = pd.MultiIndex.from_frame(result[['date', 'symbol']])
    for column in columns:
        wide = result.pivot(index='date', columns='symbol', values=column).reindex(calendar)
        for window in windows:
            delta = wide - wide.shift(window)
            # Require every feature observation in the trailing window.
            delta = delta.where(wide.notna().rolling(window + 1).sum().eq(window + 1))
            result[f'{column}_delta_{window}'] = delta.stack(future_stack=True).reindex(index).to_numpy()
    return result


def freeze_candidates(scores):
    """Future labels/quality never enter membership or its rank denominator."""
    result = scores[['date', 'symbol', 'score_lightgbm', 'fold_start']].copy()
    if result.duplicated(['date', 'symbol']).any() or not np.isfinite(result.score_lightgbm).all():
        raise ValueError('Invalid score identity/value')
    result['oracle_percentile'] = result.groupby('date').score_lightgbm.rank(pct=True)
    result = result.sort_values(['date', 'score_lightgbm', 'symbol'], ascending=[True, False, True])
    result['oracle_rank'] = result.groupby('date').cumcount() + 1
    result['oracle_top20'] = result.oracle_percentile.ge(.8)
    return result.loc[result.oracle_top20 | result.oracle_rank.le(50)].copy()


def terminal_deciles(labels, cfg):
    """Global H20 terminal ranks, never sector/pool ranks or path-sign labels.

    Use the same rank(method=max)/N and ceil(rank*10) as the canonical builder.
    Archived paths impose stricter future quality; coverage and unknowns remain
    explicit. No missing future return is treated as a negative outcome.
    """
    result = labels.copy()
    if result.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate label keys')
    eligible = result.feature_eligible.fillna(False)
    good = (eligible & result.path_qualified.fillna(False)
            & np.isfinite(result.terminal_return)
            & pd.to_datetime(result.oracle_available_date).le(pd.Timestamp(cfg['label_as_of'])))
    counts = eligible.groupby(result.date).transform('sum')
    coverage = good.groupby(result.date).transform('sum') / counts.replace(0, np.nan)
    qualified = good & counts.ge(cfg['min_label_universe']) & coverage.ge(cfg['min_daily_label_coverage'])
    returns = result.terminal_return.where(good)
    ranks = returns.groupby(result.date).rank(method='max', pct=True)
    distinct = returns.groupby(result.date).transform('nunique')
    result['oracle_decile'] = np.ceil(ranks * 10).clip(1, 10).where(qualified & distinct.gt(1))
    result['label_coverage'] = coverage
    return result[['date', 'symbol', 'oracle_decile', 'oracle_available_date', 'terminal_return', 'label_coverage']]


def target(frame, task):
    decile = frame.oracle_decile
    if task == 'D1_VS_D10':
        return decile.eq(10).astype(float).where(decile.isin([1, 10]))
    if task not in ('D10_VS_REST', 'D1_VS_REST'):
        raise ValueError('Unknown task')
    return decile.eq(10 if task == 'D10_VS_REST' else 1).astype(float).where(decile.notna())


def causal_training(frame, start):
    boundary = pd.Timestamp(start)
    return frame.loc[frame.date.lt(boundary) & pd.to_datetime(frame.oracle_available_date).lt(boundary)].copy()


def transform_train_test(train, test, columns, cfg):
    """All imputation, clipping and scaling are learned on mature train only."""
    a = train[columns].replace([np.inf, -np.inf], np.nan)
    b = test[columns].replace([np.inf, -np.inf], np.nan)
    med = a.median().fillna(0.)
    lo, hi = (a.quantile(q).fillna(med) for q in cfg['winsor_quantiles'])
    a = a.fillna(med).clip(lo, hi, axis=1)
    b = b.fillna(med).clip(lo, hi, axis=1)
    mean, scale = a.mean(), a.std(ddof=0).replace(0, 1).fillna(1.)
    return ((a-mean)/scale).to_numpy(float), ((b-mean)/scale).to_numpy(float)


def group_corrections(train, test, xtrain, xtest, ptr, ptest, cfg):
    """Shared reference -> sector ridge slopes -> shrunk symbol residual.

    Same-date centering removes market-wide residuals using TRAIN labels only.
    Sector weights sum to one per observed sector/session; raw repeated rows
    cannot pretend to be independent years of evidence. Priors are fixed.
    """
    work = train[['date', 'symbol', 'sector', '_target']].copy().reset_index(drop=True)
    residual = work._target.to_numpy() - ptr
    residual -= pd.Series(residual).groupby(work.date).transform('mean').to_numpy()
    sector_train, sector_test = np.zeros(len(train)), np.zeros(len(test))
    evidence = []
    a, b = np.column_stack([np.ones(len(train)), xtrain]), np.column_stack([np.ones(len(test)), xtest])
    for sector, indices in work.groupby('sector', sort=True).indices.items():
        if sector == 'UNKNOWN':
            continue
        idx = np.asarray(indices)
        sub = work.iloc[idx]
        positives = int(sub._target.sum())
        dates = sub.date.nunique()
        if dates < cfg['min_sector_dates'] or min(positives, len(sub)-positives) < cfg['min_group_each_class']:
            continue
        weight = 1 / sub.groupby('date').date.transform('size').to_numpy()
        z = a[idx]
        penalty = np.eye(z.shape[1]) * cfg['sector_prior_sessions']
        coef = np.linalg.solve(z.T @ (z * weight[:, None]) + penalty, z.T @ (residual[idx] * weight))
        sector_train[idx] = z @ coef
        test_idx = np.flatnonzero(test.sector.eq(sector).to_numpy())
        sector_test[test_idx] = b[test_idx] @ coef
        evidence.append(dict(level='sector', group=sector, train_dates=int(dates), train_rows=len(sub),
                             intercept=float(coef[0]), slope_norm=float(np.linalg.norm(coef[1:]))))
    cap = cfg['max_probability_correction']
    sector_train, sector_test = np.clip(sector_train, -cap, cap), np.clip(sector_test, -cap, cap)
    remaining = residual - sector_train
    remaining -= pd.Series(remaining).groupby(work.date).transform('mean').to_numpy()
    symbol_test = np.zeros(len(test))
    eligible_symbols = set()
    for symbol, indices in work.groupby('symbol', sort=True).indices.items():
        idx = np.asarray(indices)
        sub = work.iloc[idx]
        positives, dates = int(sub._target.sum()), sub.date.nunique()
        if dates < cfg['min_symbol_dates'] or min(positives, len(sub)-positives) < cfg['min_group_each_class']:
            continue
        # One symbol/session is unique. Fixed pseudo-session prior shrinks offset.
        effect = float(remaining[idx].sum() / (len(idx) + cfg['symbol_prior_sessions']))
        symbol_test[test.symbol.eq(symbol).to_numpy()] = np.clip(effect, -cap, cap)
        eligible_symbols.add(symbol)
        evidence.append(dict(level='symbol', group=symbol, train_dates=int(dates), train_rows=len(sub), intercept=effect))
    sector_seen = {row['group'] for row in evidence if row['level'] == 'sector'}
    return (np.clip(ptest + sector_test, 1e-5, 1-1e-5),
            np.clip(ptest + sector_test + symbol_test, 1e-5, 1-1e-5),
            test.sector.isin(sector_seen).to_numpy(), test.symbol.isin(eligible_symbols).to_numpy(), evidence)


def daily_metrics(frame, task):
    """Equal-date metrics, including theoretical tails and full-pool selections."""
    y = target(frame, task)
    good = y.notna()
    part = frame.loc[good].copy()
    part['_y'] = y[good].to_numpy()
    rows = []
    for arm in ARMS:
        pred = part[arm]
        r = pred.groupby(part.date).rank(method='average')
        pos = part._y.eq(1)
        n1 = pos.groupby(part.date).sum()
        n0 = (~pos).groupby(part.date).sum()
        sums = r.where(pos, 0).groupby(part.date).sum()
        auc = ((sums-n1*(n1+1)/2)/(n1*n0)).where(n1.ge(2) & n0.ge(2))
        brier = ((pred-part._y)**2).groupby(part.date).mean()
        # Freeze the shortlist on ALL candidates, before label/tail exclusions.
        picked = frame[['date', 'symbol', 'oracle_decile', arm]].sort_values(
            ['date', arm, 'symbol'], ascending=[True, False, True])
        rank = picked.groupby('date').cumcount() + 1
        selected = picked.loc[rank.le(np.ceil(picked.groupby('date').symbol.transform('size')*.2))]
        selection_coverage = selected.oracle_decile.notna().groupby(selected.date).mean()
        known = selected.loc[selected.oracle_decile.notna()]
        d10 = known.oracle_decile.eq(10).groupby(known.date).mean()
        d1 = known.oracle_decile.eq(1).groupby(known.date).mean()
        out = pd.DataFrame(dict(auc=auc, brier=brier, selected_d10=d10, selected_d1=d1,
                                selected_label_coverage=selection_coverage))
        out['arm'], out['task'] = arm, task
        rows.append(out.rename_axis('date').reset_index())
    return pd.concat(rows, ignore_index=True)


def holm_adjust(values):
    valid = sorted((p, key) for key, p in values.items() if p is not None)
    result, previous = {}, 0.
    for i, (p, key) in enumerate(valid):
        previous = max(previous, min(1., (len(valid)-i)*p))
        result[key] = previous
    return {key: result.get(key) for key in values}


def block_pvalues(daily, cfg, calendar):
    """Joint paired date-block null, two-sided; Holm over all 12 group probes."""
    order = pd.Series(np.arange(len(calendar)), index=calendar)
    raw = {}
    rng = np.random.default_rng(cfg['seed'])
    for task in cfg['tasks']:
        sub = daily.loc[daily.task.eq(task) & daily.date.ge('2023-01-01')]
        wide = sub.pivot(index='date', columns='arm', values='brier')
        for family in ('J', 'PATH'):
            for level in ('SECTOR', 'HIERARCHY'):
                key = f'{task}:{level}_{family}'
                delta = (wide[f'GLOBAL_{family}']-wide[f'{level}_{family}']).dropna()
                blocks = order.reindex(delta.index) // cfg['block_sessions']
                means = delta.groupby(blocks.to_numpy()).mean().to_numpy()
                if len(means) < cfg['min_blocks']:
                    raw[key] = None
                    continue
                observed = abs(means.mean())
                null = np.abs((rng.choice([-1., 1.], size=(cfg['permutations'], len(means))) * means).mean(axis=1))
                raw[key] = float((1+(null >= observed-1e-15).sum())/(1+len(null)))
    adjusted = holm_adjust(raw)
    return {key: dict(p_raw=p, p_holm=adjusted[key]) for key, p in raw.items()}


def gate(validation, confirmations, p_holm, cfg):
    """2024-26 never decide feature/window/sign/threshold choices."""
    return bool(validation['auc'] is not None and validation['auc'] >= cfg['validation_min_auc']
                and validation['auc_delta'] >= cfg['validation_min_auc_delta'] and validation['brier_gain'] > 0
                and validation['dates'] >= cfg['min_evaluable_dates']
                and validation['corrected_fraction'] >= cfg['min_corrected_fraction']
                and sum(c['auc_delta'] is not None and c['auc_delta'] >= cfg['confirmation_min_auc_delta']
                        and c['brier_gain'] > 0 and c['dates'] >= cfg['min_evaluable_dates'] for c in confirmations)
                    >= cfg['min_positive_confirmation_periods']
                and p_holm is not None and p_holm <= cfg['alpha_holm'])


def prepare_protocol(output, cfg):
    paths = {CONFIG, Path(__file__), HISTORY/'protocol.json', HISTORY/'feature_profile.json',
             HISTORY/'labels.parquet', EXTERNAL/'plan.json', EXTERNAL/'scores.parquet',
             EXTERNAL/'labels.parquet', SECTORS, Path('modelFactory/cross_sectional.py'),
             Path('modelFactory/oracle/build_labels.py'), Path('modelFactory/oracle_path/train.py')}
    folds = []
    for folder in sorted((HISTORY/'folds').iterdir()):
        done = read(folder/'done.json')
        for key in ('train_available_max', 'val_available_max'):
            if pd.Timestamp(done['metrics'][key]) >= pd.Timestamp(done['metrics']['test_start']):
                raise ValueError('Noncausal original Oracle fold')
        for name in ('path_model.txt', 'oof.parquet'):
            verify_hashes(folder, {name: done['files'][name]})
            paths.add(folder/name)
        paths.add(folder/'done.json')
        folds.append(dict(folder=str(folder), **{k: done['metrics'][k] for k in
                         ('test_start', 'test_end', 'train_available_max', 'val_available_max')}))
    plan = read(EXTERNAL/'plan.json')
    for key in ('train_available_max', 'val_available_max'):
        if pd.Timestamp(plan[key]) >= pd.Timestamp('2024-01-01'):
            raise ValueError('External Oracle fit not causal')
    for root in (HISTORY, EXTERNAL):
        for folder in sorted((root/'chunks').iterdir()):
            done = read(folder/'done.json')
            verify_hashes(folder, {'features.parquet': done['files']['features.parquet']})
            paths.update([folder/'features.parquet', folder/'done.json'])
    protocol = dict(config=cfg, folds=folds, source_hashes={str(p): digest(p) for p in sorted(paths)},
                    no_sql=True, no_provider_calls=True, no_broker_calls=True, no_pnl=True,
                    research_reference_fits=True, no_serving_model_training=True,
                    current_non_pit_sectors=True, static_current_universe=True)
    if (output/'protocol.json').exists() and read(output/'protocol.json') != protocol:
        raise ValueError('Changed protocol/source; use a new output directory')
    atomic_json(output/'protocol.json', protocol)
    return protocol


def prepare_population(output, cfg, protocol):
    marker = output/'population-manifest.json'
    if marker.exists():
        verify_hashes(output, read(marker)['files'])
        return pd.read_parquet(output/'population.parquet')
    import lightgbm as lgb
    profile = read(HISTORY/'feature_profile.json')
    model_cols = profile['feature_columns']
    raw_cols = list(dict.fromkeys(c.removesuffix('_xs_rank') for c in model_cols))
    base = cfg['base_features']
    trajectory = [f'{c}_delta_{w}' for c in base for w in cfg['trajectory_sessions']]
    calendar = nyse_sessions('2016-01-01', cfg['label_as_of'])
    sectors = pd.read_parquet(SECTORS)
    if sectors.symbol.duplicated().any():
        raise ValueError('Ambiguous sector identity')
    sectors['sector_raw'] = sectors.sector
    sectors['sector'] = sectors.sector.fillna('').map(_map_to_gics_sector).replace('Other', 'UNKNOWN')
    populations = []
    for phase, root in [('historical', HISTORY), ('external', EXTERNAL)]:
        parts = []
        folders = sorted((root/'chunks').iterdir())
        for i, folder in enumerate(folders):
            atomic_json(output/'progress.json', dict(status='RUNNING', phase=f'{phase}_features', completed=i, total=len(folders)))
            columns = list(dict.fromkeys(['date', 'symbol', *(raw_cols if phase == 'historical' else base)]))
            part = pd.read_parquet(folder/'features.parquet', columns=columns)
            part = trajectory_features(part, calendar, base, cfg['trajectory_sessions'])
            part = part.loc[part.date.between(cfg['first_training_date'] if phase == 'historical' else '2024-01-01',
                                              '2023-07-07' if phase == 'historical' else cfg['decision_end'])]
            parts.append(part)
        features = pd.concat(parts, ignore_index=True)
        del parts
        if features.duplicated(['date', 'symbol']).any():
            raise ValueError('Duplicate observable features')
        if phase == 'historical':
            features = restore_ranks(features, profile['generator_options'])
            scored = []
            for fold in protocol['folds']:
                folder = Path(fold['folder'])
                atomic_json(output/'progress.json', dict(status='RUNNING', phase='original_Oracle_inference', fold=folder.name))
                sub = features.loc[features.date.between(fold['test_start'], fold['test_end'])]
                booster = lgb.Booster(model_file=str(folder/'path_model.txt'))
                if booster.feature_name() != model_cols:
                    raise ValueError('Original model feature order mismatch')
                score = sub[['date', 'symbol']].copy()
                score['score_lightgbm'] = booster.predict(sub[model_cols].replace([np.inf, -np.inf], np.nan).astype(np.float32), num_threads=2)
                score['fold_start'] = folder.name
                old = pd.read_parquet(folder/'oof.parquet', columns=['date', 'symbol', 'score_lightgbm'])
                check = old.merge(score, on=['date', 'symbol'], validate='one_to_one', suffixes=('_old', '_new'))
                difference = float((check.score_lightgbm_old-check.score_lightgbm_new).abs().max())
                if len(check) != len(old) or not np.isfinite(difference) or difference > 1e-7:
                    raise ValueError('Original Oracle scores no longer reproduce')
                atomic_json(output/f'oracle-integrity-{folder.name}.json', dict(rows=len(check), max_difference=difference))
                scored.append(score)
                LOG.info('Original Oracle fold reproduced: %s', folder.name)
            scores = pd.concat(scored, ignore_index=True)
        else:
            scores = pd.read_parquet(root/'scores.parquet')
            scores = scores.loc[scores.date.le(cfg['decision_end'])]
            if not scores.fold_start.eq(read(EXTERNAL/'plan.json')['fixed_fold']).all():
                raise ValueError('External score fold mismatch')
        frozen = freeze_candidates(scores)
        frozen = frozen.merge(features[['date', 'symbol', *base, *trajectory]], on=['date', 'symbol'], how='left', validate='one_to_one')
        labels = terminal_deciles(pd.read_parquet(root/'labels.parquet'), cfg)
        frozen = frozen.merge(labels, on=['date', 'symbol'], how='left', validate='one_to_one')
        frozen['phase'] = phase
        populations.append(frozen)
        del features, scores, labels, frozen
        gc.collect()
    population = pd.concat(populations, ignore_index=True).merge(sectors, on='symbol', how='left', validate='many_to_one')
    population['sector'] = population.sector.fillna('UNKNOWN')
    if population.duplicated(['date', 'symbol']).any():
        raise ValueError('Overlapping historical/external dates')
    population.to_parquet(output/'population.parquet', index=False)
    atomic_json(marker, dict(files={'population.parquet': digest(output/'population.parquet')}, rows=len(population)))
    return population


def fit_references(population, output, cfg):
    base = cfg['base_features']
    path = base + [f'{c}_delta_{w}' for c in base for w in cfg['trajectory_sessions']]
    all_daily, evidence, coverage = [], [], []
    for year in [cfg['validation_year'], *cfg['confirmation_years']]:
        start = f'{year}-01-01'
        train_all = causal_training(population.loc[population.oracle_top20], start)
        test = population.loc[population.date.dt.year.eq(year)].copy().reset_index(drop=True)
        if test.empty:
            raise ValueError(f'Missing planned period {year}')
        for task in cfg['tasks']:
            atomic_json(output/'progress.json', dict(status='RUNNING', phase='diagnostic_references', year=year, task=task))
            train = train_all.assign(_target=target(train_all, task)).dropna(subset=['_target']).reset_index(drop=True)
            if train._target.nunique() != 2:
                raise ValueError('No mature binary training sample')
            predictions = test[['date', 'symbol', 'oracle_rank', 'oracle_top20', 'oracle_decile', 'sector']].copy()
            for family, columns in [('J', base), ('PATH', path)]:
                xtrain, xtest = transform_train_test(train, test, columns, cfg)
                weights = 1 / train.groupby('date').date.transform('size').to_numpy()
                weights /= weights.mean()
                model = LogisticRegression(C=cfg['logistic_C'], max_iter=500, solver='lbfgs', random_state=cfg['seed'])
                model.fit(xtrain, train._target, sample_weight=weights)
                if int(model.n_iter_.max()) >= model.max_iter:
                    raise RuntimeError('Reference logistic did not converge')
                ptr, ptest = model.predict_proba(xtrain)[:, 1], model.predict_proba(xtest)[:, 1]
                sector, hierarchy, seen_sector, seen_symbol, rows = group_corrections(train, test, xtrain, xtest, ptr, ptest, cfg)
                predictions[f'GLOBAL_{family}'], predictions[f'SECTOR_{family}'], predictions[f'HIERARCHY_{family}'] = ptest, sector, hierarchy
                for row in rows:
                    evidence.append(dict(year=year, task=task, family=family, **row))
                for level, corrected in [('SECTOR', seen_sector), ('HIERARCHY', seen_sector | seen_symbol)]:
                    coverage.append(dict(year=year, task=task, arm=f'{level}_{family}',
                                         corrected_fraction=float(corrected[test.oracle_top20].mean()), train_rows=len(train),
                                         train_dates=int(train.date.nunique()), max_train_available=str(train.oracle_available_date.max())))
            predictions.to_parquet(output/f'predictions-{year}-{task}.parquet', index=False)
            for pool in ['ORACLE_TOP20_PERCENT', *cfg['robustness_pools']]:
                keep = predictions.oracle_top20 if pool == 'ORACLE_TOP20_PERCENT' else predictions.oracle_rank.le(int(pool.split('_')[0][3:]))
                metrics = daily_metrics(predictions.loc[keep], task)
                metrics['pool'], metrics['year'] = pool, year
                all_daily.append(metrics)
            LOG.info('Diagnostic complete: %s %s (%d train / %d test)', year, task, len(train), len(test))
    daily = pd.concat(all_daily, ignore_index=True)
    daily.to_parquet(output/'daily-metrics.parquet', index=False)
    pd.DataFrame(evidence).to_csv(output/'group-evidence.csv', index=False)
    pd.DataFrame(coverage).to_csv(output/'correction-coverage.csv', index=False)
    return daily, pd.DataFrame(coverage)


def summarize(daily, coverage, cfg):
    primary = daily.loc[daily.pool.eq('ORACLE_TOP20_PERCENT')]
    calendar = nyse_sessions('2022-01-01', cfg['decision_end'])
    pvalues = block_pvalues(primary, cfg, calendar)
    summary = []
    for (task, year, arm), sub in primary.groupby(['task', 'year', 'arm']):
        family = 'PATH' if arm.endswith('PATH') else 'J'
        reference = primary.loc[primary.task.eq(task) & primary.year.eq(year) & primary.arm.eq(f'GLOBAL_{family}')].set_index('date')
        paired = sub.set_index('date').join(reference[['auc', 'brier']], rsuffix='_base')
        avg = lambda s: float(s.mean()) if s.notna().any() else None
        cov = coverage.loc[coverage.task.eq(task) & coverage.year.eq(year) & coverage.arm.eq(arm)]
        summary.append(dict(task=task, year=int(year), arm=arm, auc=avg(paired.auc),
                            auc_delta=avg(paired.auc-paired.auc_base), brier=avg(paired.brier),
                            brier_gain=avg(paired.brier_base-paired.brier), dates=int(paired.auc.notna().sum()),
                            selected_d10=avg(paired.selected_d10), selected_d1=avg(paired.selected_d1),
                            corrected_fraction=float(cov.corrected_fraction.iloc[0]) if len(cov) else 0.))
    gates = []
    for key, p in pvalues.items():
        task, arm = key.split(':')
        rows = [r for r in summary if r['task'] == task and r['arm'] == arm]
        validation = next(r for r in rows if r['year'] == cfg['validation_year'])
        confirmation = [r for r in rows if r['year'] in cfg['confirmation_years']]
        gates.append(dict(task=task, arm=arm, **p, statistical_gate_pass=gate(validation, confirmation, p['p_holm'], cfg)))
    passes = [g for g in gates if g['statistical_gate_pass']]
    # Every downstream decision remains blocked by current-sector/non-vintage metadata.
    return dict(status='COMPLETED_EXPLORATORY', verdict='GROUP_STRUCTURE_TO_CONFIRM_NOT_ALPHA' if passes else 'NO_STABLE_GROUP_STRUCTURE',
                summary=summary, gates=gates, specialist_training_authorized=False, production_promotion=False,
                limitations=['Current sectors, not historical PIT; missing/Other -> shared reference.',
                             'Current static universe and adjusted-price archives, not certified historical vintages.',
                             'Terminal H20 deciles, not dominant path sign or TP-before-SL profitability.',
                             '63-session blocks approximate serial dependence; overlapping labels and repeated symbols.',
                             '2023 is partial through July 7; 2026 is partial through September 2.',
                             '2024-2026 already observed; not independent untouched confirmation.',
                             'This probes fixed linear sector responses and symbol offsets, not all nonlinear interactions.',
                             'D1-vs-D10 is conditional on two future tails; full-pool tasks are necessary for selection.'])


def run(output, config=CONFIG):
    output = Path(output)
    cfg = read(config)
    with exclusive_run(output):
        if (output/'report.json').exists():
            raise ValueError('Completed dossier is immutable; choose a new directory')
        try:
            atomic_json(output/'progress.json', dict(status='RUNNING', phase='source_integrity'))
            protocol = prepare_protocol(output, cfg)
            population = prepare_population(output, cfg, protocol)
            coverage_rows = []
            for year, sub in population.loc[population.oracle_top20].groupby(population.date.dt.year):
                coverage_rows.append(dict(year=int(year), selected=len(sub), dates=int(sub.date.nunique()),
                                          symbols=int(sub.symbol.nunique()), known_labels=int(sub.oracle_decile.notna().sum()),
                                          sector_known_fraction=float(sub.sector.ne('UNKNOWN').mean())))
            pd.DataFrame(coverage_rows).to_csv(output/'population-coverage.csv', index=False)
            daily, coverage = fit_references(population, output, cfg)
            result = summarize(daily, coverage, cfg)
            result['population_coverage'] = coverage_rows
            pd.DataFrame(result['summary']).to_csv(output/'summary.csv', index=False)
            verify_hashes(Path('.'), protocol['source_hashes'])
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
