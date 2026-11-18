"""Read-only path accounting for archived anti-SL exclusions, not a replay."""
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

SOURCE = Path('artifacts/research/us_q051_b_early_sl/20261116-v1')
PRICES = Path('artifacts/research/us_q051_sl_pause/20261116-30sessions-pause100-v1/inputs')
ROOT = Path('artifacts/research/us_q051_anti_sl_metrics/20261118-v1/excluded-h10')


def path_result(entry, opening, high, low, close, volume):
    arrays = [np.asarray(x, dtype=float) for x in [opening, high, low, close, volume]]
    o, h, lo, c, v = arrays
    if any(len(a) != 11 or not np.isfinite(a).all() or not (a > 0).all() for a in arrays):
        raise ValueError('Incomplete11-session holding/exit price window')
    if not np.isclose(o[0], entry, rtol=0, atol=1e-8):
        raise ValueError('Frozen entry price differs from archived label')
    if (h < np.maximum.reduce([o, lo, c])).any() or (lo > np.minimum.reduce([o, h, c])).any():
        raise ValueError('Invalid OHLC window')
    stop = round(float(entry) * .95, 2)
    hits = np.flatnonzero(lo[:10] <= stop)
    first = int(hits[0]) if len(hits) else None
    # Exitopen11 is outside the10 holding sessions. Standing stop has priority
    # on a gap below the stop at this opening, but both exits have the same price.
    exit_price = min(o[first], stop) if first is not None else o[10]
    return dict(stop_price=stop, first_session_sl=bool(len(hits) and first == 0),
        stop_during_h10=bool(len(hits)), stop_session=first + 1 if first is not None else None,
        close10=float(c[9]), open11=float(o[10]),
        terminal_open11_below_entry=bool(o[10] < entry), terminal_open11_equal_entry=bool(o[10] == entry),
        terminal_open11_above_entry=bool(o[10] > entry), close10_below_entry=bool(c[9] < entry),
        strategy_exit_price=float(exit_price), strategy_exit_below_entry=bool(exit_price < entry),
        strategy_exit_equal_entry=bool(exit_price == entry), strategy_exit_above_entry=bool(exit_price > entry),
        terminal_return_pct=100 * (o[10] / entry - 1), strategy_gross_return_pct=100 * (exit_price / entry - 1),
        strategy_net_after_8bps_per_leg=bool(exit_price * (1 - .0008) > entry * (1 + .0008)))


