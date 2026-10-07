"""Reconstruct the saved Oracle feature contract; audit, never train or write SQL.

Chunk caches contain base features only. Cross-sectional ranks are computed AFTER
all symbol chunks are assembled for a year, never inside a symbol shard.
Stored labels retain their ORIGINAL batch universe; do not relabel after exclusions.
"""
from __future__ import annotations

import argparse
import gc
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, event, text

from database.connection import get_sqlalchemy_engine
from modelFactory import features as feature_module
from modelFactory import factor_features as factor_module
from modelFactory.oracle.dataset import build_feature_matrix
from modelFactory.oracle.leakage import assert_no_forbidden_features, assert_no_future_features
from modelFactory.oracle.security_continuity import load_security_discontinuities, DEFAULT_REGISTRY_PATH
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

LOG = logging.getLogger(__name__)


def readonly_begin(conn):
    conn.exec_driver_sql('SET TRANSACTION READ ONLY')


def summarize_features(frame, columns):
    """Exact per-year statistics on emitted features, not pre-cleaning inputs."""
    result = []
    for column in columns:
        values = pd.to_numeric(frame[column], errors='coerce')
        finite = np.isfinite(values.to_numpy(dtype=float))
        good = values.loc[finite]
        quantiles = good.quantile([.001, .01, .5, .99, .999]) if len(good) else None
        top = good.abs().nlargest(3).index
        examples = []
        for idx in top:
            examples.append(dict(symbol=str(frame.at[idx, 'symbol']),
                date=str(pd.Timestamp(frame.at[idx, 'date']).date()), value=float(values.at[idx])))
        result.append(dict(feature=column, rows=len(values), finite=int(finite.sum()),
            null=int(values.isna().sum()), infinite=int(np.isinf(values.to_numpy(dtype=float)).sum()),
            zeros=int(good.eq(0).sum()), distinct=int(good.nunique()),
            minimum=float(good.min()) if len(good) else None,
            maximum=float(good.max()) if len(good) else None,
            quantiles={str(k): float(v) for k, v in quantiles.items()} if quantiles is not None else {},
            largest_absolute_examples=examples))
    return result


def restore_ranks(frame, columns):
    """Same groupby.rank(pct=True) convention as Oracle build_feature_matrix."""
    result = frame.copy()
    for column in columns:
        if column.endswith('_xs_rank'):
            source = column[:-len('_xs_rank')]
            if source not in result:
                raise ValueError(f'Missing cross-sectional source: {source}')
            result[column] = result.groupby('date')[source].rank(pct=True)
    missing = sorted(set(columns) - set(result))
    if missing:
        raise ValueError(f'Missing contract columns: {missing}')
    if result.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate feature keys: cross-sectional universe ambiguous')
    return result


