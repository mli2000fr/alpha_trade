"""Independent arithmetic/coverage review of the completed unit audit."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_path_top5_leverage_grid import read


def review(root):
    root = Path(root)
    protocol, report = read(root/'protocol.json'), read(root/'report.json')
    verify_hashes(Path('.'), protocol['sources'])
    verify_hashes(root, report['files'])
    if report['status'] != 'COMPLETED_EXPLORATORY' or len(report['summaries']) != 6:
        raise ValueError('Incomplete audit')
    candidates = pd.read_parquet(Path(protocol['source'])/'candidates.parquet')
    candidates = candidates[candidates.backend.eq('catboost')]
    checks = []
    for s in report['summaries']:
        folder = root/f"{s['year']}-H{s['horizon']}"
        rows, excluded = (pd.read_parquet(folder/name) for name in ['counterfactuals.parquet', 'excluded.parquet'])
        keys = ['date', 'symbol']
        union = pd.concat([rows[keys], excluded[keys]])
        expected = candidates[candidates.year.eq(s['year'])][keys]
        if union.duplicated(keys).any():
            raise ValueError('Candidate counted twice')
        pd.testing.assert_frame_equal(union.sort_values(keys).reset_index(drop=True),
                                      expected.sort_values(keys).reset_index(drop=True), check_exact=True)
        if not (rows.entry_date.gt(rows.date) & rows.label_available.ge(rows.entry_date)).all():
            raise ValueError('Invalid chronology')
        for name in protocol['profiles']:
            if not rows[f'{name}_value_date'].between(rows.entry_date, rows.label_available).all():
                raise ValueError('Outcome outside common horizon')
            opened = ~rows[f'{name}_closed']
            if not rows.loc[opened, f'{name}_reason'].eq('OPEN_MTM').all() or not rows.loc[
                    opened, f'{name}_value_date'].eq(rows.loc[opened, 'label_available']).all():
                raise ValueError('Open mark pretends to be an exit')
            ratio = rows[f'{name}_value_price']/rows.entry_price
            leg = protocol['costs']['per_leg_cost_bps']/10000.
            net = 100*(ratio*(1-np.where(rows[f'{name}_closed'], leg, 0))-(1+leg))
            if not np.allclose(net, rows[f'{name}_net_pct'], atol=1e-10, rtol=0):
                raise ValueError('Costs incorrectly booked')
        matrix = rows[[f'{p}_net_pct' for p in protocol['profiles']]].to_numpy(dtype=float)
        best = matrix.max(axis=1)
        sums = matrix.mean(axis=0)
        stats = s['all_candidates']
        if not np.isclose(best.mean()-sums.max(), stats['ceiling_minus_best_constant_mean_pct'], atol=1e-10):
            raise ValueError('Incorrect personalization headroom')
        tied = np.isclose(matrix, best[:, None], rtol=0, atol=1e-10)
        checks.append(dict(year=s['year'], horizon=s['horizon'], checked=len(rows), excluded=len(excluded),
            all_three_negative_share=float((matrix.max(axis=1) < 0).mean()),
            all_three_equal_share=float((tied.sum(axis=1) == 3).mean()),
            unique_best_shares={name: float(((tied.sum(axis=1) == 1) & tied[:, k]).mean())
                                for k, name in enumerate(protocol['profiles'])},
            exact_membership_accounting=True, costs_mtm_and_chronology_verified=True))
    result = dict(status='ALL_SIX_COHORTS_VERIFIED', checks=checks,
        research_script_sha256=digest(__file__), source_report_sha256=digest(root/'report.json'),
        checked_rows=sum(c['checked'] for c in checks), native_exit_parity=report['native_parity'],
        training=False, sql_writes=False, production_changed=False, learnability_proven=False)
    atomic_json(root/'completion-audit.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--output', required=True)
    print(review(parser.parse_args().output))
