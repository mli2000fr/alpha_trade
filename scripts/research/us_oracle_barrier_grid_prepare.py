"""Repair AVB feature units, common ranks and frozen inference; never fit/write SQL."""
import argparse
import gc
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import event

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.features import compute_features
from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle.security_continuity import load_security_discontinuities, split_frame_on_discontinuities
from modelFactory.oracle_barrier import SCORES
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_barrier_comparison import (
    EXTERNAL, NEW, OLD, SECTORS, checkpoint_frame, freeze_candidates, read, readonly_statement,
)
from scripts.research.us_oracle_barrier_comparison_remediation import verify_replay_sources
from scripts.research.us_oracle_h20_dataset_audit import readonly_begin, restore_ranks
from scripts.research.us_oracle_merger_replay import prepare_prices


def compute_avb(bars, benchmark, options, selector, columns):
    benchmark = benchmark.sort_values('date').reset_index(drop=True)
    if any(options.get(k, False) for k in ('include_sentiment', 'include_fundamentals',
        'include_macro_vix', 'include_macro_vxn', 'include_macro_vix3m', 'include_macro_move')):
        raise ValueError('Unarchived external feature family')
    kwargs = {k: v for k, v in options.items() if k != 'enable_cross_sectional_ranks'}
    parts = [compute_features(p, benchmark_df=benchmark, **kwargs)
             for p in split_frame_on_discontinuities(bars, 'AVB', load_security_discontinuities())]
    result = pd.concat(parts, ignore_index=True)
    result = result.merge(selector[['date', 'symbol', 'selector_short_score']],
                          on=['date', 'symbol'], how='inner', suffixes=('_discard', ''), validate='one_to_one')
    missing = set(columns)-set(result)
    if missing:
        raise ValueError(f'Missing regenerated features {sorted(missing)}')
    return result[['date', 'symbol', *columns]]


def assert_feature_canary(rebuilt, archived, columns, *, before='2026-07-13'):
    pairs = rebuilt.merge(archived, on=['date', 'symbol'], suffixes=('_rebuilt', '_archive'), validate='one_to_one')
    if len(pairs) != len(archived):
        raise ValueError('AVB regenerated membership mismatch')
    canary = pairs.loc[pairs.date.lt(before)]
    if len(canary) < 300:
        raise ValueError('Insufficient pre-correction canary')
    drift = []
    for c in columns:
        same = np.isclose(canary[c+'_rebuilt'].to_numpy(np.float32),
                          canary[c+'_archive'].to_numpy(np.float32), rtol=1e-6, atol=1e-6, equal_nan=True)
        if not same.all():
            drift.append(dict(feature=c, rows=int((~same).sum())))
    if drift:
        raise ValueError(f'Unrelated baseline feature drift: {drift}')
    return dict(rows=len(canary), columns=len(columns), unrelated_drift=drift)


def replace_avb_features(features, rebuilt):
    columns = [c for c in features if c not in ('date', 'symbol')]
    original = features.loc[features.symbol.eq('AVB')]
    replacement = original[['date', 'symbol']].merge(rebuilt, on=['date', 'symbol'], validate='one_to_one')
    if len(replacement) != len(original):
        raise ValueError('Repaired feature keys changed')
    result = pd.concat([features.loc[features.symbol.ne('AVB')], replacement[features.columns]], ignore_index=True)
    if result.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate repaired feature keys')
    return result


