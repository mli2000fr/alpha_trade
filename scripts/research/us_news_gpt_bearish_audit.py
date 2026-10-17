"""Offline post-run audit of cached-news SHORT replays; no SQL or API access."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_short_replay import verify_short_trades


def close(actual, expected, label):
    if not np.allclose(actual, expected, atol=1e-6, rtol=1e-9):
        raise ValueError(label)


def audit(root):
    root = Path(root)
    read = lambda name: json.loads(Path(name).read_text(encoding='utf-8'))
    protocol = read(root / 'ready.json')
    if protocol != read(root / 'protocol.json'):
        raise ValueError('Protocol marker differs')
    verify_hashes(Path('.'), protocol['sources'])
    verify_hashes(root, protocol['files'])
    report = read(root / 'report.json')
    if report['status'] != 'COMPLETED' or len(report['reports']) != 12:
        raise ValueError('Twelve completed cases required')
    candidates = pd.read_parquet(root / 'candidates.parquet')
    bearish = candidates[candidates.bearish]
    valid = candidates.decision.eq('BEARISH') & candidates.technical_status.eq('VALID')
    if len(candidates) != 13780 or len(bearish) != 734 or not candidates.bearish.eq(valid).all():
        raise ValueError('Original candidate membership changed')
    if not candidates.GPT_BEARISH_ONLY.eq(candidates.selected & valid).all():
        raise ValueError('Unexpected bearish eligibility')
    sql_validation = read(root / 'sql-bearish-validation.json')
    if len(sql_validation) != 734 or {r['cache_key'] for r in sql_validation} != set(bearish.cache_key):
        raise ValueError('SQL response validation membership changed')
    prices = pd.read_parquet(protocol['prices'])
    indexed = prices.set_index(['symbol', 'date'])
    cases, seen = [], set()
    expected_cases = {(year, profile, arm) for year in (2024, 2025, 2026)
                      for profile in protocol['profiles'] for arm in protocol['arms']}
    for item in report['reports']:
        key = (item['year'], item['profile'], item['arm'])
        if key in seen or key not in expected_cases or not item['status'].startswith('COMPLETED'):
            raise ValueError('Unexpected/repeated/failed case')
        seen.add(key)
        folder = root / '-'.join(map(str, key))
        if read(folder / 'case-report.json') != item:
            raise ValueError('Case report differs from aggregate')
        verify_hashes(folder, item['files'])
        if (item['batch_id'] != protocol['models'][str(item['year'])]
                or item['research_allow_short_normal'] != (item['profile'] == 'RESEARCH_SHORT_NORMAL')
                or item['new_gpt_calls'] != 0 or item['database_writes'] or item['training']):
            raise ValueError('Unexpected model, permissions or side effects')
        days = nyse_sessions('2023-01-01', item['terminal_session'])
        trades = pd.read_parquet(folder / 'trades.parquet')
        if trades.empty:
            # Native no-entry cases legitimately serialize a zero-column frame.
            trades = pd.DataFrame({name: pd.Series(dtype='object')
                                   for name in ('exit_reason', 'symbol', 'entry_date', 'exit_date', 'pnl')})
            for name in ('entry_date', 'exit_date'):
                trades[name] = pd.to_datetime(trades[name])
        daily = pd.read_parquet(folder / 'daily.parquet')
        expected_days = days[days >= pd.Timestamp(item['first_session'])]
        if list(pd.to_datetime(daily.date)) != list(expected_days):
            raise ValueError('Incomplete daily timeline')
        signals = candidates[candidates.date.dt.year.eq(item['year']) & candidates[item['arm']]]
        allowed = {(days[days.get_loc(r.date) + 1], r.symbol) for r in signals.itertuples()
                   if days.get_loc(r.date) + 1 < len(days)}
        opened = [(pd.Timestamp(e['date']), symbol) for e in read(folder / 'executions.json')
                  for symbol in e['opened']]
        if len(set(opened)) != len(opened) or any(pair not in allowed for pair in opened):
            raise ValueError('Unexpected/repeated next-session entry')
        if item['actual_entries'] != len(opened):
            raise ValueError('Entry count differs')
        if trades.exit_reason.str.contains('terminal|trailing', regex=True).any():
            raise ValueError('Unexpected terminal/trailing exit')
        regular = trades[~trades.exit_reason.eq('learned_exit_next_open')]
        verify_short_trades(regular, prices, days, protocol['tp'], protocol['sl'], protocol['borrow_fee_annual'])
        maintenance = {pd.Timestamp(r['date']): r for r in read(folder / 'maintenance.json')}
        for row in trades[trades.exit_reason.eq('learned_exit_next_open')].itertuples():
            previous = days[days.get_loc(row.exit_date) - 1]
            if not maintenance[previous]['breach']:
                raise ValueError('Margin exit not preceded by breach')
            close(row.exit_price, indexed.at[(row.symbol, row.exit_date), 'open'], 'Margin cover not at next open')
        for row in trades.itertuples():
            close(row.replay_initial_stop_price, row.entry_price * 1.05, 'Wrong SHORT SL')
            close(row.replay_take_profit_price, row.entry_price * .80, 'Wrong SHORT TP')
            close(row.quantity, round(row.quantity), 'Fractional SHORT quantity')
            age = days.get_loc(row.exit_date) - days.get_loc(row.entry_date)
            if not 0 <= age <= 20 or row.side != 'sell':
                raise ValueError('Wrong side or holding period')
            close(row.borrow_cost, row.quantity * row.entry_price * protocol['borrow_fee_annual'] * age / 252,
                  'Incorrect closed borrow fee')
            close(row.pnl, 2 * row.quantity * row.entry_price - row.entry_cost + row.proceeds - row.borrow_cost,
                  'Incorrect SHORT cash flow')
        # Reconstruct every end-of-day liability from closed legs plus final open lots.
        # SHORT sale credits must not be counted as profit, including after partial covers.
        lots = [dict(symbol=r.symbol, quantity=r.quantity, entry_date=r.entry_date, exit_date=r.exit_date,
                     entry_price=r.entry_price, credit=2*r.quantity*r.entry_price-r.entry_cost)
                for r in trades.itertuples()]
        for position in item['open_positions']:
            entry = pd.Timestamp(position['entry_date'])
            if days.get_loc(days[-1]) - days.get_loc(entry) >= 20 or position['quantity'] <= 0:
                raise ValueError('Invalid/expired open lot')
            close(position['quantity'], round(position['quantity']), 'Fractional open SHORT')
            lots.append(dict(symbol=position['symbol'], quantity=position['quantity'], entry_date=entry,
                             exit_date=days[-1] + pd.Timedelta(days=1), entry_price=position['entry_price'],
                             credit=position['unrealized_pnl_usd'] + position['quantity']*position['mark']))
        completed_pairs = set(zip(trades.entry_date, trades.symbol))
        completed_pairs.update((pd.Timestamp(p['entry_date']), p['symbol']) for p in item['open_positions'])
        if completed_pairs != set(opened):
            raise ValueError('Opened lots not accounted for')
        interest = 0.
        for row in daily.itertuples():
            day = pd.Timestamp(row.date)
            active = [lot for lot in lots if lot['entry_date'] <= day < lot['exit_date']]
            debt = sum(lot['quantity'] * indexed.at[(lot['symbol'], day), 'close'] for lot in active)
            accrual = sum(lot['quantity'] * lot['entry_price'] * protocol['borrow_fee_annual']
                          * (days.get_loc(day)-days.get_loc(lot['entry_date'])) / 252 for lot in active)
            realized = float(trades.loc[trades.exit_date.le(day), 'pnl'].sum())
            interest += float(row.margin_interest)
            close(row.positions, len({lot['symbol'] for lot in active}), 'Wrong open position count')
            close(row.gross_notional, debt, 'Wrong SHORT mark liability')
            close(row.open_borrow_accrual, accrual, 'Wrong accrued borrow liability')
            close(row.settled_cash + row.unsettled_cash, 4000 + realized - interest + sum(lot['credit'] for lot in active),
                  'Daily cash reconciliation failed')
            close(row.equity, row.settled_cash + row.unsettled_cash - debt, 'Daily SHORT equity failed')
            close(row.equity_net_accrued_borrow, row.equity - accrual, 'Net-borrow equity failed')
        close(item['margin_interest'], interest, 'Total interest differs')
        close(item['final_capital_usd'], daily.equity_net_accrued_borrow.iloc[-1], 'Final wealth differs')
        if item['year'] < 2026 and item['open_positions']:
            raise ValueError('Old-year expiry tail incomplete')
        calendar = daily[daily.date.le(f'{item["year"]}-12-31' if item['year'] < 2026 else '2026-09-30')]
        cc = pd.concat([pd.Series([4000.]), calendar.equity_net_accrued_borrow], ignore_index=True)
        close(item['calendar_end_capital_usd'], cc.iloc[-1], 'Calendar wealth differs')
        close(item['calendar_end_return_pct'], 100*(cc.iloc[-1]/4000-1), 'Calendar return differs')
        close(item['calendar_end_drawdown_pct'], 100*(cc/cc.cummax()-1).min(), 'Calendar drawdown differs')
        case = {k: item[k] for k in ('year', 'profile', 'arm', 'actual_entries', 'closed_positions',
                'winning_positions', 'losing_positions', 'winning_pct', 'positive_closed_pnl_usd',
                'negative_closed_pnl_usd', 'calendar_end_capital_usd', 'calendar_end_return_pct',
                'calendar_end_drawdown_pct', 'calendar_end_positions', 'final_capital_usd', 'net_return_pct',
                'mean_gross_leverage', 'closed_borrow_usd', 'accrued_open_borrow_usd')}
        case.update(open_positions=len(item['open_positions']), all_checks_passed=True)
        cases.append(case)
    if seen != expected_cases:
        raise ValueError('Missing case')
    comparisons = []
    for profile in protocol['profiles']:
        for year in (2024, 2025, 2026):
            filtered = next(c for c in cases if (c['year'], c['profile'], c['arm']) == (year, profile, 'GPT_BEARISH_ONLY'))
            control = next(c for c in cases if (c['year'], c['profile'], c['arm']) == (year, profile, 'ORACLE_TOP20_ALL_SHORT'))
            comparisons.append(dict(year=year, profile=profile,
                return_advantage_points=filtered['calendar_end_return_pct']-control['calendar_end_return_pct'],
                capital_advantage_usd=filtered['calendar_end_capital_usd']-control['calendar_end_capital_usd'],
                drawdown_reduction_points=filtered['calendar_end_drawdown_pct']-control['calendar_end_drawdown_pct'],
                exposure_matched=False))
    value = dict(status='AUDITED_EXPLORATORY_NOT_PIT_NOT_SHORTABILITY_CERTIFIED', cases=cases,
        comparisons=comparisons, no_new_gpt_calls=True, sql_writes=False, independent_holdout=False,
        verdict='RESEARCH filter beats unfiltered SHORT in three years but loses in two; native gates yield only five filtered entries',
        limitations=['Borrow availability assumed; low hypothetical fee; recalls and dividend compensation absent',
                     'Historical news/PIT and LLM future knowledge not certified; current sectors; exposure not matched'],
        files={name: digest(root/name) for name in ['report.json', 'ready.json', 'sql-bearish-validation.json', 'candidates.parquet']})
    atomic_json(root / 'audit.json', value)
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    result = audit(parser.parse_args().output)
    print(json.dumps({key: value for key, value in result.items() if key != 'files'}))
