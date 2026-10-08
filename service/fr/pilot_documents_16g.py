"""Bounded, on-demand DILA pilot document archive; never releases instruments."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from service.fr.issuer_pilot_16g import checked, select_candidates
from service.fr.prediction_contract_16a import ROOT, scoped_path

MAX_BYTES = 8_000_000
OFFICIAL = 'https://echanges.dila.gouv.fr/OPENDATA/AMF/'


def official_url(url):
    parts = urlsplit(url)
    prefixes = {'fr.ftp.opendatasoft.com': '/datadila/INFOFI/',
                'echanges.dila.gouv.fr': '/OPENDATA/AMF/'}
    prefix = prefixes.get(parts.hostname)
    if (parts.scheme != 'https' or not prefix or parts.port not in (None, 443)
            or parts.username or parts.password or parts.query or parts.fragment
            or not parts.path.startswith(prefix)):
        raise ValueError('Only exact official DILA document paths are allowed')
    relative = parts.path[len(prefix):]
    if not re.fullmatch(r'[A-Z0-9]+/\d{4}/\d{2}/FC[A-Z0-9]+_\d{8}\.pdf', relative):
        raise ValueError('Invalid DILA document pathname')
    return OFFICIAL + relative


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirect refused; review the destination before collecting')


def fetch(url):
    # No TLS bypass, credentials, guessed documents or unrestricted redirects.
    request = Request(official_url(url), headers={
        'User-Agent': 'AlphaTrade-Research/1.0 (public-data-readonly)'})
    with build_opener(NoRedirects()).open(request, timeout=25) as response:
        raw = response.read(MAX_BYTES + 1)
        content_type = response.headers.get('Content-Type', '')
        status = response.status
    if len(raw) > MAX_BYTES or not raw.startswith(b'%PDF-'):
        raise ValueError('Oversized or non-PDF document')
    return raw, {'http_status': status, 'content_type': content_type}


def collect(inventory, output, *, root=ROOT, fetcher=fetch):
    inventory = scoped_path(str(inventory), root)
    output = scoped_path(str(output), root)
    source, source_hash = checked(inventory)
    rows = select_candidates(source)
    if source.get('status') != 'PILOT_INVENTORY_NOT_RELEASED':
        raise ValueError('Frozen pilot inventory required')
    documents = [dict(item, symbol=symbol) for symbol, row in rows.items()
                 for item in row.get('metadata', [])]
    if len(documents) > 6 or len({r['id'] for r in documents}) != len(documents):
        raise ValueError('Only six distinct frozen pilot documents may be collected')
    for item in documents:
        if item['isin'] != rows[item['symbol']]['isin']:
            raise ValueError('Document identity differs from pilot')
        official_url(item['document_url'])
    if output.exists():
        raise ValueError('Use a new output directory to preserve prior observations')
    output.mkdir(parents=True)
    (output / 'pdfs').mkdir()
    results = []
    for item in documents:
        result = {**item, 'document_read': False, 'effective_event_qualified': False,
                  'download_url': official_url(item['document_url'])}
        try:
            raw, response = fetcher(result['download_url'])
            if len(raw) > MAX_BYTES or not raw.startswith(b'%PDF-'):
                raise ValueError('Oversized or non-PDF document')
            digest = hashlib.sha256(raw).hexdigest()
            path = output / 'pdfs' / f'{digest}.pdf'
            path.write_bytes(raw)
            result.update(status='ARCHIVED_NOT_REVIEWED', sha256=digest,
                          pdf_path=str(path), bytes=len(raw), response=response,
                          document_observed_at=datetime.now(UTC).isoformat())
        except Exception as exc:
            result.update(status='DOWNLOAD_FAILED', error=str(exc)[:400],
                          attempted_at=datetime.now(UTC).isoformat())
        results.append(result)
    report = {'market_code': 'FR_EQ', 'status': 'DOCUMENTS_ARCHIVED_NOT_RELEASED',
              'created_at': datetime.now(UTC).isoformat(),
              'source_inventory': str(inventory), 'source_inventory_sha256': source_hash,
              'historical_decision_at': source['decision_at'],
              'requested': len(results),
              'archived': sum(r['status'] == 'ARCHIVED_NOT_REVIEWED' for r in results),
              'failed': sum(r['status'] == 'DOWNLOAD_FAILED' for r in results),
              'metadata_availability_is_not_pdf_receipt': True,
              'actions_independently_qualified': False,
              'trading_currency_interval_qualified': False,
              'serving_allowed': False, 'orders_allowed': False, 'sql_writes': False,
              'documents': results}
    if report['failed']:
        report['status'] = 'PARTIAL_DOCUMENT_DOWNLOAD_FAILURE'
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', default='artifacts/fr/research/issuer_pilot_16g/three-issuers-20261008-v1/report.json')
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    result = collect(args.inventory, args.output_dir)
    print(json.dumps({k: result[k] for k in ('status', 'requested', 'archived', 'failed')}))
    if result['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
