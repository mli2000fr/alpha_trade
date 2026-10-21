"""Independent completed robustness review, accounting and entry-lineage checks."""
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_intraday_protection_grid import READ, case_key as original_case_key
from scripts.research.us_oracle_grid_robustness import REFERENCE, profile_key, ANCHOR


def cost_identity(trades, opened, case):
    sign = 1 if case['side'] == 'buy' else -1
    fee = case['fee_bps']/10000
    if len(trades):
        price_closed = sign*trades.quantity*(trades.exit_price-trades.entry_price)
        transaction_closed = fee*trades.quantity*(trades.entry_price+trades.exit_price)
        errors = trades.pnl-(price_closed-transaction_closed-trades.borrow_cost)
        maximum = float(errors.abs().max())
        price_pnl = float(price_closed.sum())
        transaction_cost = float(transaction_closed.sum())
        borrow = float(trades.borrow_cost.sum())
    else:
        maximum = price_pnl = transaction_cost = borrow = 0.
    for row in opened:
        p = sign*row['qty']*(row['mark']-row['entry_price'])
        f = fee*row['qty']*row['entry_price']
        b = row.get('borrow_accrued_usd', 0.)
        maximum = max(maximum, abs(row['unrealized_pnl_usd']-(p-f-b)))
        price_pnl += p; transaction_cost += f; borrow += b
    error = price_pnl-transaction_cost-borrow-case['financing_usd']-case['net_pnl_usd']
    maximum = max(maximum, abs(error))
    if maximum > 1e-6:
        raise ValueError('Independent signed-price/fees/borrow/MTM identity failed')
    return dict(max_error_usd=maximum, price_pnl_usd=price_pnl, transaction_costs_usd=transaction_cost,
                borrow_usd=borrow, financing_usd=case['financing_usd'], net_pnl_usd=case['net_pnl_usd'])


def verify_admissions(trades, opened, eligibility, c, paths):
    allowed = {(int(e['pair_id']), pd.Timestamp(e['decision_time'])): e
               for e in eligibility if e['reason'] == 'KEEP'}
    seen = set()
    for r in trades.to_dict('records')+opened:
        key = int(r['pair_id']), pd.Timestamp(r['entry_timestamp'])
        if key in seen or key not in allowed or r['side'] != c['side']:
            raise ValueError('Unapproved or duplicate stressed entry')
        seen.add(key); e = allowed[key]
        if r['symbol'] in c['excluded_symbols']:
            raise ValueError('Excluded symbol traded')
        day = pd.Timestamp(key[1].tz_convert('America/New_York').date())
        if c['excluded_quarter'] is not None and day.quarter == c['excluded_quarter']:
            raise ValueError('Excluded entry quarter traded')
        old = pd.Timestamp(e['original_time'])
        if key[1] != old+pd.Timedelta(minutes=5*c['delay_bars']):
            raise ValueError('Entry delay not the declared boundary')
        if old.tz_convert('America/New_York').date() != key[1].tz_convert('America/New_York').date():
            raise ValueError('Unqualified overnight delayed entry')
        match = paths[int(r['pair_id'])].loc[lambda g: g.bar_timestamp.eq(key[1])]
        if len(match) != 1 or not np.isclose(match.open.iloc[0], r['entry_price'], atol=1e-10):
            raise ValueError('Entry fill not actual corresponding open')
    return len(seen)


