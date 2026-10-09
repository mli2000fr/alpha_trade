"""Isolated Full-to-Delta reference replay; never repairs history or enables serving."""
from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path

from service.fr.esma_firds_download import _check
from service.fr.esma_firds_history import archive_records, apply_event
from service.fr.prediction_contract_16a import ROOT, scoped_path
from service.fr.qualification_dossier_16g import build, inspect_anchor, read_proof
from service.fr.security_master_daily_15e import validate_index

FIELDS = ('currency', 'cfi', 'name', 'first_trade_reported',
          'termination_reported', 'publication_from_reported')


def final_record(versions, end):
    eligible = [v for v in versions if v['asof_from'] <= str(end)
                and (v.get('asof_to') is None or v['asof_to'] >= str(end))]
    if len(eligible) != 1:
        raise ValueError('Missing or ambiguous reference version at replay end')
    return eligible[0]


def compare(history, master, candidates, end):
    pairs = [(s['isin'], venue['mic']) for s in master['symbols'] for venue in s['market_reference']]
    if len(pairs) != len(set(pairs)):
        raise ValueError('Duplicate current master ISIN/MIC')
    current = {(s['isin'], venue['mic']): venue['versions']
               for s in master['symbols'] for venue in s['market_reference']}
    rows = []
    for identity in sorted(candidates, key=lambda item: item['symbol']):
        key = (identity['isin'], identity['mic'])
        reasons = []
        left = right = None
        try:
            left = final_record(history.get(key, []), end)
            right = final_record(current.get(key, []), end)
            reasons.extend(f'FIELD_DIFF:{f}' for f in FIELDS if left.get(f) != right.get(f))
            if left['event'] in ('TermntdRcrd', 'CancRcrd') or right['event'] in ('TermntdRcrd', 'CancRcrd'):
                reasons.append('TERMINAL_EVENT')
        except ValueError as exc:
            reasons.append(str(exc))
        rows.append({'symbol': identity['symbol'], 'isin': key[0], 'mic': key[1],
            'matches_current_payload': not reasons, 'differences': reasons,
            'replayed_payload': {f: left.get(f) for f in FIELDS} if left else None,
            'current_payload': {f: right.get(f) for f in FIELDS} if right else None,
            'servable': False})
    return rows


