"""Qualify earlier CatBoost OOF candidates and J-only protection features.

Inference with existing weights only. No selector fitting, SQL or network.
Features, target outcomes, rejected candidates and purges stay separate.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import gc
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from modelFactory.features import _build_adjusted_price_frame, _rsi, _atr_value
from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle.security_continuity import (
    DEFAULT_REGISTRY_PATH, load_security_discontinuities, split_frame_on_discontinuities,
    path_crosses_known_discontinuity,
)
from modelFactory.oracle_path.train import digest, restore_ranks
from modelFactory.oracle_path.predict import load_contract, select_fold
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, verify_hashes
from scripts.research.us_oracle_path_top5_leverage_grid import read
from scripts.research.us_oracle_path_protection_headroom import (
    PROFILES, SL, build_chunk, price_arrays, nonoverlap, KNOWN_CODE_DRIFT,
)

LOG = logging.getLogger(__name__)
HISTORY = Path('artifacts/research/oracle_path_comparison/20261013-v1/models/oracle-path-comparison/oracle_path')
HEADROOM = Path('artifacts/research/us_oracle_path_protection_headroom/20261014-v2')
MACRO = Path('artifacts/research/us_oracle_path_entry_separability/20261014-v2')
STOCK = ['daily_return', 'intraday_range', 'overnight_gap', 'volume_ratio_20',
    'rolling_volatility_20', 'rolling_volatility_60', 'rsi_14', 'atr20_pct',
    'sma20_distance', 'sma50_distance', 'momentum_5', 'momentum_20', 'momentum_60',
    'momentum_120', 'vol_ratio_20_60', 'range_position_20']
MARKET = ['market_return_20', 'market_volatility_20', 'market_trend_strength_50',
          'regime_bull_market', 'regime_risk_off', 'relative_strength_20', 'relative_strength_60']
FEATURES = [*STOCK, *MARKET, 'oracle_rank']
START, END, AS_OF, HORIZON = '2018-07-05', '2023-07-07', '2023-12-29', 60
ANNUAL_MODELS = {2024: 'model-factory-20261014113215-437ed1',
                 2025: 'model-factory-20261014113226-102eca',
                 2026: 'model-factory-20261014113232-bc35a7'}


def annual_test_contracts(profile, universe):
    """Bind the user's new test models; never choose an in-sample future fold."""
    contracts, sources = {}, {}
    for year, batch in ANNUAL_MODELS.items():
        root, protocol, current, folds = load_contract('artifacts/models', batch)
        if protocol.get('training_backend') != 'catboost':
            raise ValueError('Requested annual model is not explicit CatBoost path')
        if current['feature_columns'] != profile['feature_columns'] or current['generator_options'] != profile['generator_options']:
            raise ValueError('Annual test model feature semantics differ from historical OOF')
        if set(protocol['universe']) != set(universe):
            raise ValueError('Annual test universe differs from OOF dataset')
        calendar = nyse_sessions(f'{year}-01-01', f'{year}-12-31' if year != 2026 else '2026-09-30')
        chosen = select_fold(calendar[0], folds)
        if any(select_fold(d, folds) != chosen for d in calendar):
            raise ValueError('Unfrozen intra-year test fold')
        fold = folds[chosen]
        if fold['backend'] != 'catboost':
            raise ValueError('Unexpected annual inference backend')
        contracts[str(year)] = dict(batch_id=batch, fold=chosen, backend=fold['backend'],
            model_sha256=fold['model_sha256'], train_available_max=fold['metrics']['train_available_max'],
            val_available_max=fold['metrics']['val_available_max'],
            requested_training_end=protocol['training_config']['data']['training_end_date'],
            decision_start=str(calendar[0].date()), decision_end=str(calendar[-1].date()),
            new_test_scores_computed=False, backtest_launched=False)
        for p in [root/'protocol.json', root/'feature_profile.json', root/'report.json',
                  root/'folds'/chosen/'done.json', Path(fold['model_file'])]:
            sources[str(p)] = digest(p)
    return contracts, sources


