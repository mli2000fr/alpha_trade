"""Technical recheck of causal TOP5 episode entry caps and native accounting."""
import argparse
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_path_top5_leverage_grid import read, nyse_sessions
from scripts.research.us_oracle_path_signal_episodes import ARMS
from scripts.research.us_oracle_path_atr_stop import verify_closed_stops


def review(output):
    root = Path(output); p, report = read(root/'protocol.json'), read(root/'report.json')
    verify_hashes(Path('.'), p['sources']); verify_hashes(root, report['files'])
    if report['status'] != 'COMPLETED_EXPLORATORY' or len(report['cases']) != 6:
        raise ValueError('Six complete cases required')
    membership = pd.read_parquet(root/'membership.parquet')
    candidates = pd.read_parquet(Path(p['source'])/'candidates.parquet')
    keys = ['date', 'symbol']
    pd.testing.assert_frame_equal(membership[keys].sort_values(keys).reset_index(drop=True),
        candidates[keys].sort_values(keys).reset_index(drop=True))
    lookup = membership.set_index(keys).episode_id.to_dict()
    # Independent reconstruction from symbol presence on consecutive sessions.
    for year, end in p['years'].items():
        year = int(year); days = nyse_sessions(f'{year}-01-01', end)
        for symbol, g in membership[membership.year.eq(year)].groupby('symbol'):
            previous, token, start = None, None, None
            for t in g.sort_values('date').itertuples(index=False):
                j = days.get_loc(t.date)
                if previous is None or j != previous+1:
                    start = t.date; token = f'{year}:{symbol}:{start.date()}'
                if t.episode_id != token or t.episode_age_sessions != j-days.get_loc(start)+1:
                    raise ValueError('Episode rearmed without observable absence or age is noncausal')
                previous = j
    reviewed = []
    for case in report['cases']:
        folder = root/case['case']; verify_hashes(folder, case['files'])
        fills = read(folder/'episode-fills.json')
        counters = Counter()
        for a in fills:
            day = pd.Timestamp(a['decision_date']); token = lookup[(day, a['symbol'])]
            if token != a['episode_id'] or not day < pd.Timestamp(a['fill_date']):
                raise ValueError('Fill episode unknown before execution')
            counters[token] += 1
            if counters[token] != a['entry_number_in_episode']:
                raise ValueError('Episode fill counter differs from actual entries')
        if case['arm'] == ARMS[1] and any(n > 1 for n in counters.values()):
            raise ValueError('Episode actually bought more than once')
        observed = Counter()
        for a in read(folder/'episode-decisions.json'):
            token = lookup[(pd.Timestamp(a['decision_date']), a['symbol'])]
            # Entry precedes current close; counts depend on actual fills only.
            n = sum(f['episode_id'] == token and pd.Timestamp(f['fill_date']) <= pd.Timestamp(a['decision_date']) for f in fills)
            if n != a['earlier_actual_entries'] or a['blocked'] != (case['arm'] == ARMS[1] and n > 0):
                raise ValueError('Noncausal gate or consumed approval instead of fill')
        native_fills = read(folder/'committed-fills.json')
        if {(a['symbol'], a['fill_date']) for a in fills} != {(a['symbol'], a['fill_date']) for a in native_fills}:
            raise ValueError('Episode fills do not match actual committed quantities')
        trades, daily = (pd.read_parquet(folder/n) for n in ['trades.parquet', 'daily.parquet'])
        verify_closed_stops(trades, native_fills, p['events'])
        latent = sum(a['unrealized_pnl_usd'] for a in read(folder/'open-positions.json'))
        realized = float(trades.pnl.sum()) if len(trades) else 0.
        final = 4000+realized+latent-case['margin_interest']
        curve = np.r_[4000., daily.equity.to_numpy(float)]
        dd = 100*float((curve/np.maximum.accumulate(curve)-1).min())
        if not np.isclose(final, daily.equity.iloc[-1], atol=1e-6) or not np.isclose(dd, case['dd_pct']):
            raise ValueError('Wealth/DD mismatch')
        if case['arm'] == ARMS[0]:
            for name in ['daily.parquet', 'trades.parquet']:
                pd.testing.assert_frame_equal(pd.read_parquet(folder/name),
                    pd.read_parquet(Path(p['source'])/f'{case["year"]}-FIXED_REFERENCE'/name), check_exact=True)
        reviewed.append(dict(case=case['case'], actual_entries=len(fills), same_episode_reentries=sum(max(0,n-1) for n in counters.values()),
            causal_original_top5_gate_verified=True, actual_fill_only_consumption_verified=True,
            stops_costs_wealth_verified=True, reference_exact=case['arm'] == ARMS[0]))
    result = dict(status='SIX_EPISODE_PORTFOLIOS_CAUSAL_GATES_FILLS_WEALTH_AND_PARITY_VERIFIED', cases=reviewed,
        report_sha256=digest(root/'report.json'), review_code_sha256=digest(__file__), independent_human_review=False)
    atomic_json(root/'completion-audit.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__); parser.add_argument('--output', required=True)
    print(review(parser.parse_args().output))