def replay(confirmation_report, anchor_dir, historical_dir, *, root=ROOT, progress=None):
    root = root.resolve()
    dossier = build(confirmation_report, root=root)
    anchor = inspect_anchor(dossier, anchor_dir, root=root)
    anchor_dir, historical_dir = [scoped_path(str(p), root) for p in (anchor_dir, historical_dir)]
    end = date.fromisoformat(dossier['reference_coverage_end'])
    start = date.fromisoformat(anchor['full_date'])
    if end <= start:
        raise ValueError('Anchor must precede replay end')
    candidates = [r for r in dossier['matrix'] if r['local_checks_without_continuity_passed']]
    if not candidates:
        raise ValueError('No diagnostic candidates')
    selected = next((p for p in sorted(dossier['master_proofs'], key=lambda p: p['observed_at'], reverse=True)
                     if p['end'] == str(end) and p['observed_at'] == dossier['reference_observed_at']), None)
    if selected is None:
        raise ValueError('Exact decision master proof missing')
    master, digest = read_proof(scoped_path(selected['path'], root))
    if digest != selected['sha256']:
        raise ValueError('Master changed after dossier construction')
    historical, historical_hash = read_proof(historical_dir / 'index.json')
    # Verify receipt availability from the decision master, not a mutable checkpoint.
    daily_dir = scoped_path(selected['path'], root).parent.parent / 'archives'
    indexed = {}
    for base, entries in [(historical_dir, historical['files']), (daily_dir, master['files'])]:
        for item in entries:
            if item.get('type') != 'DLTINS' or not str(start) < item['date'] <= str(end):
                continue
            old = indexed.get(item['file'])
            if old and old[0].get('md5') and item.get('md5') and old[0]['md5'] != item['md5']:
                raise ValueError('Conflicting archive index checksums')
            indexed[item['file']] = (item, base / item['date'][:4] / item['file'])
    missing = validate_index([r[0] for r in indexed.values()], start+timedelta(days=1), end)
    if missing:
        raise ValueError('Missing Delta publication dates: ' + ','.join(missing))
    targets = {r['isin'] for r in candidates}
    mics = {r['mic'] for r in candidates}
    history, anomalies, evidence = {}, [], []
    files = []
    full_index, _ = read_proof(anchor_dir / 'index.json')
    for row in full_index['files']:
        if row['type'] == 'FULINS_E' and row['date'] == str(start):
            files.append((row, anchor_dir / row['date'][:4] / row['file']))
    files.extend(indexed.values())
    files.sort(key=lambda pair: (pair[0]['date'], pair[0]['type'] != 'FULINS_E', pair[0]['file']))
    for number, (row, path) in enumerate(files, 1):
        proof = _check(scoped_path(str(path), root), row.get('md5'))
        if row.get('sha256') and row['sha256'] != proof['sha256']:
            raise ValueError('Archive SHA-256 differs from decision master')
        count = 0
        for record in archive_records(path, targets, mics):
            apply_event(history, record, date.fromisoformat(row['date']), row['file'], anomalies)
            count += 1
        evidence.append({'path': str(path.relative_to(root)).replace('\\', '/'),
                         'date': row['date'], 'type': row['type'], **proof, 'target_events': count})
        if progress:
            progress(number, len(files), row['file'])
    comparisons = compare(history, master, candidates, end)
    mismatches = [r for r in comparisons if not r['matches_current_payload']]
    finished = datetime.now(UTC).isoformat()
    matched = not anomalies and not mismatches
    return {'schema_version': 1, 'market_code': 'FR_EQ',
        'status': 'ANCHORED_REFERENCE_MATCHED_NOT_RELEASED' if matched else 'ANCHORED_REPLAY_RESERVED',
        'qualified_at': finished, 'qualification_semantics': 'TECHNICAL_REPLAY_COMPLETION_NOT_RELEASE',
        'full_date': str(start), 'end': str(end), 'decision_at': dossier['decision_at'],
        'source_confirmation_sha256': dossier['source_sha256'], 'master_sha256': digest,
        'historical_index_sha256': historical_hash, 'anchor_inspection': anchor,
        'candidate_count': len(candidates), 'matched_count': len(comparisons)-len(mismatches),
        'archive_count': len(files), 'delta_archive_count': len(indexed),
        'missing_publication_days': [], 'files': evidence, 'anomalies': anomalies,
        'comparisons': comparisons, 'mismatch_count': len(mismatches),
        'post_full_chain_technically_complete': True,
        'historical_continuity_confirmed': False,
        'inherited_historical_missing_days': master.get('historical_missing_days', []),
        'prospective_contract_draft': {
            'status': 'DRAFT_NOT_APPROVED', 'scope': 'CURRENT_REFERENCE_SINCE_NEW_FULL_NOT_HISTORICAL_REPAIR',
            'reference_anchor': str(start), 'reference_coverage_end': str(end),
            'not_usable_before': finished, 'timezone': 'Europe/Paris', 'calendar': 'XPAR',
            'required_gates': ['INDEPENDENT_ANCHOR_REVIEW', 'IDENTITY_COVERAGE_FULL_FEATURE_WINDOW',
                'QUALIFIED_ACTIONS_AND_CURRENCIES', 'MODEL_RELEASE_REVIEW',
                'SPRINT15_OPERATIONAL_RESERVES', 'FROZEN_PROSPECTIVE_WINDOW_AND_LABEL_MATURITY'],
            'historical_boolean_must_remain_false': True, 'orders_allowed': False,
            'serving_allowed': False, 'sql_writes': False},
        'serving_allowed': False, 'orders_allowed': False, 'sql_writes': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirmation-report', type=Path, required=True)
    parser.add_argument('--anchor-dir', type=Path, required=True)
    parser.add_argument('--historical-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    allowed = (ROOT / 'artifacts/fr/research/anchor_replay_16g2').resolve()
    if output == allowed or not output.is_relative_to(allowed) or output.exists():
        parser.error('New isolated FR anchor_replay_16g2 directory required')
    output.mkdir(parents=True, exist_ok=False)
    # Append-only journal: a failure retains progress without replacing any evidence.
    def progress(done, total, name):
        message = {'completed': done, 'total': total, 'file': name, 'at': datetime.now(UTC).isoformat()}
        with (output / 'journal.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(message)+'\n')
        print(f'{done}/{total} {name}', flush=True)
    try:
        report = replay(args.confirmation_report, args.anchor_dir, args.historical_dir, progress=progress)
    except Exception as exc:
        with (output / 'failure.json').open('x', encoding='utf-8') as stream:
            json.dump({'status': 'FAILED', 'error': str(exc), 'serving_allowed': False}, stream, indent=2)
        raise
    with (output / 'report.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({k: report[k] for k in ('status', 'candidate_count', 'matched_count',
                                          'archive_count', 'mismatch_count')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