def fold_is_causal(done):
    metrics = done['metrics']
    start, end = pd.Timestamp(metrics['test_start']), pd.Timestamp(metrics['test_end'])
    if pd.isna(start) or pd.isna(end) or start > end:
        raise ValueError('Invalid OOF scoring window')
    for key in ('train_available_max', 'val_available_max'):
        known = pd.Timestamp(metrics[key])
        if pd.isna(known) or known >= start:
            raise ValueError('OOF fold sees labels from its scoring window')
    return start, end


def freeze_top5(scores):
    if scores.duplicated(['date', 'symbol']).any() or not np.isfinite(scores.score).all():
        raise ValueError('Duplicate/nonfinite observable score')
    if not scores.score.between(0, 1).all():
        raise ValueError('Invalid amplitude probability')
    frame = scores.sort_values(['date', 'score', 'symbol'], ascending=[True, False, True]).copy()
    frame['oracle_rank'] = frame.groupby('date').cumcount()+1
    return frame[frame.oracle_rank.le(5)].copy()


def protocol_for(output):
    marker = output/'protocol.json'
    if marker.exists():
        saved = read(marker); verify_hashes(Path('.'), saved['sources'])
        if saved['features'] != FEATURES or saved['horizon'] != HORIZON:
            raise ValueError('Changed dataset contract: new output required')
        return saved
    headroom = read(HEADROOM/'report.json')
    verify_hashes(HEADROOM, headroom['files'])
    if headroom['verdict'] != 'MATERIAL_HINDSIGHT_SPACE_NOT_LEARNABILITY':
        raise ValueError('Completed headroom qualification required')
    sources, drift = {}, []
    old_plan = read(HISTORY.parents[2]/'plan.json')
    for name, expected in old_plan['source_hashes'].items():
        actual = digest(name)
        if expected != actual:
            if Path(name).as_posix() not in KNOWN_CODE_DRIFT:
                raise ValueError(f'Unexplained historical source drift: {name}')
            drift.append(dict(path=name, original_sha256=expected, current_sha256=actual))
        sources[name] = actual
    folds = []
    for folder in sorted((HISTORY/'folds').iterdir()):
        done = read(folder/'done.json'); verify_hashes(folder, done['files'])
        start, end = fold_is_causal(done)
        if not {'catboost_model.cbm', 'oof.parquet'} <= set(done['files']):
            raise ValueError('Original CatBoost weight/OOF absent')
        folds.append(dict(name=folder.name, start=str(start.date()), end=str(end.date()),
                          train_available_max=done['metrics']['train_available_max'],
                          val_available_max=done['metrics']['val_available_max']))
        for name in ('done.json', 'catboost_model.cbm', 'oof.parquet'):
            sources[str(folder/name)] = digest(folder/name)
    if len(folds) != 10 or folds[0]['start'] != START or folds[-1]['end'] != END:
        raise ValueError('Expected ten causal historical folds')
    for folder in sorted((HISTORY/'chunks').iterdir()):
        done = read(folder/'done.json')
        verify_hashes(folder, {n: done['files'][n] for n in ['features.parquet', 'bars.parquet']})
        for name in ('done.json', 'features.parquet', 'bars.parquet'):
            sources[str(folder/name)] = digest(folder/name)
    paths = [HISTORY.parents[2]/'plan.json', HISTORY/'protocol.json', HISTORY/'feature_profile.json',
        HEADROOM/'protocol.json', HEADROOM/'report.json', HEADROOM/'completion-audit.json',
        Path(__file__), Path('tests/test_us_oracle_path_protection_dataset.py'),
        Path('modelFactory/features.py'), Path('modelFactory/oracle/security_continuity.py'),
        DEFAULT_REGISTRY_PATH, Path('scripts/research/us_oracle_path_protection_headroom.py'),
        MACRO/'macro-snapshot.parquet.json', MACRO/'macro-snapshot.parquet']
    sources.update({str(p): digest(p) for p in paths})
    profile = read(HISTORY/'feature_profile.json')
    old = read(HISTORY/'protocol.json')
    annual_contracts, annual_sources = annual_test_contracts(profile, old['universe'])
    sources.update(annual_sources)
    registry = load_security_discontinuities()
    encoded = {s: [asdict(e) for e in events] for s, events in registry.items()}
    # Compare timestamps via JSON normalization, as in the original trainer.
    import json
    if json.loads(json.dumps(encoded, default=str)) != old['security_discontinuities']:
        raise ValueError('Discontinuities differ from source Oracle')
    value = dict(features=FEATURES, excluded_features=['macro_publication_vintages', 'selector_short_score',
        'sentiment/news', 'consensus/fundamentals', 'current_sector', 'symbol/date/year',
        'score_oracle_upstream_lineage_reserved', 'entry_price_or_gap_J1', 'future_results'],
        folds=folds, features_profile=profile, universe=old['universe'], profiles=PROFILES, sl=SL,
        start=START, end=END, as_of=AS_OF, horizon=HORIZON, top=5, original_backend='catboost',
        splits=dict(fit_decision_end='2021-12-31', fit_label_before='2022-01-01',
                    validation_year=2022, validation_label_before='2023-01-01', control_year=2023),
        raw_price_adjustment='split; no extra dividend adjustment in outcomes',
        calculation_prices='adj_close / close factor same as archived feature generator',
        readiness=dict(min_examples_per_split=100, min_dates_per_split=30, min_feature_coverage=.95),
        historical_code_drift=drift, sources=sources, selector_training=False, oracle_training=False,
        annual_test_models=annual_contracts,
        sql_writes=False, broker_calls=False, production_changed=False,
        strict_provider_vintages_certified=False, oracle_selector_input_lineage_reserved=True,
        frozen_protocol_document_sha256=digest('doc/ml/oracle_path_protections_dataset_oof_20261014.md'))
    atomic_json(marker, value)
    return value