def label_checks(frame, current_symbols, registry):
    """Validate stored targets against CURRENT endpoint bars, not an old snapshot.

    Rank checks use the whole stored batch, before filtering current symbols.
    Availability dates are normalized to Timestamp to avoid date/NaT comparisons.
    """
    data = frame.copy().reset_index(drop=True)
    for column in ('prediction_date', 'oracle_exit_date', 'oracle_available_date'):
        data[column] = pd.to_datetime(data[column], errors='coerce')
    numeric = ('future_return', 'future_return_raw', 'oracle_pct_rank', 'oracle_decile',
               'oracle_extreme10', 'target_quality_valid', 'start_px', 'end_px')
    for column in numeric:
        data[column] = pd.to_numeric(data[column], errors='coerce')
    valid = data.target_quality_valid.eq(1)
    rankable = valid & np.isfinite(data.future_return) & data.oracle_pct_rank.notna()
    expected_rank = pd.Series(np.nan, index=data.index)
    expected_rank.loc[rankable] = data.loc[rankable].groupby('prediction_date').future_return.rank(method='max', pct=True)
    expected_decile = np.ceil(data.oracle_pct_rank * 10).clip(1, 10)
    expected_extreme = data.oracle_pct_rank.ge(.9) | data.oracle_pct_rank.le(.1)
    recomputed = data.end_px / data.start_px - 1
    checks = {
        'duplicate_label_keys': data.duplicated(['prediction_date', 'symbol'], keep=False),
        'valid_missing_or_invalid_dates': valid & (
            data.prediction_date.isna() | data.oracle_exit_date.isna() | data.oracle_available_date.isna()
            | data.oracle_exit_date.le(data.prediction_date)
            | data.oracle_available_date.le(data.oracle_exit_date)),
        'valid_nonfinite_return': valid & ~np.isfinite(data.future_return),
        'valid_return_differs_raw': valid & ~np.isclose(data.future_return, data.future_return_raw, atol=1e-9, rtol=1e-8, equal_nan=False),
        'valid_rank_out_of_bounds': valid & data.oracle_pct_rank.notna() & ~data.oracle_pct_rank.between(0, 1),
        'valid_rank_mismatch_original_universe': rankable & ~np.isclose(data.oracle_pct_rank, expected_rank, atol=1e-9, rtol=1e-8),
        'valid_decile_mismatch': rankable & data.oracle_decile.ne(expected_decile),
        'valid_extreme_mismatch': rankable & data.oracle_extreme10.ne(expected_extreme.astype(int)),
        'valid_missing_endpoint': valid & (data.start_px.isna() | data.end_px.isna()),
        'valid_nonpositive_endpoint': valid & (data.start_px.le(0) | data.end_px.le(0)),
        'valid_endpoint_source_mismatch': valid & data.start_source.notna() & data.end_source.notna() & data.start_source.ne(data.end_source),
        'valid_return_mismatch_current_bars': valid & np.isfinite(recomputed) & ~np.isclose(data.future_return_raw, recomputed, atol=1e-8, rtol=1e-7),
    }
    known = pd.Series(False, index=data.index)
    for symbol, entries in registry.items():
        for entry in entries:
            known |= (data.symbol.eq(symbol)
                      & data.prediction_date.le(entry.last_predecessor_date)
                      & data.oracle_exit_date.ge(entry.first_successor_date))
    checks['valid_known_identity_crossing'] = valid & known
    scope = data.symbol.isin(current_symbols)
    counts = {}
    samples = []
    for name, mask in checks.items():
        mask = mask.fillna(False)
        counts[name] = dict(original_batch=int(mask.sum()), current_universe=int((mask & scope).sum()))
        for row in data.loc[mask, ['symbol', 'prediction_date', 'future_return_raw', 'start_px', 'end_px']].head(10).to_dict('records'):
            samples.append(dict(check=name, **{
                k: (None if pd.isna(v) else str(v) if isinstance(v, pd.Timestamp) else v)
                for k, v in row.items()}))
    return dict(rows=len(data), valid=int(valid.sum()), current_universe_rows=int(scope.sum()),
        original_batch_symbols=int(data.symbol.nunique()),
        current_universe_symbols=int(data.loc[scope, 'symbol'].nunique()),
        null_rank_valid=int((valid & data.oracle_pct_rank.isna()).sum()),
        quality_reasons=data.target_quality_reason.fillna('NONE').value_counts().to_dict(),
        checks=counts, samples=samples)


def audit_labels(engine, batch_id, start, end, symbols, registry):
    query = text('''SELECT l.prediction_date,l.symbol,l.oracle_exit_date,l.oracle_available_date,
        l.future_return,l.future_return_raw,l.oracle_pct_rank,l.oracle_decile,l.oracle_extreme10,
        l.target_quality_valid,l.target_quality_reason,
        CAST(COALESCE(s.adj_close,s.`close`) AS DOUBLE) start_px,
        CAST(COALESCE(e.adj_close,e.`close`) AS DOUBLE) end_px,
        s.data_source start_source,e.data_source end_source
        FROM global_oracle_labels l
        LEFT JOIN stock_bars_daily s ON s.symbol=l.symbol AND s.`date`=l.prediction_date
        LEFT JOIN stock_bars_daily e ON e.symbol=l.symbol AND e.`date`=l.oracle_exit_date
        WHERE l.batch_id=:batch AND l.horizon=20 AND l.prediction_date BETWEEN :start AND :end
        ORDER BY l.prediction_date,l.symbol''')
    with engine.connect() as conn:
        frame = pd.read_sql(query, conn, params=dict(batch=batch_id, start=start, end=end))
    return label_checks(frame, set(symbols), registry)


