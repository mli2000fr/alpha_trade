"""Independent hypothetical LONG outcomes for each of the 74 vetoed signals.

Not a portfolio: no capital/sector/correlation/one-position gate; overlapping
symbol/date cases retained. Existing frozen local inputs only, no API or SQL.
Two entry definitions explicitly distinguished, same SL7/noTP/noTR/open21.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_winner_gpt_veto_august_2026 import base, grid
from scripts.research.us_winner_sl3_tp7_tr3_open11_audit_20261023 import scalar_exit, near

PARENT = Path('artifacts/research/us_winner_gpt_veto_august_2026/20261025-score1-4-v1')
ROOT = PARENT / 'signal-outcomes-v1'
FEE = .0008


def first_confirmation(path, day, days):
    """First causal fresh cross + two closes; execute at following bar open."""
    pos = days.index(day)
    for current in days[pos+1:pos+21]:
        prior = days[days.index(current)-1]
        previous = path[path.trade_date.eq(pd.Timestamp(prior))]
        session = path[path.trade_date.eq(pd.Timestamp(current))].reset_index(drop=True)
        if previous.empty or session.empty:
            raise ValueError('Qualified common cohort has an absent entry session')
        level = float(previous.high.max())
        closes = session.close.to_numpy(float)
        for i in range(3, len(session)):
            if closes[i-3] <= level and closes[i-2] > level and closes[i-1] > level:
                return session.iloc[i]
    return None


def vector_exit(path, entry_time, entry_price, due):
    """Independent first-hit exit with deadline before opening-stop priority."""
    stop = round(float(entry_price)*.93, 2)
    frame = path[path.bar_timestamp.ge(entry_time)]
    hit = frame[(frame.bar_timestamp.eq(due)) | frame.open.le(stop) | frame.low.le(stop)]
    if hit.empty:
        return None
    b = hit.iloc[0]
    if b.bar_timestamp == due:
        return b.bar_timestamp, float(b.open), 'HORIZON_OPEN'
    if b.open <= stop:
        return b.bar_timestamp, float(b.open), 'STOP_GAP'
    return b.bar_end_timestamp, stop, 'STOP'


def evaluate(path, entry, schedule):
    days = [s.session_date for s in schedule]
    entry_time = pd.Timestamp(entry.bar_timestamp)
    entry_day = entry_time.tz_convert('America/New_York').date()
    due = pd.Timestamp(schedule[days.index(entry_day)+20].open_at_utc)
    price = float(entry.open)
    result = scalar_exit(path, entry_time, price, due, sl=.07, tp=None, trail=None)
    check = vector_exit(path, entry_time, price, due)
    if result is None:
        if check is not None:
            raise AssertionError('Scalar/vector status differs')
        last = path[path.bar_timestamp.ge(entry_time)].iloc[-1]
        return dict(status='OPEN_CENSORED', entry_time=str(entry_time), entry_price=price,
            due_open=str(due), mark_time=str(last.bar_end_timestamp), mark_price=float(last.close),
            open_pnl_per_share=float(last.close)-price-price*FEE)
    if check is None or result[0] != check[0] or result[2] != check[2]:
        raise AssertionError('Scalar/vector exit differs')
    near(result[1], check[1])
    exit_time, exit_price, reason = result
    net = exit_price-price-FEE*(price+exit_price)
    return dict(status='WIN' if net > 0 else 'LOSS' if net < 0 else 'FLAT',
        entry_time=str(entry_time), entry_price=price, due_open=str(due), exit_time=str(exit_time),
        exit_price=exit_price, exit_reason=reason, net_pnl_per_share=net,
        net_return_pct=100*net/price)


def run():
    parent = base.read(PARENT/'protocol.json')
    report = base.read(PARENT/'report.json')
    if report['status'] != 'COMPLETED_AUDITED_EXPLORATORY':
        raise ValueError('Audited parent required')
    base.verify(parent['sources'])
    base.verify({str(PARENT/k): v for k, v in parent['files'].items()})
    manifest = base.read(PARENT/'inputs/snapshot.json')
    base.verify({str(PARENT/'inputs'/k): v for k, v in manifest['files'].items()})
    cohort = pd.read_parquet(PARENT/'common-cohort.parquet')
    chosen = cohort[cohort.selected & cohort.gpt_veto].copy()
    if len(chosen) != 74 or chosen.duplicated(['date', 'symbol']).any():
        raise ValueError('Exact 74 vetoed qualified symbol/date pairs required')
    pd.testing.assert_frame_equal(chosen.reset_index(drop=True),
        pd.read_parquet(PARENT/'veto-eligible.parquet').reset_index(drop=True))
    schedule = [s for s in grid.calendar().sessions(date(2026,7,20), date(2026,11,30)) if s.is_open]
    days = [s.session_date for s in schedule]
    raw = {}
    for symbol in chosen.symbol.unique():
        f = pd.read_parquet(PARENT/'inputs'/f'{symbol}.parquet')
        for k in ('open', 'high', 'low', 'close', 'volume'):
            f[k] = pd.to_numeric(f[k], errors='raise').astype(float)
        if f.duplicated('bar_timestamp').any() or not np.isfinite(f[['open','high','low','close']]).all().all():
            raise ValueError('Bad OHLC')
        raw[symbol] = f.sort_values('bar_timestamp').reset_index(drop=True)
    paths = [Path(__file__), Path('tests/test_us_winner_gpt_veto_signal_outcomes_august_2026.py'),
        PARENT/'protocol.json', PARENT/'report.json', PARENT/'common-cohort.parquet',
        PARENT/'veto-eligible.parquet', PARENT/'inputs/snapshot.json',
        Path('scripts/research/us_winner_sl3_tp7_tr3_open11_audit_20261023.py')]
    sources = {str(f): base.digest(f) for f in paths}
    ROOT.mkdir(exist_ok=False)
    protocol = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), sources=sources,
        signals=74, cutoff='VALID score1..4, common qualified cohort only',
        entry_modes=['DIRECT_J_PLUS_1_OPEN', 'WINNER_FIRST_CONFIRMATION'],
        winner_entry='Wait at most20 sessions, fresh cross above prior session high plus two5m closes; next bar open.',
        exit='Fixed SL7 rounded to cents, noTP/noTR, open21 from actual fill, gap aware.',
        costs='8bps each side, hypothetical one share, no leverage/financing.',
        individual_counterfactual=True, portfolio_risk_or_capital_constraints=False,
        overlapping_symbol_date_cases=True, final_observation='2026-09-30',
        censored_not_wins_or_losses=True, historical_GPT_non_PIT=True, future_coverage_bias=True,
        gpt_calls=0, SQL_reads=False, SQL_writes=False, provider_calls=0, broker_orders=False)
    base.save_new(ROOT/'protocol.json', protocol)
    rows = []
    for row in chosen.itertuples():
        day = pd.Timestamp(row.date).date()
        path = raw[row.symbol]
        next_day = days[days.index(day)+1]
        direct = path[path.trade_date.eq(pd.Timestamp(next_day))].iloc[0]
        confirmed = first_confirmation(path, day, days)
        for mode, entry in [('DIRECT_J_PLUS_1_OPEN', direct), ('WINNER_FIRST_CONFIRMATION', confirmed)]:
            answer = dict(status='NO_ENTRY') if entry is None else evaluate(path, entry, schedule)
            rows.append(dict(date=str(day), symbol=row.symbol, oracle_rank=int(row.oracle_rank),
                gpt_score=int(row.gpt_score), mode=mode, **answer))
    frame = pd.DataFrame(rows)
    frame.to_parquet(ROOT/'outcomes.parquet', index=False)
    summaries = []
    for mode, f in frame.groupby('mode'):
        closed = f[f.status.isin(['WIN', 'LOSS', 'FLAT'])]
        summaries.append(dict(mode=mode, signals=len(f), unique_symbols=int(f.symbol.nunique()),
            counts=f.status.value_counts().to_dict(),
            closed_win_pct=100*closed.status.eq('WIN').mean() if len(closed) else None,
            average_closed_return_pct=float(closed.net_return_pct.mean()) if len(closed) else None,
            by_score=[dict(gpt_score=int(score), counts=g.status.value_counts().to_dict())
                for score, g in f.groupby('gpt_score')]))
    base.verify(sources)
    result = dict(status='COMPLETED_DOUBLE_CHECKED_COUNTERFACTUAL', cases=summaries,
        economic_portfolio=False, scalar_vector_exit_checks=int(frame.status.isin(['WIN','LOSS','FLAT']).sum()),
        sources=sources, files={'outcomes.parquet': base.digest(ROOT/'outcomes.parquet')})
    base.save_new(ROOT/'report.json', result)
    print(base.json.dumps({k: v for k, v in result.items() if k not in ('sources', 'files')}))


if __name__ == '__main__':
    import requests
    requests.Session.request = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('No network'))
    run()
