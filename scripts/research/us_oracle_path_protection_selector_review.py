"""Review frozen selector decisions and twelve portfolio artifacts, no refit."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research import us_oracle_path_protection_selector as selector
from scripts.research.us_oracle_path_top5_leverage_grid import read


def review(root):
    root = Path(root)
    protocol, report, ready = (read(root/n) for n in ['protocol.json', 'report.json', 'ready.json'])
    verify_hashes(Path('.'), protocol['sources']); verify_hashes(root, report['files']); verify_hashes(root, ready['files'])
    if report['status'] != 'COMPLETED_EXPLORATORY' or len(report['cases']) != 12:
        raise ValueError('Twelve completed cases required')
    x, saved = (pd.read_parquet(root/n) for n in ['annual-features.parquet', 'profile-decisions.parquet'])
    predicted = selector.predict_profiles(root/'selector', x[x.selected][['date', 'symbol', *protocol['features']]])
    keys = ['date', 'symbol']
    pd.testing.assert_frame_equal(predicted.sort_values(keys).reset_index(drop=True),
                                  saved.sort_values(keys).reset_index(drop=True), check_exact=True)
    if not read(root/'selector/fit.json')['val_available_max'].startswith('2022-12-30'):
        raise ValueError('Unexpected selector validation boundary')
    cases = []
    for case in report['cases']:
        folder = root/case['case']; verify_hashes(folder, case['files'])
        daily, trades = (pd.read_parquet(folder/n) for n in ['daily.parquet', 'trades.parquet'])
        final = float(daily.equity.iloc[-1])
        curve = np.r_[4000., daily.equity.to_numpy(float)]
        dd = 100*float((curve/np.maximum.accumulate(curve)-1).min())
        open_rows = read(folder/'open-positions.json')
        unrealized = sum(r['unrealized_pnl_usd'] for r in open_rows)
        realized = float(trades.pnl.sum()) if len(trades) else 0.
        if not np.isclose(final, 4000+realized+unrealized-case['margin_interest'], atol=1e-6, rtol=0):
            raise ValueError('Final equity arithmetic changed')
        if not np.isclose(dd, case['dd_pct'], atol=1e-10) or not np.isclose(100*(final/4000-1), case['net_return_pct'], atol=1e-10):
            raise ValueError('Return/DD reported incorrectly')
        decisions = read(folder/'profiles.json')
        lookup = saved.set_index(keys)
        if case['arm'] == 'LEARNED':
            for entry in decisions:
                value = lookup.loc[(pd.Timestamp(entry['decision_date']), entry['symbol'])]
                if value.chosen_profile != entry['profile']:
                    raise ValueError('Execution decision differs from frozen model')
        opened = read(folder/'opened-profiles.json')
        for row in opened:
            trail, tp = selector.PROFILES[row['profile']]
            if row['profile'] not in protocol['profiles']:
                raise ValueError('Unfrozen profile')
        cases.append(dict(case=case['case'], closed_positions=case['closed_positions'],
                          wealth_dd_verified=True, decision_profiles_verified=True,
                          executed_profiles=case['executed_profiles']))
    parity = []
    for year in selector.dataset.ANNUAL_MODELS:
        learned = root/f'{year}-LEARNED'
        if all(v['profile'] == 'LARGE' for v in read(learned/'profiles.json')):
            fixed = root/f'{year}-FIXED_LARGE'
            for name in ['trades.parquet', 'daily.parquet']:
                pd.testing.assert_frame_equal(pd.read_parquet(learned/name), pd.read_parquet(fixed/name), check_exact=True)
            parity.append(dict(year=year, learned_equals_fixed_large_trades_curve=True))
    result = dict(status='TWELVE_CASES_AND_FROZEN_DECISIONS_VERIFIED', cases=cases,
        annual_profiles=saved.assign(year=saved.date.dt.year).groupby(['year', 'chosen_profile']).size().reset_index(name='count').to_dict('records'),
        learned_constant_parity=parity, source_report_sha256=digest(root/'report.json'),
        review_code_sha256=digest(__file__), oracle_retrained=False, selector_refitted=False,
        sql_writes=False, production_changed=False, independent_holdout=False)
    atomic_json(root/'completion-audit.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__); parser.add_argument('--output', required=True)
    print(review(parser.parse_args().output))
