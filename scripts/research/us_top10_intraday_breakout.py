"""Frozen TOP10 H10 / prior-session breakout, existing SIP bars only.

The snapshot phase uses SELECT inside a READ ONLY transaction. Replay is offline.
No provider download, fit, SQL write, production configuration, or order.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import shutil

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

SOURCE = Path('artifacts/research/us_h10_h20_frozen_comparison/20261019-v1')
PARENT = Path('artifacts/research/us_top10_four_session_confirmation/20261019-v1/protocol.json')
PRICE = Path('artifacts/research/us_h10_price_readiness/20261019-v1/qualification-final-v4/research-prices.parquet')
LOG = logging.getLogger(__name__)
POLICIES = ['BREAKOUT', 'MATCHED_REVERSE', 'MATCHED_LONG', 'MATCHED_SHORT', 'OPEN_LONG', 'OPEN_SHORT']
READ = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))


def prepare(root):
    if (root/'protocol.json').exists():
        protocol = READ(root/'protocol.json')
        verify_hashes(Path('.'), protocol['sources'])
        return protocol
    if list(root.iterdir()):
        raise ValueError('New empty output directory required')
    parent = READ(PARENT)
    files = [Path(__file__), Path('tests/test_us_top10_intraday_breakout.py'),
             Path('scripts/research/us_top10_intraday_breakout_audit.py'),
             SOURCE/'protocol.json', SOURCE/'final-audit.json', PARENT, PRICE]
    if READ(SOURCE/'final-audit.json')['status'] != 'PASS_EXPLORATORY_ONLY':
        raise ValueError('Unqualified source scores')
    for year in (2024, 2025, 2026):
        done = READ(SOURCE/f'{year}-done.json')
        name = f'{year}-H10-scores.parquet'
        if digest(SOURCE/name) != done['files'][name]:
            raise ValueError('Changed score snapshot')
        files.extend([SOURCE/name, SOURCE/f'{year}-done.json'])
        for f in (SOURCE/name, SOURCE/f'{year}-done.json', PRICE):
            if digest(f) != parent['sources'][str(f)]:
                raise ValueError(f'Parent lineage mismatch: {f}')
    protocol = dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources={str(f): digest(f) for f in files},
        signals='Original annual research H10 TOP10 at J, rank<=10; no later confirmation, rerank or replacement',
        observation_end='2026-09-30', years=[2024, 2025, 2026],
        source='alpha_trade.stock_bars_intraday / alpaca / alpaca_sip / 5m / US_EQ / raw',
        reference='J high/low reconstructed from its complete regular-session raw SIP 5m bars, NOT adjusted daily prices',
        entry='First J+1 completed 5m close strictly above J high or below J low; next contiguous bar open. Last bar cannot trigger executable entry.',
        one_entry=True, flip=False, tp=.10, sl=.05, holding_sessions=10, trailing=False,
        timeout='Final regular-session 5m close of J+10, entry session J+1 inclusive',
        collision='Stop first within same 5m bar; adverse gap exits at open, favourable TP gap fills only at limit',
        numerical_tolerance='1e-12 times barrier price to treat exact decimal touches consistently, not a trading buffer',
        exit_timestamps='Gap/time exits have a point timestamp; intrabar TP/SL is interval-censored between exit_bar_start and exit_bar_end; exit_time records its upper bound, not an invented fill time',
        completeness='Require all scheduled regular-session 5m bars for J through J+10, positive volume, valid raw unfilled OHLC, no duplicates. Exclude whole opportunity on any gap, even if an earlier exit would succeed.',
        price_basis='Daily normalized reference vs raw SIP aggregated OHLC must match up to one constant scale over 11 sessions, with <=1% ratio spread over all fields. No inferred split or patched price.',
        price_reserves=parent['price_reserves'], identity_events=parent['identity_events'],
        costs_per_leg=.0008, short_borrow_annual=.003,
        costs='Illustrative 8bps per executed leg including price-scaled exit; short borrow .3% annual by calendar days/365, no historical locates/dividends/recalls',
        policies=POLICIES, controls='Same entry time all-long/all-short/reverse on triggered pairs; open long/short on same fully covered universe including no-break pairs',
        independence='Earliest-first per symbol, either direction blocked through full J+10, not early exit; freeze same cohort for matched policies',
        bootstrap='20-signal-session blocks, 2000 fixed-seed ratio bootstrap; descriptive, not virgin holdout',
        sql_writes=False, downloads=False, fit=False, orders=False, portfolio_pnl=False,
        reserves=['Already explored years, current survivor universe, sparse-bar/coverage selection',
                  'OHLC cannot establish intra-bar tick order; no bid/ask/depth/fills, ideal next-bar open execution',
                  'Historical retrieval time is not historical publication availability; cannot assert point-in-time bars from observed_at',
                  'Price returns only, no dividends/corporate action cashflows; reject discontinuous price basis',
                  'No capital, reinvestment, leverage, historical short availability or annual capital drawdown claim'])
    atomic_json(root/'protocol.json', protocol)
    scores = pd.concat([pd.read_parquet(SOURCE/f'{y}-H10-scores.parquet',
        columns=['date', 'symbol', 'score', 'rank', 'year']) for y in protocol['years']], ignore_index=True)
    scores['date'] = pd.to_datetime(scores.date).dt.normalize()
    scores = scores[scores['rank'].le(10)].sort_values(['date', 'rank', 'symbol']).reset_index(drop=True)
    if scores.duplicated(['date', 'symbol']).any() or not scores.groupby('date').size().eq(10).all():
        raise ValueError('Invalid frozen TOP10 membership')
    scores.to_parquet(root/'selected-at-j.parquet', index=False)
    schedule = mcal.get_calendar('NYSE').schedule(start_date=scores.date.min(), end_date=protocol['observation_end'])
    schedule.index.name = 'date'
    schedule.reset_index().to_parquet(root/'sessions.parquet', index=False)
    atomic_json(root/'prepared.json', dict(files={f: digest(root/f) for f in ['selected-at-j.parquet', 'sessions.parquet']}))
    return protocol


def tasks_for(scores, sessions):
    days = pd.DatetimeIndex(sessions.date)
    needed = {}
    for row in scores.itertuples():
        i = days.get_indexer([row.date])[0]
        if i < 0 or i+10 >= len(days):
            raise ValueError('Signal without full calendar horizon')
        for day in days[i:i+11]:
            needed.setdefault((row.symbol, day.year), set()).add(day.date())
    return [(symbol, year, sorted(days)) for (symbol, year), days in sorted(needed.items())]


def snapshot(root, reuse=None):
    """One repeatable, read-only transaction, all local parts sealed together."""
    prepare(root)
    if (root/'snapshot-ready.json').exists():
        verify_hashes(root, READ(root/'snapshot-ready.json')['files'])
        return
    if reuse is not None:
        if (root/'snapshot').exists():
            raise ValueError('Snapshot destination must be empty')
        origin = READ(reuse/'snapshot-ready.json')
        verify_hashes(reuse, origin['files'])
        for name in ['selected-at-j.parquet', 'sessions.parquet']:
            if digest(root/name) != digest(reuse/name):
                raise ValueError('Incompatible snapshot membership/calendar')
        shutil.copytree(reuse/'snapshot', root/'snapshot')
        atomic_json(root/'snapshot-ready.json', origin)
        atomic_json(root/'snapshot-origin.json', dict(root=str(reuse),
            snapshot_ready_sha256=digest(reuse/'snapshot-ready.json'),
            reason='Numerical decimal-barrier touch and interval-censored timestamp corrections only. Same frozen rules and same SQL snapshot, no new data.'))
        return
    from sqlalchemy import bindparam, text
    from database.connection import get_sqlalchemy_engine
    parts = root/'snapshot'
    parts.mkdir(exist_ok=False)  # Never resume a different DB snapshot invisibly.
    scores = pd.read_parquet(root/'selected-at-j.parquet')
    sessions = pd.read_parquet(root/'sessions.parquet')
    tasks = tasks_for(scores, sessions)
    sql = text('''SELECT symbol,bar_timestamp,bar_end_timestamp,trade_date,open,high,low,close,
        volume,is_filled,data_adjustment,session_tag,provider,data_source,market_code,
        interval_code,observed_at,payload_hash,run_id
        FROM stock_bars_intraday
        WHERE symbol=:symbol AND bar_timestamp>=:start AND bar_timestamp<:end
          AND trade_date IN :dates AND interval_code='5m' AND data_source='alpaca_sip'
          AND provider='alpaca' AND market_code='US_EQ' AND session_tag='regular'
        ORDER BY bar_timestamp''').bindparams(bindparam('dates', expanding=True))
    engine = get_sqlalchemy_engine()
    files = {}; counts = []
    started = datetime.now(timezone.utc).isoformat()
    with engine.connect() as conn:
        conn.execute(text('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
        conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
        for i, (symbol, year, dates) in enumerate(tasks):
            params = dict(symbol=symbol, start=pd.Timestamp(dates[0]).to_pydatetime(),
                end=(pd.Timestamp(dates[-1])+pd.Timedelta(days=2)).to_pydatetime(), dates=dates)
            rows = pd.read_sql_query(sql, conn, params=params)
            for col in ['bar_timestamp', 'bar_end_timestamp', 'observed_at']:
                rows[col] = pd.to_datetime(rows[col], utc=True)
            rows['trade_date'] = pd.to_datetime(rows.trade_date)
            filename = f'snapshot/{i:04d}-{symbol}-{year}.parquet'
            rows.to_parquet(root/filename, index=False)
            files[filename] = digest(root/filename)
            counts.append(dict(symbol=symbol, year=year, requested_sessions=len(dates),
                rows=len(rows), sessions=int(rows.trade_date.nunique())))
            atomic_json(root/'progress.json', dict(status='SNAPSHOTTING', completed=i+1, total=len(tasks),
                rows=sum(c['rows'] for c in counts), current=symbol))
            if i % 10 == 0:
                LOG.info('Snapshot %d/%d %s: %d rows', i+1, len(tasks), symbol, len(rows))
        conn.rollback()
    engine.dispose()
    pd.DataFrame(counts).to_csv(root/'snapshot-coverage.csv', index=False)
    atomic_json(root/'snapshot-ready.json', dict(started_at_utc=started,
        finished_at_utc=datetime.now(timezone.utc).isoformat(), transaction='REPEATABLE READ / READ ONLY / ROLLBACK',
        files=files, tasks=len(tasks), rows=sum(c['rows'] for c in counts)))


def qualify_day(frame, opening, closing):
    expected = pd.date_range(opening, closing, freq='5min', inclusive='left')
    if frame is None or len(frame) == 0:
        return None, 'MISSING_SESSION'
    f = frame.sort_values('bar_timestamp')
    if f.bar_timestamp.duplicated().any():
        return None, 'DUPLICATE_BARS'
    if len(f) != len(expected) or not pd.DatetimeIndex(f.bar_timestamp).equals(expected):
        return None, 'INCOMPLETE_5M_GRID'
    if not pd.DatetimeIndex(f.bar_end_timestamp).equals(expected+pd.Timedelta(minutes=5)):
        return None, 'INVALID_END_TIMESTAMP'
    if not (f.is_filled.eq(0).all() and f.data_adjustment.eq('raw').all() and f.volume.gt(0).all()
            and f.provider.eq('alpaca').all() and f.data_source.eq('alpaca_sip').all()
            and f.market_code.eq('US_EQ').all() and f.interval_code.eq('5m').all()
            and f.session_tag.eq('regular').all()):
        return None, 'INVALID_BAR_METADATA_OR_VOLUME'
    a = f[['open', 'high', 'low', 'close']].to_numpy(dtype=float)
    if not np.isfinite(a).all() or (a <= 0).any() or (a[:,1] < a.max(axis=1)).any() or (a[:,2] > a.min(axis=1)).any():
        return None, 'INVALID_OHLC'
    return f.reset_index(drop=True), 'OK'


def first_break(frame, high, low):
    if not np.isfinite([high, low]).all() or high < low or low <= 0:
        raise ValueError('Invalid prior-session bounds')
    for i, price in enumerate(frame.close.to_numpy(dtype=float)[:-1]):
        if price > high:
            return i+1, 'LONG'
        if price < low:
            return i+1, 'SHORT'
    return None


def simulate(path, side, tp=.10, sl=.05, cost=.0008):
    """Completed signal bar is NOT in path; first row is next-bar execution."""
    if side not in ('LONG', 'SHORT') or len(path) == 0:
        raise ValueError('Invalid side/path')
    a = path[['open', 'high', 'low', 'close']].to_numpy(dtype=float)
    if not np.isfinite(a).all() or (a<=0).any() or (a[:,1]<a.max(axis=1)).any() or (a[:,2]>a.min(axis=1)).any():
        raise ValueError('Invalid path OHLC')
    sign = 1 if side == 'LONG' else -1
    entry = a[0,0]; stop = entry*(1-sign*sl); take = entry*(1+sign*tp)
    st = abs(stop)*1e-12; tt = abs(take)*1e-12
    outcome = 'TIMEOUT'; price = a[-1,3]; idx = len(a)-1; collision = False; gap = False
    for i, (op, high, low, close) in enumerate(a):
        hit_stop = low <= stop+st if sign == 1 else high >= stop-st
        hit_take = high >= take-tt if sign == 1 else low <= take+tt
        if sign*(op-stop) <= st:
            price, outcome, idx, gap = op, 'SL', i, True
            break
        if sign*(op-take) >= -tt:
            price, outcome, idx = take, 'TP', i
            break
        if hit_stop:
            price, outcome, idx, collision = stop, 'SL', i, bool(hit_take)
            break
        if hit_take:
            price, outcome, idx = take, 'TP', i
            break
    entry_time = path.bar_timestamp.iloc[0]; exit_time = path.bar_timestamp.iloc[idx]
    at_open = outcome != 'TIMEOUT' and (
        sign*(a[idx,0]-stop) <= st or sign*(a[idx,0]-take) >= -tt)
    if not at_open:
        exit_time = path.bar_end_timestamp.iloc[idx]
    if outcome == 'TIMEOUT':
        exit_time = path.bar_end_timestamp.iloc[-1]
    # Same-session borrowing charged one calendar day conservatively.
    calendar_days = max(1, (exit_time.date()-entry_time.date()).days)
    fees = cost*(1+price/entry)
    borrow = .003*calendar_days/365 if side == 'SHORT' else 0.
    gross = sign*(price/entry-1)
    return dict(side=side, entry_price=float(entry), exit_price=float(price),
        entry_time=entry_time, exit_time=exit_time, outcome=outcome, gap_stop=gap,
        exit_bar_start=path.bar_timestamp.iloc[idx], exit_bar_end=path.bar_end_timestamp.iloc[idx],
        exit_time_precision='POINT' if at_open or outcome=='TIMEOUT' else '5M_INTERVAL',
        collision=collision, gross=float(gross), costs=float(fees), borrow=float(borrow),
        net=float(gross-fees-borrow), exit_bar=idx)


def independent_ids(frame):
    accepted = []; blocked = {}
    for r in frame.sort_values(['date', 'rank', 'symbol']).itertuples():
        if r.entry_date > blocked.get(r.symbol, pd.Timestamp.min):
            accepted.append(r.pair_id)
            blocked[r.symbol] = r.last_path_date
    return set(accepted)


def summary(frame, days):
    if not len(frame):
        return dict(n=0, mean_net=None, win_rate=None, ci95=[None, None])
    gain = frame.loc[frame.net.gt(0), 'net']; loss = frame.loc[frame.net.lt(0), 'net']
    blocks = days.get_indexer(pd.to_datetime(frame.date))//20
    totals = pd.DataFrame(dict(block=blocks, net=frame.net.to_numpy(), n=1)).groupby('block')[['net', 'n']].sum()
    ci = [None, None]
    if len(totals) >= 5:
        rng = np.random.default_rng(20261019)
        draws = rng.integers(0, len(totals), size=(2000, len(totals)))
        v = totals.to_numpy()[draws].sum(axis=1)
        ci = [float(x) for x in np.quantile(v[:,0]/v[:,1], [.025, .975])]
    return dict(n=len(frame), mean_net=float(frame.net.mean()), median_net=float(frame.net.median()),
        win_rate=float(frame.net.gt(0).mean()), profit_factor=float(gain.sum()/-loss.sum()) if len(loss) else None,
        mean_gain=float(gain.mean()) if len(gain) else None, mean_loss=float(loss.mean()) if len(loss) else None,
        worst=float(frame.net.min()), ci95=ci, blocks=len(totals),
        outcomes={str(k): int(v) for k, v in frame.outcome.value_counts().items()},
        ambiguous=int(frame.collision.sum()), gap_stops=int(frame.gap_stop.sum()))


def replay(root):
    p = prepare(root)
    if (root/'report.json').exists():
        raise ValueError('Replay result immutable; use existing report')
    verify_hashes(root, READ(root/'prepared.json')['files'])
    snap = READ(root/'snapshot-ready.json'); verify_hashes(root, snap['files'])
    scores = pd.read_parquet(root/'selected-at-j.parquet')
    schedule = pd.read_parquet(root/'sessions.parquet').set_index('date')
    days = pd.DatetimeIndex(schedule.index)
    daily = pd.read_parquet(PRICE, columns=['symbol', 'date', 'open', 'high', 'low', 'close']).set_index(['symbol', 'date'])
    raw = pd.concat([pd.read_parquet(root/f) for f in snap['files']], ignore_index=True)
    groups = dict(tuple(raw.groupby(['symbol', 'trade_date'], sort=False)))
    del raw
    qualified = {}; reasons = {}; aggregates = {}
    for (symbol, day), frame in groups.items():
        if day not in schedule.index:
            continue
        op, cl = schedule.loc[day, ['market_open', 'market_close']]
        q, reason = qualify_day(frame, op, cl)
        reasons[symbol, day] = reason
        if q is not None:
            qualified[symbol, day] = q
            aggregates[symbol, day] = [q.open.iloc[0], q.high.max(), q.low.min(), q.close.iloc[-1]]
    groups.clear()
    coverage = []; trades = []
    for pair_id, row in enumerate(scores.itertuples()):
        i = days.get_indexer([row.date])[0]; window = days[i:i+11]
        base = dict(pair_id=pair_id, date=row.date, symbol=row.symbol, rank=row.rank, year=row.year,
            entry_date=window[1], last_path_date=window[-1])
        reason = 'OK'
        for day in window:
            if (row.symbol, day) not in qualified:
                reason = reasons.get((row.symbol, day), 'MISSING_SESSION')
                break
        for symbol, reserve in p['price_reserves'].items():
            if symbol == row.symbol and window[-1] >= pd.Timestamp(reserve['start']):
                reason = 'RESERVED_PRICE_BASIS'
        for ev in p['identity_events'].get(row.symbol, []):
            if window[0] <= pd.Timestamp(ev['last_predecessor_date']) and window[-1] >= pd.Timestamp(ev['first_successor_date']):
                reason = 'IDENTITY_DISCONTINUITY'
        ratio_spread = None
        if reason == 'OK':
            keys = [(row.symbol, d) for d in window]
            if not all(k in daily.index for k in keys):
                reason = 'MISSING_DAILY_CROSSCHECK'
            else:
                reference = daily.loc[keys, ['open', 'high', 'low', 'close']].to_numpy(dtype=float)
                ratio = np.asarray([aggregates[k] for k in keys])/reference
                ratio_spread = float(ratio.max()/ratio.min()-1)
                if not np.isfinite(ratio).all() or (reference<=0).any() or ratio_spread > .01:
                    reason = 'PRICE_BASIS_OR_DAILY_DISAGREEMENT'
        coverage.append(dict(**base, status=reason, ratio_spread=ratio_spread))
        if reason != 'OK':
            continue
        prev = qualified[row.symbol, window[0]]
        entry_day = qualified[row.symbol, window[1]]
        path = pd.concat([qualified[row.symbol, d] for d in window[1:]], ignore_index=True)
        trigger = first_break(entry_day, prev.high.max(), prev.low.min())
        coverage[-1]['triggered'] = trigger is not None
        coverage[-1]['trigger_side'] = trigger[1] if trigger else None
        for policy, side in [('OPEN_LONG', 'LONG'), ('OPEN_SHORT', 'SHORT')]:
            trades.append(dict(**base, policy=policy, **simulate(path, side)))
        if trigger is None:
            continue
        start, side = trigger
        for policy, direction in [('BREAKOUT', side), ('MATCHED_REVERSE', 'SHORT' if side == 'LONG' else 'LONG'),
                                  ('MATCHED_LONG', 'LONG'), ('MATCHED_SHORT', 'SHORT')]:
            trades.append(dict(**base, policy=policy, signal_time=entry_day.bar_end_timestamp.iloc[start-1],
                **simulate(path.iloc[start:].reset_index(drop=True), direction)))
        if pair_id % 500 == 0:
            LOG.info('Replay %d/%d', pair_id+1, len(scores))
    cov = pd.DataFrame(coverage); out = pd.DataFrame(trades)
    cov.to_parquet(root/'coverage.parquet', index=False)
    cov.groupby(['year', 'status']).size().rename('n').to_csv(root/'coverage-reasons.csv')
    if len(out):
        independent = independent_ids(out[out.policy.eq('BREAKOUT')])
        open_independent = independent_ids(out[out.policy.eq('OPEN_LONG')])
        out['independent'] = [r.pair_id in (open_independent if r.policy.startswith('OPEN_') else independent) for r in out.itertuples()]
    out.to_parquet(root/'trades.parquet', index=False)
    results = []
    if len(out):
        for (year, policy), f in out.groupby(['year', 'policy']):
            for side in ['ALL', 'LONG', 'SHORT']:
                g = f if side == 'ALL' else f[f.side.eq(side)]
                for mode in ['ALL', 'NON_OVERLAP']:
                    h = g if mode == 'ALL' else g[g.independent]
                    results.append(dict(year=int(year), policy=policy, side=side, cohort=mode, **summary(h, days)))
    annual = pd.DataFrame(results)
    annual.to_csv(root/'summary.csv', index=False)
    report = dict(status='EXPLORATORY_PARTIAL_COVERAGE' if len(out) else 'BLOCKED_NO_QUALIFIED_INTRADAY_WINDOWS',
        signal_pairs=len(cov), qualified_pairs=int(cov.status.eq('OK').sum()),
        missing_pairs=int(cov.status.ne('OK').sum()), snapshot_rows=snap['rows'],
        triggered_pairs=int(out.policy.eq('BREAKOUT').sum()) if len(out) else 0,
        coverage_by_year={str(y): dict(total=len(f), qualified=int(f.status.eq('OK').sum())) for y, f in cov.groupby('year')},
        exclusions={str(k): int(v) for k,v in cov.status.value_counts().items()}, summaries=results,
        files={f: digest(root/f) for f in ['coverage.parquet', 'coverage-reasons.csv', 'trades.parquet', 'summary.csv']},
        conclusion='No promotion: descriptive per-occasion test, inspect controls, non-overlap and coverage; no annual portfolio return')
    atomic_json(root/'report.json', report)
    atomic_json(root/'progress.json', dict(status='COMPLETED', qualified=report['qualified_pairs'], triggered=report['triggered_pairs']))
    LOG.info('Finished: %s', {k:v for k,v in report.items() if k not in ['summaries','files']})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['prepare', 'snapshot', 'replay'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse-snapshot', type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    args.output.mkdir(parents=True, exist_ok=True)
    if args.reuse_snapshot is not None and args.phase != 'snapshot':
        parser.error('--reuse-snapshot only for snapshot phase')
    if args.phase == 'snapshot':
        snapshot(args.output, args.reuse_snapshot)
    else:
        {'prepare': prepare, 'replay': replay}[args.phase](args.output)


if __name__ == '__main__':
    main()
