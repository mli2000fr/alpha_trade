"""Separate research H10/H20 amplitude models on identical cached data/folds.

No production module changes, model registration, SQL, broker or LLM calls.
The sole fitted-target difference is maximum amplitude over 10 versus 20 sessions.
Rolling 504 train / 126 validation, common 21-session embargo; annual 2024/25/26.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import gc
import logging

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research import us_h10_price_readiness as readiness
from scripts.research import us_h10_h20_common_data as common
from scripts.research import us_oracle_holding_horizons as execution
from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle_path.labels import classify
from modelFactory.oracle_path.train import restore_ranks, train_catboost
from modelFactory.oracle_path import TARGET
from modelFactory.oracle.train import roc_auc

TRAIN = Path('artifacts/research/oracle_path_comparison/20261013-v1/models/oracle-path-comparison/oracle_path')
TEST = Path('artifacts/research/oracle_path_confirmation/20261013-v1')
QUALITY = Path('artifacts/research/us_h10_price_readiness/20261019-v1/qualification-final-v4')
LOG = logging.getLogger(__name__)


def read(path): return execution.read(path)


def prepare(root):
    if (root/'protocol.json').exists():
        p = read(root/'protocol.json'); verify_hashes(Path('.'), p['sources']); return p
    root.mkdir(parents=True, exist_ok=False)
    quality = read(QUALITY/'report.json'); verify_hashes(Path('.'), quality['sources']); verify_hashes(QUALITY, quality['files'])
    profile = read(TRAIN/'feature_profile.json'); old = read(TRAIN/'protocol.json')
    columns = [c for c in profile['feature_columns'] if c != 'selector_short_score']
    days = nyse_sessions('2016-01-01', '2026-10-09')
    folds = {str(year): {k: [str(d.date()) for d in v] for k, v in common.frozen_annual_dates(days, year).items()}
        for year in (2024, 2025, 2026)}
    sources = {str(p): digest(p) for p in [Path(__file__), Path(common.__file__), Path(execution.__file__),
        Path('tests/test_us_h10_h20_comparison.py'), TRAIN/'protocol.json', TRAIN/'feature_profile.json', QUALITY/'report.json',
        QUALITY/'research-prices.parquet', QUALITY/'quality-reserves.json', Path('modelFactory/oracle_path/labels.py'),
        Path('modelFactory/oracle_path/train.py')]}
    for tree in (TRAIN, TEST):
        for folder in sorted((tree/'chunks').iterdir()):
            done = read(folder/'done.json')
            verify_hashes(folder, {n: done['files'][n] for n in ('bars.parquet', 'features.parquet')})
            for name in ('done.json', 'bars.parquet', 'features.parquet'): sources[str(folder/name)] = digest(folder/name)
    reserves = quality['feature_reserves'] + [dict(symbol=s, start=e['start'], reason=e['reason']) for s, e in quality['price_reserves'].items()]
    params = {k: v for k, v in old['training_config']['baseline'].items() if k.startswith('catboost_')}
    p = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), sources=sources, feature_columns=columns,
        generator_options=profile['generator_options'], universe=old['universe'], universe_count=len(old['universe']),
        folds=folds, model_horizons=[10, 20], holding_horizons=[10, 20], backend='catboost', params=params,
        seed=42, threads=4, train_dates=504, validation_dates=126, common_embargo_sessions=21,
        ranking='ceil(0.20*N observable scores), score DESC symbol ASC before future qualification; no replacement',
        selection='Fixed backend/settings; early stopping on same chronological validation dates; no champion choice on test',
        test_end='2026-09-01', observation_prices_end='2026-09-30', calendar_availability_end='2026-10-09',
        feature_reserves=reserves, price_reserves=quality['price_reserves'], identity_events=old['security_discontinuities'],
        target='TOP20% maximum absolute adjusted high/low excursion relative J close; availability J+H+1',
        common_training_population='both H10/H20 labels qualified; purge with later H20 availability for BOTH models',
        feature_quality='Finite original base features; selector_short_score excluded because PIT lineage uncertified; XS ranks recomputed before label filtering',
        feature_cache_not_repaired='Exclude each known mixed-basis feature history from first observed break, until rebuild; no global symbol deletion',
        execution='J+1 open, TP10/SL10, no trailing, close-N expiry; gaps/ambiguous OHLC as prior contract',
        fees_per_leg=execution.gate.COST_PER_LEG, borrow_annual=execution.gate.BORROW_ANNUAL,
        sql=False, api_calls=0, production_changes=False, model_promotion=False, orders=False,
        interpretation='New research reference H20 trained on same rolling folds/data as H10; not a reproduction of old annual batch scores',
        reserves=['Already explored years / static current survivor universe',
            'Vendor corporate-action normalization is not full independent daily execution proof',
            'Unknown future path kept as missing, not negative or replaced',
            'Per-occasion net outcomes, no capital recycling, real margin, exhaustive dividends or portfolio PnL'])
    atomic_json(root/'protocol.json', p); (root/'parts').mkdir(); return p


def build(root):
    p = read(root/'protocol.json'); verify_hashes(Path('.'), p['sources'])
    if (root/'data-ready.json').exists(): verify_hashes(root, read(root/'data-ready.json')['files']); return
    days = nyse_sessions('2016-01-01', '2026-10-09')
    earliest = min(f['train'][0] for f in p['folds'].values())
    prices = pd.read_parquet(QUALITY/'research-prices.parquet').set_index(['symbol', 'date'])
    base_columns = [c for c in p['feature_columns'] if not c.endswith('_xs_rank')]
    labels = {h: [] for h in p['model_horizons']}; members = []; files = {}; coverage = []
    for i, train_folder in enumerate(sorted((TRAIN/'chunks').iterdir()), 1):
        part = root/'parts'/train_folder.name; part.mkdir(exist_ok=True)
        marker = part/'done.json'
        if marker.exists():
            done = read(marker); verify_hashes(part, done['files'])
        else:
            test_folder = TEST/'chunks'/train_folder.name
            bars = pd.concat([pd.read_parquet(train_folder/'bars.parquet'), pd.read_parquet(test_folder/'bars.parquet')], ignore_index=True)
            if bars.duplicated(['date', 'symbol']).any(): raise ValueError('Overlapping cached price sources')
            bars = bars[bars.date.le('2026-09-30')].copy()
            for symbol, spec in readiness.SPLITS.items():
                mask = bars.symbol.eq(symbol) & bars.date.lt('2023-01-01')
                for c in (*readiness.FIELDS, 'adj_close'): bars.loc[mask, c] *= spec['factor']
                bars.loc[mask, 'volume'] /= spec['factor']
                mask = bars.symbol.eq(symbol) & bars.date.ge('2023-01-01')
                idx = pd.MultiIndex.from_frame(bars.loc[mask, ['symbol', 'date']])
                if len(idx):
                    corrected = prices.reindex(idx)
                    if corrected['close'].isna().any(): raise ValueError('Missing normalized cached price')
                    for c in (*readiness.FIELDS, 'adj_close', 'volume'): bars.loc[mask, c] = corrected[c].to_numpy()
            fs = []
            for folder in (train_folder, test_folder):
                f = pd.read_parquet(folder/'features.parquet', filters=[('date', '>=', pd.Timestamp(earliest)), ('date', '<=', pd.Timestamp('2026-09-01'))],
                    columns=['date', 'symbol', *base_columns])
                fs.append(f)
            features = pd.concat(fs, ignore_index=True)
            if features.duplicated(['date', 'symbol']).any(): raise ValueError('Duplicate feature cache key')
            eligible = common.feature_eligible(features, p['feature_reserves'], base_columns)
            coverage_rows = [dict(chunk=train_folder.name, input_features=len(features), eligible_features=int(eligible.sum()))]
            features = features[eligible].copy(); feature_keys = features[['date', 'symbol']]
            targets = {h: [] for h in p['model_horizons']}; trade_parts = []
            for symbol, group in bars.groupby('symbol', observed=True):
                current = feature_keys[feature_keys.symbol.eq(symbol)]
                if current.empty: continue
                for h in p['model_horizons']:
                    label, grid, good = common.symbol_targets(group, days, horizon=h, start=earliest, end='2026-10-09',
                        identity_events=p['identity_events'].get(symbol, []), price_reserve=p['price_reserves'].get(symbol))
                    label = label.merge(current, on=['date', 'symbol'], validate='one_to_one')
                    targets[h].append(label)
                    if h == 20:
                        eligible_paths = label[label.path_qualified & label.date.between('2024-01-01', '2026-09-01')]
                        positions = days.get_indexer(eligible_paths.date)
                        if len(positions):
                            for holding in p['holding_horizons']:
                                for side in ('LONG', 'SHORT'):
                                    out = execution.paths(grid, positions, side, horizon=holding, tp=.1, sl=.1)
                                    trade_parts.append(pd.DataFrame(dict(date=eligible_paths.date.to_numpy(), symbol=symbol, side=side,
                                        year=eligible_paths.date.dt.year.to_numpy(), holding=holding, entry_date=days[positions+1],
                                        last_path_date=days[positions+20], **out)))
            # J admission only: the label function retains good-at-J rows even
            # when the FUTURE path is unqualified. Do not use path_qualified
            # here, otherwise future availability would change score ranks.
            admitted_j = pd.concat(targets[20], ignore_index=True)[['date', 'symbol']]
            features = features.merge(admitted_j, on=['date', 'symbol'], validate='one_to_one')
            coverage_rows[0]['valid_j_features'] = len(features)
            features.to_parquet(part/'features.parquet', index=False)
            for h, pieces in targets.items(): pd.concat(pieces, ignore_index=True).to_parquet(part/f'labels-h{h}.parquet', index=False)
            pd.concat(trade_parts, ignore_index=True).to_parquet(part/'execution.parquet', index=False)
            done = dict(files={n: digest(part/n) for n in ['features.parquet', 'labels-h10.parquet', 'labels-h20.parquet', 'execution.parquet']}, coverage=coverage_rows)
            atomic_json(marker, done)
        for n, sha in done['files'].items(): files[str((part/n).relative_to(root))] = sha
        members.append(pd.read_parquet(part/'features.parquet', columns=['date', 'symbol']))
        for h in p['model_horizons']: labels[h].append(pd.read_parquet(part/f'labels-h{h}.parquet'))
        coverage.extend(done['coverage'])
        atomic_json(root/'progress.json', dict(status='RUNNING', phase='COMMON_DATA', completed=i, total=72))
        LOG.info('Common dataset %d/72 chunks', i)
    membership = pd.concat(members, ignore_index=True); combined = None
    for h, pieces in labels.items():
        f = classify(pd.concat(pieces, ignore_index=True))
        f = f[['date', 'symbol', TARGET, 'oracle_available_date', 'path_amplitude', 'daily_coverage']].rename(columns={
            TARGET: f'target_h{h}', 'oracle_available_date': f'available_h{h}', 'path_amplitude': f'amplitude_h{h}', 'daily_coverage': f'coverage_h{h}'})
        combined = f if combined is None else combined.merge(f, on=['date', 'symbol'], how='outer', validate='one_to_one')
    combined.to_parquet(root/'labels.parquet', index=False); membership.to_parquet(root/'observable-membership.parquet', index=False)
    files.update({n: digest(root/n) for n in ('labels.parquet', 'observable-membership.parquet')})
    pd.DataFrame(coverage).to_csv(root/'coverage.csv', index=False); files['coverage.csv'] = digest(root/'coverage.csv')
    verify_hashes(Path('.'), p['sources'])
    atomic_json(root/'data-ready.json', dict(files=files, label_rows=len(combined), observable_rows=len(membership)))


def train(root):
    p = read(root/'protocol.json'); verify_hashes(Path('.'), p['sources'])
    verify_hashes(root, read(root/'data-ready.json')['files'])
    from catboost import CatBoostClassifier
    cfg = SimpleNamespace(baseline=SimpleNamespace(**p['params']), reproducibility=SimpleNamespace(seed=p['seed']), max_workers=p['threads'])
    for year, fold in p['folds'].items():
        marker = root/f'{year}-done.json'
        if marker.exists(): verify_hashes(root, read(marker)['files']); continue
        allowed = pd.DatetimeIndex(pd.to_datetime(fold['train']+fold['val']+fold['test']))
        parts = [pd.read_parquet(folder/'features.parquet', filters=[('date', '>=', allowed.min()), ('date', '<=', allowed.max())])
            for folder in sorted((root/'parts').iterdir())]
        x = restore_ranks(pd.concat(parts, ignore_index=True), p['generator_options']); del parts; gc.collect()
        x = x[x.date.isin(allowed)].copy()
        y = pd.read_parquet(root/'labels.parquet', filters=[('date', '>=', allowed.min()), ('date', '<=', allowed.max())])
        f = x.merge(y, on=['date', 'symbol'], validate='one_to_one'); del x, y; gc.collect()
        common_y = f.target_h10.notna() & f.target_h20.notna()
        train_mask = f.date.isin(pd.to_datetime(fold['train'])) & common_y
        val_mask = f.date.isin(pd.to_datetime(fold['val'])) & common_y
        test_mask = f.date.isin(pd.to_datetime(fold['test']))
        if not f.loc[train_mask, 'available_h20'].lt(pd.Timestamp(fold['val'][0])).all(): raise ValueError('Train-label leakage')
        if not f.loc[val_mask, 'available_h20'].lt(pd.Timestamp(fold['test'][0])).all(): raise ValueError('Validation-label leakage')
        summaries = {}; files = {}; columns = p['feature_columns']
        for h in p['model_horizons']:
            folder = root/'models'/year/f'H{h}'; folder.mkdir(parents=True, exist_ok=True)
            atomic_json(root/'progress.json', dict(status='RUNNING', phase='TRAINING_RESEARCH_MODEL', year=year, horizon=h,
                n_train=int(train_mask.sum()), n_val=int(val_mask.sum()), n_test=int(test_mask.sum())))
            LOG.info('Fit %s H%d: train=%d validation=%d test=%d', year, h, train_mask.sum(), val_mask.sum(), test_mask.sum())
            tr = f.loc[train_mask, columns+[f'target_h{h}']].rename(columns={f'target_h{h}': TARGET})
            va = f.loc[val_mask, columns+[f'target_h{h}']].rename(columns={f'target_h{h}': TARGET})
            model = train_catboost(tr, va, columns, cfg); del tr, va; gc.collect()
            path = folder/'model.cbm'; model.save_model(str(path))
            validation_score = model.predict_proba(f.loc[val_mask, columns], thread_count=p['threads'])[:, 1]
            scores = f.loc[test_mask, ['date', 'symbol', 'target_h10', 'target_h20', 'amplitude_h10', 'amplitude_h20']].copy()
            scores['score'] = model.predict_proba(f.loc[test_mask, columns], thread_count=p['threads'])[:, 1]
            reloaded = CatBoostClassifier().load_model(str(path))
            sample = f.loc[test_mask, columns].iloc[:100]
            np.testing.assert_array_equal(model.predict_proba(sample), reloaded.predict_proba(sample))
            scores['model_horizon'] = h; scores['year'] = int(year)
            scores = scores.sort_values(['date', 'score', 'symbol'], ascending=[True, False, True])
            scores['rank'] = scores.groupby('date').cumcount()+1
            scores['scored_count'] = scores.groupby('date').symbol.transform('size')
            scores['selected'] = scores['rank'].le(np.ceil(.2*scores.scored_count))
            out = root/f'{year}-H{h}-scores.parquet'; scores.to_parquet(out, index=False)
            summaries[str(h)] = dict(backend='catboost', target_horizon=h, n_train=int(train_mask.sum()), n_val=int(val_mask.sum()),
                max_train_available=str(f.loc[train_mask, 'available_h20'].max()), max_val_available=str(f.loc[val_mask, 'available_h20'].max()),
                validation_auc=roc_auc(f.loc[val_mask, f'target_h{h}'].to_numpy(), validation_score),
                best_iteration=int(model.get_best_iteration()), model_file=str(path.relative_to(root)), model_sha256=digest(path),
                test_rows=len(scores), selected_rows=int(scores.selected.sum()), seed=p['seed'], reloaded_exact=True)
            for item in (path, out): files[str(item.relative_to(root))] = digest(item)
            atomic_json(folder/'contract.json', dict(protocol_sha256=digest(root/'protocol.json'), **summaries[str(h)],
                feature_columns=columns, serving_ready=False, sql_persisted=False))
            files[str((folder/'contract.json').relative_to(root))] = digest(folder/'contract.json')
            del model, reloaded, scores; gc.collect()
        atomic_json(marker, dict(year=year, summaries=summaries, files=files, common_train_rows=int(train_mask.sum()), common_validation_rows=int(val_mask.sum())))
        del f; gc.collect()
    atomic_json(root/'training-ready.json', dict(status='COMPLETED_RESEARCH_MODELS_NO_PROMOTION', files={f'{year}-done.json': digest(root/f'{year}-done.json') for year in p['folds']}))


def compare(root):
    p = read(root/'protocol.json'); verify_hashes(Path('.'), p['sources'])
    trades = pd.concat([pd.read_parquet(folder/'execution.parquet') for folder in sorted((root/'parts').iterdir())], ignore_index=True)
    trades = execution.gate.attach_costs(trades)
    rows = []; amplitude = []
    for year in p['folds']:
        verify_hashes(root, read(root/f'{year}-done.json')['files'])
        for model_h in p['model_horizons']:
            scores = pd.read_parquet(root/f'{year}-H{model_h}-scores.parquet')
            selected = scores[scores.selected].copy()
            selected.to_parquet(root/f'{year}-H{model_h}-top20pct.parquet', index=False)
            for target_h in p['model_horizons']:
                qualified = selected[selected[f'target_h{target_h}'].notna()]
                amplitude.append(dict(year=int(year), model_horizon=model_h, target_horizon=target_h,
                    selected=len(selected), evaluated=len(qualified), coverage=len(qualified)/len(selected),
                    top20_precision=float(qualified[f'target_h{target_h}'].mean()), mean_amplitude=float(qualified[f'amplitude_h{target_h}'].mean())))
            panel = selected[['date', 'symbol']].merge(trades[trades.year.eq(int(year))], on=['date', 'symbol'], validate='one_to_many')
            for (hold, side), group in panel.groupby(['holding', 'side']):
                # No per-symbol trust gate or direction model: each side separately.
                independent = execution.base.independent_fast(group)
                daily = group.groupby('date').net_outcome.mean()
                rows.append(dict(year=int(year), model_horizon=model_h, holding=int(hold), side=side,
                    selected=len(selected), evaluated=len(group), coverage=len(group)/len(selected),
                    mean_net=float(group.net_outcome.mean()), win_rate=float(group.net_outcome.gt(0).mean()),
                    tp_rate=float(group.tp_first.mean()), sl_rate=float(group.sl_first.mean()),
                    terminal_right=float(group.terminal_direction_right.mean()), independent_n=len(independent),
                    independent_mean_net=float(independent.net_outcome.mean()), mean_loser=float(group.loc[group.net_outcome.le(0), 'net_outcome'].mean()),
                    worst_net=float(group.net_outcome.min()), daily_net_interval=execution.gate.block_interval(daily, nyse_sessions('2024-01-01', '2026-10-09'))))
    pd.DataFrame([{k: v for k, v in row.items() if not isinstance(v, dict)} for row in rows]).to_csv(root/'execution-comparison.csv', index=False)
    pd.DataFrame(amplitude).to_csv(root/'amplitude-comparison.csv', index=False)
    verify_hashes(Path('.'), p['sources'])
    atomic_json(root/'report.json', dict(status='COMPLETED_EXPLORATORY_NO_PROMOTION', protocol_sha256=digest(root/'protocol.json'),
        execution=rows, amplitude=amplitude, files={n: digest(root/n) for n in ['execution-comparison.csv', 'amplitude-comparison.csv']},
        claim='Research H10/H20 amplitude models compared; no trained directional classifier, no annual capital-return claim'))
    atomic_json(root/'progress.json', dict(status='COMPLETED_EXPLORATORY_NO_PROMOTION', phase='DONE'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['prepare', 'build', 'train', 'compare'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    {'prepare': prepare, 'build': build, 'train': train, 'compare': compare}[args.phase](args.output)
