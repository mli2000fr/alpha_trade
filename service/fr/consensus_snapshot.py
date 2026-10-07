"""Bounded prospective Yahoo consensus POC; file quarantine, never SQL or serving."""
from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import ssl
import tempfile
import time
import uuid
from importlib.metadata import version, PackageNotFoundError
from zoneinfo import ZoneInfo

from service.inpi.files import atomic

FIELDS = ('numberOfAnalystOpinions', 'recommendationMean', 'recommendationKey',
          'targetLowPrice', 'targetMeanPrice', 'targetMedianPrice', 'targetHighPrice')
METHODS = ('get_earnings_estimate', 'get_revenue_estimate', 'get_eps_trend')
EXTRA_METHODS = ('get_eps_revisions', 'get_recommendations', 'get_upgrades_downgrades')
ARCHIVE_VERSION = 'fr-consensus-v2'
IDENTITY_FIELDS = ('symbol', 'shortName', 'longName', 'quoteType', 'currency', 'exchange', 'website')


def library_version():
    try:
        return version('yfinance')
    except PackageNotFoundError:
        return 'UNAVAILABLE'


def archive_endpoint(root, symbol, method, value, metadata, reference):
    """Keep successful responses even if a subsequent endpoint pauses the run."""
    content = json.dumps(clean(value), sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    digest = hashlib.sha256(content).hexdigest()
    folder = root/'endpoints'  # Short root keeps atomic temporary paths within Windows limits.
    obj = folder/'objects'/f'{digest}.json'
    if not obj.exists():
        atomic(obj, clean(value))
    if hashlib.sha256(obj.read_bytes()).hexdigest() != digest:
        raise ValueError('Archive endpoint corrompue')
    atomic(folder/'observations'/symbol/f'{uuid.uuid4().hex[:12]}.json',
           {'symbol': symbol, 'endpoint': method, 'source_sha256': digest, 'object_path': str(obj),
            'endpoint_observation': metadata, 'available_at': metadata.get('received_at', metadata.get('finished_at')),
            'reference_identity': reference, 'archive_version': ARCHIVE_VERSION,
            'yfinance_version': library_version(), 'ml_eligible': False})


class CollectionPause(RuntimeError):
    """Budget or provider limitation; keep partial checkpoints, never swallow."""


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if hasattr(value, 'item'):
        return clean(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def has_value(value):
    if isinstance(value, dict):
        return any(has_value(v) for v in value.values())
    if isinstance(value, list):
        return any(has_value(v) for v in value)
    return value is not None and value != ''


def numeric_field(value, field):
    if not isinstance(value, dict):
        return False
    if field in value:
        cell = value[field]
        if isinstance(cell, dict):
            return any(type(v) in (int, float) and math.isfinite(v) for v in cell.values())
        return type(cell) in (int, float) and math.isfinite(cell)
    return any(numeric_field(v, field) for v in value.values())


def collect(cfg, result, *, root, identities, dry_run=False, max_symbols=None,
            ticker_factory=None, sleep=time.sleep):
    if cfg.get('universe_mode') == 'all_verified_active':
        from service.fr.consensus_daily import collect_daily
        return collect_daily(cfg, result, root=root, identities=identities,
                             dry_run=dry_run, max_symbols=max_symbols,
                             ticker_factory=ticker_factory, sleep=sleep)
    extras = cfg.get('archive_extra_methods', [])
    if not isinstance(extras, list) or len(extras) != len(set(extras)) or any(m not in EXTRA_METHODS for m in extras):
        raise ValueError('Endpoints additionnels consensus non autorisés')
    limit = int(cfg.get('max_symbols_per_run', 3))
    pace = float(cfg.get('request_interval_seconds', 1))
    if not 1 <= limit <= 10 or not math.isfinite(pace) or pace < 1:
        raise ValueError('POC limité à 1..10 titres, intervalle >=1 seconde')
    symbols = cfg.get('pilot_symbols')
    if not isinstance(symbols, list) or not symbols or len(set(symbols)) != len(symbols):
        raise ValueError('Liste pilote explicite unique requise')
    if max_symbols is not None:
        if not 1 <= max_symbols <= limit:
            raise ValueError('max_symbols dépasse le budget pilote')
        symbols = symbols[:max_symbols]
    if len(symbols) > limit:
        raise ValueError('Liste au-delà du budget pilote')
    with gzip.open(identities, 'rt', encoding='utf-8') as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    selected = {}
    for symbol in symbols:
        matches = [r for r in rows if r.get('provider_symbol') == symbol
                   and r.get('identity_state') == 'VERIFIED_RESEARCH'
                   and r.get('provider_status_current') == 'active']
        if not isinstance(symbol, str) or not symbol.endswith('.PA') or len(matches) != 1:
            raise ValueError('Titre pilote FR actif unique non vérifié')
        selected[symbol] = matches[0]
    result.update(requested_count=len(symbols), errors=[], coverage={},
                  sql_writes=False, historical_pit=False, identity_qualified=False,
                  universe_sha256=hashlib.sha256(identities.read_bytes()).hexdigest())
    if dry_run:
        return
    if ticker_factory is None:
        from service.yahoo.clientYahooFinance import _import_yfinance
        from service.fr.yahoo_price_reference_pilot import verified_tls_context
        from curl_cffi.requests import Session
        # curl_cffi does not consume Python's SSLContext. Export the same trusted
        # roots to a temporary bundle; verification and hostname checks stay on.
        with tempfile.TemporaryDirectory(prefix='fr-consensus-ca-') as temporary:
            bundle = Path(temporary)/'roots.pem'
            bundle.write_text(''.join(ssl.DER_cert_to_PEM_cert(c)
                                     for c in verified_tls_context().get_ca_certs(binary_form=True)), encoding='ascii')
            with Session(impersonate='chrome', verify=str(bundle), timeout=30) as session:
                return collect(cfg, result, root=root, identities=identities,
                               max_symbols=max_symbols,
                               ticker_factory=lambda s: _import_yfinance().Ticker(s, session=session), sleep=sleep)
    for symbol in symbols:
        try:
            ticker = ticker_factory(symbol)
            endpoint_times = {}
            started = datetime.now(UTC).isoformat()
            info = ticker.get_info()
            endpoint_times['get_info'] = {'started_at': started, 'received_at': datetime.now(UTC).isoformat(), 'status': 'RECEIVED'}
            if not isinstance(info, dict) or info.get('symbol') != symbol or info.get('currency') != 'EUR' or info.get('exchange') not in ('PAR', 'EPA'):
                raise ValueError('Identité Yahoo/EUR/Paris absente ou contradictoire')
            rule = (cfg.get('identity_checks') or {}).get(symbol)
            if rule:
                review_day = date.fromisoformat(str(rule['reviewed_on']))
                age = (datetime.now(ZoneInfo('Europe/Paris')).date() - review_day).days
                if (selected[symbol].get('isin') != rule.get('isin')
                    or info.get('longName') != rule.get('yahoo_long_name')
                    or info.get('quoteType') != 'EQUITY' or not 0 <= age <= 30):
                    raise ValueError('Identité pilote révisée contradictoire ou revue expirée')
            payload = {'info': {k: info.get(k) for k in FIELDS},
                       'yahoo_identity': {k: info.get(k) for k in IDENTITY_FIELDS},
                       'raw_info': clean(info), 'tables': {}}
            archive_endpoint(root, symbol, 'get_info', info, endpoint_times['get_info'], selected[symbol])
            warnings = []
            for method in (*METHODS, *extras):
                sleep(pace)
                started = datetime.now(UTC).isoformat()
                try:
                    table = clean(getattr(ticker, method)(as_dict=True))
                    if not isinstance(table, dict):
                        raise ValueError('Format de tableau inattendu')
                    payload['tables'][method] = table
                    endpoint_times[method] = {'started_at': started, 'received_at': datetime.now(UTC).isoformat(), 'status': 'RECEIVED'}
                    if not has_value(table):
                        warnings.append(method + ':EMPTY_OR_UNAVAILABLE')
                except CollectionPause:
                    raise
                except Exception as exc:
                    payload['tables'][method] = None
                    endpoint_times[method] = {'started_at': started, 'finished_at': datetime.now(UTC).isoformat(), 'status': 'ERROR', 'error_type': type(exc).__name__}
                    warnings.append(method + ':' + type(exc).__name__)
                else:
                    # Persistence failure is blocking, not downgraded to a provider warning.
                    archive_endpoint(root, symbol, method, table, endpoint_times[method], selected[symbol])
            payload = clean(payload)
            coverage = {'price_targets': any(type(payload['info'].get(k)) in (int, float) and payload['info'][k] > 0 for k in FIELDS if k.startswith('target')),
                        'recommendations': type(payload['info'].get('numberOfAnalystOpinions')) in (int, float) and payload['info']['numberOfAnalystOpinions'] > 0,
                        **{m: numeric_field(payload['tables'][m], 'current' if m == 'get_eps_trend' else 'avg') for m in METHODS}}
            result['coverage'][symbol] = coverage
            if not any(coverage.values()):
                raise ValueError('Aucune donnée consensus disponible')
            observed = datetime.now(UTC).isoformat()
            content = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
            digest = hashlib.sha256(content).hexdigest()
            target = root/'objects'/f'{digest}.json'
            if not target.exists():
                atomic(target, payload)
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError('Archive consensus corrompue')
            record = {'symbol': symbol, 'reference_identity': selected[symbol],
                      'source': 'Yahoo Finance via yfinance', 'source_sha256': digest,
                      'object_path': str(target), 'observed_at': observed, 'available_at': observed,
                      'state': 'QUARANTINED_UNQUALIFIED', 'historical_pit': False,
                      'identity_qualified': bool(rule), 'identity_scope': 'CURRENT_PILOT_MAPPING_ONLY',
                      'identity_review': rule, 'ml_eligible': False,
                      'archive_version': ARCHIVE_VERSION, 'yfinance_version': library_version(),
                      'endpoint_observations': endpoint_times,
                      'fiscal_period_state': 'UNQUALIFIED_PROVIDER_LABELS',
                      'unit_state': 'UNQUALIFIED_PROVIDER_VALUES',
                      'coverage': coverage, 'warnings': warnings}
            atomic(root/'observations'/symbol/f'{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}-{uuid.uuid4().hex[:8]}.json', record)
            result['received_count'] += 1
            result['persisted_count'] += 1
            result['warning_count'] += len(warnings)
            result.setdefault('identity_checks', {})[symbol] = bool(rule)
        except CollectionPause:
            raise
        except Exception as exc:
            result['failed_count'] += 1
            result['errors'].append({'symbol': symbol, 'error': type(exc).__name__ + ': ' + str(exc)[:200] if isinstance(exc, ValueError) else type(exc).__name__})
        sleep(pace)
    result['identity_qualified'] = (result['failed_count'] == 0
                                   and len(result.get('identity_checks', {})) == len(symbols)
                                   and all(result.get('identity_checks', {}).values()))
    if result['failed_count']:
        raise RuntimeError('POC consensus incomplet ; consulter errors et coverage')


def main():
    from service.fr.operational_batch_15a import ROOT, OPS, load_section
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--not-before', type=date.fromisoformat,
                        help='Interdire une collecte avant cette date Europe/Paris')
    args = parser.parse_args()
    if args.not_before and datetime.now(ZoneInfo('Europe/Paris')).date() < args.not_before:
        print(json.dumps({'status': 'NOT_DUE', 'not_before': str(args.not_before)}))
        return
    cfg = load_section('fr_consensus_snapshot', ROOT/'batch_fr.yaml')
    if cfg.get('universe_mode') == 'all_verified_active':
        # Manual CLI must share scheduled checkpoints, locks and run records.
        from service.fr.operational_batch_15a import run
        output = run('fr_consensus_snapshot', dry_run=args.dry_run)
        print(json.dumps(output, ensure_ascii=False))
        if output['status'] == 'FAILED':
            raise SystemExit(1)
        return
    result = dict(requested_count=0, received_count=0, persisted_count=0, failed_count=0, warning_count=0)
    folder = OPS/'fr_consensus_snapshot'/'poc'/f'{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}'
    lock = OPS/'fr_consensus_snapshot'/'.lock'
    locked = False
    try:
        if not args.dry_run:
            lock.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, 'w') as stream:
                stream.write(str(os.getpid()))
            locked = True
        collect(cfg, result, root=folder, identities=ROOT/cfg['identities_file'], dry_run=args.dry_run)
        result['status'] = 'DRY_RUN' if args.dry_run else 'SUCCESS_RESEARCH_ONLY'
    except Exception as exc:
        result.update(status='FAILED', failed_count=max(1, result['failed_count']), error_message=str(exc))
    finally:
        if locked:
            lock.unlink(missing_ok=True)
    if not args.dry_run:
        atomic(folder/'report.json', result)
    print(json.dumps(result, ensure_ascii=False))
    if result['status'] == 'FAILED':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
