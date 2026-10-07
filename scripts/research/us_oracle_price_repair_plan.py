"""Prepare a reviewed-price repair diff; deliberately has no SQL write mode.

Current provider rereads are evidence, not independent certification or PIT data.
Only existing keys are proposed; original identity/provenance is preserved.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from database.connection import get_sqlalchemy_engine
from service.eodhd.adapters import (
    eodhd_to_split_only, to_stock_bars_daily_row, to_stock_bars_row,
)
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest
from scripts.research.us_oracle_feature_outliers import diagnose_segment


DAILY_FIELDS = ('open', 'high', 'low', 'close', 'volume', 'adj_close', 'vwap',
                'daily_return', 'is_filled', 'data_adjustment', 'data_source')
BAR_FIELDS = ('open_price', 'high_price', 'low_price', 'close_price', 'volume',
              'trade_count', 'vwa_price', 'data_adjustment', 'data_source')


def validate_prices(frame):
    """Block invalid proposals, without suppressing legitimate large returns."""
    prices = frame[['open', 'high', 'low', 'close']].apply(pd.to_numeric)
    if not np.isfinite(prices.to_numpy()).all() or prices.le(0).any().any():
        raise ValueError('Nonpositive/nonfinite proposed OHLC')
    if (prices.high.lt(prices[['open', 'close', 'low']].max(axis=1)).any()
            or prices.low.gt(prices[['open', 'close', 'high']].min(axis=1)).any()):
        raise ValueError('Inconsistent proposed OHLC range')
    volume = pd.to_numeric(frame.volume)
    if (not np.isfinite(volume).all() or volume.lt(0).any()
            or volume.ne(np.floor(volume)).any()):
        raise ValueError('Invalid proposed volume')
    if frame.duplicated(['symbol', 'date']).any():
        raise ValueError('Duplicate proposed key')


def select_candidates(local, fresh):
    """A >1% close disagreement is a review trigger, not a repair approval."""
    left = local[['symbol', 'date', 'close']].copy()
    right = fresh[['symbol', 'date', 'close']].copy()
    for frame in (left, right):
        frame['date'] = pd.to_datetime(frame.date).dt.normalize()
    merged = left.merge(right, on=['symbol', 'date'], suffixes=('_old', '_new'),
                        validate='one_to_one')
    ratio = merged.close_old / merged.close_new
    result = merged.loc[ratio.sub(1).abs().gt(.01)].copy()
    result['review_group'] = np.where(
        (result.symbol.eq('KNTK') & result.date.between('2017-05-02', '2018-11-12'))
        | (result.symbol.eq('AMTB') & result.date.lt('2018-10-18')),
        'KNOWN_2018_SCALE_ANOMALY', 'SEPARATE_REVIEW_REQUIRED')
    return result


def propose_existing(old, replacements, keys, fields):
    """Exact-key update proposals only, retaining all unspecified columns."""
    if old.duplicated(keys).any() or replacements.duplicated(keys).any():
        raise ValueError('Ambiguous existing/proposed key')
    indexed = old.set_index(keys, drop=False)
    proposed = indexed.copy()
    diff = []
    for _, row in replacements.iterrows():
        key = tuple(row[k] for k in keys)
        if key not in indexed.index:
            raise ValueError(f'Missing existing key: {key}')
        for field in fields:
            before, after = indexed.loc[key, field], row[field]
            equal = ((pd.isna(before) and pd.isna(after))
                     or (not pd.isna(before) and not pd.isna(after) and before == after))
            if not equal:
                diff.append(dict(**{k: row[k] for k in keys}, field=field,
                                 before=before, after=after))
            proposed.loc[key, field] = after
    return proposed.reset_index(drop=True), diff


def run(root, output):
    output.mkdir(parents=True, exist_ok=False)
    source = root / 'comparison'
    hashes, daily_rows, bar_rows = {}, [], []
    for symbol in ('AMTB', 'KNTK'):
        files = [source / f'{symbol}-bars-full.json', source / f'{symbol}-splits-full.json']
        for path in files:
            hashes[str(path.resolve())] = digest(path)
        raw, splits = [json.loads(p.read_text(encoding='utf-8')) for p in files]
        canonical = eodhd_to_split_only(raw, splits)
        daily_rows.extend(to_stock_bars_daily_row(row, symbol) for row in canonical)
        bar_rows.extend(to_stock_bars_row(row, symbol) for row in canonical)
    fresh = pd.DataFrame(daily_rows)
    fresh['date'] = pd.to_datetime(fresh.date)
    validate_prices(fresh)
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    if engine.url.database != 'alpha_trade':
        raise ValueError('US database required')
    snapshots = {}
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql('SET TRANSACTION READ ONLY')
            for table, predicate in (
                ('stock_bars_daily', '`date` BETWEEN :start AND :end'),
                ('stock_bars', 'timeframe=\'1D\' AND `timestamp` BETWEEN :start AND :end'),
            ):
                statement = text(f'SELECT * FROM {table} WHERE symbol IN :symbols AND {predicate}').bindparams(
                    bindparam('symbols', expanding=True))
                snapshots[table] = pd.read_sql(statement, conn, params=dict(
                    symbols=['AMTB', 'KNTK'], start='2017-01-01', end='2024-12-31 23:59:59'))
    finally:
        engine.dispose()
    daily = snapshots['stock_bars_daily']
    daily['date'] = pd.to_datetime(daily.date)
    bars = snapshots['stock_bars']
    bars['timestamp'] = pd.to_datetime(bars.timestamp)
    candidates = select_candidates(daily, fresh)
    candidates.to_parquet(output / 'candidates.parquet', index=False)
    selected = fresh.merge(candidates[['symbol', 'date', 'review_group']],
                           on=['symbol', 'date'], validate='one_to_one')
    replacement_bars = pd.DataFrame(bar_rows)
    replacement_bars['timestamp'] = pd.to_datetime(replacement_bars.timestamp)
    selected_keys = selected[['symbol', 'date']].rename(columns={'date': 'timestamp'})
    selected_keys['timestamp'] += pd.Timedelta(hours=9, minutes=30)
    replacement_bars = replacement_bars.merge(selected_keys, on=['symbol', 'timestamp'], validate='one_to_one')
    summaries = {}
    for table, replacements, keys, fields in (
        ('stock_bars_daily', selected, ['symbol', 'date'], DAILY_FIELDS),
        ('stock_bars', replacement_bars, ['symbol', 'timeframe', 'timestamp'], BAR_FIELDS),
    ):
        old = snapshots[table].merge(replacements[keys], on=keys, validate='one_to_one')
        proposed, diff = propose_existing(old, replacements, keys, fields)
        before_path, after_path = output / f'{table}-before.parquet', output / f'{table}-proposed.parquet'
        old.to_parquet(before_path, index=False)
        proposed.to_parquet(after_path, index=False)
        atomic_json(output / f'{table}-diff.json', diff)
        summaries[table] = dict(rows=len(proposed), changed_fields=len(diff),
                               before_sha256=digest(before_path), proposed_sha256=digest(after_path))
    groups = candidates.groupby(['symbol', 'review_group']).agg(
        rows=('date', 'size'), first=('date', 'min'), last=('date', 'max')).reset_index()
    # Offline sensitivity only: prove the proposed historical replacements address
    # the reported maxima, without changing production features or cross-section ranks.
    history_path = root / 'suspect-bars.parquet'
    hashes[str(history_path.resolve())] = digest(history_path)
    history = pd.read_parquet(history_path)
    history['date'] = pd.to_datetime(history.date)
    sensitivity = []
    for variant in ('LOCAL', 'KNOWN_2018_ONLY', 'ALL_REVIEW_CANDIDATES'):
        trial = history.copy()
        if variant != 'LOCAL':
            patch = selected if variant == 'ALL_REVIEW_CANDIDATES' else selected.loc[
                selected.review_group.eq('KNOWN_2018_SCALE_ANOMALY')]
            trial, _ = propose_existing(trial, patch, ['symbol', 'date'],
                                        ['open', 'high', 'low', 'close', 'volume', 'adj_close', 'vwap'])
        for symbol, frame in trial.groupby('symbol'):
            features = diagnose_segment(frame)
            retained = features.loc[features.date.ge('2016-01-01')]
            for feature in ('daily_return_recomputed', 'overnight_gap_recomputed',
                            'rolling_volatility_20_recomputed'):
                values = retained[feature].abs()
                index = values.idxmax()
                sensitivity.append(dict(variant=variant, symbol=symbol, feature=feature,
                    max_abs=float(values.loc[index]), date=retained.loc[index, 'date']))
    atomic_json(output / 'offline-sensitivity.json', sensitivity)
    report = dict(status='PREPARED_REQUIRES_REVIEW', sql_writes=False, training=False,
                  source_hashes=hashes, groups=groups.to_dict('records'), tables=summaries,
                  limitations=['Same-provider evidence, not independent certification',
                               'AMTB split effective-date convention remains to qualify',
                               'Only >1% close disagreements selected; not exhaustive OHLCV audit',
                               'No writes or production feature guard activated',
                               'Existing model artifacts unchanged; database repair would not repair trained models'])
    atomic_json(output / 'report.json', report)
    print(json.dumps(report, default=str))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.root, args.output)