def score_folds(output, protocol):
    from catboost import CatBoostClassifier
    pieces = []
    columns = protocol['features_profile']['feature_columns']
    raw = list(dict.fromkeys(c.removesuffix('_xs_rank') for c in columns))
    for number, spec in enumerate(protocol['folds']):
        folder = output/'folds'/spec['name']; folder.mkdir(parents=True, exist_ok=True)
        marker = folder/'done.json'
        if marker.exists():
            saved = read(marker); verify_hashes(folder, saved['files'])
            pieces.append(pd.read_parquet(folder/'candidates.parquet')); continue
        parts = []
        for k, chunk in enumerate(sorted((HISTORY/'chunks').iterdir())):
            frame = pd.read_parquet(chunk/'features.parquet', columns=['date', 'symbol', *raw],
                filters=[('date', '>=', pd.Timestamp(spec['start'])), ('date', '<=', pd.Timestamp(spec['end']))])
            if not frame.empty:
                frame[raw] = frame[raw].astype(np.float32)
                parts.append(frame)
            if k % 12 == 0:
                atomic_json(output/'progress.json', dict(status='SCORING_OOF', fold=spec['name'],
                    completed_folds=number, total_folds=10, read_chunks=k, total_chunks=72))
        matrix = restore_ranks(pd.concat(parts, ignore_index=True), protocol['features_profile']['generator_options'])
        del parts; gc.collect()
        if matrix.duplicated(['date', 'symbol']).any():
            raise ValueError('Duplicate observable feature membership')
        model = CatBoostClassifier().load_model(str(HISTORY/'folds'/spec['name']/'catboost_model.cbm'))
        if model.feature_names_ != columns:
            raise ValueError('CatBoost feature order mismatch')
        values = matrix[columns].replace([np.inf, -np.inf], np.nan).astype(np.float32)
        scores = matrix[['date', 'symbol']].copy()
        scores['score'] = model.predict_proba(values, thread_count=2)[:, 1]
        scores['fold_start'] = spec['name']
        old = pd.read_parquet(HISTORY/'folds'/spec['name']/'oof.parquet',
                              columns=['date', 'symbol', 'score_catboost'])
        compared = old.merge(scores, on=['date', 'symbol'], validate='one_to_one')
        error = float((compared.score_catboost-compared.score).abs().max())
        if len(compared) != len(old) or not np.isfinite(error) or error > 1e-7:
            raise ValueError(f'Archived OOF score reproduction failed: {spec["name"]}: {error}')
        selected = freeze_top5(scores)
        selected = selected.merge(matrix[['date', 'symbol', *STOCK, *MARKET]],
                                  on=['date', 'symbol'], how='left', validate='one_to_one')
        scores.to_parquet(folder/'observable-scores.parquet', index=False)
        selected.to_parquet(folder/'candidates.parquet', index=False)
        saved = dict(observable_rows=len(scores), original_oof_rows=len(old), original_score_max_error=error,
            candidates=len(selected), files={n: digest(folder/n) for n in ['observable-scores.parquet', 'candidates.parquet']})
        atomic_json(marker, saved); pieces.append(selected)
        LOG.info('OOF %s: %s observable / %s TOP5; max reproduction error %s',
                 spec['name'], len(scores), len(selected), error)
        del model, matrix, values, scores, compared; gc.collect()
    pool = pd.concat(pieces, ignore_index=True)
    if pool.duplicated(['date', 'symbol']).any() or not pool.groupby('date').size().eq(5).all():
        raise ValueError('Overlapping/incomplete historical TOP5')
    return pool


