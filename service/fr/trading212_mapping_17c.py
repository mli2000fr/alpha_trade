"""Freeze a research-only Paris listing mapping from archived DEMO metadata."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone

from service.fr.broker_contract_17a import valid_isin
from service.fr.prediction_contract_16a import ROOT, scoped_path


def qualify(rows):
    mapped, excluded, seen, tickers = [], [], set(), set()
    for row in rows:
        isin = row.get('isin')
        if not valid_isin(isin) or isin in seen:
            raise ValueError('Invalid or duplicate FR ISIN')
        seen.add(isin)
        if row.get('expected_mic') != 'XPAR':
            excluded.append({'symbol': row['symbol'], 'isin': isin,
                             'reason': 'MIC_OUTSIDE_INITIAL_XPAR_PILOT',
                             'expected_mic': row.get('expected_mic')})
            continue
        candidates = [m for m in row.get('matches', [])
                      if m.get('currency') == 'EUR'
                      and m.get('schedule_exchange_names') == ['Euronext Paris']
                      and isinstance(m.get('ticker'), str) and m['ticker']]
        if len(candidates) != 1:
            excluded.append({'symbol': row['symbol'], 'isin': isin,
                             'reason': 'NO_UNIQUE_PARIS_EUR_METADATA_MATCH'})
            continue
        ticker = candidates[0]['ticker']
        if ticker in tickers:
            raise ValueError('Broker ticker collision')
        tickers.add(ticker)
        mapped.append({'symbol': row['symbol'], 'isin': isin,
                       'broker_ticker': ticker, 'currency': 'EUR',
                       'listing_mic_expected': 'XPAR',
                       'listing_evidence': 'BROKER_SCHEDULE_NAME_NOT_EXECUTION_VENUE',
                       'execution_mic_qualified': False, 'orders_allowed': False})
    return mapped, excluded


def run(*, snapshot_dir, output_dir, root=ROOT):
    snapshot = scoped_path(snapshot_dir, root)
    report = json.loads((snapshot / 'report.json').read_text(encoding='utf-8'))
    if (report.get('environment'), report.get('market_code'),
            report.get('account_currency'), report.get('orders_sent')) != ('DEMO', 'FR_EQ', 'EUR', 0):
        raise ValueError('Invalid DEMO snapshot context')
    if report.get('sql_writes') is not False or report.get('live_enabled') is not False:
        raise ValueError('Unexpected snapshot permissions')
    for endpoint in ('instruments', 'exchanges'):
        raw = (snapshot / f'{endpoint}.private.json').read_bytes()
        if hashlib.sha256(raw).hexdigest() != report['endpoint_receipts'][endpoint]['sha256']:
            raise ValueError('Metadata receipt hash mismatch')
    # Recompute matches from original evidence; do not trust a manually edited match file.
    from service.fr.trading212_demo_17b import match_instruments
    packet = scoped_path(report['source_packet'], root).read_bytes()
    if hashlib.sha256(packet).hexdigest() != report['source_sha256']:
        raise ValueError('FR packet hash mismatch')
    source = json.loads(packet)
    if source.get('market_code') != 'FR_EQ':
        raise ValueError('Non-FR packet')
    rows = match_instruments(source['matrix'],
        json.loads((snapshot / 'instruments.private.json').read_bytes()),
        json.loads((snapshot / 'exchanges.private.json').read_bytes()))
    mapped, excluded = qualify(rows)
    manifest = {
        'schema_version': 1, 'status': 'MAPPING_FROZEN_RESEARCH_NOT_RELEASED',
        'environment': 'DEMO', 'market_code': 'FR_EQ', 'currency': 'EUR',
        'orders_allowed': False, 'sql_writes': False, 'live_enabled': False,
        'source_snapshot': snapshot_dir, 'source_packet_sha256': report['source_sha256'],
        'metadata_receipts': {name: report['endpoint_receipts'][name]
                              for name in ('instruments', 'exchanges')},
        'population_count': len(rows), 'mapped_count': len(mapped),
        'excluded_count': len(excluded),
        'history_access_qualified': 'history' in report['endpoint_receipts'],
        'blockers': ['EXECUTION_MIC_NOT_QUALIFIED', 'BROKER_ADAPTER_NOT_DELIVERED',
                     'PROTECTIONS_AND_IDEMPOTENCE_NOT_QUALIFIED', 'SHADOW_DATA_NOT_RELEASED']
                    + (['HISTORY_ACCESS_REFUSED'] if 'history' not in report['endpoint_receipts'] else []),
        'mapped': mapped, 'excluded': excluded,
    }
    output = scoped_path(output_dir, root)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'manifest.json').write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    return {key: value for key, value in manifest.items() if key not in {'mapped', 'excluded', 'metadata_receipts'}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot-dir', required=True)
    parser.add_argument('--output-dir', default='artifacts/fr/research/trading212_mapping_17c/mapping-' +
                        datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f'))
    print(json.dumps(run(**vars(parser.parse_args())), ensure_ascii=False))


if __name__ == '__main__':
    main()
