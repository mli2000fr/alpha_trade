"""Recheck six ATR stop portfolios, J-only sizing and baseline parity offline."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_path_top5_leverage_grid import read
from scripts.research.us_oracle_path_atr_stop import ARMS, verify_closed_stops


def review(output):
    root = Path(output); p, report = read(root/'protocol.json'), read(root/'report.json')
    verify_hashes(Path('.'), p['sources']); verify_hashes(root, report['files'])
    if report['status'] != 'COMPLETED_EXPLORATORY' or len(report['cases']) != 6:
        raise ValueError('Six complete cases required, no economic conclusion on failed cases')
    prices = pd.read_parquet(p['prices'])
    groups = {s: f.sort_values('date') for s, f in prices.groupby('symbol')}
    cases = []
    for case in report['cases']:
        folder = root/case['case']; verify_hashes(folder, case['files'])
        for metadata in [case, read(folder/'report.json')]:
            if metadata['sizing_unchanged'] != (case['arm'] == ARMS[0]) or not metadata['risk_budget_unchanged']:
                raise ValueError('Sizing metadata contradicts risk-distance experiment')
        decisions, fills = read(folder/'stop-decisions.json'), read(folder/'committed-fills.json')
        for a in decisions:
            prefix = groups[a['symbol']]
            prefix = prefix[prefix.date.le(a['decision_date'])]
            # Independent arithmetic, no call to rule or native ATR implementation.
            c = prefix.close; prev = c.shift(1)
            tr = pd.concat([prefix.high-prefix.low, (prefix.high-prev).abs(),
                            (prefix.low-prev).abs()], axis=1).max(axis=1)
            atr = float(tr.tail(20).mean()); close = float(c.iloc[-1])
            if len(tr) < 20 or not np.isclose(atr, a['atr20_j'], atol=1e-8) or not np.isclose(close, a['close_j']):
                raise ValueError('Wrong decision ATR/close or future price used')
            fraction = .05 if case['arm'] == ARMS[0] else max(.05, min(.10, atr/close))
            if not np.isclose(a['sl'], fraction, atol=1e-12):
                raise ValueError('Stop rule or boundaries changed')
            budget = a['equity_j']*.02
            if not np.isclose(a['base_risk_budget_usd'], budget, atol=1e-8):
                raise ValueError('Nominal budget rose with stop')
            if a['approved'] and a['approved_nominal_risk_usd'] > budget*max(0, a['native_risk_multiplier'])+1e-6:
                raise ValueError('Approval nominal risk too high')
        lookup = {(a['decision_date'], a['symbol']): a for a in decisions}
        for a in fills:
            known = lookup[(a['decision_date'], a['symbol'])]
            if not pd.Timestamp(a['decision_date']) < pd.Timestamp(a['fill_date']) or not known['approved']:
                raise ValueError('Noncausal or unapproved fill')
            if a['sl'] != known['sl']:
                raise ValueError('Recomputed or widened fill stop')
            if not np.isclose(a['attempted_nominal_risk_usd'], a['attempted_qty']*a['fill_price']*a['sl']):
                raise ValueError('Misreported actual fill risk')
            if a['attempted_nominal_risk_usd'] > known['effective_risk_budget_usd']*1.03+1e-5:
                raise ValueError('Fill risk over J budget plus permitted gap')
        trades, daily = (pd.read_parquet(folder/n) for n in ['trades.parquet', 'daily.parquet'])
        verify_closed_stops(trades, fills, p['events'])
        unrealized = sum(a['unrealized_pnl_usd'] for a in read(folder/'open-positions.json'))
        realized = float(trades.pnl.sum()) if len(trades) else 0.
        final = 4000+realized+unrealized-case['margin_interest']
        curve = np.r_[4000., daily.equity.to_numpy(float)]
        dd = 100*float((curve/np.maximum.accumulate(curve)-1).min())
        if not np.isclose(final, daily.equity.iloc[-1], atol=1e-6) or not np.isclose(dd, case['dd_pct']):
            raise ValueError('Incorrect reported wealth or drawdown')
        if not np.isclose(100*(final/4000-1), case['net_return_pct']):
            raise ValueError('Incorrect reported return')
        if case['arm'] == ARMS[0]:
            for name in ['trades.parquet', 'daily.parquet']:
                pd.testing.assert_frame_equal(pd.read_parquet(folder/name),
                    pd.read_parquet(Path(p['source'])/f'{case["year"]}-FIXED_REFERENCE'/name), check_exact=True)
        cases.append(dict(case=case['case'], decision_stops=len(decisions), actual_fills=len(fills),
            closed_lots=len(trades), nominal_budget_and_fill_risk_verified=True, causal_atr_prefixes_verified=True,
            fixed_native_parity_verified=case['arm'] == ARMS[0], wealth_dd_verified=True))
    result = dict(status='SIX_PORTFOLIOS_STOP_RISK_WEALTH_AND_FIXED_PARITY_VERIFIED', cases=cases,
        report_sha256=digest(root/'report.json'), review_code_sha256=digest(__file__),
        independent_human_review=False, no_new_fit_or_broker_calls=True)
    atomic_json(root/'completion-audit.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__); parser.add_argument('--output', required=True)
    print(review(parser.parse_args().output))
