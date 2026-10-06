"""Prospective whole-universe FR consensus quarantine, daily checkpoints and caps."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
import gzip
import hashlib
import html
import json
import math
from pathlib import Path
import ssl
import tempfile
import unicodedata
from zoneinfo import ZoneInfo

from service.inpi.files import atomic
from service.fr.consensus_snapshot import collect, CollectionPause, METHODS, EXTRA_METHODS
from service.fr.sprint5_subset_audit import valid_isin


def normal_name(value):
    text = html.unescape(str(value or ''))
    text = ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c)).upper()
    # Exact company names only, punctuation and legal suffixes ignored; no fuzzy match.
    words = ''.join(c if c.isalnum() else ' ' for c in text).split()
    while words and words[-1] in ('SA', 'SE', 'PLC', 'NV'):
        words.pop()
    return ''.join(words)


def reference_scope(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    groups, isin_groups = defaultdict(list), defaultdict(set)
    excluded = []
    for row in rows:
        symbol = row.get('provider_symbol')
        if row.get('identity_state') != 'VERIFIED_RESEARCH' or row.get('provider_status_current') != 'active':
            excluded.append({'symbol': symbol, 'isin': row.get('isin'), 'reason': 'NOT_VERIFIED_CURRENT_ACTIVE'})
            continue
        groups[symbol].append(row)
        isin_groups[row.get('isin')].add(symbol)
    selected = {}
    for symbol, matches in sorted(groups.items(), key=lambda item: str(item[0])):
        row = matches[0]
        reason = None
        if not isinstance(symbol, str) or not symbol.endswith('.PA') or any(c in symbol for c in '/\\'):
            reason = 'NOT_PARIS_SYMBOL'
        elif len(matches) != 1 or len(isin_groups[row.get('isin')]) != 1:
            reason = 'AMBIGUOUS_SYMBOL_ISIN'
        elif not valid_isin(row.get('isin')):
            reason = 'INVALID_ISIN'
        names = {normal_name(v.get('name')) for m in row.get('market_reference', []) if m.get('mic') in ('XPAR', 'ALXP', 'XMLI')
                 for v in m.get('versions', []) if v.get('asof_to') is None}
        names.discard('')
        if not reason and not names:
            reason = 'NO_CURRENT_PARIS_REFERENCE_NAME'
        if reason:
            excluded.append({'symbol': symbol, 'isin': row.get('isin'), 'reason': reason})
        else:
            selected[symbol] = (row, names)
    return len(rows), selected, excluded


def is_rate_limit(exc):
    return type(exc).__name__ == 'YFRateLimitError' or getattr(getattr(exc, 'response', None), 'status_code', None) == 429


class IdentityMismatch(ValueError):
    pass


class CheckedTicker:
    def __init__(self, ticker, symbol, names, reserve):
        self.ticker, self.symbol, self.names, self.reserve = ticker, symbol, names, reserve

    def call(self, method, **kwargs):
        self.reserve()
        try:
            return getattr(self.ticker, method)(**kwargs)
        except Exception as exc:
            if is_rate_limit(exc):
                raise CollectionPause('YAHOO_RATE_LIMIT') from None
            raise

    def get_info(self):
        info = self.call('get_info')
        if (not isinstance(info, dict) or info.get('symbol') != self.symbol
            or info.get('currency') != 'EUR' or info.get('exchange') not in ('PAR', 'EPA')
            or info.get('quoteType') != 'EQUITY'):
            raise IdentityMismatch('YAHOO_IDENTITY_OR_INSTRUMENT_MISMATCH')
        if not ({normal_name(info.get('shortName')), normal_name(info.get('longName'))} & self.names):
            raise IdentityMismatch('YAHOO_REFERENCE_NAME_MISMATCH')
        return info

    def __getattr__(self, method):
        if method not in (*METHODS, *EXTRA_METHODS):
            raise AttributeError(method)
        return lambda **kwargs: self.call(method, **kwargs)


def collect_daily(cfg, result, *, root, identities, dry_run=False, max_symbols=None,
                  ticker_factory=None, sleep=None):
    import time
    sleep = sleep or time.sleep
    total, scope, exclusions = reference_scope(identities)
    pace = float(cfg.get('request_interval_seconds', 1))
    limit = int(cfg.get('max_symbols_per_run', 400))
    budget = int(cfg.get('max_endpoint_calls_per_day', 1600))
    attempts = int(cfg.get('max_attempts_per_symbol_per_day', 2))
    if not 1 <= limit <= 1000 or not 4 <= budget <= 10000 or not 1 <= attempts <= 3 or not math.isfinite(pace) or pace < 1:
        raise ValueError('Budgets consensus invalides')
    if max_symbols is not None:
        if not 1 <= max_symbols <= limit:
            raise ValueError('Limite de smoke invalide')
        scope = dict(list(scope.items())[:max_symbols])
    if len(scope) > limit:
        raise ValueError('Univers consensus au-delà du plafond configuré')
    digest = hashlib.sha256(identities.read_bytes()).hexdigest()
    day = datetime.now(ZoneInfo('Europe/Paris')).date().isoformat()
    result.update(requested_count=len(scope), sql_writes=False, historical_pit=False,
                  identity_qualified=False, universe_sha256=digest, total_reference=total,
                  reference_exclusions=exclusions, reference_excluded_count=len(exclusions),
                  observation_day=day, errors=[], coverage={}, skipped_completed=0,
                  received_unit='valid_consensus_snapshots', persisted_unit='new_observations',
                  requested_unit='eligible_reference_symbols', pending_count=len(scope))
    if dry_run:
        return
    if not scope:
        raise ValueError('Aucun titre consensus éligible dans le référentiel')
    if ticker_factory is None:
        from service.yahoo.clientYahooFinance import _import_yfinance
        from service.fr.yahoo_price_reference_pilot import verified_tls_context
        from curl_cffi.requests import Session
        with tempfile.TemporaryDirectory(prefix='fr-consensus-daily-ca-') as temporary:
            bundle = Path(temporary)/'roots.pem'
            bundle.write_text(''.join(ssl.DER_cert_to_PEM_cert(c) for c in verified_tls_context().get_ca_certs(binary_form=True)), encoding='ascii')
            with Session(impersonate='chrome', verify=str(bundle), timeout=30) as session:
                return collect_daily(cfg, result, root=root, identities=identities,
                                     max_symbols=max_symbols, sleep=sleep,
                                     ticker_factory=lambda s: _import_yfinance().Ticker(s, session=session))
    checkpoint = root/'days'/f'{day}.json'
    state = json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint.exists() else {'day': day, 'symbols': {}, 'endpoint_calls': 0}
    if state.get('universe_sha256', digest) != digest:
        raise ValueError('Référentiel modifié dans la journée ; revue du checkpoint requise')
    state.update(universe_sha256=digest, reference_exclusions=exclusions, market_code='FR_EQ')
    terminal = {'COMPLETED', 'NO_COVERAGE', 'EXCLUDED_IDENTITY'}
    run_symbols = root/'daily_observations'/day

    def save():
        atomic(checkpoint, state)

    def reserve():
        if state['endpoint_calls'] >= budget:
            raise CollectionPause('LOCAL_DAILY_ENDPOINT_BUDGET')
        state['endpoint_calls'] += 1
        save()  # Reserve before call, including failures. Not a vendor quota claim.

    for symbol, (reference, names) in scope.items():
        prior = state['symbols'].get(symbol, {})
        if prior.get('status') in terminal:
            # Reconcile persisted observation from an interrupted attempt or prior run.
            if prior.get('status') == 'COMPLETED':
                file = Path(prior['observation_path'])
                if not file.is_relative_to(root.resolve()) or not file.exists():
                    raise ValueError('Observation checkpoint absente ou hors périmètre')
                observation = json.loads(file.read_text(encoding='utf-8'))
                obj = Path(observation['object_path'])
                if not obj.is_relative_to(root.resolve()) or hashlib.sha256(obj.read_bytes()).hexdigest() != observation['source_sha256']:
                    raise ValueError('Objet consensus checkpoint corrompu')
            result['skipped_completed'] += 1
            continue
        # A crash after persistence but before checkpoint must not repeat today's snapshot.
        recovered = list((run_symbols/'observations'/symbol).glob('*.json'))
        if recovered:
            if len(recovered) != 1:
                raise ValueError('Plusieurs snapshots quotidiens du même titre')
            observation = json.loads(recovered[0].read_text(encoding='utf-8'))
            obj = Path(observation['object_path'])
            if not obj.is_relative_to(root.resolve()) or hashlib.sha256(obj.read_bytes()).hexdigest() != observation['source_sha256']:
                raise ValueError('Objet récupéré corrompu')
            state['symbols'][symbol] = {'status': 'COMPLETED', 'observation_path': str(recovered[0].resolve()), 'coverage': observation['coverage']}
            save()
            result['skipped_completed'] += 1
            continue
        if prior.get('attempts', 0) >= attempts:
            continue
        local = dict(requested_count=0, received_count=0, persisted_count=0, failed_count=0, warning_count=0)
        local_cfg = {**cfg, 'universe_mode': 'pilot', 'pilot_symbols': [symbol], 'max_symbols_per_run': 1}
        rule = (cfg.get('identity_checks') or {}).get(symbol)
        if rule:
            age = (datetime.now(ZoneInfo('Europe/Paris')).date() - datetime.fromisoformat(str(rule['reviewed_on'])).date()).days
            if not 0 <= age <= 30:
                local_cfg['identity_checks'] = {}  # Exact reference name still required; no manual qualification.
        entry = {'status': 'RUNNING', 'attempts': prior.get('attempts', 0)+1}
        state['symbols'][symbol] = entry
        save()
        try:
            collect(local_cfg, local, root=run_symbols, identities=identities,
                    ticker_factory=lambda s: CheckedTicker(ticker_factory(s), s, names, reserve), sleep=sleep)
            entry.update(status='COMPLETED', coverage=local['coverage'][symbol],
                         observation_path=str(next((run_symbols/'observations'/symbol).glob('*.json')).resolve()))
            result['received_count'] += local['received_count']
            result['persisted_count'] += local['persisted_count']
            result['warning_count'] += local['warning_count']
            result['coverage'][symbol] = local['coverage'][symbol]
        except CollectionPause as exc:
            entry.update(status='PENDING', attempts=prior.get('attempts', 0), reason=str(exc))
            result['pause_reason'] = str(exc)
            save()
            break
        except RuntimeError:
            messages = local.get('errors', [])
            message = messages[0]['error'] if messages else 'UNKNOWN_COLLECTION_ERROR'
            if message.startswith('IdentityMismatch') or message.startswith('ValueError: Identité'):
                entry.update(status='EXCLUDED_IDENTITY', reason=message)
            elif message == 'ValueError: Aucune donnée consensus disponible':
                entry.update(status='NO_COVERAGE', reason=message)
            else:
                entry.update(status='FAILED', reason=message)
                result['failed_count'] += 1
                result['errors'].append({'symbol': symbol, 'error': message})
        save()
        print(json.dumps({'batch': 'fr_consensus_snapshot', 'symbol': symbol, 'status': entry['status'], 'processed': len(state['symbols']), 'total': len(scope)}, ensure_ascii=False), flush=True)
    counts = Counter(v.get('status') for s, v in state['symbols'].items() if s in scope)
    result.update(endpoint_calls_today=state['endpoint_calls'], symbol_status_counts=dict(counts),
                  archived_symbols_today=counts['COMPLETED'],
                  excluded_identity_count=counts['EXCLUDED_IDENTITY'], empty_count=counts['NO_COVERAGE'],
                  pending_count=len(scope)-sum(counts[s] for s in terminal),
                  checkpoint_path=str(checkpoint))
    result['coverage_complete'] = result['pending_count'] == 0
    result['coverage_ratio'] = counts['COMPLETED']/len(scope)
    result['exclusions'] = [{'symbol': s, **v} for s, v in state['symbols'].items() if s in scope and v.get('status') in ('EXCLUDED_IDENTITY', 'NO_COVERAGE', 'FAILED')]
    state['last_result'] = result
    save()
    if result.get('pause_reason'):
        result['warning_count'] += 1
        raise RuntimeError('Collecte consensus interrompue : ' + result['pause_reason'])
    if result['pending_count']:
        raise RuntimeError('Collecte consensus incomplète ; reprise des titres en échec requise')
