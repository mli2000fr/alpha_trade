"""Reconstruct pre-anchor reference coverage in research only, never release serving."""
from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
from pathlib import Path

from service.fr.anchor_replay_16g2 import FIELDS, final_record
from service.fr.esma_firds_download import _check, _download, _tls_context, list_files
from service.fr.esma_firds_history import apply_event, archive_records
from service.fr.prediction_contract_16a import ROOT, scoped_path
from service.fr.security_master_daily_15e import validate_index


def check_chain(index, start, end):
    missing = validate_index([r for r in index if r['type'] == 'DLTINS'],
                             start + timedelta(days=1), end)
    names = [r['file'] for r in index if r['type'] == 'FULINS_E']
    expected = {f'FULINS_E_{start:%Y%m%d}_{n:02d}of02.zip' for n in (1, 2)}
    if len(names) != 2 or set(names) != expected or missing:
        raise ValueError(f'Incomplete archive index: full={names} missing={missing}')
    return missing


def qualify(history, candidates, sessions, anomalies):
    rows = []
    for row in candidates:
        key = (row['isin'], row['mic'])
        days = []
        for day in sessions:
            try:
                version = final_record(history.get(key, []), day)
                first = (version.get('first_trade_reported') or '')[:10]
                end = (version.get('termination_reported') or '')[:10]
                valid = (version['event'] not in ('TermntdRcrd', 'CancRcrd')
                         and bool(first) and first <= str(day)
                         and (not end or end.startswith('9999-') or end > str(day)))
                days.append({'date': str(day), 'reference_active': valid,
                             'payload': {f: version.get(f) for f in FIELDS}})
            except ValueError as exc:
                days.append({'date': str(day), 'reference_active': False, 'reason': str(exc)})
        rows.append({'symbol': row['symbol'], 'isin': key[0], 'mic': key[1], 'sessions': days,
                     'covered_session_count': sum(d['reference_active'] for d in days),
                     'all_sessions_active': bool(days) and all(d['reference_active'] for d in days),
                     'trading_currency_qualified': False, 'servable': False})
    return {'matrix': rows, 'candidate_count': len(rows),
            'reference_covered_count': sum(r['all_sessions_active'] for r in rows),
            'anomalies': anomalies, 'serving_allowed': False, 'orders_allowed': False,
            'sql_writes': False, 'historical_decision_release': False}


def run(packet_path, output_dir, *, root=ROOT, full_date='2026-09-12'):
    packet_path, output = [scoped_path(str(p), root) for p in (packet_path, output_dir)]
    output.mkdir(parents=True, exist_ok=False)
    data = packet_path.read_bytes()
    packet = json.loads(data)
    if packet['market_code'] != 'FR_EQ' or packet.get('serving_allowed') is not False:
        raise ValueError('Non-serving FR packet required')
    candidates = packet['matrix']
    pairs = {(r['isin'], r['mic']) for r in candidates}
    if len(pairs) != len(candidates) or not pairs:
        raise ValueError('Unique nonempty population required')
    sessions = sorted({date.fromisoformat(d) for r in candidates
                       for d in r['feature_identity_sessions_before_anchor']})
    start, end = date.fromisoformat(full_date), date(2026, 9, 25)
    if start not in (date(2026, 9, 5), date(2026, 9, 12)):
        raise ValueError('Unregistered anchor date')
    if not sessions or max(sessions) > end:
        raise ValueError('Unexpected feature window')
    context = _tls_context()
    index = list_files(start, end, start, context)
    received = datetime.now(UTC).isoformat()
    (output / 'index.json').write_text(json.dumps({'received_at': received, 'files': index}, indent=2))
    try:
        missing = check_chain(index, start, end)
    except ValueError as exc:
        report = {'market_code': 'FR_EQ', 'status': 'BLOCKED_ARCHIVE_INDEX',
            'created_at': datetime.now(UTC).isoformat(), 'index_received_at': received,
            'start': str(start), 'end': str(end), 'error': str(exc),
            'source_packet_sha256': hashlib.sha256(data).hexdigest(),
            'serving_allowed': False, 'orders_allowed': False, 'sql_writes': False}
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report), flush=True)
        return report
    history, anomalies, proofs = {}, [], []
    targets, mics = {p[0] for p in pairs}, {p[1] for p in pairs}
    reusable = root / 'artifacts/fr/esma_firds/replay_2018'
    for number, item in enumerate(index, 1):
        local = reusable / '2026' / item['file']
        if local.is_file():
            proof = _check(local, item.get('md5'))
            reused = True
        else:
            _download(item, output / 'archives', context)
            local = output / 'archives/2026' / item['file']
            proof = _check(local, item.get('md5'))
            reused = False
        events = 0
        for record in archive_records(local, targets, mics):
            if (record['isin'], record['mic']) not in pairs:
                continue
            apply_event(history, record, date.fromisoformat(item['date']), item['file'], anomalies)
            events += 1
        proofs.append({**item, **proof, 'path': str(local.relative_to(root)),
                       'verified_at': datetime.now(UTC).isoformat(),
                       'reused': reused, 'target_events': events})
        print(f'{number}/{len(index)} {item["file"]} target_events={events} anomalies={len(anomalies)}', flush=True)
    report = qualify(history, candidates, sessions, anomalies)
    passed = not anomalies and report['reference_covered_count'] == len(candidates)
    report.update({'market_code': 'FR_EQ',
        'status': 'PREANCHOR_RECONSTRUCTED_NOT_RELEASED' if passed else 'PREANCHOR_RESERVED',
        'created_at': datetime.now(UTC).isoformat(), 'index_received_at': received,
        'decision_at': packet['decision_at'], 'source_packet_sha256': hashlib.sha256(data).hexdigest(),
        'start': str(start), 'end': str(end), 'session_count': len(sessions),
        'sessions_before_new_anchor': [str(d) for d in sessions if d < start],
        'files': proofs, 'missing_publication_days': missing,
        'knowledge_semantics': 'RECONSTRUCTION_AFTER_DECISION_NOT_ORIGINAL_RECEIPT_PROOF'})
    (output / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('status', 'reference_covered_count', 'candidate_count')}, ensure_ascii=False), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--full-date', default='2026-09-12')
    args = parser.parse_args()
    run(args.packet, args.output_dir, full_date=args.full_date)


if __name__ == '__main__':
    main()