def review(root):
    root = Path(root)
    report = READ(root/'report.json'); protocol = READ(root/'protocol.json')
    verify_hashes(root, READ(root/'final-review.json')['files'])
    verify_hashes(root, READ(root/'prepared.json')['files'])
    verify_hashes(Path('.'), protocol['sources'])
    if report['completed'] != 86 or report['failed'] or len(report['cases']) != 86:
        raise ValueError('Complete86-case replay required')
    originals = {r['case']: r for r in READ(REFERENCE/'report.json')['cases']}
    paths = {int(k): g for k, g in pd.read_parquet(root/'bars.parquet').groupby('pair_id')}
    costs = []; effects = []; entries = 0
    metric_keys = ['return_pct', 'net_pnl_usd', 'final_capital_usd', 'max_drawdown_pct', 'trades',
        'winners', 'losers', 'win_rate_pct', 'avg_win_usd', 'avg_loss_usd',
        'avg_winner_holding_sessions', 'avg_loser_holding_sessions', 'mean_capital_used_usd', 'open_positions']
    for c in report['cases']:
        out = root/'cases'/c['case']; verify_hashes(out, c['files'])
        trades = pd.read_parquet(out/'trades.parquet'); opened = READ(out/'open-positions.json')
        if c['scenario'] == 'baseline':
            original = originals[original_case_key(c)]
            source = REFERENCE/'cases'/original['case']
            for name in ['trades.parquet', 'marks.parquet', 'open-positions.json']:
                if digest(source/name) != original['files'][name]:
                    raise ValueError('Original baseline artifact changed')
            for name in ['trades.parquet', 'marks.parquet']:
                pd.testing.assert_frame_equal(pd.read_parquet(out/name), pd.read_parquet(source/name), check_exact=True)
            if opened != READ(source/'open-positions.json'):
                raise ValueError('Baseline open positions differ from sealed original')
        counts = verify_admissions(trades, opened, READ(out/'entry-eligibility.json'), c, paths)
        entries += counts
        audit = cost_identity(trades, opened, c)
        audit.update(case=c['case'], year=c['year'], side=c['side'], scenario=c['scenario'], profile=profile_key(c))
        costs.append(audit)
        old = originals[original_case_key(c)]
        row = dict(case=c['case'], year=c['year'], side=c['side'], scenario=c['scenario'], profile=profile_key(c),
                   fee_bps=c['fee_bps'], delay_bars=c['delay_bars'], entries=counts,
                   excluded_symbols=','.join(c['excluded_symbols']), excluded_quarter=c['excluded_quarter'])
        for k in metric_keys:
            row[k] = c[k]; row[k+'_original'] = old[k]
            row[k+'_delta'] = c[k]-old[k] if c[k] is not None and old[k] is not None else None
        row.update(gap_stop_trades=int(trades.exit_reason.eq('GAP_STOP').sum()) if len(trades) else 0,
            worst_trade_net_pct=float(trades.net_return_pct.min()) if len(trades) else None)
        effects.append(row)
    pd.DataFrame(costs).to_csv(root/'cost-audit.csv', index=False)
    table = pd.DataFrame(effects)
    table.to_csv(root/'scenario-effects.csv', index=False)
    family = table[table.scenario.isin(['cost25', 'delay5m'])]
    summaries = []
    for (side, key), group in family.groupby(['side', 'profile']):
        by_year = group.drop_duplicates('year')
        row = dict(side=side, profile=key,
            original_both_years_positive=bool(by_year.return_pct_original.gt(0).all()))
        for scenario in ['cost25', 'delay5m']:
            g = group[group.scenario.eq(scenario)]
            row[scenario+'_both_years_positive'] = bool(g.return_pct.gt(0).all())
            row[scenario+'_worst_return'] = float(g.return_pct.min())
            row[scenario+'_max_dd'] = float(g.max_drawdown_pct.max())
        row['positive_all_individual_stresses'] = row['original_both_years_positive'] and all(
            row[s+'_both_years_positive'] for s in ['cost25', 'delay5m'])
        summaries.append(row)
    pd.DataFrame(summaries).to_csv(root/'family-stress-summary.csv', index=False)
    anchor_neighborhood = pd.read_csv(root/'neighborhoods.csv').loc[lambda g: g.profile.eq(profile_key(ANCHOR))]
    atomic_json(root/'post-review.json', dict(status='PASS_STRESS_LINEAGE_AND_COST_IDENTITY',
        audited_cases=86, admitted_lots_checked=entries, max_cost_identity_error_usd=max(r['max_error_usd'] for r in costs),
        anchor_neighborhood=anchor_neighborhood.to_dict('records'), independent_human_review=False,
        files={n: digest(root/n) for n in ['report.json', 'annual-summary.csv', 'cost-audit.csv',
            'scenario-effects.csv', 'family-stress-summary.csv', 'neighborhoods.csv']},
        review_sources={str(Path(__file__)): digest(Path(__file__))}))


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=Path('artifacts/research/us_oracle_grid_robustness/20261021-v2'))
    review(p.parse_args().output)