def summarize(frame):
    names = ['stop_during_h10', 'terminal_open11_below_entry', 'terminal_open11_equal_entry',
        'terminal_open11_above_entry', 'close10_below_entry', 'strategy_exit_below_entry',
        'strategy_exit_equal_entry', 'strategy_exit_above_entry', 'strategy_net_after_8bps_per_leg']
    return dict(signals=len(frame), **{n: int(frame[n].sum()) for n in names},
        no_stop_but_terminal_below_entry=int((~frame.stop_during_h10 & frame.terminal_open11_below_entry).sum()),
        stop_then_terminal_above_or_equal=int((frame.stop_during_h10 & ~frame.terminal_open11_below_entry).sum()))


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    files = [SOURCE / 'filter-decisions.parquet', SOURCE / 'test-labels-and-risks.parquet',
             *[PRICES / (name + '.parquet') for name in ['open', 'high', 'low', 'close', 'volume', 'actions']]]
    labels = pd.read_parquet(files[1])
    decisions = pd.read_parquet(files[0])
    selected = decisions.loc[decisions['case'].eq('SL10') & decisions.excluded_by_sl,
                             ['date', 'symbol', 'entry_year']].merge(labels, on=['date', 'symbol'], validate='one_to_one')
    selected = selected[selected.first_session_sl.notna() & selected.event_available.le('2026-10-01')].copy()
    if len(selected) != 1496:
        raise ValueError('Cohort no longer matches1496 archived evaluable exclusions')
    first_session_count = int(selected.first_session_sl.eq(1).sum())
    selected = selected[selected.first_session_sl.eq(0)].copy()
    prices = {name: pd.read_parquet(PRICES / (name + '.parquet')) for name in ['open', 'high', 'low', 'close', 'volume']}
    calendar = prices['open'].index
    for data in prices.values():
        pd.testing.assert_index_equal(calendar, data.index)
        pd.testing.assert_index_equal(prices['open'].columns, data.columns)
    rows = []
    for row in selected.itertuples():
        offset = calendar.get_indexer([row.entry_day])[0]
        if offset < 0:
            raise ValueError('Entry date missing')
        windows = {k: v.loc[:, row.symbol].iloc[offset:offset + 11].to_numpy(float) for k, v in prices.items()}
        result = path_result(row.entry_open, windows['open'], windows['high'], windows['low'], windows['close'], windows['volume'])
        if result['first_session_sl'] != bool(row.first_session_sl):
            raise ValueError('Frozen daily path contradicts first-session label')
        rows.append(dict(signal_date=row.date, symbol=row.symbol, entry_year=row.entry_year,
            entry_date=row.entry_day, horizon_date=calendar[offset + 9], scheduled_exit=calendar[offset + 10],
            entry_price=row.entry_open, archived_net_long=row.net_long,
            original_long_label_missing=bool(pd.isna(row.net_long)), **result))
    detail = pd.DataFrame(rows)
    sub = detail[~detail.first_session_sl]
    if len(sub) != 1240:
        raise ValueError('Cohort no longer matches1240 non-first-session stops')
    known = sub.archived_net_long.notna()
    mismatches = sub[known & sub.archived_net_long.ne(sub.strategy_net_after_8bps_per_leg.astype(float))]
    mismatches.to_csv(ROOT / 'archived-label-differences.csv', index=False)
    if not sub.loc[sub.stop_during_h10, 'stop_session'].between(2, 10).all():
        raise ValueError('Later stop must occur in sessions2 through10')
    assert (sub.strategy_exit_below_entry.sum() + sub.strategy_exit_equal_entry.sum()
            + sub.strategy_exit_above_entry.sum()) == len(sub)
    detail.to_csv(ROOT / 'excluded-signal-paths.csv', index=False)
    annual = [dict(entry_year=y, **summarize(g)) for y, g in sub.groupby('entry_year')]
    pd.DataFrame(annual).to_csv(ROOT / 'non-first-session-annual.csv', index=False)
    pd.crosstab(sub.stop_during_h10, sub.terminal_open11_below_entry).to_csv(ROOT / 'stop-vs-terminal-crosstab.csv')
    atomic_json(ROOT / 'summary.json', dict(status='COMPLETE_DAILY_PATH_DIAGNOSTIC',
        full_excluded_cohort=dict(signals=1496, first_session_sl=first_session_count,
            stop_during_h10=first_session_count + int(sub.stop_during_h10.sum())),
        no_first_session_sl_cohort=summarize(sub),
        original_long_label_missing_in_subcohort=int(sub.original_long_label_missing.sum()),
        archived_long_label_differences=len(mismatches),
        label_difference_note='Comparison uses booked cent-rounded Winner stop; archived LONG labels use unrounded stop',
        reconstruction='Frozen continuous daily replay matrices include cross-year windows; no new predictions',
        stop='rounded entry*.95, fixed, earliest hit among entry session through session10',
        scheduled_exit='opening of session11, entry session is session1',
        price_comparisons='gross prices, before fees, financing and dividends; not actual executed trades',
        incomplete_windows=0, provider_calls=0, SQL_writes=0, portfolio_replay=False,
        strict_PIT=False, source_sha256={str(p): digest(p) for p in files}))
    print((ROOT / 'summary.json').read_text(encoding='utf-8')[:4200])


if __name__ == '__main__':
    main()
