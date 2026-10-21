"""Read-only attribution of sealed SHORT grids; no new strategy simulation.

Fixed transactions before costs are an accounting decomposition, NOT a zero-
cost counterfactual backtest (admissions/sizes/risk paths would change).
"""
import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path('artifacts/research/us_intraday_protection_grid')
REFERENCE = 'SL7-TR15-H20-TPOFF'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified(path, expected):
    if digest(path) != expected:
        raise ValueError('Sealed artifact changed: '+str(path))


def cost_identity(root, row):
    directory = root/'cases'/row['case']
    for name in ('trades.parquet', 'open-positions.json'):
        verified(directory/name, row['files'][name])
    t = pd.read_parquet(directory/'trades.parquet')
    opened = read(directory/'open-positions.json')
    sign = -1 if row['side'] == 'sell' else 1
    gross = sign*t.quantity*(t.exit_price-t.entry_price)
    fees = .0008*t.quantity*(t.entry_price+t.exit_price)
    errors = t.pnl-(gross-fees-t.borrow_cost)
    if len(errors) and errors.abs().max() > 1e-6:
        raise ValueError('Independent signed PnL/cost identity failed: '+row['case'])
    open_gross = sum(sign*r['qty']*(r['mark']-r['entry_price']) for r in opened)
    entry_fees = sum(.0008*r['qty']*r['entry_price'] for r in opened)
    borrow = float(t.borrow_cost.sum())+sum(r.get('borrow_accrued_usd', 0.) for r in opened)
    all_fees = float(fees.sum())+entry_fees
    price_pnl = float(gross.sum())+open_gross
    error = price_pnl-all_fees-borrow-row['financing_usd']-row['net_pnl_usd']
    if abs(error) > 1e-6:
        raise ValueError('Total MTM/fees/borrow identity failed: '+row['case'])
    return t, dict(year=row['year'], case=row['case'], closed_price_pnl=float(gross.sum()),
        open_price_pnl=open_gross, fixed_trades_price_pnl=price_pnl, transaction_fees=all_fees,
        borrow=borrow, financing=row['financing_usd'], total_costs=all_fees+borrow+row['financing_usd'],
        net_pnl=row['net_pnl_usd'], gross_winners=int(gross.gt(0).sum()),
        net_winners=int(t.pnl.gt(0).sum()), max_accounting_error=max(abs(error), float(errors.abs().max()) if len(errors) else 0.))


def excursions(trade, path):
    """Confirmed BEFORE exit bar plus actual fill; no within-exit-bar ordering claim."""
    prior = path.loc[path.bar_timestamp.ge(trade['entry_timestamp']) & path.bar_timestamp.lt(trade['exit_timestamp'])]
    lo = min(float(prior.low.min()) if len(prior) else trade['entry_price'], trade['entry_price'], trade['exit_price'])
    hi = max(float(prior.high.max()) if len(prior) else trade['entry_price'], trade['entry_price'], trade['exit_price'])
    p = trade['entry_price']
    if trade['side'] == 'sell':
        return 100*(1-lo/p), 100*(hi/p-1)
    return 100*(hi/p-1), 100*(1-lo/p)


