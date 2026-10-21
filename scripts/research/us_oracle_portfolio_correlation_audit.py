"""Independent pair/history/held-state review; no new strategy or price calls."""
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_intraday_protection_grid import READ, PRICE, load_tapes
from scripts.research.us_short_loss_attribution import cost_identity


def scalar_pearson(a, b, minimum=25):
    valid = np.isfinite(a) & np.isfinite(b)
    x, y = a[valid], b[valid]
    n = len(x)
    if n < minimum:
        return n, None
    x, y = x-x.mean(), y-y.mean()
    denom = float(np.sqrt(np.dot(x, x)*np.dot(y, y)))
    return (n, float(np.dot(x, y)/denom)) if denom else (n, None)


def candidate_priority(record):
    return pd.Timestamp(record['oracle_date']), int(record['rank']), record['symbol'], int(record['pair_id'])


def expected_holdings(records, event, candidate):
    ts = pd.Timestamp(event['time'])
    priority = candidate_priority(candidate)
    held = {}
    for r in records:
        entry = pd.Timestamp(r['entry_timestamp'])
        exit_time = pd.Timestamp(r['exit_timestamp']) if 'exit_timestamp' in r else None
        if entry > ts or entry == ts and candidate_priority(r) >= priority:
            continue
        if exit_time is not None and exit_time <= ts:
            continue
        if r['symbol'] in held:
            raise ValueError('Overlapping same-symbol positions')
        held[r['symbol']] = r
    return held


def verify_return_archive(daily, returns):
    """Independent array validation/pct-change, including missing exchange days."""
    max_error = 0.
    for s in returns.columns:
        g = daily[daily.symbol.eq(s)].set_index('date').reindex(returns.index)
        a = g[['open', 'high', 'low', 'close', 'volume']].to_numpy(float)
        good = np.isfinite(a).all(axis=1) & (a > 0).all(axis=1)
        good &= a[:, 1] >= np.maximum(a[:, 0], a[:, 3])
        good &= a[:, 2] <= np.minimum(a[:, 0], a[:, 3])
        good &= g.is_filled.eq(0).to_numpy() & g.data_adjustment.eq('split').to_numpy()
        expected = np.full(len(a), np.nan)
        for i in range(1, len(a)):
            if good[i] and good[i-1]:
                expected[i] = a[i, 3]/a[i-1, 3]-1
        actual = returns[s].to_numpy(float)
        if not np.allclose(expected, actual, atol=1e-12, rtol=1e-12, equal_nan=True):
            raise ValueError('Independent archived return reconstruction failed')
        valid = np.isfinite(expected)
        if valid.any():
            max_error = max(max_error, float(np.max(np.abs(expected[valid]-actual[valid]))))
    return max_error


