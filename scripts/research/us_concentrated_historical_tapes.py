"""Assemble pre-portfolio historical lifecycle tapes, offline; never calculate PnL.

One unit is a technical probe, NOT PortfolioBuilder approval or real liquidity.
Future price quality checks annotate tapes and never reselect winning candidates.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile
import time

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_contract_audit import frozen_configs, validate_replay_tape

LOG = logging.getLogger(__name__)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, value):
    """Preserve the last checkpoint across transient Windows reader/AV locks.

    Unique sibling temp avoids temp-name collisions, but is not a multi-writer
    lock: never launch two instances on the same output directory.
    """
    path = Path(path)
    payload = json.dumps(value, indent=2, default=str, allow_nan=False)
    descriptor, name = tempfile.mkstemp(prefix=f'.{path.stem}-', suffix='.tmp', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(20):
            try:
                temporary.replace(path)
                return
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(min(.05 * 2**attempt, .5))
    finally:
        # Never delete the previous checkpoint or mask the original I/O error.
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            LOG.warning('Could not remove checkpoint temporary file %s', temporary)


def verify_hashes(root, mapping):
    for filename, expected in mapping.items():
        if digest(root / filename) != expected:
            raise ValueError(f'Source changed: {filename}')


def decision_rows(candidates):
    """Explicit allowlist: no realised labels, returns, or future quality flags."""
    columns = ['date', 'symbol', 'proba_extreme', 'fold_start', 'ORACLE_TOP20',
               'ORACLE_TOP10', 'INTERSECTION_ORACLE_TOP10']
    frame = candidates[columns].copy()
    frame['date'] = pd.to_datetime(frame.date)
    if frame.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate candidate')
    frame = frame.sort_values(['date', 'proba_extreme', 'symbol'], ascending=[True, False, True])
    frame['oracle_rank'] = frame.groupby('date').cumcount() + 1
    return frame


def apply_overlay(bars, overlay):
    bars = bars.copy()
    for row in overlay.to_dict('records'):
        mask = bars.symbol.eq(row['symbol']) & bars.date.eq(pd.Timestamp(row['date']))
        if mask.sum() != 1 or float(bars.loc[mask, 'volume'].iloc[0]) != row['original_volume']:
            raise ValueError('Overlay target absent, duplicate, or changed')
        bars.loc[mask, 'volume'] = row['replacement_volume']
    return bars


def entry_probe(row, bar, atr):
    from risk_management.models import PortfolioEntry
    from risk_management.enums import Decision, SizingMethod
    close = float(bar['close'])
    short = row['side'] == 'sell'
    risk = 2.5 * atr
    tp_distance = min(3 * atr, .07 * close)
    return PortfolioEntry(symbol=row['symbol'], sector='UNQUALIFIED_PIT_SECTOR',
        entry_price=close, score_used=float(row['proba_extreme']),
        score_source='frozen_oracle_amplitude_forced_research_side', atr_20=atr,
        proposed_shares=1., approved_shares=1., target_notional=close, target_weight=0.,
        decision=Decision.ACCEPTED, decision_reason='TECHNICAL_UNIT_PROBE_NOT_PORTFOLIO_APPROVAL',
        sizing_method=SizingMethod.UNKNOWN, selection_rank=int(row['oracle_rank']),
        stop_price_initial=close + risk if short else close - risk,
        take_profit_price=close - tp_distance if short else close + tp_distance,
        tp_atr_multiple=3., tp_max_pct=.07, risk_per_share=risk,
        score_snapshot_date=row['date'].date(), price_asof_date=row['date'].date(),
        atr_asof_date=row['date'].date(), trade_date=row['date'].date(), side=row['side'])


def path_flags(row, bars, calendar):
    """Retrospective annotations, not an entry filter or economic certification."""
    entry = pd.Timestamp(row['execution_date'])
    exit_raw = row.get('replay_exit_date')
    end = pd.Timestamp(exit_raw) if pd.notna(exit_raw) else calendar[-1]
    days = calendar[(calendar >= entry) & (calendar <= end)]
    path = bars.reindex(days)
    flags = []
    if path[['open', 'high', 'low', 'close']].isna().any().any():
        flags.append('MISSING_ACTUAL_PATH_BAR')
    if (path.volume.fillna(0) <= 0).any():
        flags.append('ZERO_OR_MISSING_ACTUAL_PATH_VOLUME')
    if path.is_filled.fillna(0).ne(0).any():
        flags.append('FILLED_ACTUAL_PATH')
    if path.instrument_id.dropna().nunique() > 1:
        flags.append('IDENTITY_CHANGE_ACTUAL_PATH')
    if not pd.notna(exit_raw):
        flags.append('OPEN_AT_TERMINAL_LIQUIDATION_NOT_TAPED')
    else:
        transition = row.get('watcher_transition_effective_date')
        if pd.notna(transition) and pd.Timestamp(transition) > end:
            flags.append('WATCHER_TRANSITION_AFTER_EXIT_REQUIRES_RECONCILIATION')
        opening = path.loc[end, 'open']
        price = row['replay_exit_price']
        reason = row['replay_exit_reason']
        short = row['side'] == 'sell'
        stop_gap = reason in ('initial_stop', 'trailing_stop') and (
            opening > price if short else opening < price)
        tp_gap = reason == 'take_profit' and (opening < price if short else opening > price)
        if stop_gap:
            flags.append('OPEN_GAP_EXIT_PRICE_REQUIRES_RECONCILIATION')
        elif tp_gap:
            flags.append('TP_OPEN_GAP_CONSERVATIVE_LIMIT_PRICE_REVIEW')
    if len(path) > 1 and path.close.pct_change(fill_method=None).abs().ge(.5).any():
        flags.append('JUMP_GE50_REVIEW_NOT_AUTOMATIC_PRICE_ERROR')
    return flags


def assemble_day(frame, bars_by_symbol, opens, highs, lows, atrs, counts, execution):
    from backtesting.execution_replay import simulate_phase3_execution_replay
    from backtesting.execution_lifecycle_replay import build_phase4_protection_replay
    from backtesting.protection_watcher_replay import build_phase5_watcher_replay
    from backtesting.exit_lifecycle_replay import build_phase7_exit_lifecycle_replay
    entries, audit = [], []
    calendar = opens.index
    for row in frame.to_dict('records'):
        day, symbol = row['date'], row['symbol']
        reason = None
        idx = calendar.searchsorted(day, side='right')
        source = bars_by_symbol[symbol]
        if idx >= len(calendar):
            reason = 'NO_NEXT_SESSION'
        elif day not in source.index:
            reason = 'MISSING_DECISION_BAR'
        else:
            bar = source.loc[day]
            atr = atrs.at[day, symbol]
            next_open = opens.at[calendar[idx], symbol]
            if not np.isfinite(atr) or atr <= 0 or counts.at[day, symbol] < 20:
                reason = 'INCOMPLETE_ATR20'
            elif not np.isfinite(bar.close) or bar.close <= 0 or bar.volume <= 0 or bar.is_filled != 0:
                reason = 'INVALID_DECISION_BAR'
            elif not np.isfinite(next_open) or next_open <= 0:
                reason = 'MISSING_NEXT_OPEN'
            elif abs(next_open / bar.close - 1) > execution.max_entry_gap_pct:
                reason = 'ENTRY_GAP_EXCEEDS_3PCT'
            elif bar.close - 2.5 * atr <= 0:
                reason = 'NONPOSITIVE_LONG_PROTECTION'
            else:
                entries.append(entry_probe(row, bar, float(atr)))
        audit.append({**row, 'entry_status': reason or 'UNIT_PROBE_READY',
                      'quantity_scope': 'ONE_UNIT_NOT_PORTFOLIO_APPROVED'})
    if not entries:
        return pd.DataFrame(audit), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    phase3 = simulate_phase3_execution_replay(entries, execution_config=execution,
        open_df=opens, risk_run_id_prefix='historical_unit_probe')
    if len(phase3.signals_df) != len(entries):
        raise ValueError('Unexpected phase3 dropped entries')
    phase4 = build_phase4_protection_replay(phase3, execution_config=execution)
    phase5 = build_phase5_watcher_replay(phase4, high_df=highs, low_df=lows)
    phase7 = build_phase7_exit_lifecycle_replay(phase5, high_df=highs, low_df=lows,
        intrabar_priority='conservative', swing_only=False)
    tape = phase7.signals_df.copy()
    validate_replay_tape(tape, calendar)
    if not tape.filled_qty.eq(1).all():
        raise ValueError('Unit quantity parity failure')
    for row in tape.to_dict('records'):
        if abs(float(row['fill_price']) - opens.at[pd.Timestamp(row['execution_date']), row['symbol']]) > .005:
            raise ValueError('Raw open fill parity failure')
    tape['path_flags'] = ['|'.join(path_flags(r, bars_by_symbol[r['symbol']], calendar))
                          for r in tape.to_dict('records')]
    tape['quantity_scope'] = 'ONE_UNIT_NOT_PORTFOLIO_APPROVED'
    tape['direction_source'] = 'FORCED_RESEARCH_SIDE_NOT_DIRECTIONAL_MODEL'
    membership = frame.rename(columns={'date': 'trade_date'})[
        ['trade_date', 'symbol', 'ORACLE_TOP20', 'ORACLE_TOP10', 'INTERSECTION_ORACLE_TOP10']]
    tape['trade_date'] = pd.to_datetime(tape.trade_date)
    tape = tape.merge(membership, on=['trade_date', 'symbol'], validate='one_to_one')
    tape['candidate_id'] = tape.trade_date.dt.strftime('%Y%m%d') + '-' + tape.symbol + '-' + tape.side
    return pd.DataFrame(audit), tape, phase7.order_lifecycle_frame, phase7.broker_event_frame


def run(source, contract, output, sides=('buy', 'sell'), max_dates=None):
    source, contract, output = map(Path, (source, contract, output))
    output.mkdir(parents=True, exist_ok=True)
    report = json.loads((source/'report.json').read_text())
    certificate = json.loads((contract/'report.json').read_text())
    verify_hashes(source, report['files_sha256'])
    verify_hashes(Path('.'), certificate['source_hashes'])
    if certificate['status'] != 'TECHNICAL_CONTRACT_VALIDATED_ON_SYNTHETIC_FIXTURES':
        raise ValueError('Technical contract not validated')
    for filename, key in [('resolved_contract.json', 'resolved_contract_sha256'),
                          ('band_volume_overlay.parquet', 'band_overlay_sha256')]:
        verify_hashes(contract, {filename: certificate[key]})
    raw = pd.read_parquet(source/'candidates.parquet')
    candidates = decision_rows(raw)
    bars = pd.concat([pd.read_parquet(source/name) for name in report['files_sha256']
                      if name.startswith('bars-')], ignore_index=True)
    bars['date'] = pd.to_datetime(bars.date)
    if bars.duplicated(['symbol', 'date']).any():
        raise ValueError('Duplicate historical bar')
    bars = apply_overlay(bars, pd.read_parquet(contract/'band_volume_overlay.parquet'))
    calendar = pd.DatetimeIndex(bars.loc[bars.symbol.eq('SPY') & bars.volume.gt(0) & bars.is_filled.eq(0), 'date']).sort_values()
    pivots = {col: bars.pivot(index='date', columns='symbol', values=col).reindex(calendar)
              for col in ('open', 'high', 'low', 'close')}
    from backtesting.simulator import BacktestEngine
    atrs = BacktestEngine._compute_atr(pivots['high'], pivots['low'], pivots['close'])
    counts = (pivots['high'].notna() & pivots['low'].notna() & pivots['close'].notna()).astype(int).rolling(20, min_periods=1).sum()
    bars_by_symbol = {symbol: group.set_index('date').sort_index() for symbol, group in bars.groupby('symbol')}
    _, execution = frozen_configs()
    manifest = {'source_files': report['files_sha256'], 'contract_report': digest(contract/'report.json'),
                'assembler_sha256': digest(__file__), 'sides': list(sides), 'max_dates': max_dates,
                'execution_config': asdict(execution), 'scope': 'PRE_PORTFOLIO_ONE_UNIT_LIFECYCLE',
                'economic_comparison': False, 'database_writes': False, 'training': False}
    manifest_path = output/'manifest.json'
    if manifest_path.exists() and json.loads(manifest_path.read_text()) != json.loads(json.dumps(manifest, default=str)):
        raise ValueError('Resume fingerprint/config mismatch; choose a new output directory')
    atomic_json(manifest_path, manifest)
    candidates.to_parquet(output/'selection_memberships.parquet', index=False)
    days = sorted(candidates.date.unique())[:max_dates]
    state = {'status': 'RUNNING', 'planned_dates': len(days), 'completed_dates': 0,
             'shards': [], 'economic_comparison': False}
    try:
        for day in days:
            day = pd.Timestamp(day)
            for side in sides:
                shard = output / f'{day:%Y%m%d}-{side}'
                marker = shard/'report.json'
                if marker.exists():
                    saved = json.loads(marker.read_text())
                    verify_hashes(shard, saved['files_sha256'])
                else:
                    shard.mkdir(exist_ok=True)
                    frame = candidates[candidates.date.eq(day)].assign(side=side)
                    # Bound quadratic pandas lifecycle-frame updates; same independent entries.
                    pieces = [assemble_day(frame.iloc[start:start+40], bars_by_symbol,
                        pivots['open'], pivots['high'], pivots['low'], atrs, counts, execution)
                        for start in range(0, len(frame), 40)]
                    audit, tape, orders, events = [pd.concat([piece[i] for piece in pieces
                        if not piece[i].empty], ignore_index=True) if any(not piece[i].empty for piece in pieces)
                        else pd.DataFrame() for i in range(4)]
                    if not tape.empty:
                        validate_replay_tape(tape, calendar)
                    hashes = {}
                    for name, data in [('entry_audit', audit), ('signals', tape), ('orders', orders), ('events', events)]:
                        file = shard/f'{name}.parquet'
                        data.to_parquet(file, index=False)
                        hashes[file.name] = digest(file)
                    flags = Counter(flag for value in tape.get('path_flags', []) for flag in value.split('|') if flag)
                    saved = {'candidates': len(frame), 'unit_tapes': len(tape),
                        'entry_status': audit.entry_status.value_counts().to_dict(),
                        'path_flags': dict(flags), 'files_sha256': hashes}
                    atomic_json(marker, saved)
                state['shards'].append({'date': str(day.date()), 'side': side, **saved})
            state['completed_dates'] += 1
            atomic_json(output/'progress.json', state)
            LOG.info('Tapes %d/%d dates; %s', state['completed_dates'], len(days), day.date())
        state['status'] = 'COMPLETED'
        overlaps = {}
        for side in sides:
            all_tapes = pd.concat([pd.read_parquet(output/f'{pd.Timestamp(day):%Y%m%d}-{side}'/'signals.parquet')
                                  for day in days], ignore_index=True)
            if all_tapes.empty:
                overlaps[side] = 0
                continue
            overlapping = 0
            for _, group in all_tapes.groupby('symbol'):
                latest_exit = pd.Timestamp.min
                for row in group.sort_values('execution_date').to_dict('records'):
                    if pd.Timestamp(row['execution_date']) <= latest_exit:
                        overlapping += 1
                    end = row.get('replay_exit_date')
                    latest_exit = max(latest_exit, pd.Timestamp(end) if pd.notna(end) else calendar[-1])
            overlaps[side] = overlapping
        blockers = ['PORTFOLIO_APPROVAL_AND_STATEFUL_QUANTITIES_NOT_ASSEMBLED',
                    'HISTORICAL_TRADABILITY_SECTOR_AND_SCORE_LINEAGE_NOT_CERTIFIED',
                    'SHORT_BORROW_NOT_CERTIFIED', 'ACTUAL_PATH_FLAGS_REQUIRE_REVIEW',
                    'TERMINAL_LIQUIDATION_NOT_TAPED']
        summary = {'status': 'PRE_PORTFOLIO_TAPES_ASSEMBLED_NOT_ECONOMICALLY_CERTIFIED',
            'completed_dates': len(days), 'full_period': max_dates is None,
            'candidates_by_side': {side: sum(x['candidates'] for x in state['shards'] if x['side'] == side) for side in sides},
            'unit_tapes_by_side': {side: sum(x['unit_tapes'] for x in state['shards'] if x['side'] == side) for side in sides},
            'entry_status': dict(sum((Counter(x['entry_status']) for x in state['shards']), Counter())),
            'path_flags': dict(sum((Counter(x['path_flags']) for x in state['shards']), Counter())),
            'same_symbol_unit_paths_overlapping_by_side': overlaps,
            'blockers': blockers, 'economic_comparison': False, 'database_writes': False,
            'policy_memberships': {p: int(candidates[p].sum()) for p in ('ORACLE_TOP20', 'ORACLE_TOP10', 'INTERSECTION_ORACLE_TOP10')},
            'redundant_control': bool(candidates.ORACLE_TOP10.equals(candidates.INTERSECTION_ORACLE_TOP10))}
        atomic_json(output/'report.json', summary)
        atomic_json(output/'progress.json', state)
        return summary
    except Exception as exc:
        state.update(status='FAILED', error=f'{type(exc).__name__}: {exc}')
        atomic_json(output/'progress.json', state)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='artifacts/research/us_concentrated_replay/prepare-20261006-v1')
    parser.add_argument('--contract', default='artifacts/research/us_concentrated_replay/contract-validation-20261006-v3')
    parser.add_argument('--output', required=True)
    parser.add_argument('--sides', default='buy,sell')
    parser.add_argument('--max-dates', type=int)
    args = parser.parse_args()
    sides = tuple(args.sides.split(','))
    if not sides or any(side not in ('buy', 'sell') for side in sides) or len(set(sides)) != len(sides):
        parser.error('--sides must be buy,sell, buy or sell')
    if args.max_dates is not None and args.max_dates <= 0:
        parser.error('--max-dates must be positive')
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(run(args.source, args.contract, args.output, sides, args.max_dates), default=str))


if __name__ == '__main__':
    main()
