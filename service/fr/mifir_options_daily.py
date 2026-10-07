"""Prospective FR MiFIR/FIRDS collection; file quarantine only, never canonical SQL."""
from datetime import datetime, timedelta
import hashlib
import json
import time
from zoneinfo import ZoneInfo

from service.fr.consensus_daily import reference_scope
from service.fr import mifir_options_poc as source
from service.inpi.files import atomic


def _archive(root, raw, receipt):
    digest = hashlib.sha256(raw).hexdigest()
    if receipt.get('sha256') != digest:
        raise ValueError('Source receipt checksum mismatch')
    path = root/'objects'/digest
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Corrupted archived source')
    else:
        with path.open('xb') as stream:
            stream.write(raw)
    return {'object': str(path), **receipt}


def collect(cfg, result, *, root, identities, dry_run=False, max_symbols=None,
            fetch=None, clock=None):
    fetch = source.fetch if fetch is None else fetch
    current = clock or datetime.now(ZoneInfo('Europe/Paris'))
    if current.tzinfo is None:
        raise ValueError('Timezone-aware collection clock required')
    total, selected, excluded = reference_scope(identities)
    if max_symbols is not None:
        if max_symbols < 1:
            raise ValueError('max_symbols must be positive')
        selected = dict(sorted(selected.items())[:max_symbols])
    universe = {row['isin']: symbol for symbol, (row, _) in selected.items()}
    if not universe:
        raise ValueError('No verified FR identities available')
    result.update(requested_count=len(universe), reference_total=total,
                  excluded_identities=excluded, counters_unit='underlying_symbols',
                  ml_eligible=False, historical_pit_qualified=False,
                  collection_scope='PARTIAL_DELAYED_TRADES_CURRENT_FIRDS')
    if dry_run:
        return
    receipts = []
    day = current.astimezone(ZoneInfo('Europe/Paris')).date()
    attempt = root/'attempts'/(current.strftime('%Y%m%dT%H%M%S%f'))
    complete = False
    try:
        page, receipt = fetch(source.TRADES_PAGE, 100_000)
        receipts.append(_archive(root, page, receipt))
        if not all(token in page.decode('utf-8') for token in
                   ('EQUITY_INDEX_DERIVATIVES', 'PREVIOUS_TRADING_DAY', 'value="PAR"')):
            raise ValueError('Public MiFIR download form changed')
        raw, receipt = fetch(source.TRADES_URL, 16_000_000)
        receipts.append(_archive(root, raw, receipt))
        trades, disclaimer = source.read_trades(raw)
        dates = sorted({source.instant(r['TradingDateTime']).date() for r in trades})
        age = int(cfg.get('max_source_age_days', 7))
        if not dates or age < 1 or any(d >= day or d < day-timedelta(days=age) for d in dates):
            raise ValueError('Missing, same-day/future or stale previous-trading-day source')
        isins = sorted({r['MifidInstrumentID'] for r in trades if source.valid_isin(r['MifidInstrumentID'])})
        budget = int(cfg.get('max_reference_calls', 80))
        if budget < 1 or len(isins) > 80*budget:
            raise ValueError('FIRDS request budget exceeded; source preserved for diagnosis')
        docs = []
        for offset in range(0, len(isins), 80):
            requested = isins[offset:offset+80]
            url = source.query_url(requested)
            cache = root/'checkpoints'/day.isoformat()/(hashlib.sha256(url.encode()).hexdigest()+'.json')
            if cache.exists():
                entry = json.loads(cache.read_text(encoding='utf-8'))
                blob = root/'objects'/entry['sha256']
                payload = blob.read_bytes()
                if hashlib.sha256(payload).hexdigest() != entry['sha256'] or entry.get('url') != url:
                    raise ValueError('Corrupted FIRDS resume checkpoint')
            else:
                payload, entry = fetch(url, 4_000_000)
                _archive(root, payload, entry)
            response = json.loads(payload)['response']
            if response['numFound'] != len(response['docs']):
                raise ValueError('Truncated FIRDS response')
            if any(d.get('isin') not in requested for d in response['docs']):
                raise ValueError('FIRDS returned unrequested instruments')
            atomic(cache, entry)
            receipts.append(entry)
            docs.extend(response['docs'])
            print(f'FR MiFIR FIRDS {min(offset+80, len(isins))}/{len(isins)}', flush=True)
            if offset+80 < len(isins):
                time.sleep(max(0.5, float(cfg.get('request_sleep_seconds', 0.5))))
        observed = source.now()
        analysis = source.analyze(trades, docs, observed, universe=universe)
        coverage = analysis['coverage']
        received = sum(v['accepted_trade_rows'] > 0 for v in coverage.values())
        result.update(received_count=received, trade_rows=len(analysis['accepted']),
                      symbols_without_accepted_trade=[s for s, v in coverage.items() if not v['accepted_trade_rows']],
                      exclusion_counts=analysis['exclusion_counts'], source_trade_dates=analysis['trade_dates'])
        # Canonicalized observations are idempotent by input content AND configured universe.
        key = hashlib.sha256(json.dumps({'trades': receipts[1]['sha256'], 'docs': docs,
            'universe': universe}, sort_keys=True).encode()).hexdigest()
        target = root/'snapshots'/f'{key}.json'
        if not target.exists():
            atomic(target, {'analysis': analysis, 'observed_at': observed, 'available_at': observed,
                'reference_receipts': receipts, 'source_disclaimer': disclaimer,
                'universe': universe, 'excluded_identities': excluded,
                'ml_eligible': False, 'canonical': False, 'historical_pit_qualified': False})
            result['persisted_count'] = received
        result.update(snapshot_path=str(target), already_archived=result['persisted_count'] == 0,
                      coverage=coverage, source_receipts=receipts)
        # Missing references are not silently treated as a complete daily feed.
        unresolved = [i for i in analysis['reference_unmatched_instruments'] if source.valid_isin(i)]
        if unresolved or analysis['ambiguous_reference_isins'] or analysis['contract_errors']:
            raise ValueError('Incomplete/ambiguous FIRDS resolution; partial evidence archived, qualification required')
        complete = True
    finally:
        atomic(attempt.with_suffix('.json'), {'receipts': receipts, 'result': result,
            'finished_at': source.now(), 'collection_complete': complete})
