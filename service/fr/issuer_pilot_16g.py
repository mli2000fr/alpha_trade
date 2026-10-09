"""Local evidence inventory, not an action/currency certification or release."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

from service.fr.prediction_contract_16a import ROOT, aware, scoped_path

PILOT = {'AIR.PA': 'NL0000235190', 'OR.PA': 'FR0000120321', 'SAN.PA': 'FR0000120578'}


def checked(path, expected=None):
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if expected is not None and digest != expected:
        raise ValueError(f'Changed evidence: {path}')
    return json.loads(data), digest


def select_candidates(packet):
    if packet.get('market_code') != 'FR_EQ':
        raise ValueError('FR packet required')
    result = {}
    for row in packet['matrix']:
        symbol = row['symbol']
        if symbol not in PILOT:
            continue
        if symbol in result or row['isin'] != PILOT[symbol] or row['mic'] != 'XPAR':
            raise ValueError('Ambiguous or mismatched pilot identity')
        result[symbol] = row
    if set(result) != set(PILOT):
        raise ValueError('Incomplete pilot population')
    return result


def metadata_inventory(folder, *, cutoff, start, end):
    """Retain distinct metadata versions and earliest observed availability, not latest.json."""
    records, proofs = {}, {}
    for path in sorted((folder / 'observations').glob('*.json')):
        obs, digest = checked(path)
        observed, available = aware(obs['observed_at']), aware(obs['available_at'])
        if available < observed:
            raise ValueError('Availability predates observation')
        if available > cutoff:
            continue
        raw_hash = obs['raw_sha256']
        if len(raw_hash) != 64 or any(c not in '0123456789abcdef' for c in raw_hash):
            raise ValueError('Invalid raw hash')
        raw_path = folder / 'raw' / f'{raw_hash}.json'
        raw, _ = checked(raw_path, raw_hash)
        if raw['query_window'] != obs['window']:
            raise ValueError('Observation window mismatch')
        proofs[str(path)] = digest
        proofs[str(raw_path)] = raw_hash
        for row in raw['records']:
            isin = row.get('identificationsociete_iso_cd_isi')
            if isin not in PILOT.values():
                continue
            transmitted = aware(row['uin_dat_amf'])
            if transmitted > cutoff or not start <= transmitted.date().isoformat() <= end:
                continue
            version = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            key = (isin, row['uin_idt_uin'], version)
            item = {'isin': isin, 'id': row['uin_idt_uin'], 'metadata_sha256': version,
                    'title': row.get('informationdeposee_inf_tit_inf'),
                    'category': row.get('sous_type_d_information'),
                    'transmitted_at': transmitted.isoformat(), 'available_at': available.isoformat(),
                    'raw_sha256': raw_hash, 'observation': str(path),
                    'document_url': row.get('url_de_recuperation'),
                    'document_read': False, 'effective_event_qualified': False}
            if key not in records or available < aware(records[key]['available_at']):
                records[key] = item
    return sorted(records.values(), key=lambda r: (r['isin'], r['transmitted_at'], r['id'])), proofs


def run(packet_path, output_dir, *, root=ROOT):
    packet_path = scoped_path(str(packet_path), root)
    packet, packet_hash = checked(packet_path)
    candidates = select_candidates(packet)
    cutoff = aware(packet['decision_at'])
    proofs = {str(packet_path): packet_hash}
    action_proofs = {str(scoped_path(path, root)): digest
                     for path, digest in packet['actions_archive_proofs'].items()}
    for row in candidates.values():
        for kind in row['actions']['types'].values():
            for support in kind['supporting_observations']:
                path = scoped_path(support['path'], root)
                obs, digest = checked(path, action_proofs[str(path)])
                if obs['raw_sha256'] != support['raw_sha256']:
                    raise ValueError('Action support mismatch')
                raw_path = path.parent.parent / 'raw' / (obs['raw_sha256'] + '.json')
                _, raw_hash = checked(raw_path, obs['raw_sha256'])
                proofs[str(path)], proofs[str(raw_path)] = digest, raw_hash
    records, metadata_proofs = metadata_inventory(
        root / 'artifacts/fr/operations/fr_dila_disclosures_sync', cutoff=cutoff,
        start='2026-09-09', end='2026-10-07')
    proofs.update(metadata_proofs)
    rows = []
    for symbol, candidate in candidates.items():
        rows.append({'symbol': symbol, 'isin': candidate['isin'], 'mic': candidate['mic'],
            'nominal_currency': candidate['nominal_currency'],
            'provider_declared_div_split_count': sum(len(k['provider_events_in_window'])
                for k in candidate['actions']['types'].values()),
            'metadata': [r for r in records if r['isin'] == candidate['isin']],
            'trading_currency_interval_qualified': False,
            'actions_independently_qualified': False, 'servable': False})
    report = {'market_code': 'FR_EQ', 'status': 'PILOT_INVENTORY_NOT_RELEASED',
        'created_at': datetime.now(UTC).isoformat(), 'decision_at': cutoff.isoformat(),
        'window': ['2026-09-09', '2026-10-07'], 'matrix': rows, 'proofs': proofs,
        'metadata_version_count': len(records), 'metadata_coverage_exhaustive': False,
        'serving_allowed': False, 'orders_allowed': False, 'sql_writes': False}
    output = scoped_path(str(output_dir), root)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    report = run(args.packet, args.output_dir)
    print(json.dumps({'status': report['status'], 'metadata_version_count': report['metadata_version_count'],
                      'symbols': {r['symbol']: len(r['metadata']) for r in report['matrix']}}))


if __name__ == '__main__':
    main()
