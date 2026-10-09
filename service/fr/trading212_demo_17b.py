"""Bounded Trading212 DEMO read-only qualification. Never a broker adapter."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from common.verified_http import verified_session
from service.fr.prediction_contract_16a import ROOT, scoped_path

ORIGIN = 'https://demo.trading212.com'
ENDPOINTS = {
    'account': '/api/v0/equity/account/summary',
    'exchanges': '/api/v0/equity/metadata/exchanges',
    'instruments': '/api/v0/equity/metadata/instruments',
    'positions': '/api/v0/equity/positions',
    'orders': '/api/v0/equity/orders',
    'history': '/api/v0/equity/history/orders',
}
DEFAULT_PACKET = 'artifacts/fr/research/release_review_16g3/anchor-20261008-v2/report.json'


class SafeReadError(RuntimeError):
    """Contains only our own error codes, never provider bodies or headers."""


class DemoReader:
    def __init__(self, key, secret, session=None):
        if not key or not secret:
            raise SafeReadError('MISSING_DEMO_CREDENTIALS')
        self._auth = (key, secret)
        self._session = session or verified_session()
        self._calls = set()

    def get(self, name):
        if name not in ENDPOINTS or name in self._calls:
            raise SafeReadError('ENDPOINT_NOT_ALLOWED_OR_ALREADY_READ')
        self._calls.add(name)
        try:
            response = self._session.get(
                ORIGIN + ENDPOINTS[name], auth=self._auth, timeout=(10, 40),
                allow_redirects=False, stream=True,
                params={'limit': 50} if name == 'history' else None,
            )
        except Exception:
            raise SafeReadError('TRANSPORT_ERROR') from None
        try:
            if response.status_code != 200:
                raise SafeReadError(f'HTTP_{int(response.status_code)}')
            chunks, size = [], 0
            for chunk in response.iter_content(chunk_size=65536):
                size += len(chunk)
                if size > 32 * 1024 * 1024:
                    raise SafeReadError('RESPONSE_TOO_LARGE')
                chunks.append(chunk)
            raw = b''.join(chunks)
            try:
                payload = json.loads(raw)
            except (ValueError, UnicodeError):
                raise SafeReadError('INVALID_JSON') from None
            expected = dict if name in {'account', 'history'} else list
            if not isinstance(payload, expected):
                raise SafeReadError('UNEXPECTED_RESPONSE_SCHEMA')
            return payload, raw
        except SafeReadError:
            raise
        except Exception:
            raise SafeReadError('RESPONSE_READ_ERROR') from None
        finally:
            response.close()

    def close(self):
        self._session.close()


def match_instruments(matrix, instruments, exchanges):
    # workingScheduleId refers to a nested schedule, NOT the exchange id.
    schedules = {}
    for exchange in exchanges:
        for schedule in exchange.get('workingSchedules') or []:
            schedules.setdefault(schedule.get('id'), []).append(exchange.get('name'))
    rows = []
    for candidate in matrix:
        matches = [item for item in instruments
                   if item.get('isin') == candidate['isin']
                   and item.get('currencyCode') == 'EUR'
                   and item.get('type') == 'STOCK']
        rows.append({
            'symbol': candidate['symbol'], 'isin': candidate['isin'],
            'expected_mic': candidate['mic'],
            'state': 'UNIQUE_METADATA_MATCH' if len(matches) == 1 else
                     'AMBIGUOUS' if matches else 'ABSENT',
            'matches': [{'ticker': item.get('ticker'),
                         'schedule_exchange_names': schedules.get(item.get('workingScheduleId'), []),
                         'currency': item.get('currencyCode')} for item in matches],
            # Listing/schedule names do not establish actual order execution venue.
            'execution_mic_qualified': False,
        })
    return rows


def run(*, output_dir, packet=DEFAULT_PACKET, root=ROOT, reader=None):
    output = scoped_path(output_dir, root)
    output.mkdir(parents=True, exist_ok=False)
    packet_raw = scoped_path(packet, root).read_bytes()
    source = json.loads(packet_raw)
    matrix = source['matrix']
    if source.get('market_code') != 'FR_EQ' or not isinstance(matrix, list):
        raise ValueError('Unexpected FR evidence packet')
    report = {
        'status': 'FAILED_READONLY_NOT_RELEASED', 'market_code': 'FR_EQ',
        'environment': 'DEMO', 'orders_sent': 0, 'orders_allowed': False,
        'sql_writes': False, 'live_enabled': False, 'serving_enabled': False,
        'source_packet': packet, 'source_sha256': hashlib.sha256(packet_raw).hexdigest(),
        'population_count': len(matrix), 'population_role': 'UNRELEASED_REVIEW_PACKET',
        'endpoint_receipts': {}, 'errors': {},
        'api_permissions_independently_verified': False,
    }
    owned = reader is None
    payloads = {}
    try:
        if owned:
            reader = DemoReader(os.environ.get('TRADING212_DEMO_API_KEY'),
                                os.environ.get('TRADING212_DEMO_API_SECRET'))
        for name in ENDPOINTS:
            try:
                payload, raw = reader.get(name)
                payloads[name] = payload
                # Private account data stays in this local research directory.
                (output / f'{name}.private.json').write_bytes(raw)
                report['endpoint_receipts'][name] = {
                    'http_status': 200, 'bytes': len(raw),
                    'sha256': hashlib.sha256(raw).hexdigest(),
                    'observed_at': datetime.now(timezone.utc).isoformat(),
                }
            except SafeReadError as exc:
                report['errors'][name] = str(exc)
                if str(exc) in {'HTTP_401', 'HTTP_403'} and name == 'account':
                    break  # No credential fallback, retries or live probing.
        report['account_currency'] = payloads.get('account', {}).get('currency')
        for name in ('instruments', 'exchanges', 'positions', 'orders'):
            report[f'{name}_count'] = len(payloads[name]) if name in payloads else None
        history = payloads.get('history', {})
        report['history_first_page_count'] = len(history.get('items', [])) if 'history' in payloads else None
        report['history_truncated'] = bool(history.get('nextPagePath')) if 'history' in payloads else None
        if 'instruments' in payloads and 'exchanges' in payloads:
            rows = match_instruments(matrix, payloads['instruments'], payloads['exchanges'])
            (output / 'instrument_matches.json').write_text(
                json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
            report['metadata_coverage'] = {
                state: sum(row['state'] == state for row in rows)
                for state in ('UNIQUE_METADATA_MATCH', 'AMBIGUOUS', 'ABSENT')}
            report['execution_mic_qualified'] = False
        if not report['errors'] and report['account_currency'] == 'EUR':
            report['status'] = 'READONLY_REACHABLE_NOT_RELEASED'
        elif report['errors'] and payloads:
            report['status'] = 'PARTIAL_READONLY_NOT_RELEASED'
        elif not report['errors']:
            report['status'] = 'BLOCKED_ACCOUNT_CURRENCY_NOT_EUR'
    except SafeReadError as exc:
        report['errors']['credentials'] = str(exc)
    finally:
        if owned and reader is not None:
            reader.close()
        (output / 'report.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', default='artifacts/fr/research/trading212_demo_17b/demo-' +
                        datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f'))
    parser.add_argument('--packet', default=DEFAULT_PACKET)
    args = parser.parse_args()
    report = run(**vars(args))
    print(json.dumps({'output_dir': args.output_dir, **report}, ensure_ascii=False))
    if report['status'] != 'READONLY_REACHABLE_NOT_RELEASED':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