def review(root):
    root = Path(root)
    report = READ(root/'report.json'); protocol = READ(root/'protocol.json')
    verify_hashes(root, READ(root/'final-review.json')['files'])
    verify_hashes(root, READ(root/'prepared.json')['files'])
    verify_hashes(Path('.'), protocol['sources'])
    if report['completed'] != 12 or report['failed']:
        raise ValueError('12 successful cases required')
    returns = pd.read_parquet(root/'returns.parquet')
    raw = pd.read_parquet(PRICE)
    return_error = verify_return_archive(raw, returns)
    tapes = load_tapes(root)
    candidates = pd.read_parquet(root/'candidates.parquet')
    by_candidate = {(int(r.pair_id), r.side, r.decision_time): r._asdict() for r in candidates.itertuples(index=False)}
    max_error = 0.; pairs_checked = events_checked = 0
    summaries = []; refusals = []; costs = []
    for case in report['cases']:
        folder = root/case['arm']/'cases'/case['case']
        verify_hashes(folder, case['files'])
        trades, cost = cost_identity(root/case['arm'], case)
        cost['arm'] = case['arm']; costs.append(cost)
        opened = READ(folder/'open-positions.json')
        records = trades.to_dict('records')+opened
        bar_index = {ts: i for i, (ts, _, _) in enumerate(tapes[case['year']]['timeline'])}
        checks = READ(folder/'correlation-events.json')
        expected_candidates = candidates[candidates.year.eq(case['year']) & candidates.side.eq(case['side'])]
        expected_keys = {(int(r.pair_id), r.side, r.decision_time) for r in expected_candidates.itertuples()
                         if r.decision_time in bar_index and r.decision_time < r.expiry
                         and np.isfinite(tapes[case['year']]['context'][
                             (r.symbol, pd.Timestamp(r.decision_time.tz_convert('America/New_York').date()))].atr)
                         and np.isfinite(tapes[case['year']]['context'][
                             (r.symbol, pd.Timestamp(r.decision_time.tz_convert('America/New_York').date()))].adv)}
        actual_keys = {(int(e['pair_id']), e['side'], pd.Timestamp(e['time'])) for e in checks}
        # Maintenance liquidation can suppress a whole session before enter().
        missing = expected_keys-actual_keys
        decisions = READ(folder/'decisions.json')
        maintenance_days = {pd.Timestamp(d['time']).tz_convert('America/New_York').date()
                            for d in decisions if 'MAINTENANCE_SESSION' in d.get('reasons', [])}
        if actual_keys-expected_keys or len(actual_keys) != len(checks) or any(
                k[2].tz_convert('America/New_York').date() not in maintenance_days for k in missing):
            raise ValueError('Silent dropped or duplicate correlation checks')
        for e in checks:
            ts = pd.Timestamp(e['time']); day = pd.Timestamp(ts.tz_convert('America/New_York').date())
            i = returns.index.get_loc(day)
            matrix = returns.iloc[max(0, i-40):i]
            if pd.Timestamp(e['source_date']) != matrix.index[-1] or matrix.index[-1] >= day:
                raise ValueError('Noncausal or stale correlation context')
            candidate = by_candidate[(int(e['pair_id']), e['side'], ts)]
            held = expected_holdings(records, e, candidate)
            if set(held) != set(e['held']):
                raise ValueError('Declared held symbols not reconstructed from transaction lifecycle')
            for s, r in held.items():
                declared = e['held'][s]
                op = tapes[case['year']]['bars'][bar_index[ts]][s][0]
                if declared['side'] != r['side'] or declared['quantity'] != r['qty'] or not np.isclose(declared['mark'], op, atol=1e-10):
                    raise ValueError('Held side/size/open mismatch')
            if case['arm'] != 'correlation' or e['symbol'] in held:
                if e['gate'] != 'NOT_APPLIED' or e['pairs']:
                    raise ValueError('Gate unexpectedly applied')
            else:
                if [p['held_symbol'] for p in e['pairs']] != sorted(held):
                    raise ValueError('Held correlation pair missing')
                statuses = set()
                for pair in e['pairs']:
                    s = pair['held_symbol']
                    n, rho = scalar_pearson(matrix[e['symbol']].to_numpy(float), matrix[s].to_numpy(float))
                    status = 'MISSING_PAIR' if rho is None else 'CORRELATED' if rho > .9 else 'PASS'
                    if status != pair['status'] or n != pair['overlap']:
                        raise ValueError('Independent scalar pair decision mismatch')
                    if rho is not None:
                        error = abs(rho-pair['correlation']); max_error = max(max_error, error)
                        if error > 1e-10:
                            raise ValueError('Scalar correlation value mismatch')
                    statuses.add(status); pairs_checked += 1
                gate = 'MISSING_PAIR' if 'MISSING_PAIR' in statuses else 'CORRELATED' if 'CORRELATED' in statuses else 'PASS'
                if gate != e['gate'] or gate != 'PASS' and e['opened']:
                    raise ValueError('Gate not honored')
                if gate != 'PASS':
                    refusals.append(dict(case=case['case'], **e))
            events_checked += 1
        concentration = pd.DataFrame(READ(folder/'concentration-events.json'))
        by_symbol = trades.groupby('symbol').pnl.sum().sort_values(ascending=False)
        positive = by_symbol.clip(lower=0).sum()
        summary = dict(arm=case['arm'], year=case['year'], side=case['side'],
            closed_trade_pnl_usd=float(trades.pnl.sum()), worst_trade_usd=float(trades.pnl.min()),
            average_worst_5_trade_pnl_usd=float(trades.pnl.nsmallest(5).mean()),
            top3_symbols_closed_pnl_usd=float(by_symbol.head(3).sum()),
            top3_share_of_positive_symbol_pnl_pct=float(100*by_symbol.clip(lower=0).head(3).sum()/positive) if positive else None,
            mean_held_count=float(concentration.held_count.mean()),
            sessions_with_high_correlation=int(concentration.high_correlation_pairs.gt(0).sum()),
            mean_known_pair_correlation=float(concentration.weighted_pair_correlation.mean()),
            sessions_without_pair_observation=int(concentration.known_pairs.eq(0).sum()))
        summaries.append(summary)
        by_symbol.rename('closed_pnl_usd').to_csv(folder/'symbol-pnl.csv')
    pd.DataFrame(summaries).to_csv(root/'concentration-summary.csv', index=False)
    pd.DataFrame(costs).to_csv(root/'cost-audit.csv', index=False)
    atomic_json(root/'refusals.json', refusals)
    atomic_json(root/'post-review.json', dict(status='PASS_PRIOR_RETURNS_HELD_STATE_PAIRS_AND_COSTS',
        events_checked=events_checked, pairs_checked=pairs_checked,
        independent_return_max_error=return_error, independent_correlation_max_error=max_error,
        cost_identity_max_error=max(c['max_accounting_error'] for c in costs),
        independent_human_review=False,
        files={n: digest(root/n) for n in ['report.json', 'annual-summary.csv', 'concentration-summary.csv',
                                          'cost-audit.csv', 'refusals.json']},
        review_sources={str(Path(__file__)): digest(Path(__file__)),
                        'scripts/research/us_short_loss_attribution.py': digest('scripts/research/us_short_loss_attribution.py')}))


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=Path('artifacts/research/us_oracle_portfolio_correlation/20261021-v1'))
    review(p.parse_args().output)
