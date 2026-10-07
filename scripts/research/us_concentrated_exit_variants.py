"""Frozen LONG exit experiment: chronological unit tapes, no portfolio PnL/SQL.

Research-only correction of gap chronology; original pipeline tapes are immutable.
Twenty sessions AFTER entry means calendar[entry_index + 20].
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.microstructure import resolve_intrabar_exit
from scripts.research.us_concentrated_historical_tapes import (
    atomic_json, apply_overlay, digest, verify_hashes,
)

VARIANTS = {
    'CURRENT_NO_EXPIRY': {'tp': True, 'trailing': True, 'holding_sessions': None},
    'REFERENCE_20_AFTER_ENTRY': {'tp': True, 'trailing': True, 'holding_sessions': 20},
    'NO_TP_FIXED_SL_20_AFTER_ENTRY': {'tp': False, 'trailing': False, 'holding_sessions': 20},
    'NO_TP_TRAILING_20_AFTER_ENTRY': {'tp': False, 'trailing': True, 'holding_sessions': 20},
}
LOG = logging.getLogger(__name__)


def resolve_long_path(signal, days, data, variant):
    """Chronological daily OHLC hypothesis, not actual broker execution evidence.

    Prior stops execute at open if gapped through; favourable TP gaps execute
    at limit conservatively. Open precedes intraday ambiguities on held positions.
    Watcher transitions are emitted only while the position is alive.
    """
    cfg = VARIANTS[variant]
    entry = pd.Timestamp(signal['execution_date'])
    start = days.get_indexer([entry])[0]
    if start < 0:
        raise ValueError('Entry absent from calendar')
    if signal['side'] != 'buy':
        raise ValueError('Frozen experiment is LONG only')
    fill, stop, tp, trail = [float(signal[k]) for k in (
        'fill_price', 'replay_initial_stop_price', 'replay_take_profit_price', 'replay_trailing_stop_pct')]
    if not (0 < stop < fill < tp) or not (0 < trail < 1):
        raise ValueError('Invalid frozen protection')
    expiry_idx = start + cfg['holding_sessions'] if cfg['holding_sessions'] else None
    last = min(expiry_idx, len(days)-1) if expiry_idx is not None else len(days)-1
    expiry_day = days[expiry_idx] if expiry_idx is not None and expiry_idx < len(days) else pd.NaT
    activation = float(signal['replay_trailing_activation_price']) if cfg['trailing'] else None
    if activation is not None and (not np.isfinite(activation) or activation <= 0):
        raise ValueError('Invalid watcher activation price')
    active_from = None
    peak = fill
    events = [{'date': str(entry.date()), 'type': 'ENTRY_UNIT', 'price': fill}]
    flags = set()
    identity = None
    last_close = None

    def finish(status, idx, price=None, reason=None):
        if price is not None:
            events.append({'date': str(days[idx].date()), 'type': 'EXIT', 'reason': reason, 'price': float(price)})
            events.append({'date': str(days[idx].date()), 'type': 'CANCEL_REMAINING_PROTECTIONS_AND_WATCHER'})
        return {'variant': variant, 'status': status,
            'exit_date': days[idx] if price is not None else pd.NaT,
            'exit_price': float(price) if price is not None else None, 'exit_reason': reason,
            'scheduled_exit_date': expiry_day,
            'watcher_effective_date': days[active_from] if active_from is not None and active_from <= idx else pd.NaT,
            'path_flags': '|'.join(sorted(flags)), 'events_json': json.dumps(events),
            'quantity_scope': 'ONE_UNIT_NOT_PORTFOLIO_APPROVED', 'economic_comparison': False}

    # data columns: open, high, low, close, volume, is_filled, instrument_id
    for idx in range(start, last+1):
        opening, high, low, close, volume, filled, instrument = data[idx]
        if not np.isfinite([opening, high, low, close]).all() or min(opening, low, close) <= 0:
            flags.add('MISSING_OR_INVALID_OHLC')
            return finish('BLOCKED_PRICE_PATH', idx)
        if not (low <= min(opening, close) <= max(opening, close) <= high):
            flags.add('INCONSISTENT_OHLC')
            return finish('BLOCKED_PRICE_PATH', idx)
        if not np.isfinite(volume) or volume <= 0 or filled != 0:
            flags.add('ZERO_VOLUME_OR_FILLED_BAR')
            return finish('BLOCKED_PRICE_PATH', idx)
        if np.isfinite(instrument):
            if identity is not None and identity != instrument:
                flags.add('IDENTITY_CHANGE')
                return finish('BLOCKED_PRICE_PATH', idx)
            identity = instrument
        if last_close is not None and abs(close / last_close - 1) >= .5:
            flags.add('JUMP_GE50_REVIEW_NOT_AUTOMATIC_ERROR')
        if active_from == idx:
            events.append({'date': str(days[idx].date()), 'type': 'TRAILING_ACTIVE_INITIAL_STOP_CANCELLED'})
        trailing_active = active_from is not None and idx >= active_from
        active_stop = peak * (1-trail) if trailing_active else stop
        stop_reason = 'trailing_stop' if trailing_active else 'initial_stop'
        if idx > start:
            if opening <= active_stop:
                return finish('RESOLVED', idx, opening, stop_reason + '_gap_open')
            if cfg['tp'] and opening >= tp:
                # A limit order does not require inventing favourable open improvement.
                return finish('RESOLVED', idx, tp, 'take_profit_gap_limit')
        resolution = resolve_intrabar_exit(day_high=high, day_low=low,
            take_profit_price=tp if cfg['tp'] else float('inf'),
            trailing_stop_price=active_stop if trailing_active else float('-inf'),
            initial_stop_price=None if trailing_active else stop,
            priority='conservative', side='buy', rng=None)
        if resolution.triggered:
            return finish('RESOLVED', idx, resolution.exit_price, resolution.exit_reason)
        # Fixed expiry is a pre-scheduled close order; no future close-trigger decision.
        if expiry_idx is not None and idx == expiry_idx:
            return finish('RESOLVED', idx, close, 'expiry_20_sessions_after_entry_close')
        if idx == len(days)-1:
            flags.add('TERMINAL_OBSERVATION_BOUNDARY')
            if expiry_idx is not None and expiry_idx >= len(days):
                flags.add('HOLDING_WINDOW_CENSORED')
            return finish('RESOLVED_TERMINAL_HYPOTHESIS', idx, close, 'terminal_close_hypothesis')
        # No posthumous activation or watcher event after an intraday exit.
        if cfg['trailing'] and active_from is None and high >= activation:
            active_from = idx+1
            events.append({'date': str(days[idx].date()), 'type': 'WATCHER_TRIGGER_NEXT_SESSION'})
        peak = max(peak, high)
        last_close = close
    raise AssertionError('Path did not terminate')


def run(source, archive, contract, output, max_dates=None):
    source, archive, contract, output = map(Path, (source, archive, contract, output))
    output.mkdir(parents=True, exist_ok=True)
    source_report = json.loads((source/'report.json').read_text())
    if source_report['completed_dates'] != 437 or not source_report['full_period']:
        raise ValueError('Historical assembly is incomplete')
    archive_report = json.loads((archive/'report.json').read_text())
    verify_hashes(archive, archive_report['files_sha256'])
    certificate = json.loads((contract/'report.json').read_text())
    verify_hashes(Path('.'), certificate['source_hashes'])
    verify_hashes(contract, {'band_volume_overlay.parquet': certificate['band_overlay_sha256']})
    protocol = {'experiment': 'US_FROZEN_LONG_EXIT_VARIANTS_20_AFTER_ENTRY_V1',
        'variants': VARIANTS, 'side': 'buy', 'horizon_convention': 'entry_calendar_index_plus_20_close',
        'gap_stop': 'raw_open_if_through_stop', 'gap_tp': 'limit_price_no_favourable_improvement',
        'intrabar': 'conservative_stop_first_after_open',
        'terminal': 'explicit_close_hypothesis_with_censor_flag_not_free_real_execution',
        'source_report_sha256': digest(source/'report.json'),
        'source_manifest_sha256': digest(source/'manifest.json'),
        'archive_report_sha256': digest(archive/'report.json'),
        'contract_report_sha256': digest(contract/'report.json'),
        'assembler_sha256': digest(__file__), 'max_dates': max_dates,
        'database_writes': False, 'training': False, 'economic_comparison': False,
        'qualification': 'RESEARCH_UNIT_PATHS_NOT_PORTFOLIO_OR_PRODUCTION_CERTIFICATION'}
    if (output/'protocol.json').exists() and json.loads((output/'protocol.json').read_text()) != protocol:
        raise ValueError('Resume protocol mismatch; choose another output directory')
    atomic_json(output/'protocol.json', protocol)
    bars = pd.concat([pd.read_parquet(archive/name) for name in archive_report['files_sha256'] if name.startswith('bars-')])
    bars['date'] = pd.to_datetime(bars.date)
    bars = apply_overlay(bars, pd.read_parquet(contract/'band_volume_overlay.parquet'))
    days = pd.DatetimeIndex(bars.loc[bars.symbol.eq('SPY') & bars.volume.gt(0) & bars.is_filled.eq(0), 'date']).sort_values()
    columns = ['open', 'high', 'low', 'close', 'volume', 'is_filled', 'instrument_id']
    arrays = {symbol: frame.set_index('date').reindex(days)[columns].to_numpy(dtype=float)
              for symbol, frame in bars.groupby('symbol')}
    shards = [x for x in json.loads((source/'progress.json').read_text())['shards'] if x['side'] == 'buy'][:max_dates]
    state = {'status': 'RUNNING', 'planned_dates': len(shards), 'completed_dates': 0, 'shards': []}
    atomic_json(output/'progress.json', state)
    try:
        for shard in shards:
            day = shard['date'].replace('-', '')
            target = output/day
            target.mkdir(exist_ok=True)
            marker = target/'report.json'
            if marker.exists():
                summary = json.loads(marker.read_text())
                verify_hashes(target, summary['files_sha256'])
            else:
                original = source/f'{day}-buy'
                verify_hashes(original, shard['files_sha256'])
                signals = pd.read_parquet(original/'signals.parquet')
                rows = []
                comparison = Counter()
                for signal in signals.to_dict('records'):
                    allowed = ('execution_date', 'side', 'fill_price', 'replay_initial_stop_price',
                        'replay_take_profit_price', 'replay_trailing_stop_pct', 'replay_trailing_activation_price')
                    resolver_signal = {key: signal[key] for key in allowed}
                    for variant in VARIANTS:
                        result = resolve_long_path(resolver_signal, days, arrays[signal['symbol']], variant)
                        if variant == 'CURRENT_NO_EXPIRY':
                            old_date = signal.get('replay_exit_date')
                            new_date = result['exit_date']
                            if result['status'] == 'BLOCKED_PRICE_PATH':
                                comparison['blocked_price_path'] += 1
                            elif pd.isna(old_date):
                                comparison['old_open_now_explicit_terminal_or_corrected_exit'] += 1
                            elif pd.Timestamp(old_date) == new_date and abs(float(signal['replay_exit_price'])-result['exit_price']) <= .005:
                                comparison['same_exit_date_and_price'] += 1
                            else:
                                comparison['exit_date_or_price_changed_requires_parity_review'] += 1
                        rows.append({**{k: signal[k] for k in ('candidate_id', 'symbol', 'trade_date',
                            'execution_date', 'fill_price', 'ORACLE_TOP20', 'ORACLE_TOP10', 'INTERSECTION_ORACLE_TOP10')},
                            **result})
                result = pd.DataFrame(rows)
                file = target/'variant_tapes.parquet'
                result.to_parquet(file, index=False)
                by_variant = {}
                for variant in VARIANTS:
                    group = result[result.variant.eq(variant)] if not result.empty else result
                    by_variant[variant] = {'tapes': len(group),
                        'status': group.status.value_counts().to_dict() if not group.empty else {},
                        'exit_reason': group.exit_reason.value_counts().to_dict() if not group.empty else {}}
                summary = {'files_sha256': {file.name: digest(file)}, 'variants': by_variant,
                    'current_policy_vs_original_tape': dict(comparison)}
                atomic_json(marker, summary)
            state['completed_dates'] += 1
            state['shards'].append({'date': shard['date'], **summary})
            atomic_json(output/'progress.json', state)
            LOG.info('Variants %s/%s dates %s', state['completed_dates'], len(shards), shard['date'])
        overall = {}
        for variant in VARIANTS:
            parts = [x['variants'][variant] for x in state['shards']]
            overall[variant] = {'tapes': sum(x['tapes'] for x in parts),
                'status': dict(sum((Counter(x['status']) for x in parts), Counter())),
                'exit_reason': dict(sum((Counter(x['exit_reason']) for x in parts), Counter()))}
        report = {'status': 'EXIT_VARIANT_UNIT_TAPES_COMPLETE_NOT_ECONOMIC_REPLAY',
            'completed_dates': len(shards), 'full_period': max_dates is None, 'variants': overall,
            'current_policy_vs_original_tape': dict(sum((Counter(x['current_policy_vs_original_tape']) for x in state['shards']), Counter())),
            'blockers': ['STATEFUL_PORTFOLIO_SIZING_AND_COSTS', 'PRODUCTION_ENGINE_PARITY_FOR_NEW_EXITS',
                         'HISTORICAL_TRADABILITY_AND_CORPORATE_ACTIONS', 'SCORE_OOF_LINEAGE'],
            'economic_comparison': False, 'database_writes': False}
        atomic_json(output/'report.json', report)
        state['status'] = 'COMPLETED'
        atomic_json(output/'progress.json', state)
        return report
    except Exception as exc:
        state.update(status='FAILED', error=f'{type(exc).__name__}: {exc}')
        atomic_json(output/'progress.json', state)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='artifacts/research/us_concentrated_replay/tapes-history-20261006-v1')
    parser.add_argument('--archive', default='artifacts/research/us_concentrated_replay/prepare-20261006-v1')
    parser.add_argument('--contract', default='artifacts/research/us_concentrated_replay/contract-validation-20261006-v3')
    parser.add_argument('--output', required=True)
    parser.add_argument('--max-dates', type=int)
    args = parser.parse_args()
    if args.max_dates is not None and args.max_dates <= 0:
        parser.error('--max-dates must be positive')
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(run(**vars(args)), default=str))


if __name__ == '__main__':
    main()
