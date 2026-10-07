"""Offline qualification of staged price repairs. No database/network access."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest
from scripts.research.us_oracle_price_repair_plan import validate_prices


def verify_plan_hashes(plan):
    report = json.loads((plan / 'report.json').read_text(encoding='utf-8'))
    for name, table in report['tables'].items():
        for suffix, field in [('before', 'before_sha256'), ('proposed', 'proposed_sha256')]:
            if digest(plan / f'{name}-{suffix}.parquet') != table[field]:
                raise ValueError(f'Modified repair snapshot: {name}/{suffix}')
    for filename, expected in report['source_hashes'].items():
        if digest(filename) != expected:
            raise ValueError(f'Modified provider/audit evidence: {filename}')
    return report


def validate_parity(daily, bars):
    validate_prices(daily)
    bars = bars.copy()
    bars['date'] = pd.to_datetime(bars.timestamp).dt.normalize()
    if not bars.timeframe.eq('1D').all():
        raise ValueError('Unexpected timeframe')
    joined = daily.merge(bars, on=['symbol', 'date'], suffixes=('_daily', '_bars'),
                         validate='one_to_one', how='outer', indicator=True)
    if not joined['_merge'].eq('both').all():
        raise ValueError('Different daily/bar key sets')
    for left, right in [('open', 'open_price'), ('high', 'high_price'),
                        ('low', 'low_price'), ('close', 'close_price'),
                        ('vwap', 'vwa_price'), ('volume_daily', 'volume_bars')]:
        if not np.allclose(joined[left], joined[right], rtol=0, atol=1e-9):
            raise ValueError(f'Daily/bar mismatch: {left}')
    if not np.allclose(daily.close, daily.adj_close, rtol=0, atol=1e-9):
        raise ValueError('Split-only adjusted-close mismatch')
    if not joined.instrument_id_daily.equals(joined.instrument_id_bars):
        raise ValueError('Daily/bar identity mismatch')


def run(root, plan, output):
    output.mkdir(parents=True, exist_ok=False)
    verify_plan_hashes(plan)
    old = pd.read_parquet(plan / 'stock_bars_daily-before.parquet')
    proposed = pd.read_parquet(plan / 'stock_bars_daily-proposed.parquet')
    bars = pd.read_parquet(plan / 'stock_bars-proposed.parquet')
    validate_parity(proposed, bars)
    for table, keys in [('stock_bars_daily', ['symbol', 'date']),
                        ('stock_bars', ['symbol', 'timeframe', 'timestamp'])]:
        before = pd.read_parquet(plan / f'{table}-before.parquet').set_index(keys).sort_index()
        after = pd.read_parquet(plan / f'{table}-proposed.parquet').set_index(keys).sort_index()
        for column in ('instrument_id', 'ingested_at'):
            if not before[column].equals(after[column]):
                raise ValueError(f'Changed protected metadata: {table}/{column}')
    local = old.loc[old.symbol.eq('KNTK')]
    fresh = proposed.loc[proposed.symbol.eq('KNTK')]
    canonical = pd.read_parquet(root / 'comparison/KNTK-canonical.parquet')
    quarterly = []
    # Official 2017 10-K gives quarterly BID ranges, NOT daily OHLC prints.
    # Compare raw-scale CLOSE only; compatibility is not price certification.
    ranges = {'2017Q2': (9.70, 9.76), '2017Q3': (9.70, 9.79), '2017Q4': (9.64, 10.01)}
    for quarter, (low, high) in ranges.items():
        group = canonical.loc[canonical.date.dt.to_period('Q').astype(str).eq(quarter)]
        raw_close = group.close / 10.0  # verified 1:20 then 2:1 => factor .1
        quarterly.append(dict(quarter=quarter, count=len(group), official_bid_low=low,
                              official_bid_high=high, vendor_raw_close_min=float(raw_close.min()),
                              vendor_raw_close_max=float(raw_close.max()),
                              outside_bid_range=int((raw_close.lt(low - .0001) | raw_close.gt(high + .0001)).sum())))
    amt_old = old.loc[old.symbol.eq('AMTB') & old.date.ge('2023-08-29')]
    amt_new = proposed.loc[proposed.symbol.eq('AMTB') & proposed.date.ge('2023-08-29')]
    report = dict(status='QUALIFIED_MECHANICALLY_NOT_INDEPENDENT_DAILY_CERTIFICATION',
        sql_writes=False, training=False,
        checks=['Plan and source SHA256 unchanged', 'Daily/1D OHLCV parity',
                'Protected identity/ingestion metadata preserved', 'Finite coherent split-only OHLCV'],
        kntk=dict(candidate_dates=len(fresh), local_unique_closes=sorted(local.close.unique().tolist()),
                  volume_changes=int(old.loc[old.symbol.eq('KNTK'), 'volume'].reset_index(drop=True).ne(
                      fresh.volume.reset_index(drop=True)).sum()), quarterly_2017=quarterly,
                  decision='ELIGIBLE_FOR_SEPARATE_REVIEWED_VENDOR_REPAIR_NOT_YET_APPLIED'),
        amtb_2023=dict(candidate_dates=len(amt_old), old_zero_volume_dates=int(amt_old.volume.eq(0).sum()),
                       old_unique_closes=sorted(amt_old.close.unique().tolist()),
                       proposed_positive_volume_dates=int(amt_new.volume.gt(0).sum()),
                       event_date='2023-08-29', decision='SEPARATE_STALE_PRICE_REPAIR_REVIEW'),
        amtb_2018=dict(decision='HOLD_PENDING_DAILY_PRICE_EVIDENCE',
                       split_trading_effective='2018-10-24',
                       company_reported_action_date='2018-10-23',
                       note='Nasdaq effective trading date agrees with EODHD; +518% remains uncertified'),
        caveats=['Bid-range compatibility is not independent validation of daily OHLCV',
                 'Exchange migration aligns with stale prices; historical importer cause unproven',
                 'No production guard, model invalidation, or repair applied'])
    atomic_json(output / 'report.json', report)
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    run(**vars(parser.parse_args()))
