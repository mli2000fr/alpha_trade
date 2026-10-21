"""Independent scalar gate review of the completed paired trend experiment."""
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_intraday_protection_grid import READ, PRICE
from scripts.research.us_short_loss_attribution import cost_identity


def smoothing(values, alpha, *, adjust=False, minimum=1):
    """Scalar recurrence, no feature helper or pandas EWM call."""
    result = np.full(len(values), np.nan)
    value = numerator = denominator = 0.
    seen = 0
    for i, x in enumerate(values):
        if not np.isfinite(x):
            if seen:
                raise ValueError('Unexpected internal gap in scalar smoother')
            continue
        if adjust:
            numerator = (1-alpha)*numerator+x
            denominator = (1-alpha)*denominator+1
            value = numerator/denominator
        else:
            value = x if not seen else alpha*x+(1-alpha)*value
        seen += 1
        if seen >= minimum:
            result[i] = value
    return result


def scalar_gate(g, side):
    """Truncated at prior session; restart after the last invalid exchange day."""
    array = g[['open', 'high', 'low', 'close', 'volume']].to_numpy(float)
    valid = np.isfinite(array).all(axis=1) & (array > 0).all(axis=1)
    valid &= (array[:, 1] >= np.maximum(array[:, 0], array[:, 3]))
    valid &= (array[:, 2] <= np.minimum(array[:, 0], array[:, 3]))
    valid &= g.is_filled.eq(0).to_numpy()
    bad = np.flatnonzero(~valid)
    start = int(bad[-1])+1 if len(bad) else 0
    a = array[start:]
    if len(a) < 60:
        return False, False, None
    h, l, c = a[:, 1], a[:, 2], a[:, 3]
    fast = smoothing(c, 2/21, minimum=20)
    slow = smoothing(c, 2/51, minimum=50)
    tr = np.r_[h[0]-l[0], np.maximum.reduce([h[1:]-l[1:], np.abs(h[1:]-c[:-1]), np.abs(l[1:]-c[:-1])])]
    up = np.r_[0., np.diff(h)]; down = np.r_[0., -np.diff(l)]
    plus = np.where((up > down) & (up > 0), up, 0.)
    minus = np.where((down > up) & (down > 0), down, 0.)
    smooth = lambda x: smoothing(x, 1/14, adjust=True, minimum=14)
    trs = np.maximum(smooth(tr), 1e-10)
    p, m = 100*smooth(plus)/trs, 100*smooth(minus)/trs
    adx = smooth(100*np.abs(p-m)/np.maximum(p+m, 1e-10))
    sign = 1 if side == 'buy' else -1
    accepted = all(sign*(c[i]-fast[i]) > 0 and sign*(fast[i]-slow[i]) > 0
                   and sign*(fast[i]-fast[i-5]) > 0 and adx[i] >= 20
                   for i in range(len(c)-3, len(c)))
    return True, bool(accepted), np.array([c[-1], fast[-1], slow[-1], fast[-6], adx[-1]])


def run(root):
    root = Path(root)
    report = READ(root/'report.json')
    if report['completed'] != 8 or report['failed']:
        raise ValueError('Eight successful paired accounts required')
    review = READ(root/'final-review.json')
    verify_hashes(root, review['files'])
    verify_hashes(root, READ(root/'prepared.json')['files'])
    verify_hashes(Path('.'), READ(root/'protocol.json')['sources'])
    eligible = pd.read_parquet(root/'eligibility.parquet')
    daily = pd.read_parquet(PRICE)
    from modelFactory.oracle.build_labels import nyse_sessions
    sessions = nyse_sessions(pd.to_datetime(daily.date).min(), pd.to_datetime(daily.date).max())
    per_symbol = {s: g.set_index('date').reindex(sessions) for s, g in
                  daily[daily.symbol.isin(eligible.symbol.unique())].groupby('symbol')}
    error = 0.
    for r in eligible.itertuples():
        day = pd.Timestamp(r.decision_time.tz_convert('America/New_York').date())
        if r.source_date != sessions[sessions.get_loc(day)-1]:
            raise ValueError('Not exactly the prior exchange session')
        qualified, accepted, numbers = scalar_gate(per_symbol[r.symbol].loc[:r.source_date], r.side)
        if qualified != r.qualified or accepted != r.accepted:
            raise ValueError('Independent scalar gate disagrees')
        if numbers is not None:
            actual = np.array([r.close, r.ema20, r.ema50, r.ema20_5ago, r.adx14])
            error = max(error, float(np.max(np.abs(numbers-actual))))
            if not np.allclose(numbers, actual, atol=1e-8, rtol=1e-10):
                raise ValueError('Independent trend values disagree')
    cost_rows = []
    for row in report['cases']:
        _, costs = cost_identity(root/row['arm'], row)
        costs['arm'] = row['arm']; cost_rows.append(costs)
    pd.DataFrame(cost_rows).to_csv(root/'cost-audit.csv', index=False)
    baseline = [r for r in report['cases'] if r['arm'] == 'baseline']
    attribution = []
    for row in baseline:
        trades = pd.read_parquet(root/'baseline'/'cases'/row['case']/'trades.parquet')
        merged = trades.merge(eligible[['pair_id', 'side', 'decision_time', 'accepted']],
            left_on=['pair_id', 'side', 'entry_timestamp'], right_on=['pair_id', 'side', 'decision_time'],
            validate='one_to_one', how='left', indicator=True)
        if not merged['_merge'].eq('both').all():
            raise ValueError('Missing gate for baseline trade')
        for accepted, group in merged.groupby('accepted'):
            attribution.append(dict(year=row['year'], side=row['side'], gate_pass=bool(accepted),
                baseline_closed_trades=len(group), winners=int(group.pnl.gt(0).sum()),
                win_rate_pct=float(100*group.pnl.gt(0).mean()),
                fixed_baseline_trades_net_usd=float(group.pnl.sum())))
    pd.DataFrame(attribution).to_csv(root/'baseline-trades-gate-attribution.csv', index=False)
    atomic_json(root/'post-review.json', dict(status='PASS_SCALAR_TREND_GATE_AND_COSTS',
        independent_human_review=False, checked_candidate_signals=len(eligible),
        scalar_feature_max_absolute_error=error,
        max_cost_accounting_error_usd=max(r['max_accounting_error'] for r in cost_rows),
        caveat='Fixed baseline trade subsets describe selection, NOT independent subportfolio backtests or causal exposure controls.',
        files={n: digest(root/n) for n in ['protocol.json', 'prepared.json', 'report.json', 'annual-summary.csv',
            'cost-audit.csv', 'baseline-trades-gate-attribution.csv']},
        review_sources={str(Path(__file__)): digest(Path(__file__)),
                        'scripts/research/us_short_loss_attribution.py': digest('scripts/research/us_short_loss_attribution.py')}))


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=Path('artifacts/research/us_oracle_persistent_trend/20261021-v1'))
    run(p.parse_args().output)
