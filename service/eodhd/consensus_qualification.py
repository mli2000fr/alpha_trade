"""Two bounded read-only checks. No subscription, consensus archive or SQL write."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from common.public_data_http import verified_session
from service.eodhd.accounts import get_eodhd_token

BASE = 'https://eodhd.com/api'


def schema_summary(payload):
    """Keep field names/counts only, never consensus values or personal account data."""
    if not isinstance(payload, dict) or not isinstance(payload.get('trends'), list):
        return {'status': 'UNEXPECTED_SCHEMA'}
    groups = payload['trends']
    rows = [row for group in groups if isinstance(group, list)
            for row in group if isinstance(row, dict)]
    if len(groups) != 1:
        return {'status': 'UNEXPECTED_SCHEMA', 'symbol_groups': len(groups)}
    return {'status': 'ACCESS_CONFIRMED' if rows else 'EMPTY_COVERAGE',
            'symbol_groups': len(groups), 'records': len(rows),
            'fields': sorted({key for row in rows for key in row}),
            'historical_pit_confirmed': False}


def qualify(*, session=None, token=None):
    result = {'checked_at': datetime.now(UTC).isoformat(), 'symbol': 'AAPL.US',
              'rights_status': 'PENDING_WRITTEN_CONFIRMATION', 'purchase_made': False,
              'consensus_payload_archived': False, 'checks': {}}
    try:
        token = token or get_eodhd_token()
    except Exception:
        result['status'] = 'MISSING_CREDENTIAL'
        return result
    with (session or verified_session()) as client:
        for name, path, extra in [('account', '/user', {}),
                                  ('consensus', '/calendar/trends', {'symbols': 'AAPL.US'})]:
            try:
                response = client.get(BASE + path, params={'api_token': token, 'fmt': 'json', **extra},
                                      timeout=30, allow_redirects=False)
                check = {'http_status': response.status_code}
                if response.status_code == 200:
                    payload = response.json()
                    if name == 'account':
                        # subscriptionType is billing cadence, NOT a product entitlement.
                        check.update(status='ACCOUNT_ACCESS_CONFIRMED',
                                     product_entitlement_confirmed=False)
                    else:
                        check.update(schema_summary(payload))
                else:
                    check['status'] = ('ACCESS_DENIED' if response.status_code in (401, 403)
                                       else 'HTTP_ERROR')
                result['checks'][name] = check
            except (requests.RequestException, ValueError) as exc:
                # Exceptions may contain token-bearing URLs: never persist their text.
                result['checks'][name] = {'status': 'TECHNICAL_ERROR', 'error_type': type(exc).__name__}
    result['status'] = result['checks'].get('consensus', {}).get('status', 'TECHNICAL_ERROR')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    report = qualify()
    root = Path(args.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    # Exclusive creation: an earlier technical qualification is never overwritten.
    with (root / 'report.json').open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
