"""Build an offline, non-serving qualification matrix from a frozen FR opening audit."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

from service.fr.prediction_contract_16a import ROOT, aware, scoped_path

CONTINUITY = 'MASTER_CONTINUITY_UNQUALIFIED'
GLOBAL_GATES = [CONTINUITY, 'INDEPENDENT_REFERENCE_QUALIFICATION',
                'INDEPENDENT_ACTIONS_QUALIFICATION', 'MODEL_RELEASE_REVIEW',
                'SPRINT15_OPERATIONAL_RESERVES']


def read_proof(path):
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def build(report_path, *, root=ROOT, now=None):
    root = root.resolve()
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError('Aware dossier timestamp required')
    report_path = scoped_path(str(report_path), root)
    report, digest = read_proof(report_path)
    if (report.get('market_code') != 'FR_EQ' or report.get('phase') != 'confirm'
            or any(report.get(k) is not False for k in ('serving_allowed', 'orders_allowed', 'sql_writes'))):
        raise ValueError('Frozen FR diagnostic-only confirmation required')
    decision, audited = aware(report['decision_at']), aware(report['audit_at'])
    if not decision <= audited <= now:
        raise ValueError('Future or inconsistent confirmation timestamp')
    assembly, reference = report['daily_assembly'], report['reference']
    if assembly['decision_at'] != report['decision_at'] or reference['decision_at'] != report['decision_at']:
        raise ValueError('Decision cutoffs differ')
    if any(assembly['archive_errors'].values()):
        raise ValueError('Archive integrity reserves require repair before building dossier')
    identities = {row['symbol']: row for row in reference['identities']}
    if len(identities) != len(reference['identities']):
        raise ValueError('Duplicate reference identity')
    diagnostics = assembly['diagnostics']
    if len({row['symbol'] for row in diagnostics}) != len(diagnostics) or len(diagnostics) != assembly['universe_count']:
        raise ValueError('Incomplete or duplicate diagnostic population')
    if set(identities) != {row['symbol'] for row in diagnostics}:
        raise ValueError('Reference and diagnostic populations differ')
    master_proofs = []
    for relative, expected in reference['proofs_sha256'].items():
        path = scoped_path(relative, root)
        state, actual = read_proof(path)
        if actual != expected or path.stem != actual:
            raise ValueError('Master archive hash mismatch')
        if state.get('market_code') != 'FR_EQ' or aware(state['last_observed_at']) > decision:
            raise ValueError('Master wrong market or observed after decision')
        master_proofs.append({'path': relative, 'sha256': actual, 'end': state['end'],
            'observed_at': state['last_observed_at'],
            'historical_continuity_confirmed': state.get('historical_continuity_confirmed', False),
            'delta_publication_continuity_confirmed': state.get('delta_publication_continuity_confirmed', False),
            'historical_missing_days': state.get('historical_missing_days', [])})
    if not master_proofs:
        raise ValueError('No verifiable archived master')
    matrix = []
    for row in sorted(diagnostics, key=lambda item: item['symbol']):
        identity = identities[row['symbol']]
        if identity['research_uid'] != row['research_uid']:
            raise ValueError('Reference identity mismatch')
        local = sorted(set(row['reasons']) - {CONTINUITY})
        local_ready = bool(row['features_computed'] and not local)
        matrix.append({'symbol': row['symbol'], 'research_uid': row['research_uid'],
            'isin': identity['isin'], 'mic': identity['mic'],
            'nominal_currency': identity['nominal_currency'],
            'reference_source_file': identity.get('source_file'),
            'features_computed': row['features_computed'],
            'local_checks_without_continuity_passed': local_ready,
            'local_blockers': local, 'missing_sessions': row['missing_sessions'],
            'global_release_gates': list(GLOBAL_GATES),
            'issuer_evidence': [{k: item[k] for k in ('id', 'archive_valid', 'reviewed_terms_known_at_decision',
                'action_adjustment_qualified', 'historical_currency_interval_qualified')}
                for item in report['evidence']['records'] if item['symbol'] == row['symbol']],
            'identity_independently_qualified': False, 'tradability_verified': False,
            'servable': False})
    counts = Counter(reason for row in matrix for reason in row['local_blockers'])
    return {'schema_version': 1, 'market_code': 'FR_EQ', 'status': 'QUALIFICATION_DOSSIER_NOT_RELEASED',
        'created_at': now.isoformat(), 'decision_at': report['decision_at'],
        'source_report': str(report_path.relative_to(root)).replace('\\', '/'), 'source_sha256': digest,
        'universe_count': len(matrix), 'features_computed_count': sum(x['features_computed'] for x in matrix),
        'local_checks_passed_count': sum(x['local_checks_without_continuity_passed'] for x in matrix),
        'local_blocker_counts': dict(sorted(counts.items())), 'matrix': matrix,
        'reference_coverage_end': reference.get('selected_coverage_end'),
        'reference_observed_at': reference.get('selected_observed_at'), 'master_proofs': master_proofs,
        'global_release_gates': list(GLOBAL_GATES), 'servable_count': 0,
        'serving_allowed': False, 'orders_allowed': False, 'sql_writes': False}


def inspect_anchor(dossier, anchor_dir, *, root=ROOT):
    """Inspect an existing official Full; presence is not a release or PIT certification."""
    from service.fr.esma_firds_download import _check
    from service.fr.esma_firds_history import archive_records
    root = root.resolve()
    anchor_dir = scoped_path(str(anchor_dir), root)
    state, receipt_hash = read_proof(anchor_dir / 'download_state.json')
    index, index_hash = read_proof(anchor_dir / 'index.json')
    if not state.get('complete') or state.get('failed'):
        raise ValueError('Complete archived Full required')
    day = index['full_date']
    indexed = {r['file']: r for r in index['files'] if r['type'] == 'FULINS_E' and r['date'] == day}
    received = {r['file']: r for r in state['files']}
    if not indexed or set(indexed) != set(received):
        raise ValueError('Full index and archive receipt differ')
    # Reuse strict fragment numbering, never accept a single missing Full fragment.
    import re
    parts = [re.fullmatch(r'FULINS_E_(\d{8})_(\d+)of(\d+)\.zip', name) for name in indexed]
    if (any(m is None for m in parts) or len({int(m[3]) for m in parts}) != 1
            or sorted(int(m[2]) for m in parts) != list(range(1, int(parts[0][3])+1))
            or any(m[1] != day.replace('-', '') for m in parts)):
        raise ValueError('Incomplete Full fragments')
    target_isins = {r['isin'] for r in dossier['matrix']}
    target_mics = {r['mic'] for r in dossier['matrix'] if r['mic']}
    found, proofs = {}, []
    for name in sorted(indexed):
        item = indexed[name]
        path = anchor_dir / day[:4] / name
        proof = _check(path, item.get('md5'))
        if proof['sha256'] != received[name]['sha256']:
            raise ValueError('Full receipt hash mismatch')
        proofs.append({'file': name, **proof})
        for record in archive_records(path, target_isins, target_mics):
            if record['event'] != 'Full':
                raise ValueError('Non-Full event in anchor')
            found.setdefault((record['isin'], record['mic']), []).append(record)
    matrix = []
    for item in dossier['matrix']:
        records = found.get((item['isin'], item['mic']), [])
        record = records[0] if len(records) == 1 else None
        matrix.append({'symbol': item['symbol'], 'isin': item['isin'], 'mic': item['mic'],
            'local_checks_without_continuity_passed': item['local_checks_without_continuity_passed'],
            'full_pair_record_count': len(records), 'unique_pair_in_full': len(records) == 1,
            'cfi': record.get('cfi') if record else None,
            'nominal_currency': record.get('currency') if record else None,
            'termination_reported': record.get('termination_reported') if record else None,
            'anchor_qualified': False})
    return {'status': 'ARCHIVED_FULL_CANDIDATE_NOT_RELEASED', 'full_date': day,
        'checked_at': datetime.now(UTC).isoformat(), 'download_receipt_sha256': receipt_hash,
        'index_sha256': index_hash, 'files': proofs, 'matrix': matrix,
        'unique_pairs_count': sum(r['unique_pair_in_full'] for r in matrix),
        'local_candidates_with_unique_pair_count': sum(r['unique_pair_in_full'] and
            r['local_checks_without_continuity_passed'] for r in matrix),
        'limitations': ['Presence does not prove tradability or currency of trading',
            'No PIT availability inferred from filename or filesystem timestamps',
            'No historical gap repaired; no post-Full delta chain certified by this audit',
            'Full predates part of the 21-session feature window; identity window needs qualification'],
        'serving_allowed': False, 'orders_allowed': False, 'sql_writes': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirmation-report', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--anchor-dir', type=Path, help='Optional existing ESMA Full archive, inspection only')
    args = parser.parse_args()
    output = args.output_dir.resolve()
    allowed = (ROOT / 'artifacts/fr/research/qualification_dossier_16g').resolve()
    if output == allowed or not output.is_relative_to(allowed) or output.exists():
        parser.error('New isolated FR qualification_dossier_16g directory required')
    dossier = build(args.confirmation_report)
    if args.anchor_dir:
        dossier['anchor_inspection'] = inspect_anchor(dossier, args.anchor_dir)
    output.mkdir(parents=True, exist_ok=False)
    # New files exclusively: never replace the confirmation or an existing review.
    with (output / 'report.json').open('x', encoding='utf-8') as stream:
        json.dump(dossier, stream, ensure_ascii=False, indent=2, allow_nan=False)
    with (output / 'local_candidates.json').open('x', encoding='utf-8') as stream:
        json.dump({'market_code': 'FR_EQ', 'role': 'DIAGNOSTIC_ONLY_NOT_TRADABLE_UNIVERSE',
            'source_sha256': dossier['source_sha256'], 'serving_allowed': False,
            'symbols': [r['symbol'] for r in dossier['matrix'] if r['local_checks_without_continuity_passed']]},
            stream, ensure_ascii=False, indent=2)
    print(json.dumps({k: dossier[k] for k in ('status', 'universe_count', 'features_computed_count',
        'local_checks_passed_count', 'servable_count')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