def benchmark_history():
    parts = [pd.read_parquet(folder/'features.parquet', columns=['date', 'benchmark_close'])
             for folder in sorted((HISTORY/'chunks').iterdir())]
    frame = pd.concat(parts, ignore_index=True).dropna()
    if frame.groupby('date').benchmark_close.nunique().gt(1).any():
        raise ValueError('Inconsistent common benchmark cache')
    return frame.drop_duplicates('date').sort_values('date').set_index('date').benchmark_close.astype(float)


def decision_features(bars, benchmark):
    """Backward-only, no SQL/selector/macro merge or future target accepted."""
    data = bars.sort_values('date').reset_index(drop=True)
    prices = _build_adjusted_price_frame(data)
    close, high, low, opening = (prices[c] for c in ['close', 'high', 'low', 'open'])
    volume = data.volume.astype(float)
    returns = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.)
    benchmark = benchmark.sort_index()
    br = benchmark.pct_change(fill_method=None)
    frame = pd.DataFrame({'date': data.date, 'daily_return': returns,
        'intraday_range': (high-low)/close.clip(lower=1e-8),
        'overnight_gap': (opening-close.shift())/close.shift().clip(lower=1e-8),
        'volume_ratio_20': volume/volume.rolling(20).mean().clip(lower=1.),
        'rolling_volatility_20': returns.rolling(20).std(),
        'rolling_volatility_60': returns.rolling(60).std(), 'rsi_14': _rsi(close, 14),
        'atr20_pct': _atr_value(high, low, close, 20)/close.clip(lower=1e-8)})
    for window in (20, 50):
        mean = close.rolling(window).mean()
        frame[f'sma{window}_distance'] = (close-mean)/mean.clip(lower=1e-8)
    for window in (5, 20, 60, 120):
        frame[f'momentum_{window}'] = close/close.shift(window)-1
    frame['vol_ratio_20_60'] = frame.rolling_volatility_20/frame.rolling_volatility_60.clip(lower=1e-8)
    minimum, maximum = close.rolling(20).min(), close.rolling(20).max()
    frame['range_position_20'] = (close-minimum)/(maximum-minimum).clip(lower=1e-8)
    b50, b200 = benchmark.rolling(50).mean(), benchmark.rolling(200).mean()
    common = {'market_return_20': br.rolling(20).mean(), 'market_volatility_20': br.rolling(20).std(),
        'market_trend_strength_50': (benchmark-b50)/b50.clip(lower=1e-8),
        'regime_bull_market': (benchmark > b200).astype(float),
        'regime_risk_off': (br.rolling(20).std() > br.rolling(60).std()).astype(float)}
    for key, values in common.items():
        frame[key] = frame.date.map(values)
    for window in (20, 60):
        frame[f'relative_strength_{window}'] = frame[f'momentum_{window}']-frame.date.map(benchmark/benchmark.shift(window)-1)
    return frame.set_index('date')


