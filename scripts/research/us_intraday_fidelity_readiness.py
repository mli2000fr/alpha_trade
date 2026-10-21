"""Bounded READ ONLY inventory for native intraday LONG/SHORT fidelity.

No optimizer, training, provider calls, orders, SQL writes or fabricated receipts.
An EOD quote is not an intraday tape; a current borrow status is not history.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_campaign import make_path, fresh_signals
from scripts.research.us_top10_intraday_breakout import qualify_day

PARENT = Path('artifacts/research/us_oracle_campaign/20261020-v1')
READ = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
TABLES = {
    'quotes': ('stock_quote_snapshots', 'quote_date', ['symbol', 'quote_date', 'quote_timestamp',
        'provider', 'feed', 'quality_status', 'collected_at', 'source_timestamp',
        'raw_payload_sha256', 'raw_payload_path', 'bid_price', 'ask_price', 'bid_size', 'ask_size']),
    'borrow': ('stock_borrow_status_snapshots', 'available_at', ['symbol', 'provider', 'observed_at',
        'available_at', 'shortable', 'marginable', 'borrow_status', 'payload_hash', 'run_id']),
    'actions': ('corporate_actions_events', 'ex_date', ['id', 'symbol', 'provider', 'provider_event_id',
        'ca_type', 'amount_per_share', 'split_from', 'split_to', 'currency', 'announcement_date',
        'ex_date', 'payable_date', 'ingested_at', 'raw_payload', 'idempotency_key']),
}


def prepare(root):
    if (root/'prepared.json').exists():
        verify_hashes(Path('.'), READ(root/'protocol.json')['sources'])
        verify_hashes(root, READ(root/'prepared.json')['files'])
        return
    if root.exists() and any(root.iterdir()):
        raise ValueError('Fresh output required')
    verify_hashes(Path('.'), READ(PARENT/'protocol.json')['sources'])
    verify_hashes(PARENT, READ(PARENT/'prepared.json')['files'])
    verify_hashes(PARENT, READ(PARENT/'report.json')['files'])
    snap = READ(PARENT/'snapshot-ready.json')
    verify_hashes(PARENT, snap['files'])
    if READ(PARENT/'final-audit.json')['status'] != 'PASS_EXPLORATORY_CAMPAIGN_AUDIT':
        raise ValueError('Unqualified parent')
    names = ['backtesting/research_intraday_native.py', __file__,
        'scripts/research/us_intraday_fidelity_audit.py',
        'tests/test_research_intraday_native.py', 'tests/test_us_intraday_fidelity_readiness.py',
        'backtesting/simulator.py', 'backtesting/microstructure.py', 'backtesting/trading_constraints.py',
        'common/trading_costs.py', 'core/direction.py', 'risk_management/config.py',
        'risk_management/constraints.py', 'risk_management/position_sizer.py', 'risk_management/liquidity.py',
        'scripts/research/us_oracle_campaign.py', 'scripts/research/us_top10_intraday_breakout.py']
    names += [PARENT/n for n in ['protocol.json', 'prepared.json', 'report.json', 'final-audit.json',
        'selected.parquet', 'coverage.parquet', 'snapshot-ready.json', 'sessions.parquet']]
    root.mkdir(parents=True)
    atomic_json(root/'protocol.json', dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources={str(n): digest(n) for n in names}, parent=str(PARENT),
        purpose='Strengthen component fidelity, inventory independent blockers; NO288-grid or annual PnL.',
        native_reuse=['BacktestEngine entry/exit/cash/mark/gross/buying_power/settlements/borrow',
            'PositionSizer', 'ConstraintChecker', 'TradingCostModel', 'core.direction', 'microstructure exits/gap'],
        not_claimed=['Full PortfolioBuilder intraday/regime/correlation parity',
            'Broker watcher/arming/partial-fill/latency parity', 'Historical stock loan availability/rates/locates',
            'Complete corporate action feed', 'Realized execution reproduction'],
        candidate_rule='First fresh LONG and first fresh SHORT separately, original TOP10 parent admitted before quality; same213 qualified campaigns, no rank replacement.21sessions future quality is a selection bias,2024absent.',
        quote_rule='Two levels: market-event simulation may use historical source timestamps with a stated latency assumption; actual as-known replay additionally requires collected_at<=decision. Both need fresh SIP prices/sizes/archives. A backfill can improve simulation without proving old application receipts.',
        borrow_rule='Historical snapshot available<=decision, age<=24h, provider Alpaca. Status and payload inventory only: table has NO fee/locate/recall history, so not full SHORT qualification.',
        action_rule='Inventory matching events, never equate an empty table with complete no-event coverage. Ingested now does not prove available before historical decisions.',
        snapshot='Single REPEATABLE READ / READ ONLY transaction then ROLLBACK; tables may be absent, reported explicitly.',
        mode='Qualification, not optimization; no annual performance computed',
        sql_writes=False, provider_calls=False, llm_calls=False, training=False, orders=False,
        production_config_changed=False))
    cov = pd.read_parquet(PARENT/'coverage.parquet')
    calendar = pd.read_parquet(PARENT/'sessions.parquet')
    schedule = calendar.set_index('date')
    days = pd.DatetimeIndex(calendar.date)
    raw = pd.concat([f for name in snap['files'] if len(f := pd.read_parquet(PARENT/name))], ignore_index=True)
    groups = dict(tuple(raw.groupby(['symbol', 'trade_date'], sort=False)))
    cases = []
    for r in cov[cov.status.eq('OK')].itertuples():
        i = days.get_loc(r.date)
        frames = []
        for day in days[i:i+21]:
            q, why = qualify_day(groups.get((r.symbol, day)), *schedule.loc[day, ['market_open', 'market_close']])
            if q is None:
                raise ValueError(f'Parent changed: {why}')
            frames.append(q)
        path = make_path(frames)
        signals = fresh_signals(path)
        for sign, side in [(1, 'buy'), (-1, 'sell')]:
            events = [k for k, direction in signals if direction == sign and k < len(path)-1]
            k = events[0] if events else None
            cases.append(dict(pair_id=r.pair_id, symbol=r.symbol, oracle_date=r.date,
                year=r.year, rank=r.rank, side=side, status='SIGNAL' if k is not None else 'NO_SIGNAL',
                decision_time=path.bar_timestamp.iloc[k] if k is not None else pd.NaT,
                signal_bar_start=path.bar_timestamp.iloc[k-1] if k is not None else pd.NaT,
                signal_close=float(path.close.iloc[k-1]) if k is not None else None,
                expiry=path.bar_timestamp.iloc[-1]))
    pd.DataFrame(cases).to_parquet(root/'candidates.parquet', index=False)
    cov.to_parquet(root/'coverage.parquet', index=False)
    atomic_json(root/'prepared.json', dict(qualified_campaigns=int(cov.status.eq('OK').sum()),
        candidates=len(cases), signals=sum(c['status'] == 'SIGNAL' for c in cases),
        files={n: digest(root/n) for n in ['candidates.parquet', 'coverage.parquet']}))


def snapshot(root):
    prepare(root)
    if (root/'snapshot.json').exists():
        verify_hashes(root, READ(root/'snapshot.json')['files'])
        return
    from sqlalchemy import text, bindparam, inspect
    from database.connection import get_sqlalchemy_engine
    cases = pd.read_parquet(root/'candidates.parquet')
    start = cases.oracle_date.min()-pd.Timedelta(days=7)
    end = cases.expiry.max().tz_convert('America/New_York').tz_localize(None).normalize()+pd.Timedelta(days=1)
    symbols = sorted(cases.symbol.unique())
    engine = get_sqlalchemy_engine()
    inventories, files = {}, {}
    started = datetime.now(timezone.utc).isoformat()
    with engine.connect() as conn:
        conn.execute(text('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
        conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
        if conn.execute(text('SELECT DATABASE()')).scalar_one() != 'alpha_trade':
            raise ValueError('This US inventory must target alpha_trade only')
        inspector = inspect(conn)
        available = set(inspector.get_table_names())
        for key, (table, datecol, desired) in TABLES.items():
            if table not in available:
                inventories[key] = dict(table=table, status='MISSING_TABLE', rows=None)
                pd.DataFrame().to_parquet(root/f'{key}.parquet', index=False)
            else:
                columns = {c['name'] for c in inspector.get_columns(table)}
                selected = [c for c in desired if c in columns]
                if 'symbol' not in columns or datecol not in columns:
                    raise ValueError(f'Unsupported table schema: {table}')
                # All identifiers are constants from the allowlist above.
                sql = text(f"SELECT {','.join(selected)} FROM {table} WHERE symbol IN :symbols "
                    f"AND {datecol}>=:start AND {datecol}<:end").bindparams(bindparam('symbols', expanding=True))
                frame = pd.read_sql_query(sql, conn, params=dict(symbols=symbols,
                    start=start.to_pydatetime(), end=end.to_pydatetime()))
                frame.to_parquet(root/f'{key}.parquet', index=False)
                inventories[key] = dict(table=table, status='SNAPSHOTTED', rows=len(frame),
                    symbols=frame.symbol.nunique(), present_columns=selected,
                    missing_columns=sorted(set(desired)-columns))
            files[f'{key}.parquet'] = digest(root/f'{key}.parquet')
        conn.rollback()
    engine.dispose()
    atomic_json(root/'snapshot.json', dict(started_at_utc=started,
        finished_at_utc=datetime.now(timezone.utc).isoformat(), symbols=len(symbols),
        start=str(start), end_exclusive=str(end), inventories=inventories, files=files,
        transaction='REPEATABLE READ / READ ONLY / ROLLBACK'))


def row_reasons(row, quotes, borrow):
    if row.status != 'SIGNAL':
        return dict(status='NO_SIGNAL', quote_candidates=0, market_event_quote_candidates=0, borrow_candidates=0)
    now = row.decision_time
    q = quotes[quotes.symbol.eq(row.symbol)].copy() if 'symbol' in quotes else pd.DataFrame()
    quote_candidates = 0
    market_candidates = 0
    if len(q) and {'source_timestamp', 'collected_at', 'provider', 'feed', 'bid_price', 'ask_price', 'bid_size', 'ask_size', 'raw_payload_sha256', 'raw_payload_path'}.issubset(q):
        source = pd.to_datetime(q.source_timestamp, utc=True, errors='coerce')
        received = pd.to_datetime(q.collected_at, utc=True, errors='coerce')
        valid_market = (source.le(now) & source.ge(now-pd.Timedelta(minutes=5))
            & q.feed.eq('sip') & q.provider.eq('alpaca')
            & q.bid_price.gt(0) & q.ask_price.ge(q.bid_price)
            & np.isfinite(q.bid_price) & np.isfinite(q.ask_price) & np.isfinite(q.bid_size) & np.isfinite(q.ask_size)
            & q.bid_size.gt(0) & q.ask_size.gt(0) & q.raw_payload_sha256.str.len().eq(64) & q.raw_payload_path.notna())
        market_candidates = int(valid_market.sum())
        quote_candidates = int((valid_market & received.le(now) & received.ge(source)).sum())
    b = borrow[borrow.symbol.eq(row.symbol)].copy() if 'symbol' in borrow else pd.DataFrame()
    borrow_candidates = 0
    if len(b) and {'available_at', 'provider', 'payload_hash'}.issubset(b):
        available = pd.to_datetime(b.available_at, utc=True, errors='coerce')
        borrow_candidates = int((available.le(now) & available.ge(now-pd.Timedelta(days=1))
            & b.provider.eq('alpaca') & b.payload_hash.notna()).sum())
    reasons = ['MISSING_SEALED_NATIVE_RISK_CONTEXT', 'UNPROVEN_COMPLETE_CORPORATE_ACTION_COVERAGE',
        'UNQUALIFIED_BROKER_FILL_ARMING_LATENCY']
    reasons += ['QUOTE_RAW_RECEIPT_REVIEW_REQUIRED'] if quote_candidates else ['NO_CONTEMPORANEOUS_5M_SIP_QUOTE_RECEIPT']
    if row.side == 'sell':
        reasons += ['BORROW_STATUS_REVIEW_REQUIRED'] if borrow_candidates else ['NO_CONTEMPORANEOUS_BORROW_SNAPSHOT']
        reasons.append('MISSING_HISTORICAL_LOAN_FEES_LOCATES_RECALLS')
    return dict(status='BLOCKED_FULL_PARITY', quote_candidates=quote_candidates,
        market_event_quote_candidates=market_candidates,
        borrow_candidates=borrow_candidates, reasons=';'.join(reasons))


def report(root):
    prepare(root)
    if (root/'report.json').exists():
        raise ValueError('Immutable completed report')
    snap = READ(root/'snapshot.json')
    verify_hashes(root, snap['files'])
    cases = pd.read_parquet(root/'candidates.parquet')
    quotes, borrow = [pd.read_parquet(root/f'{key}.parquet') for key in ['quotes', 'borrow']]
    rows = [dict(r._asdict(), **row_reasons(r, quotes, borrow)) for r in cases.itertuples(index=False)]
    frame = pd.DataFrame(rows)
    frame.to_parquet(root/'readiness.parquet', index=False)
    summaries = []
    for (year, side), g in frame.groupby(['year', 'side']):
        active = g[g.status.ne('NO_SIGNAL')]
        reasons = active.reasons.str.split(';').explode().value_counts() if len(active) else pd.Series(dtype=int)
        summaries.append(dict(year=int(year), side=side, campaigns=len(g), signals=len(active),
            no_signal=int(g.status.eq('NO_SIGNAL').sum()),
            quote_candidate_cases=int(active.quote_candidates.gt(0).sum()),
            market_event_quote_candidate_cases=int(active.market_event_quote_candidates.gt(0).sum()),
            borrow_candidate_cases=int(active.borrow_candidates.gt(0).sum()),
            full_parity_qualified=0, reasons={str(k): int(v) for k, v in reasons.items()}))
    actions = pd.read_parquet(root/'actions.parquet')
    atomic_json(root/'report.json', dict(status='COMPONENT_ADAPTER_DELIVERED_FULL_PARITY_BLOCKED',
        sources_verified=True, sql_writes=False, provider_calls=False, annual_pnl_computed=False,
        optimizer_started=False, summaries=summaries, inventories=snap['inventories'],
        corporate_action_types={str(k): int(v) for k, v in actions.ca_type.value_counts().items()} if 'ca_type' in actions else {},
        files={'readiness.parquet': digest(root/'readiness.parquet')},
        next_steps=['Recover/qualify contemporaneous quote archives if available, never substitute close-of-day quotes',
            'Export native risk/regime/sector/correlation decision receipts and validate intraday timing',
            'Qualify corporate-action coverage and effective/payable events',
            'SHORT requires contemporaneous shortability and costs/locates/recalls or remains hypothetical',
            'Calibrate fills/arming in prospective PAPER; even PAPER is not real exchange fills'],
        note='No candidate is marked qualified by default. Nonempty tables do not prove all-domain coverage. Market-event quotes backfilled now can support a realistic simulation with declared latency assumptions; they do NOT prove the historical application received them then.'))
    print(READ(root/'report.json'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase', choices=['prepare', 'snapshot', 'report'], required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    {'prepare': prepare, 'snapshot': snapshot, 'report': report}[args.phase](args.output)


if __name__ == '__main__':
    main()
