"""Offline key/tail comparison of completed feature shards before/after correction."""
import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json


def run(before, after):
    old_protocol = json.loads((before / 'protocol.json').read_text())
    new_protocol = json.loads((after / 'protocol.json').read_text())
    for key in ('batch_id', 'horizon', 'start', 'end', 'universe_sha256', 'features', 'chunk_size'):
        if old_protocol[key] != new_protocol[key]:
            raise ValueError(f'Comparison protocol mismatch: {key}')
    expected = (new_protocol['symbols'] + new_protocol['chunk_size'] - 1) // new_protocol['chunk_size']
    paths = sorted(after.glob('features-*.parquet'))
    if len(paths) != expected or any(not p.with_suffix('.json').exists() for p in paths):
        raise ValueError('Complete committed feature shards required')
    counts = Counter()
    changed = []
    columns = ['date', 'symbol', 'rsi_14_div_volatility_20', 'rolling_volatility_20',
               'log_return_div_intraday_range', 'intraday_range']
    for path in paths:
        current = pd.read_parquet(path, columns=columns)
        previous = pd.read_parquet(before / path.name, columns=['date', 'symbol'])
        if not current[['date', 'symbol']].equals(previous):
            changed.append(path.name)
        counts['rows'] += len(current)
        counts['rsi_vol_ratio_abs_gt_1e6'] += int(current.rsi_14_div_volatility_20.abs().gt(1e6).sum())
        counts['log_range_ratio_abs_gt_1e6'] += int(current.log_return_div_intraday_range.abs().gt(1e6).sum())
        counts['rsi_floor_not_neutral'] += int((current.rolling_volatility_20.le(1e-8) & current.rsi_14_div_volatility_20.ne(0)).sum())
        counts['log_floor_not_neutral'] += int((current.intraday_range.le(1e-8) & current.log_return_div_intraday_range.ne(0)).sum())
    result = dict(status='COMPLETED_OFFLINE_FEATURE_COMPARISON', counts=dict(counts), changed_key_shards=changed,
        before=str(before), after=str(after), caveat='Feature shards only; annual statistics/label audit may still run; no predictive or PnL claim')
    atomic_json(after / 'feature_comparison.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    args = parser.parse_args()
    run(args.before, args.after)