def j_history_quality(data, benchmark, days):
    numeric = data[['open', 'high', 'low', 'close', 'volume']].astype(float)
    valid = np.isfinite(numeric).all(axis=1) & numeric.gt(0).all(axis=1) & data.is_filled.eq(0)
    valid &= data.high.ge(data[['open', 'close']].max(axis=1)) & data.low.le(data[['open', 'close']].min(axis=1))
    valid &= data.high.ge(data.low)
    ids = data.instrument_id.astype('string')
    codes, _ = pd.factorize(ids)
    identity = pd.Series(codes, index=data.index, dtype=float).mask(codes < 0)
    stable = identity.rolling(121, min_periods=121).max().eq(identity.rolling(121, min_periods=121).min())
    stock = valid.rolling(121, min_periods=121).sum().eq(121) & stable
    b = benchmark.reindex(days)
    bvalid = np.isfinite(b) & b.gt(0)
    bvalid = bvalid.rolling(201, min_periods=201).sum().eq(201)
    return stock & bvalid.reindex(data.index).fillna(False)


def assign_split(date, available):
    date, available = pd.Timestamp(date), pd.Timestamp(available)
    if pd.isna(available):
        return 'UNAVAILABLE_LABEL'
    if date <= pd.Timestamp('2021-12-31'):
        return 'FIT_2018_2021' if available < pd.Timestamp('2022-01-01') else 'PURGED_FIT_BOUNDARY'
    if date.year == 2022:
        return 'VALIDATION_2022' if available < pd.Timestamp('2023-01-01') else 'PURGED_VALIDATION_BOUNDARY'
    if date.year == 2023 and available <= pd.Timestamp(AS_OF):
        return 'CONTROL_2023'
    return 'OUTSIDE'