def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    roots = ['20261021-v1', '20261021-1x-v1', '20261021-1x-risk-v2', '20261021-1x-risk-dd15-v1']
    reports, grid = {}, []
    sources = {}
    for name in roots:
        root = BASE/name
        review = read(root/'final-review.json')
        if 'report.json' not in review['files']:
            raise ValueError('Final review does not seal report: '+name)
        verified(root/'report.json', review['files']['report.json'])
        report = read(root/'report.json')
        if report['failed'] or report['completed'] != 576:
            raise ValueError('Not a complete grid: '+name)
        sources[str(root/'report.json')] = digest(root/'report.json')
        reports[name] = report['cases']
        for year in (2025, 2026):
            for side in ('buy', 'sell'):
                cases = [r for r in report['cases'] if r['year'] == year and r['side'] == side]
                values = np.array([r['return_pct'] for r in cases])
                grid.append(dict(run=name, year=year, side=side, profiles=len(values),
                    positive=int((values > 0).sum()), minimum=float(values.min()),
                    median=float(np.median(values)), maximum=float(values.max())))
    root = BASE/roots[-1]
    prepared = read(root/'prepared.json')
    for name in ('bars.parquet', 'candidates.parquet', 'risk-regimes.parquet'):
        verified(root/name, prepared['files'][name])
        sources[str(root/name)] = digest(root/name)
    paths = {int(k): g.sort_values('bar_timestamp') for k, g in pd.read_parquet(root/'bars.parquet').groupby('pair_id')}
    candidates = pd.read_parquet(root/'candidates.parquet')
    regimes = pd.read_parquet(root/'risk-regimes.parquet').set_index('date').regime.to_dict()
    costs, reference, reference_trades = [], [], []
    for row in reports[roots[-1]]:
        if row['side'] != 'sell' and row['case'] != f"{row['year']}-LONG-{REFERENCE}":
            continue
        trades, cost = cost_identity(root, row)
        if row['side'] == 'sell':
            costs.append(cost)
        if row['case'] not in (f"{row['year']}-SHORT-{REFERENCE}", f"{row['year']}-LONG-{REFERENCE}"):
            continue
        trades = trades.copy()
        trades['year'] = row['year']
        trades['regime_at_entry'] = trades.entry_date.map(regimes)
        if trades.regime_at_entry.isna().any():
            raise ValueError('Missing archived prior-session regime')
        trades['price_pnl'] = (-1 if row['side'] == 'sell' else 1)*trades.quantity*(trades.exit_price-trades.entry_price)
        extra = [excursions(t, paths[t['pair_id']]) for t in trades.to_dict('records')]
        trades['favorable_confirmed_pct'], trades['adverse_confirmed_pct'] = np.array(extra).T
        terminal = []
        for t in trades.to_dict('records'):
            cap = pd.Timestamp('2025-12-31 23:59:59Z' if row['year'] == 2025 else '2026-09-30 23:59:59Z')
            path = paths[t['pair_id']]
            last = path.loc[path.bar_timestamp.eq(t['expiry'])]
            terminal.append(None if t['expiry'] > cap or last.empty else
                100*((t['entry_price']-float(last.iloc[0].open))/t['entry_price'])*(-1 if row['side'] == 'buy' else 1))
        trades['terminal_direction_return_pct'] = terminal
        reference_trades.append(trades)
        winners, losers = trades.loc[trades.pnl.gt(0)], trades.loc[trades.pnl.lt(0)]
        payoff = row['avg_win_usd']/abs(row['avg_loss_usd'])
        reference.append(dict(case=row['case'], **{k: row[k] for k in ['year', 'side', 'return_pct',
            'trades', 'winners', 'losers', 'win_rate_pct', 'avg_win_usd', 'avg_loss_usd',
            'avg_win_pct', 'avg_loss_pct', 'avg_winner_holding_sessions', 'avg_loser_holding_sessions',
            'max_drawdown_pct', 'mean_capital_used_usd']}, cost_decomposition=cost,
            observed_payoff_ratio=payoff, observed_break_even_win_pct=100/(1+payoff),
            losers_with_confirmed_3pct_profit_pct=100*float(losers.favorable_confirmed_pct.ge(3).mean()),
            losers_with_confirmed_5pct_profit_pct=100*float(losers.favorable_confirmed_pct.ge(5).mean()),
            winners_median_favorable_pct=float(winners.favorable_confirmed_pct.median()),
            losers_median_favorable_pct=float(losers.favorable_confirmed_pct.median()),
            all_trades_confirmed_3pct_profit_pct=100*float(trades.favorable_confirmed_pct.ge(3).mean()),
            all_trades_confirmed_5pct_profit_pct=100*float(trades.favorable_confirmed_pct.ge(5).mean()),
            paired_terminal_mature=int(trades.terminal_direction_return_pct.notna().sum()),
            paired_terminal_direction_win_pct=100*float(trades.loc[trades.terminal_direction_return_pct.notna(),
                'terminal_direction_return_pct'].gt(0).mean()),
            stopped_losers_terminal_mature=int(losers.terminal_direction_return_pct.notna().sum()),
            stopped_losers_later_terminal_positive=int(losers.terminal_direction_return_pct.gt(0).sum()),
            exits=trades.groupby('exit_reason').agg(trades=('pnl', 'size'), net_pnl=('pnl', 'sum'),
                losers=('pnl', lambda s: s.lt(0).sum())).reset_index().to_dict('records')))
    cost_frame = pd.DataFrame(costs)
    fixed_costs = cost_frame.groupby('year').agg(profiles=('case', 'size'),
        gross_positive=('fixed_trades_price_pnl', lambda s: s.gt(0).sum()),
        best_price_pnl=('fixed_trades_price_pnl', 'max'), median_transaction_fees=('transaction_fees', 'median'),
        maximum_borrow=('borrow', 'max'), max_accounting_error=('max_accounting_error', 'max')).reset_index()
    actual = pd.concat(reference_trades, ignore_index=True)
    actual.to_parquet(output/'reference-trade-attribution.parquet', index=False)
    short = actual.loc[actual.side.eq('sell')].copy()
    symbol = short.groupby(['year', 'symbol']).agg(trades=('pnl', 'size'), pnl=('pnl', 'sum')).reset_index()
    by_regime = short.groupby(['year', 'regime_at_entry']).agg(trades=('pnl', 'size'), pnl=('pnl', 'sum'),
        winners=('pnl', lambda s: s.gt(0).sum()), mean_return_pct=('net_return_pct', 'mean')).reset_index()
    worst = short.sort_values('pnl').head(12)
    columns = ['year', 'symbol', 'entry_timestamp', 'exit_timestamp', 'entry_price', 'exit_price',
        'quantity', 'pnl', 'exit_reason', 'net_return_pct', 'favorable_confirmed_pct']
    # Diagnostic only, never an executable future-based filter or new backtest.
    diagnostic, pair_order = [], []
    for row in candidates.loc[candidates.status.eq('SIGNAL')].to_dict('records'):
        path = paths[row['pair_id']]
        cap = pd.Timestamp(f"{row['year']}-12-31 23:59:59Z") if row['year'] == 2025 else pd.Timestamp('2026-09-30 23:59:59Z')
        tail = path.loc[path.bar_timestamp.ge(row['decision_time']) & path.bar_timestamp.le(min(row['expiry'], cap))]
        if len(tail) < 2 or tail.iloc[0].bar_timestamp != row['decision_time']:
            continue
        entry = float(tail.iloc[0].open)
        terminal = float(tail.iloc[-1].open)
        diagnostic.append(dict(year=row['year'], side=row['side'], pair_id=row['pair_id'], censored=row['expiry'] > cap,
            entry_session=int(tail.iloc[0].session_offset),
            terminal_short_return_pct=100*(1-terminal/entry),
            directional_terminal_win=(terminal < entry if row['side'] == 'sell' else terminal > entry)))
    diag = pd.DataFrame(diagnostic)
    for year in (2025, 2026):
        for side in ('buy', 'sell'):
            g = diag.loc[diag.year.eq(year) & diag.side.eq(side)]
            mature = g.loc[~g.censored]
            pair_order.append(dict(year=year, side=side, signal_cases=len(g),
                mature_terminal_cases=len(mature), right_censored_terminal=int(g.censored.sum()),
                median_signal_session_from_oracle=float(g.entry_session.median()),
                terminal_direction_win_pct=100*float(mature.directional_terminal_win.mean()),
                mean_underlying_terminal_return_pct=-float(mature.terminal_short_return_pct.mean()),
                median_underlying_terminal_return_pct=-float(mature.terminal_short_return_pct.median())))
    summary = dict(created_at_utc=datetime.now(UTC).isoformat(), status='COMPLETED_READ_ONLY_ATTRIBUTION',
        full_live_parity=False, independent_human_review=False, source_sha256=sources,
        script_sha256=digest(Path(__file__)),
        cohort=dict(pairs=int(candidates.pair_id.nunique()), symbols=int(candidates.symbol.nunique()),
            years=[2025, 2026], end_2026='2026-09-30'),
        grids=grid, fixed_short_transactions_before_costs=fixed_costs.to_dict('records'),
        reference_profiles=reference, short_attribution_by_regime=by_regime.to_dict('records'),
        short_attribution_by_symbol=symbol.sort_values(['year', 'pnl']).to_dict('records'),
        worst_short_trades=worst[columns].to_dict('records'),
        all_candidate_signal_diagnostic_not_traded_pnl=pair_order,
        limitations=['No new backtest, model, SQL, provider, LLM, order or parameter change',
            'Grids are highly correlated; 144 policies are not 144 independent trials',
            'Cohort conditional on future coverage, not complete TOP10 or whole universe; no2024',
            'Oracle research CatBoost PATH_H20, not directional model or guaranteed negative move',
            'Regime and excursion attributions retrospective, not validated predictive filters',
            'Borrow assumed available at0.3%annual; actual loan fees/recalls/locates absent',
            'Frozen old grid expiry includes pre-entry waiting, not new20holding-session runtime',
            'Excursion includes only bars strictly before exit bar and actual exit fill',
            'Price PnL before costs holds original transactions fixed; no altered-capital re-simulation'])
    (output/'report.json').write_text(json.dumps(summary, indent=2, default=str, allow_nan=False), encoding='utf-8')
    print(json.dumps(summary, indent=2, default=str, allow_nan=False))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    run(parser.parse_args().output)
