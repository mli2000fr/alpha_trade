"""EODHD current consensus snapshots; dates on records are NOT PIT vintages."""
from __future__ import annotations

import logging
import math
import time
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import text

from common.public_data_http import verified_session
from database.repositories.eodhd_consensus import TABLE, persist_rows
from service.eodhd.clientEodhd import (
    _do_request, _get_base_url, _get_token, EodhdPermissionError,
    EodhdSymbolNotFound, EodhdBarsFetchError, _redact_sensitive_text,
)
from service.eodhd.quota import get_default_tracker, EodhdQuotaExceeded, EodhdCircuitOpen
from service.eodhd.symbols import to_eodhd

LOG = logging.getLogger(__name__)
BATCH = 'eodhd_consensus_snapshot'
FIELDS = {
    'eps_avg': 'earningsEstimateAvg', 'eps_low': 'earningsEstimateLow',
    'eps_high': 'earningsEstimateHigh', 'eps_analyst_count': 'earningsEstimateNumberOfAnalysts',
    'eps_growth': 'earningsEstimateGrowth', 'eps_year_ago': 'earningsEstimateYearAgoEps',
    'revenue_avg': 'revenueEstimateAvg', 'revenue_low': 'revenueEstimateLow',
    'revenue_high': 'revenueEstimateHigh', 'revenue_analyst_count': 'revenueEstimateNumberOfAnalysts',
    'revenue_growth': 'revenueEstimateGrowth', 'revenue_year_ago': 'revenueEstimateYearAgoEps',
    'eps_current': 'epsTrendCurrent', 'eps_7d_ago': 'epsTrend7daysAgo',
    'eps_30d_ago': 'epsTrend30daysAgo', 'eps_60d_ago': 'epsTrend60daysAgo',
    'eps_90d_ago': 'epsTrend90daysAgo', 'revisions_up_7d': 'epsRevisionsUpLast7days',
    'revisions_up_30d': 'epsRevisionsUpLast30days',
    'revisions_down_7d': 'epsRevisionsDownLast7days',
    'revisions_down_30d': 'epsRevisionsDownLast30days', 'provider_growth': 'growth',
}
COUNTS = {key for key in FIELDS if 'count' in key or key.startswith('revisions_')}


def number(value, *, count=False):
    if value is None or (isinstance(value, str) and value.strip().lower() in ('', 'null', 'nan', 'n/a', '-')):
        return None
    if isinstance(value, bool):
        raise ValueError('Boolean instead of numeric consensus')
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Non-finite consensus')
    if count:
        if result < 0 or result != int(result) or result > 2147483647:
            raise ValueError('Invalid analyst/revision count')
        return int(result)
    return result


def parse(payload, symbols, observed, run_id):
    from service.forward_pit.batch import _json, _hash
    if observed.tzinfo is None:
        raise ValueError('Observation must be timezone-aware')
    if not isinstance(payload, dict) or not isinstance(payload.get('trends'), list):
        raise ValueError('Unexpected Earnings Trends schema')
    allowed = {to_eodhd(symbol): symbol for symbol in symbols}
    rows = {symbol: [] for symbol in symbols}
    identities = {}
    for group in payload['trends']:
        if not isinstance(group, list):
            raise ValueError('Unexpected trends group')
        for item in group:
            if not isinstance(item, dict) or item.get('code') not in allowed:
                raise ValueError('Unexpected consensus symbol')
            symbol = allowed[item['code']]
            period = date.fromisoformat(item['date'])
            horizon = item.get('period')
            if horizon not in ('0q', '+1q', '0y', '+1y'):
                raise ValueError('Unknown relative fiscal horizon')
            identity = (symbol, period, horizon)
            digest = _hash(item)
            if identity in identities:
                if identities[identity] != digest:
                    raise ValueError('Conflicting duplicate fiscal period')
                continue
            identities[identity] = digest
            values = {key: number(item.get(native), count=key in COUNTS) for key, native in FIELDS.items()}
            stamp = observed.astimezone(UTC).replace(tzinfo=None)
            rows[symbol].append(dict(provider='eodhd', symbol=symbol,
                snapshot_date=observed.astimezone(ZoneInfo('America/New_York')).date(),
                fiscal_period_end=period, horizon_raw=horizon, observed_at=stamp, available_at=stamp,
                run_id=run_id, currency=None, **values,
                fiscal_identity_qualified=False, units_qualified=False,
                historical_pit_qualified=False, qualification_status='RESEARCH_ONLY',
                raw_hash=digest, raw_payload_json=_json(item), parser_version='eodhd_v1'))
    return rows


def fetch(symbols, session):
    return _do_request(endpoint='calendar/trends', url=_get_base_url()+'/calendar/trends',
        params={'api_token': _get_token(), 'fmt': 'json',
                'symbols': ','.join(to_eodhd(symbol) for symbol in symbols)},
        session=session, tracker=get_default_tracker(), feature=BATCH)