def run(args):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    profile_path = Path('artifacts/models/oracle/champions') / args.batch_id / 'feature_profile.json'
    meta_path = profile_path.with_name('oracle_champions.json')
    profile = json.loads(profile_path.read_text(encoding='utf-8'))
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    if int(profile.get('oracle_horizon', 20)) != 20:
        raise ValueError('H20 contract required')
    if profile.get('oracle_universe_mode') != 'static_bars':
        raise ValueError('This audit requires an explicit static_bars contract')
    columns = profile['feature_columns']
    if len(columns) != len(set(columns)):
        raise ValueError('Duplicate contract feature names')
    assert_no_forbidden_features(columns)
    assert_no_future_features(columns)
    for fold in meta:
        if fold['feature_columns'] != columns:
            raise ValueError('Fold/profile feature contract mismatch')
        model_path = profile_path.parent / fold['model_file']
        with model_path.open(encoding='utf-8') as stream:
            saved = next(line for line in stream if line.startswith('feature_names=')).strip().split('=', 1)[1].split()
        if saved != columns:
            raise ValueError('Model/profile feature contract mismatch')
    universe = Path(args.universe)
    symbols = sorted(set(s.strip().upper() for s in universe.read_text().split(',') if s.strip()))
    protocol = dict(batch_id=args.batch_id, horizon=20, start=args.start, end=args.end,
        universe=str(universe), universe_sha256=digest(universe), symbols=len(symbols),
        profile_sha256=digest(profile_path), metadata_sha256=digest(meta_path),
        code_sha256=digest(__file__), chunk_size=args.chunk_size, features=columns,
        feature_source_sha256=digest(feature_module.__file__),
        factor_source_sha256=digest(factor_module.__file__),
        continuity_registry_sha256=digest(DEFAULT_REGISTRY_PATH),
        numerical_contract_version=feature_module.NUMERICAL_FEATURE_CONTRACT_VERSION,
        generator_options=profile['generator_options'], sql_writes=False, training=False,
        semantics='Current code/data reconstruction; original batch labels audited separately; no PIT certification')
    protocol_path = output / 'protocol.json'
    if protocol_path.exists() and json.loads(protocol_path.read_text()) != protocol:
        raise ValueError('Resume protocol mismatch: use another output directory')
    atomic_json(protocol_path, protocol)
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    if engine.url.database != 'alpha_trade':
        raise ValueError('US database required')
    event.listen(engine, 'begin', readonly_begin)
    base_columns = [c for c in columns if not c.endswith('_xs_rank')]
    needed = list(dict.fromkeys(base_columns + [c[:-len('_xs_rank')] for c in columns if c.endswith('_xs_rank')]))
    options = {**profile['generator_options'], 'enable_cross_sectional_ranks': False}
    chunk_paths = []
    total = (len(symbols) + args.chunk_size - 1) // args.chunk_size
    try:
        for index, offset in enumerate(range(0, len(symbols), args.chunk_size)):
            part = output / f'features-{index:03d}.parquet'
            marker = part.with_suffix('.json')
            chunk_paths.append(part)
            if marker.exists() and part.exists() and json.loads(marker.read_text())['sha256'] == digest(part):
                continue
            if args.max_chunks is not None and index >= args.max_chunks:
                atomic_json(output / 'progress.json', dict(status='PAUSED_LIMIT', phase='features', completed=index, total=total))
                return
            chunk = symbols[offset:offset + args.chunk_size]
            frame = build_feature_matrix(engine, chunk, start_date=args.start, end_date=args.end, generator_options=options)
            missing = sorted(set(needed) - set(frame))
            if missing:
                raise ValueError(f'Missing calculated features: {missing}')
            frame = frame.loc[frame.date.between(pd.Timestamp(args.start), pd.Timestamp(args.end)), ['date', 'symbol', *needed]].copy()
            if frame.duplicated(['date', 'symbol']).any():
                raise ValueError('Duplicate emitted feature keys')
            frame.to_parquet(part, index=False)
            raw_query = text('SELECT symbol,`date` FROM stock_bars_daily WHERE symbol IN :symbols AND `date` BETWEEN :start AND :end').bindparams(bindparam('symbols', expanding=True))
            with engine.connect() as conn:
                raw = pd.read_sql(raw_query, conn, params=dict(symbols=chunk, start=args.start, end=args.end), parse_dates=['date'])
            coverage = raw.merge(frame[['date', 'symbol']], on=['date', 'symbol'], how='left', indicator=True)
            lost = coverage.loc[coverage._merge.eq('left_only')]
            atomic_json(marker, dict(sha256=digest(part), symbols=chunk, raw_rows=len(raw), emitted_rows=len(frame),
                raw_duplicate_keys=int(raw.duplicated(['date', 'symbol']).sum()),
                not_emitted_rows=len(lost), not_emitted_by_symbol=lost.symbol.value_counts().to_dict(),
                missing_symbols=sorted(set(chunk) - set(frame.symbol))))
            atomic_json(output / 'progress.json', dict(status='RUNNING', phase='features', completed=index + 1, total=total, rows=len(frame)))
            LOG.info('Feature chunks %d/%d rows=%d', index + 1, total, len(frame))
            del frame, raw, coverage
            gc.collect()
        registry = load_security_discontinuities()
        yearly = []
        for year in range(pd.Timestamp(args.start).year, pd.Timestamp(args.end).year + 1):
            result_path = output / f'year-{year}.json'
            if result_path.exists():
                yearly.append(json.loads(result_path.read_text()))
                continue
            begin = max(pd.Timestamp(args.start), pd.Timestamp(year=year, month=1, day=1))
            finish = min(pd.Timestamp(args.end), pd.Timestamp(year=year, month=12, day=31))
            parts = [pd.read_parquet(path, filters=[('date', '>=', begin), ('date', '<=', finish)]) for path in chunk_paths]
            frame = restore_ranks(pd.concat(parts, ignore_index=True), columns)
            del parts
            stats = summarize_features(frame, columns)
            labels = audit_labels(engine, args.batch_id, str(begin.date()), str(finish.date()), symbols, registry)
            item = dict(year=year, rows=len(frame), symbols=int(frame.symbol.nunique()),
                features=stats, labels=labels,
                constant_features=[s['feature'] for s in stats if s['distinct'] <= 1],
                nonfinite_features=[s['feature'] for s in stats if s['null'] or s['infinite']])
            atomic_json(result_path, item)
            yearly.append(item)
            atomic_json(output / 'progress.json', dict(status='RUNNING', phase='annual_statistics_and_labels', completed=len(yearly), total=pd.Timestamp(args.end).year - pd.Timestamp(args.start).year + 1))
            LOG.info('Year %d complete rows=%d labels=%d', year, len(frame), labels['rows'])
            del frame
            gc.collect()
        markers = [json.loads(p.with_suffix('.json').read_text()) for p in chunk_paths]
        report = dict(status='COMPLETED_READ_ONLY_AUDIT', symbols=len(symbols), feature_count=len(columns), folds=len(meta),
            rows=sum(y['rows'] for y in yearly), raw_rows=sum(m['raw_rows'] for m in markers),
            not_emitted_rows=sum(m['not_emitted_rows'] for m in markers),
            missing_symbols=sorted({s for m in markers for s in m['missing_symbols']}),
            yearly=[{k: v for k, v in y.items() if k != 'features'} for y in yearly],
            caveats=['Emitted features only: non-finite inputs may already have been dropped or imputed by compute_features',
                'Cross-sectional features rebuilt on CURRENT reduced universe, unlike original model training',
                'Labels audited on ORIGINAL stored batch universe, no SQL relabeling',
                'Current endpoint prices; no historical dataset snapshot; no exhaustive unknown identity/path or PIT proof',
                'Annual quantiles exact per year, no approximation merged into global quantiles',
                'Stored exit dates used for return checks; exact H20 calendar offset not independently certified'])
        atomic_json(output / 'report.json', report)
        atomic_json(output / 'progress.json', dict(status='COMPLETED', phase='done', rows=report['rows']))
        LOG.info('Audit completed: %s', output)
    finally:
        event.remove(engine, 'begin', readonly_begin)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-id', required=True)
    parser.add_argument('--universe', default='config/univers/univers_filtred_tradable.txt')
    parser.add_argument('--start', default='2016-01-01')
    parser.add_argument('--end', default='2024-12-31')
    parser.add_argument('--chunk-size', type=int, default=25)
    parser.add_argument('--max-chunks', type=int)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.chunk_size < 1 or pd.Timestamp(args.start) > pd.Timestamp(args.end):
        parser.error('Invalid chunk size or date range')
    logging.basicConfig(level=logging.INFO)
    try:
        run(args)
    except Exception as exc:
        destination = Path(args.output)
        if destination.is_dir():
            atomic_json(destination / 'error.json', dict(status='FAILED', error_type=type(exc).__name__,
                message=str(exc) if isinstance(exc, (ValueError, KeyError)) else 'See stderr; no SQL parameters logged here'))
        raise


if __name__ == '__main__':
    main()
