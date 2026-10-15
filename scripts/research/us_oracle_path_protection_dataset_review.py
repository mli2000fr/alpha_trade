"""Independent key, target and split review, without fitting or SQL."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle_path.train import digest
from scripts.research.us_concentrated_historical_tapes import atomic_json, verify_hashes
from scripts.research.us_oracle_path_top5_leverage_grid import read


def review(root):
    root = Path(root)
    protocol, report = read(root/'protocol.json'), read(root/'report.json')
    verify_hashes(Path('.'), protocol['sources']); verify_hashes(root, report['files'])
    if report['status'] != 'COMPLETED_QUALIFICATION' or report['training']:
        raise ValueError('Completed no-fit dataset required')
    c, x, y, excluded, index = (pd.read_parquet(root/name) for name in ['candidates.parquet',
        'decision-features.parquet', 'outcomes.parquet', 'excluded.parquet', 'dataset-index.parquet'])
    keys = ['date', 'symbol']
    def canonical(f):
        if f.duplicated(keys).any():
            raise ValueError('Duplicate candidate key')
        return f[keys].sort_values(keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(canonical(c), canonical(x), check_exact=True)
    pd.testing.assert_frame_equal(canonical(c), canonical(index), check_exact=True)
    pd.testing.assert_frame_equal(canonical(c), canonical(pd.concat([y, excluded])), check_exact=True)
    if set(x) != set(keys+protocol['features']):
        raise ValueError('Unexpected/future feature columns')
    if c.date.max() >= pd.Timestamp('2024-01-01'):
        raise ValueError('Annual tests entered the fit dataset')
    days = nyse_sessions('2016-01-01', protocol['as_of'])
    starts = days.get_indexer(y.date)
    expected_entry, expected_available = days[starts+1], days[starts+protocol['horizon']]
    if not np.array_equal(y.entry_date.to_numpy(), expected_entry.to_numpy()) or not np.array_equal(
            y.label_available.to_numpy(), expected_available.to_numpy()):
        raise ValueError('Entry/common label chronology differs')
    for profile in protocol['profiles']:
        if not y[f'{profile}_value_date'].between(y.entry_date, y.label_available).all():
            raise ValueError('Profile observes prices outside common window')
    for profile in ('court', 'large'):
        expected = y[f'{profile.upper()}_net_pct']-y.REFERENCE_net_pct
        if not np.allclose(expected, y[f'target_{profile}_advantage_pct'], atol=1e-12, rtol=0):
            raise ValueError('Personalization target differs')
    splits = []
    for name, boundary in [('FIT_2018_2021', '2022-01-01'), ('VALIDATION_2022', '2023-01-01'),
                           ('CONTROL_2023', '2024-01-01')]:
        sub = y[y.split.eq(name)]
        if not sub.label_available.lt(pd.Timestamp(boundary)).all():
            raise ValueError('Label crossed training/validation boundary')
        joined = sub[keys].merge(x, validate='one_to_one')
        if not np.isfinite(joined[protocol['features']]).all().all():
            raise ValueError('Incomplete input in approved split')
        splits.append(dict(name=name, checked=len(sub), label_available_max=str(sub.label_available.max().date())))
    for year, model in protocol['annual_test_models'].items():
        if any(pd.Timestamp(model[k]) >= pd.Timestamp(f'{year}-01-01') for k in ['train_available_max', 'val_available_max']):
            raise ValueError('Annual fold in-sample at start of year')
    folds = [read(p) for p in sorted((root/'folds').glob('*/done.json'))]
    if len(folds) != 10 or any(f['original_score_max_error'] > 1e-7 for f in folds):
        raise ValueError('Incomplete OOF reproduction')
    result = dict(status='DATASET_KEYS_TARGETS_AND_PURGES_VERIFIED', candidates=len(c),
        qualified_outcomes=len(y), exclusions=len(excluded), split_checks=splits,
        original_observable_scored_rows=sum(f['observable_rows'] for f in folds),
        original_conditioned_oof_rows=sum(f['original_oof_rows'] for f in folds),
        max_oof_score_error=max(f['original_score_max_error'] for f in folds),
        source_report_sha256=digest(root/'report.json'), review_script_sha256=digest(__file__),
        annual_test_contracts_verified=True, selector_training=False, sql_writes=False, broker_calls=False,
        strict_pit_certified=False, learnability_proven=False)
    atomic_json(root/'completion-audit.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__); parser.add_argument('--output', required=True)
    print(review(parser.parse_args().output))