def prepare(source, evidence, output, threads=4):
    output.mkdir(parents=True, exist_ok=True)
    original = read(source/'protocol.json')
    verify_replay_sources(original['source_hashes'])
    verify_hashes(evidence, read(evidence/'manifest.json')['files'])
    profile = read(NEW/'feature_profile.json')
    feature_paths = sorted(EXTERNAL.glob('corrected-features-*.parquet'))
    if len(feature_paths) != 72:
        raise ValueError('Incomplete external feature archive')
    model_paths = dict(old=OLD/'corrected/2024-01-08/model.txt',
                       long=NEW/'folds/2024-01-08/long_model.txt',
                       short=NEW/'folds/2024-01-08/short_model.txt')
    input_paths = [source/'protocol.json', source/'scores.parquet', source/'macro.parquet',
                   Path(SECTORS), *feature_paths, *model_paths.values(), evidence/'manifest.json',
                   *[evidence/k for k in read(evidence/'manifest.json')['files']]]
    bars_parts = []
    for p in sorted(source.glob('bars-*.parquet')):
        verify_hashes(source, {p.name: read(source/f'{p.name}.json')['sha256']})
        input_paths.append(p)
        bars_parts.append(pd.read_parquet(p))
    for p in feature_paths:
        marker = p.name.replace('corrected-features-', 'features-').replace('.parquet', '.json')
        verify_hashes(EXTERNAL, {p.name: read(EXTERNAL/marker)[p.name]})
    for name in ('scores.parquet', 'macro.parquet'):
        verify_hashes(source, {name: read(source/f'{name}.json')['sha256']})
    hashes = {str(p): digest(p) for p in input_paths}
    config = dict(source=str(source), evidence=str(evidence), source_hashes=hashes,
        code_sha256=digest(__file__), feature_engine_sha256=digest('modelFactory/features.py'),
        factor_engine_sha256=digest('modelFactory/factor_features.py'),
        universe=original['universe'], columns=profile['feature_columns'],
        options=profile['generator_options'], frozen_model_files={k: str(v) for k,v in model_paths.items()},
        sql_writes=False, training=False, broker_orders=False,
        correction_scope='AVB feature share units + affected common daily cross-sectional ranks')
    marker = output/'input-protocol.json'
    if marker.exists() and read(marker) != config:
        raise ValueError('Preparation inputs changed; use a new output')
    atomic_json(marker, config)
    if (output/'prepared.json').exists():
        prepared = read(output/'prepared.json')
        verify_hashes(output, prepared['files'])
        return prepared
    atomic_json(output/'progress.json', dict(status='PREPARING', phase='price_units'))
    bars = pd.concat(bars_parts, ignore_index=True)
    bars['volume'] = bars.volume.astype(float)
    calendar = nyse_sessions(pd.Timestamp('2024-01-01').date(), pd.Timestamp(original['as_of']).date())
    prices, qualification = prepare_prices(bars, evidence, calendar)
    prices['instrument_id'] = prices.instrument_id.astype('string')
    prices.to_parquet(output/'prices.parquet', index=False)
    del bars, bars_parts, prices
    gc.collect()
    atomic_json(output/'progress.json', dict(status='PREPARING', phase='feature_repair'))
    features = pd.concat([pd.read_parquet(p) for p in feature_paths], ignore_index=True)
    archived = features.loc[features.symbol.eq('AVB')].copy()
    base_columns = [c for c in profile['feature_columns'] if not c.endswith('_xs_rank')]
    historical = read(OLD/'protocol.json')
    audit = read(Path(historical['after'])/'protocol.json')
    warmup = (pd.Timestamp(audit['start'])-pd.Timedelta(days=1100)).date().isoformat()
    def load_warmup():
        engine = get_sqlalchemy_engine(db_name='alpha_trade')
        if engine.url.database != 'alpha_trade':
            raise ValueError('Wrong US database')
        event.listen(engine, 'begin', readonly_begin)
        event.listen(engine, 'before_cursor_execute', readonly_statement)
        try:
            return load_universe_bars(engine, ['AVB','SPY'], start_date=warmup, end_date='2026-09-03')
        finally:
            engine.dispose()
    warm = checkpoint_frame(output, 'warmup-avb-spy.parquet', load_warmup)
    avb, spy = warm.loc[warm.symbol.eq('AVB')].copy(), warm.loc[warm.symbol.eq('SPY')].copy()
    # Restore only the independently qualified dates; preserve all old input units.
    avb['volume'] = avb.volume.astype(float)
    raw_feature = compute_avb(avb, spy, profile['generator_options'], archived, base_columns)
    baseline_canary = assert_feature_canary(raw_feature, archived, base_columns)
    target_dates = pd.date_range(qualification['avb_restored_first_date'], qualification['avb_restored_last_date'])
    repaired = avb.copy()
    mask = repaired.date.isin(target_dates)
    # The cached evidence supplies the ratio; this does not tune an output return.
    from scripts.research.us_oracle_merger_replay import RATIO, provider_frame
    for c in ('open','high','low','close','adj_close','vwap'):
        repaired.loc[mask, c] *= RATIO
    repaired.loc[mask, 'volume'] /= RATIO
    raw_prices = provider_frame(evidence, 'AVB')
    matched = repaired.loc[mask].merge(raw_prices, on='date', suffixes=('_repaired','_sip'), validate='one_to_one')
    if len(matched) != qualification['avb_successor_adjusted_rows']:
        raise ValueError('Changed SQL share-basis dates')
    for c in ('open','high','close'):
        if not np.isclose(matched[c+'_repaired'], matched[c+'_sip'], rtol=.001, atol=1e-6).all():
            raise ValueError('Current warmup cannot use archived AVB restoration')
    rebuilt = compute_avb(repaired, spy, profile['generator_options'], archived, base_columns)
    corrected_canary = assert_feature_canary(rebuilt, archived, base_columns)
    rebuilt.to_parquet(output/'repaired-avb-features.parquet', index=False)
    features = replace_avb_features(features, rebuilt)
    original_scores = pd.read_parquet(source/'scores.parquet')
    features = features.merge(original_scores[['date','symbol']], on=['date','symbol'], validate='one_to_one')
    if len(features) != len(original_scores):
        raise ValueError('Frozen eligibility changed')
    for c in features.select_dtypes(include='float64'):
        features[c] = features[c].astype(np.float32)
    features = restore_ranks(features, profile['feature_columns'])
    features[profile['feature_columns']] = features[profile['feature_columns']].replace([np.inf,-np.inf],np.nan).astype(np.float32)
    atomic_json(output/'progress.json', dict(status='PREPARING', phase='frozen_inference', rows=len(features)))
    import lightgbm as lgb
    scores = features[['date','symbol']].copy()
    for key, p in model_paths.items():
        model = lgb.Booster(model_file=str(p))
        if model.feature_name() != profile['feature_columns']:
            raise ValueError('Frozen model feature order changed')
        column = 'old_score' if key == 'old' else SCORES[key]
        scores[column] = model.predict(features[profile['feature_columns']], num_threads=threads)
    scores['max_score'] = scores[list(SCORES.values())].max(axis=1)
    paired = scores.merge(original_scores, on=['date','symbol'], suffixes=('_repaired','_old'), validate='one_to_one')
    changes = []
    for year, group in paired.groupby(paired.date.dt.year):
        for c in ('old_score', *SCORES.values()):
            equal = np.isclose(group[c+'_repaired'], group[c+'_old'], rtol=1e-10, atol=1e-10)
            if year == 2025 and not equal.all():
                raise ValueError('2025 inference changed without a 2025 price correction')
            changes.append(dict(year=int(year), score=c, changed_rows=int((~equal).sum())))
    scores.to_parquet(output/'scores.parquet', index=False)
    pd.read_parquet(source/'macro.parquet').to_parquet(output/'macro.parquet', index=False)
    selections = []
    for arm in ('OLD_TERMINAL_LONG','NEW_BARRIER_LONG'):
        for n in (10,20,50):
            for name, panel in [('before', original_scores),('after', scores)]:
                selected = freeze_candidates(panel.loc[panel.date.dt.year.eq(2026)], n, arm)
                dates = selected.loc[selected.symbol.eq('AVB'),'date']
                selections.append(dict(arm=arm,count=n,version=name,selected_avb_dates=len(dates),
                                       dates=[str(d.date()) for d in dates]))
    july = rebuilt.loc[rebuilt.date.eq('2026-07-13'),['date','daily_return','overnight_gap','momentum_20','atr_14_norm']]
    report = dict(status='AVB_FEATURES_AND_COMMON_RANKS_REPAIRED', qualification=qualification,
        baseline_canary=baseline_canary, corrected_canary=corrected_canary,
        repaired_20260713=july.to_dict('records'), score_changes=changes, selections=selections,
        non_avb_base_features_unchanged=True, common_daily_ranks_recomputed=True,
        predictions_recomputed=True, models_unchanged=True, sql_writes=False,
        files={name: digest(output/name) for name in ('prices.parquet','scores.parquet','macro.parquet',
            'warmup-avb-spy.parquet','repaired-avb-features.parquet')})
    for p, checksum in hashes.items():
        if digest(p) != checksum:
            raise ValueError(f'Original input changed during preparation {p}')
    atomic_json(output/'prepared.json', report)
    atomic_json(output/'progress.json', dict(status='READY_GRID', rows=len(scores), sessions=int(scores.date.nunique())))
    print(json.dumps(dict(status=report['status'], canary=corrected_canary, score_changes=changes,
                         selections=selections), default=str))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    prepare(**vars(args))