def load_symbols(engine, cfg):
    from service.forward_pit.batch import _collection_symbols
    source = cfg.get('symbol_source', 'universe-file')
    if source == 'universe-file':
        return _collection_symbols(cfg)
    if source != 'stock_bars_daily':
        raise ValueError('Unknown EODHD consensus symbol_source')
    if engine is None or engine.url.database != 'alpha_trade':
        raise ValueError('stock_bars_daily universe requires alpha_trade (US)')
    with engine.connect() as conn:
        values = conn.execute(text('SELECT DISTINCT symbol FROM stock_bars_daily '
            'WHERE symbol IS NOT NULL ORDER BY symbol')).scalars().all()
    symbols = sorted({str(value).strip().upper() for value in values if str(value).strip()})
    limit = cfg.get('max_symbols')
    if limit not in (None, '', 'all', 'ALL'):
        if int(limit) <= 0:
            raise ValueError('max_symbols must be positive')
        symbols = symbols[:int(limit)]
    return symbols


def collect(engine, cfg, run_id, dry_run):
    from service.forward_pit.batch import Outcome, BatchRunError, _collection_symbols, _raw
    symbols = load_symbols(engine, cfg)
    outcome = Outcome(requested=len(symbols), details={'scope': 'RESEARCH_ONLY',
        'historical_pit': False, 'skipped_symbols': 0, 'received_rows': 0, 'api_calls': 0,
        'errors': [], 'missing_fields': {}, 'no_consensus_symbols': [], 'invalid_symbols': [],
        'units': 'symbols requested/received/empty/failed; rows persisted'})
    if not symbols:
        raise BatchRunError('Consensus universe is empty', outcome)
    size = int(cfg.get('batch_size', 20))
    pause = float(cfg.get('sleep_seconds', 1.1))
    threshold = float(cfg.get('min_coverage',0.95))
    if not 1 <= size <= 100 or pause < 0 or not 0 <= threshold <= 1:
        raise BatchRunError('Invalid consensus batch_size/sleep_seconds', outcome)
    reference_file = cfg.get('coverage_symbols_file')
    reference = set(_collection_symbols({'symbols_file':reference_file})) if reference_file else set(symbols)
    if cfg.get('max_symbols') not in (None, '', 'all', 'ALL'):
        # A bounded smoke can qualify only its explicitly sampled symbols.
        reference &= set(symbols)
    if not reference:
        raise BatchRunError('Empty consensus coverage reference universe', outcome)
    outcome.details['coverage_symbols_file'] = reference_file
    outcome.details['reference_requested'] = len(reference)
    outcome.details['reference_missing_from_collection'] = sorted(reference-set(symbols))
    covered = set()

    def update_coverage():
        outcome.details['overall_coverage'] = len(covered)/len(symbols)
        outcome.details['reference_covered'] = len(covered & reference)
        outcome.details['reference_missing'] = sorted(reference-covered)
        outcome.details['coverage'] = len(covered & reference)/len(reference)
        outcome.details['no_consensus_count'] = len(outcome.details['no_consensus_symbols'])
        outcome.details['invalid_symbol_count'] = len(outcome.details['invalid_symbols'])
    if not dry_run:
        if engine.url.database != 'alpha_trade':
            raise BatchRunError('Consensus requires alpha_trade (US)', outcome)
        try:
            with engine.connect() as conn:
                # Fail before any API call if migration is missing.
                conn.execute(text(f'SELECT id FROM {TABLE} LIMIT 0'))
        except Exception as exc:
            outcome.failed = 1
            raise BatchRunError(
                'EODHD schema unavailable; check SQL 0099 and database connection: '
                + _redact_sensitive_text(str(exc))[:500], outcome) from None
    today = datetime.now(ZoneInfo('America/New_York')).date()
    if not dry_run:
        with engine.connect() as conn:
            existing = set(conn.execute(text(f'SELECT DISTINCT symbol FROM {TABLE} '
                'WHERE provider=:provider AND snapshot_date=:day'),
                dict(provider='eodhd', day=today)).scalars())
        covered.update(existing & set(symbols))
    outcome.details['skipped_symbols'] = len(covered)
    pending = [symbol for symbol in symbols if symbol not in covered]

    def _request_group(group, session):
        outcome.details['api_calls'] += 1
        try:
            payload = fetch(group, session)
        except EodhdBarsFetchError as exc:
            # An invalid ticker must not discard an otherwise valid batch.
            invalid = not isinstance(exc, EodhdPermissionError) and (
                isinstance(exc, EodhdSymbolNotFound) or
                ('HTTP 422' in str(exc) and 'symbol' in str(exc).lower()))
            if invalid:
                if len(group)>1:
                    mid = len(group)//2
                    request_group(group[:mid], session)
                    request_group(group[mid:], session)
                else:
                    outcome.empty += 1
                    outcome.details['invalid_symbols'].append({'symbol':group[0],
                        'message':_redact_sensitive_text(str(exc))[:500]})
                # Invalid leaves must not abort the sibling subtree.
                return
            if isinstance(exc, EodhdPermissionError):
                raise
            outcome.failed += len(group)
            outcome.details['errors'].append({'symbols':group,'error_type':type(exc).__name__,
                'message':_redact_sensitive_text(str(exc))[:500]})
            return
        observed = datetime.now(UTC)
        # Archive the ENTIRE response even when normalization rejects it.
        if not dry_run:
            with engine.begin() as conn:
                _raw(conn, run_id, BATCH, 'eodhd', '/calendar/trends', ','.join(group),
                     payload, observed=observed.replace(tzinfo=None))
        by_symbol = parse(payload, group, observed, run_id)
        for symbol, rows in by_symbol.items():
            if not rows:
                outcome.empty += 1
                outcome.details['no_consensus_symbols'].append(symbol)
                continue
            if not dry_run:
                # Entire symbol/day committed together: safe daily resume.
                with engine.begin() as conn:
                    outcome.persisted += persist_rows(conn, rows)
            outcome.received += 1
            covered.add(symbol)
            outcome.details['received_rows'] += len(rows)
            for key in FIELDS:
                count = sum(row[key] is None for row in rows)
                outcome.details['missing_fields'][key] = outcome.details['missing_fields'].get(key,0)+count
            LOG.info('Consensus %s rows=%d persisted=%d', symbol, len(rows), outcome.persisted)

    def request_group(group, session):
        before = outcome.received + outcome.empty + outcome.failed
        try:
            _request_group(group, session)
        except (EodhdPermissionError, EodhdQuotaExceeded, EodhdCircuitOpen):
            raise
        except Exception as exc:
            # Local technical errors must also leave sibling subtrees runnable.
            accounted = outcome.received + outcome.empty + outcome.failed - before
            outcome.failed += len(group)-accounted
            outcome.details['errors'].append({'symbols':group,'error_type':type(exc).__name__,
                'message':_redact_sensitive_text(str(exc))[:500]})

    with verified_session() as session:
        for offset in range(0,len(pending),size):
            group = pending[offset:offset+size]
            before = outcome.received + outcome.empty + outcome.failed
            try:
                request_group(group, session)
            except (EodhdPermissionError, EodhdQuotaExceeded, EodhdCircuitOpen) as exc:
                outcome.failed += len(group)-(outcome.received+outcome.empty+outcome.failed-before)
                outcome.details['errors'].append({'symbols':group,'error_type':type(exc).__name__,
                    'message':_redact_sensitive_text(str(exc))[:500]})
                outcome.details['unprocessed_symbols'] = len(pending)-(offset+len(group))
                update_coverage()
                raise BatchRunError(_redact_sensitive_text(str(exc)),outcome) from None
            except Exception as exc:
                outcome.failed += len(group)-(outcome.received+outcome.empty+outcome.failed-before)
                outcome.details['errors'].append({'symbols':group,'error_type':type(exc).__name__,
                    'message':_redact_sensitive_text(str(exc))[:500]})
            time.sleep(pause)
    update_coverage()
    coverage = outcome.details['coverage']
    if coverage < threshold or outcome.failed:
        raise BatchRunError(f'EODHD consensus coverage={coverage:.2%}, failures={outcome.failed}; see details',outcome)
    return outcome


def main():
    """Small live-access smoke, explicitly without SQL writes."""
    import argparse
    import json
    from pathlib import Path
    from common.config_loader import load_batch_config
    from service.forward_pit.batch import BatchRunError
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', required=True)
    parser.add_argument('--max-symbols', type=int, default=2)
    parser.add_argument('--batch-config')
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    cfg = dict(load_batch_config(args.batch_config)[BATCH], max_symbols=args.max_symbols)
    root = Path(args.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    # Do not overwrite a previous access proof.
    with (root/'report.json').open('x', encoding='utf-8') as handle:
        try:
            engine = None
            if cfg.get('symbol_source') == 'stock_bars_daily':
                from database.connection import get_sqlalchemy_engine
                engine = get_sqlalchemy_engine()
            outcome = collect(engine,cfg,'eodhd-consensus-smoke',True)
            report = {'status':'DRY_RUN','checked_at':datetime.now(UTC).isoformat(), **outcome.__dict__}
        except BatchRunError as exc:
            report = {'status':'FAILED','error':str(exc), **exc.outcome.__dict__}
        json.dump(report,handle,indent=2,ensure_ascii=False,default=str)
    print(json.dumps(report,ensure_ascii=False,default=str))
    if report['status']=='FAILED':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
