"""Prepare frozen candidates and price-path evidence. SELECT only; no replay."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, event, text

from database.connection import get_sqlalchemy_engine
from scripts.research.us_extreme50_capture import forbid_writes
from scripts.research.us_extreme50_price_qualification import reservations

POLICIES = ('ORACLE_TOP20', 'ORACLE_TOP10', 'INTERSECTION_ORACLE_TOP10')


def dump(path, payload):
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str,
                               allow_nan=False), encoding='utf-8')


def candidate_panel(panel, start, end):
    """Selection is archived and independent of future labels and price quality."""
    selected = panel[list(POLICIES)].fillna(False).any(axis=1)
    data = panel[selected & panel.date.between(pd.Timestamp(start), pd.Timestamp(end))].copy()
    if data.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate candidates')
    data['reserved_identity'] = reservations(data)
    return data


def inspect_paths(candidates, bars, sessions, progress=None):
    """H20 diagnostic windows are NOT actual lifecycle exits or trading vetoes."""
    rows = []
    sessions = pd.DatetimeIndex(sessions).sort_values().unique()
    by_symbol = {s: b.sort_values('date').reset_index(drop=True) for s, b in bars.groupby('symbol')}
    for symbol, group in candidates.groupby('symbol'):
        if progress:
            progress(symbol, len(rows), len(candidates))
        prices = by_symbol.get(symbol, bars.iloc[:0]).sort_values('date')
        dates = pd.DatetimeIndex(prices.date)
        adj = pd.to_numeric(prices.adj_close, errors='coerce')
        jump = adj.pct_change(fill_method=None).abs().ge(.5).to_numpy()
        for item in group.to_dict('records'):
            start = pd.Timestamp(item['date'])
            pos = sessions.searchsorted(start, side='right')
            entry = sessions[pos] if pos < len(sessions) else pd.NaT
            # Derive the observation boundary from calendar, never from label availability.
            end = sessions[pos+19] if pos+19 < len(sessions) else pd.NaT
            flags = []
            if pd.isna(entry) or pd.isna(end):
                flags.append('INCOMPLETE_OBSERVATION_CALENDAR')
            right = end if pd.notna(end) else (sessions[-1] if len(sessions) else start)
            left_index, right_index = dates.searchsorted(start), dates.searchsorted(right, side='right')
            path = prices.iloc[left_index:right_index]
            expected = int(((sessions >= start) & (sessions <= right)).sum())
            actual = len(path)
            expected_dates = sessions[(sessions >= start) & (sessions <= right)]
            missing = len(expected_dates.difference(pd.DatetimeIndex(path.date)))
            if missing:
                flags.append('MISSING_SESSION_BARS')
            zero = int(pd.to_numeric(path.volume, errors='coerce').fillna(0).le(0).sum())
            filled = int(path.is_filled.fillna(True).astype(bool).sum())
            invalid = int((~np.isfinite(pd.to_numeric(path.adj_close, errors='coerce'))
                           | pd.to_numeric(path.adj_close, errors='coerce').le(0)).sum())
            if zero:
                flags.append('ZERO_VOLUME_PATH')
            if filled:
                flags.append('FILLED_PATH')
            if invalid:
                flags.append('INVALID_PRICE')
            # Ignore a jump into the first price: it is outside this close-to-close window.
            jumps = int(jump[left_index+1:right_index].sum())
            if jumps:
                flags.append('DAILY_JUMP_GE50_REVIEW_NOT_PROOF_OF_ERROR')
            if path.instrument_id.dropna().nunique() > 1:
                flags.append('LOCAL_IDENTITY_CHANGE')
            if item['reserved_identity']:
                flags.append('RESERVED_IDENTITY')
            entry_rows = prices[prices.date.eq(entry)]
            if entry_rows.empty or not np.isfinite(pd.to_numeric(entry_rows.open, errors='coerce')).all() or entry_rows.open.le(0).any():
                flags.append('MISSING_OR_INVALID_NEXT_OPEN')
            rows.append(dict(date=start, symbol=symbol, next_session_entry=entry,
                             diagnostic_h20_end=end, expected_bars=expected, actual_bars=actual,
                             missing_session_bars=missing,
                             zero_volume_bars=zero, filled_bars=filled, invalid_prices=invalid,
                             large_daily_jumps=jumps, flags='|'.join(flags),
                             independently_certified=False))
    return pd.DataFrame(rows)


def run(source, output):
    source, output = Path(source), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    origin = json.loads((source/'protocol.json').read_text(encoding='utf-8'))
    start, end = '2025-01-01', '2026-09-30'
    if pd.Timestamp(origin['training_metadata']['training_end_date']) >= pd.Timestamp(start):
        raise ValueError('Frozen economic period must follow training end')
    protocol = dict(experiment='US_CONCENTRATED_AMPLITUDE_PREPARATION_V1',
        batch_id=origin['batch_id'], universe_hash=origin['universe_hash'],
        source_protocol_sha256=hashlib.sha256((source/'protocol.json').read_bytes()).hexdigest(),
        start=start, observation_end=end, policies=POLICIES, sides=['LONG_ONLY', 'SHORT_ONLY'],
        price_qualification_as_of='2026-10-06', database_writes=False, replay=False,
        entry='next regular session open, never signal-day close',
        portfolio=dict(initial_equity_usd=4000, max_positions=8, fractional=True,
                       rank='Oracle score descending, symbol ascending ties',
                       sizing='Canonical risk sizing must be frozen and verified before replay; no custom sizing here',
                       max_entry_gap_pct=.03, max_sector_exposure_pct=.5,
                       max_portfolio_drawdown_pct=.15, drawdown_recovery_pct=.92,
                       target_annual_vol=.13,
                       replacements='No replacement after retrospective price qualification failure'),
        lifecycle=dict(initial_stop_atr_multiple=2.5, tp_atr_multiple=3., tp_max_pct=.07,
                       trailing='canonical watcher/risk-based 2.5ATR; verify exact engine parity before replay',
                       time_stop=False, forced_h20_exit=False, terminal_liquidation=end),
        costs=dict(commission_bps_each_side=1., slippage_bps_each_side=2.,
                   margin_interest_annual=.075, spread='Resolve canonical cost contract before replay; never silently zero',
                   short_borrow='Missing historical availability/fees: SHORT economic certification blocked'),
        warning='Exploratory previously examined periods; not a new independent confirmation',
        gates=['Exact canonical execution/cost parity', 'Score timestamp/OOF lineage qualification',
               'Historical tradability/corporate-action qualification',
               'Full actual lifecycle paths, not just diagnostic H20 windows'])
    protocol_path = output/'protocol.json'
    if protocol_path.exists() and json.loads(protocol_path.read_text(encoding='utf-8')) != json.loads(json.dumps(protocol)):
        raise ValueError('Protocol already frozen with different values')
    dump(protocol_path, protocol)
    parts = [candidate_panel(pd.read_parquet(p), start, end) for p in sorted(source.glob('20*/panel.parquet'))]
    candidates = pd.concat(parts, ignore_index=True).sort_values(['date','symbol'])
    candidates.to_parquet(output/'candidates.parquet', index=False)
    symbols = sorted(set(candidates.symbol) | {'SPY'})
    engine = get_sqlalchemy_engine()
    event.listen(engine, 'before_cursor_execute', forbid_writes)
    try:
        with engine.connect() as conn:
            if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
                raise ValueError('US database required')
            for year, a, b in [(2024,'2024-10-01','2024-12-31'),
                               (2025,'2025-01-01','2025-12-31'),
                               (2026,'2026-01-01',end)]:
                path = output/f'bars-{year}.parquet'
                if path.exists():
                    continue
                dump(output/'progress.json', dict(phase='EXTRACT_BARS', year=year, symbols=len(symbols)))
                query = text('SELECT date,symbol,open,high,low,close,adj_close,volume,is_filled,instrument_id,data_source,data_adjustment FROM stock_bars_daily WHERE date BETWEEN :a AND :b AND symbol IN :symbols').bindparams(bindparam('symbols', expanding=True))
                bars = pd.read_sql(query, conn, params=dict(a=a,b=b,symbols=symbols))
                bars['date'] = pd.to_datetime(bars.date)
                if bars.duplicated(['date','symbol']).any():
                    raise ValueError('Duplicate price keys')
                temporary = path.with_suffix('.tmp.parquet')
                bars.to_parquet(temporary,index=False)
                temporary.replace(path)
    finally:
        event.remove(engine, 'before_cursor_execute', forbid_writes)
        engine.dispose()
    bars = pd.concat([pd.read_parquet(p) for p in sorted(output.glob('bars-*.parquet'))], ignore_index=True)
    sessions = bars.loc[bars.symbol.eq('SPY') & bars.volume.gt(0) & bars.is_filled.eq(0), 'date']
    sessions = sessions[sessions.between(start,end)]
    dump(output/'progress.json',dict(phase='CHECK_PATHS',candidates=len(candidates)))
    def progress(symbol, completed, total):
        dump(output/'progress.json',dict(phase='CHECK_PATHS',symbol=symbol,
                                        completed=completed,total=total))
    checks = inspect_paths(candidates, bars, sessions, progress=progress)
    checks.to_parquet(output/'path_checks.parquet',index=False)
    summaries = []
    for policy in POLICIES:
        group = candidates[candidates[policy]].merge(checks,on=['date','symbol'],validate='one_to_one')
        flags = group['flags'].str.split('|').explode()
        summaries.append(dict(policy=policy, candidates=len(group), dates=int(group.date.nunique()),
            symbols=int(group.symbol.nunique()), diagnostic_flags=flags[flags.ne('')].value_counts().to_dict(),
            no_local_flag=int(group['flags'].eq('').sum())))
    report = dict(status='PREPARED_NOT_ECONOMIC_REPLAY', candidates=len(candidates),
        symbols=int(candidates.symbol.nunique()), bars=len(bars), policies=summaries,
        calendar='SPY observed positive-volume bars; proxy, not certified exchange calendar',
        price_qualification='local flags only; no independent path certification',
        policy_disagreements={f'{a}_VS_{b}':int(candidates[a].ne(candidates[b]).sum())
                              for i,a in enumerate(POLICIES) for b in POLICIES[i+1:]},
        database_writes=False, training=False, economic_replay=False,
        files_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob('*.parquet')})
    dump(output/'report.json',report)
    dump(output/'progress.json',dict(phase='COMPLETED',report=str(output/'report.json')))
    print(json.dumps(report,ensure_ascii=False))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',default='artifacts/research/us_extreme50_capture/audit-20261006-v1')
    parser.add_argument('--output',default='artifacts/research/us_concentrated_replay/prepare-20261006-v1')
    run(**vars(parser.parse_args()))
