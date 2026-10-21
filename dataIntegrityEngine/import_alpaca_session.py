"""Exact-session SIP import for scheduled US Pipeline step 1 (no orders)."""
from datetime import UTC, date, datetime, timedelta
import argparse
import json
import logging
import math
import time
from zoneinfo import ZoneInfo

from sqlalchemy import text

from common.config_loader import load_config
from common.universe_files import load_universe_file_symbols
from core.run_summary import attach_schema_version
from database.connection import SessionLocal, get_sqlalchemy_engine
from dataIntegrityEngine.bar_importer_common import normalize_symbols, resolve_bars_provider
from dataIntegrityEngine.backfill_alpaca_history import convert
from dataIntegrityEngine.eodhd.readiness import calendar_us, target_coverage
from dataIntegrityEngine.import_eodhd_bar import (
    _get_latest_bar_dates, _upsert_stock_bars, _upsert_stock_bars_daily,
)
from service.alpaca.clientAlpaca import DEFAULT_HISTORY_YEARS
from service.alpaca.daily_history import DailyHistoryBlocked, fetch_daily_history

LOGGER = logging.getLogger(__name__)


def convert_session_window(symbol, bars, start, day):
    """Isolate invalid *older* observations, never relax the target-day gate.

    B3's all-or-nothing converter is unchanged. A zero-volume stale observation
    in J-7/J must not discard otherwise valid dates or the new observation J.
    Duplicate dates and ambiguous timestamps remain blocking for the symbol.
    """
    try:
        daily, raw = convert(symbol, bars, 'sip', start, str(day))
        return daily, raw, []
    except ValueError:
        qualified = []; rejected = []; seen = set()
        for bar in bars:
            stamp = datetime.fromisoformat(str(bar['t']).replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                raise ValueError('Missing daily timestamp timezone')
            bar_day = stamp.astimezone(ZoneInfo('America/New_York')).date()
            if bar_day in seen:
                raise ValueError('Duplicate daily date')
            seen.add(bar_day)
            try:
                convert(symbol, [bar], 'sip', start, str(day))
                qualified.append(bar)
            except ValueError as exc:
                if bar_day >= day:
                    raise  # Never salvage an invalid target or future bar.
                rejected.append(dict(symbol=symbol, date=str(bar_day),
                                     reason=str(exc)[:200]))
        if not rejected:
            raise
        daily, raw = convert(symbol, qualified, 'sip', start, str(day))
        return daily, raw, rejected


def ready_at(day, *, calendar=None):
    calendar = calendar or calendar_us()
    if day not in calendar.session_dates(day, day):
        raise ValueError(f'Date hors séance US : {day}')
    return calendar.session_bounds(day)[1] + timedelta(minutes=20)


def await_session(day, *, wait=False, now_fn=None, sleep_fn=None, calendar=None):
    now_fn = now_fn or (lambda: datetime.now(UTC))
    sleep_fn = sleep_fn or time.sleep
    ready = ready_at(day, calendar=calendar)
    now = now_fn()
    if now.tzinfo is None:
        raise ValueError('Horodatage timezone-aware requis')
    if ready - now > timedelta(hours=24):
        raise ValueError('Date cible future : attente limitée à 24 heures')
    while now < ready:
        if not wait:
            raise ValueError('Attendre clôture US + 20 minutes pour le SIP historique')
        LOGGER.info('Attente SIP séance=%s prête=%s reste=%.0fs', day, ready, (ready-now).total_seconds())
        sleep_fn(min(60, (ready-now).total_seconds()))
        now = now_fn()
    return ready


def run(*, target_date, symbols, benchmark='SPY', minimum=.95, wait=False,
        account_id='default', config=None, now_fn=None, sleep_fn=None,
        calendar=None, session=None, engine=None):
    config = load_config() if config is None else config
    if resolve_bars_provider(config) != 'alpaca':
        raise ValueError('Import quotidien Alpaca requis mais fournisseur configuré différent')
    if not math.isfinite(minimum) or not 0 < minimum <= 1:
        raise ValueError('Couverture minimale attendue dans ]0,1]')
    universe = normalize_symbols(symbols)
    benchmark = benchmark.strip().upper()
    if not universe or not benchmark:
        raise ValueError('Univers explicite et benchmark non vides requis')
    day = date.fromisoformat(str(target_date))
    await_session(day, wait=wait, now_fn=now_fn, sleep_fn=sleep_fn, calendar=calendar)
    own = session is None
    db = session if session is not None else SessionLocal()
    summary = dict(provider='alpaca', feed='sip', target_date=str(day), mode='write',
        targeted_symbols=len(set(universe) | {benchmark}), universe_symbols=len(universe),
        successful_symbols=0, failed_symbols=0,
        inserted_bars=0, rows_upserted_stock_bars=0, rows_upserted_stock_bars_daily=0,
        errors=0, symbol_errors=[], symbol_failures=[], rejected_history_bars=[], status='RUNNING')
    failed = set()
    try:
        if db.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
            raise ValueError('US database alpha_trade required')
        imports = list(dict.fromkeys([*universe, benchmark]))
        latest = _get_latest_bar_dates(db, imports)
        for index, symbol in enumerate(imports, 1):
            # Refresh seven calendar days even when J exists. Catch up older
            # histories from their last date; first import keeps legacy depth.
            last = latest.get(symbol)
            start = min(day-timedelta(days=7), last) if last else day-timedelta(days=365*DEFAULT_HISTORY_YEARS)
            try:
                bars = fetch_daily_history(symbol, start=start.isoformat(), end=str(day),
                                           feed='sip', account_id=account_id)
                daily, raw, rejected = convert_session_window(symbol, bars, start.isoformat(), day)
                if not any(row['date'] == day for row in daily):
                    failed.add(symbol)
                n_daily = _upsert_stock_bars_daily(db, daily)
                n_raw = _upsert_stock_bars(db, raw)
                db.commit()  # No bookmark: repeating uses the same canonical keys.
                summary['rejected_history_bars'].extend(rejected)
                if rejected:
                    LOGGER.warning('SIP %s : %d anciennes barres invalides isolées, contrôle J inchangé', symbol, len(rejected))
                if symbol in failed:
                    available = [str(row['date']) for row in daily]
                    summary['symbol_failures'].append(dict(symbol=symbol, reason='NO_TARGET_BAR',
                        target_date=str(day), received_rows=len(bars),
                        latest_qualified_provider_date=max(available) if available else None))
                summary['rows_upserted_stock_bars_daily'] += n_daily
                summary['rows_upserted_stock_bars'] += n_raw
                summary['inserted_bars'] += n_raw
                if symbol not in failed:
                    summary['successful_symbols'] += 1
            except Exception as exc:
                db.rollback()
                failed.add(symbol)
                error = dict(symbol=symbol, error_type=type(exc).__name__)
                # ValueError messages are local validation reasons, never HTTP
                # URLs/credentials. Other exceptions expose only their type.
                if isinstance(exc, ValueError):
                    error['validation_reason'] = str(exc)[:200]
                summary['symbol_errors'].append(error)
                summary['symbol_failures'].append(dict(**error,
                    reason='RIGHTS_OR_QUOTA' if isinstance(exc, DailyHistoryBlocked) else 'IMPORT_ERROR'))
                LOGGER.error('SIP import %s failed: %s', symbol, type(exc).__name__)
                if isinstance(exc, DailyHistoryBlocked):
                    summary['stopped_reason'] = 'account_rights_or_quota'
                    summary['errors'] += 1
                    break  # No IEX/EODHD fallback, no repeated authorization failures.
            LOGGER.info('SIP séance=%s %d/%d %s lignes=%d échecs=%d',
                        day, index, len(imports), symbol, summary['inserted_bars'], len(failed))
        summary['failed_symbols'] = len(failed)
        summary['failed_symbol_list'] = sorted(failed)
        summary['warning_count'] = len(failed | {r['symbol'] for r in summary['rejected_history_bars']})
        attempted = set(imports[:index])
        summary['attempted_symbols'] = len(attempted)
        summary['pending_symbol_list'] = sorted(set(imports) - attempted)
        summary['pending_symbols'] = len(summary['pending_symbol_list'])
        try:
            gate = target_coverage(engine if engine is not None else get_sqlalchemy_engine(),
                universe, str(day), benchmark=benchmark, minimum=minimum,
                required_source='alpaca_sip', excluded_symbols=failed, require_raw=True)
            summary['target_coverage'] = gate
            if gate['status'] != 'PASSED':
                summary['errors'] += 1
                summary.setdefault('stopped_reason', 'target_date_coverage_insufficient')
                summary['error_message'] = (f"Cours SIP {day} insuffisants : {gate['covered']}/{gate['requested']} "
                    f"({gate['coverage_ratio']:.1%}), minimum={minimum:.1%}, "
                    f"benchmark {benchmark} disponible={gate['benchmark_available']}")
        except Exception as exc:
            summary['errors'] += 1
            summary.setdefault('stopped_reason', 'target_date_coverage_check_failed')
            summary['error_message'] = f'Contrôle des cours J impossible : {type(exc).__name__}'
        summary['status'] = 'FAILED' if summary['errors'] else 'COMPLETED'
        return summary
    finally:
        if own:
            db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--target-date', required=True)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument('--symbol-source')
    scope.add_argument('--symbols', nargs='+')
    parser.add_argument('--wait-for-publication', action='store_true')
    parser.add_argument('--require-target-coverage', action='store_true')
    parser.add_argument('--min-target-coverage', type=float, default=.95)
    parser.add_argument('--benchmark-symbol', default='SPY')
    parser.add_argument('--account', default='default')
    args = parser.parse_args(argv)
    if not args.write or not args.require_target_coverage:
        raise ValueError('Import de séance : --write et --require-target-coverage obligatoires')
    logging.basicConfig(level=logging.INFO, stream=__import__('sys').stdout)
    symbols = load_universe_file_symbols(args.symbol_source) if args.symbol_source else args.symbols
    result = run(target_date=args.target_date, symbols=symbols, benchmark=args.benchmark_symbol,
        minimum=args.min_target_coverage, wait=args.wait_for_publication, account_id=args.account)
    print('::alpha_trade_run_summary::'+json.dumps(attach_schema_version(result), default=str), flush=True)
    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