def inputs_at_j(pool, prices, benchmark, days, registry):
    result, canaries = [], []
    for symbol, candidates in pool.groupby('symbol'):
        bars = prices[prices.symbol.eq(symbol)].copy()
        if bars.empty:
            raise ValueError('Missing selected historical symbol price tape')
        pieces, qualities = [], []
        for part in split_frame_on_discontinuities(bars, symbol, registry):
            pieces.append(decision_features(part, benchmark))
            full = part.set_index('date').reindex(days[(days >= part.date.min()) & (days <= part.date.max())])
            qualities.append(j_history_quality(full, benchmark, days))
        calc = pd.concat(pieces)
        quality = pd.concat(qualities)
        if calc.index.duplicated().any() or quality.index.duplicated().any():
            raise ValueError('Duplicate price history segment')
        selected = candidates[['date', 'symbol', 'fold_start', 'oracle_rank', 'score']].copy()
        selected = selected.merge(calc[STOCK+MARKET], left_on='date', right_index=True, how='left', validate='one_to_one')
        good = selected.date.map(quality).fillna(False) & np.isfinite(selected[STOCK+MARKET]).all(axis=1)
        selected['feature_quality_reason'] = np.where(good, '', 'J_121_VALID_BARS_IDENTITY_OR_BENCHMARK_201_OR_FEATURES')
        # Integrity check, not feature selection based on outcomes.
        archived = candidates[['date', *STOCK, *MARKET]].set_index('date')
        comparison = selected.set_index('date')[STOCK+MARKET]
        common = comparison.index.intersection(archived.index)
        actual, expected = comparison.loc[common].to_numpy(float), archived.loc[common].to_numpy(float)
        agreement = np.isclose(actual, expected, atol=1e-4, rtol=1e-4, equal_nan=True)
        if not agreement.all():
            bad = np.argwhere(~agreement)[0]
            raise ValueError(f'Recomputed J feature differs {symbol}/{common[bad[0]]}/{(STOCK+MARKET)[bad[1]]}: '
                             f'{actual[tuple(bad)]} vs {expected[tuple(bad)]}')
        # Fixed first/middle/last dates, not based on target or winning profile.
        for day in sorted(set(candidates.date.iloc[[0, len(candidates)//2, -1]])):
            part = next(p for p in split_frame_on_discontinuities(bars, symbol, registry)
                        if p.date.min() <= day <= p.date.max())
            truncated = decision_features(part[part.date.le(day)], benchmark[benchmark.index <= day])
            pd.testing.assert_series_equal(calc.loc[day, STOCK+MARKET], truncated.loc[day, STOCK+MARKET], check_exact=True)
        canaries.append(dict(symbol=symbol, selected=len(candidates), qualified=int(good.sum()),
            cache_features_match=True, prefix_dates_checked=min(3, len(candidates)), prefix_exact=True))
        result.append(selected)
    return pd.concat(result, ignore_index=True), canaries


def macro_inventory():
    marker = read(MACRO/'macro-snapshot.parquet.json'); verify_hashes(MACRO, marker['files'])
    macro = pd.read_parquet(MACRO/'macro-snapshot.parquet')
    columns = [c for c in macro if c not in ['trade_date', 'created_at', 'updated_at']]
    return dict(status='EXCLUDED_FROM_PRIMARY_FEATURES_PUBLICATION_PIT_UNQUALIFIED',
        source_sha256=digest(MACRO/'macro-snapshot.parquet'), rows=len(macro),
        coverage={c: int(macro[c].notna().sum()) for c in columns},
        storage_times_are_not_publication_times=True)


def run(output):
    output = Path(output)
    with exclusive_run(output):
        atomic_json(output/'progress.json', dict(status='VERIFYING_INPUTS'))
        protocol = protocol_for(output)
        if (output/'report.json').exists():
            saved = read(output/'report.json'); verify_hashes(output, saved['files']); return saved
        pool = score_folds(output, protocol)
        pool.to_parquet(output/'candidates.parquet', index=False)
        days = nyse_sessions('2016-01-01', AS_OF)
        chunks = []
        symbols = set(pool.symbol)
        for folder in sorted((HISTORY/'chunks').iterdir()):
            frame = pd.read_parquet(folder/'bars.parquet', filters=[('symbol', 'in', sorted(symbols))])
            chunks.append(frame)
        prices = pd.concat(chunks, ignore_index=True)
        if prices.duplicated(['date', 'symbol']).any():
            raise ValueError('Duplicate source price key')
        if not prices.data_adjustment.eq('split').all():
            raise ValueError('Historical prices not all on frozen split basis')
        benchmark = benchmark_history()
        benchmark.rename('benchmark_close').reset_index().to_parquet(output/'benchmark-history.parquet', index=False)
        atomic_json(output/'progress.json', dict(status='QUALIFYING_J_FEATURES', candidates=len(pool)))
        registry = load_security_discontinuities()
        features, canaries = inputs_at_j(pool, prices, benchmark, days, registry)
        if set(FEATURES)-set(features) or len(features) != len(pool):
            raise ValueError('Decision feature membership differs')
        features[['date', 'symbol', *FEATURES]].to_parquet(output/'decision-features.parquet', index=False)
        atomic_json(output/'feature-canaries.json', canaries)
        inputs = pool[['date', 'symbol', 'score', 'oracle_rank']].copy()
        inputs['year'] = inputs.date.dt.year
        inputs = inputs.merge(features[['date', 'symbol', 'feature_quality_reason']], on=['date', 'symbol'], validate='one_to_one')
        inputs['selected'] = inputs.feature_quality_reason.eq('')
        arrays = price_arrays(prices, set(pool.symbol), days)
        outcomes, excluded = build_chunk(inputs, arrays, days, [], HORIZON)
        reserved = outcomes.apply(lambda row: path_crosses_known_discontinuity(row.symbol, row.entry_date,
                                                                              row.label_available, registry), axis=1)
        if reserved.any():
            extra = outcomes.loc[reserved, ['date', 'symbol', 'year', 'oracle_rank', 'score', 'horizon']].copy()
            extra['reason'] = 'KNOWN_SECURITY_DISCONTINUITY'
            excluded = pd.concat([excluded, extra], ignore_index=True)
            outcomes = outcomes[~reserved].copy()
        if len(outcomes)+len(excluded) != len(pool):
            raise ValueError('Candidate qualification accounting lost rows')
        outcomes['split'] = [assign_split(d, a) for d, a in zip(outcomes.date, outcomes.label_available)]
        for name in ('COURT', 'LARGE'):
            outcomes[f'target_{name.lower()}_advantage_pct'] = outcomes[f'{name}_net_pct']-outcomes.REFERENCE_net_pct
        outcomes.to_parquet(output/'outcomes.parquet', index=False)
        excluded.to_parquet(output/'excluded.parquet', index=False)
        index = inputs.merge(outcomes[['date', 'symbol', 'label_available', 'split']], on=['date', 'symbol'], how='left', validate='one_to_one')
        index = index.merge(excluded[['date', 'symbol', 'reason']], on=['date', 'symbol'], how='left', validate='one_to_one')
        index['split'] = index['split'].fillna('EXCLUDED')
        index.to_parquet(output/'dataset-index.parquet', index=False)
        splits = []
        for name in ('FIT_2018_2021', 'VALIDATION_2022', 'CONTROL_2023'):
            rows = outcomes[outcomes.split.eq(name)]
            x = rows[['date', 'symbol']].merge(features[['date', 'symbol', *FEATURES]], validate='one_to_one')
            if len(rows) and not np.isfinite(x[FEATURES]).all().all():
                raise ValueError('A missing feature slipped into ready labels')
            spaced = nonoverlap(rows, days)
            matrix = rows[[f'{p}_net_pct' for p in PROFILES]].to_numpy(float)
            splits.append(dict(name=name, examples=len(rows), dates=int(rows.date.nunique()),
                symbols=int(rows.symbol.nunique()), nonoverlapping_examples=len(spaced),
                decision_start=str(rows.date.min().date()) if len(rows) else None,
                decision_end=str(rows.date.max().date()) if len(rows) else None,
                label_available_max=str(rows.label_available.max().date()) if len(rows) else None,
                all_three_equal_share=float(np.isclose(matrix, matrix[:, :1], rtol=0, atol=1e-10).all(axis=1).mean()) if len(rows) else None,
                all_three_negative_share=float((matrix.max(axis=1)<0).mean()) if len(rows) else None))
        admitted = features[features.feature_quality_reason.eq('')]
        coverage = {c: float(np.isfinite(admitted[c]).mean()) if len(admitted) else 0. for c in FEATURES}
        original_coverage = {c: float(np.isfinite(features[c]).mean()) for c in FEATURES}
        gate = all(s['examples'] >= 100 and s['dates'] >= 30 for s in splits) and all(v >= .95 for v in coverage.values())
        macro = macro_inventory()
        atomic_json(output/'lineage-inventory.json', dict(authorized_features=FEATURES,
            calculation_causality='PREFIX_EXACT_AND_ARCHIVED_VALUES_MATCH',
            provider_historical_vintages='RESERVED_CURRENT_ADJUSTED_HISTORY',
            oracle_population_lineage='RESERVED_SELECTOR_SHORT_INPUT', excluded_macro=macro,
            excluded_other_families=protocol['excluded_features']))
        verify_hashes(Path('.'), protocol['sources'])
        report = dict(status='COMPLETED_QUALIFICATION',
            verdict='READY_FOR_EXPLORATORY_PILOT_NOT_TRAINED' if gate else 'BLOCKED_DATASET_COVERAGE',
            original_candidates=len(pool), feature_qualified=len(admitted), outcome_qualified=len(outcomes),
            exclusions=excluded.reason.value_counts().to_dict(), splits=splits,
            purges=outcomes[outcomes.split.str.startswith('PURGED')].split.value_counts().to_dict(),
            features=FEATURES, feature_coverage_admitted_at_J=coverage,
            feature_finite_coverage_original_TOP5=original_coverage,
            annual_test_models=protocol['annual_test_models'],
            original_folds_verified=10, all_oof_scores_reproduced=True, prefix_canaries=canaries,
            training=False, sql_writes=False, broker_calls=False, production_changed=False,
            strict_pit_certified=False, learnability_proven=False, independent_holdout=False,
            files={str(p.relative_to(output)): digest(p) for p in output.rglob('*')
                   if p.suffix in ['.parquet', '.json'] and p.name not in ['report.json', 'progress.json']})
        atomic_json(output/'report.json', report)
        atomic_json(output/'progress.json', dict(status=report['status'], verdict=report['verdict'], splits=splits))
        LOG.info('Dataset qualification finished: %s', report['verdict'])
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__); parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
        handlers=[logging.StreamHandler(), logging.FileHandler(Path(args.output)/'stderr.log', encoding='utf-8')])
    try:
        run(args.output)
    except Exception as exc:
        atomic_json(Path(args.output)/'failure.json', dict(status='FAILED', error=str(exc), error_type=type(exc).__name__))
        raise
