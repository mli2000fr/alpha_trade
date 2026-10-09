"""Verify a frozen FR release-review handoff offline, without granting release."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

from service.fr.prediction_contract_16a import ROOT, aware, scoped_path
from service.fr.qualification_dossier_16g import read_proof
from service.fr.release_review_16g3 import validate_review


def check(packet_path, review_path=None, *, root=ROOT, now=None):
    root = root.resolve()
    now = now or datetime.now(UTC)
    report, packet_hash = read_proof(scoped_path(str(packet_path), root))
    if (report.get('market_code') != 'FR_EQ'
            or report.get('status') != 'RELEASE_REVIEW_PENDING_NOT_RELEASED'
            or any(report.get(k) is not False for k in ('serving_allowed', 'orders_allowed', 'sql_writes'))):
        raise ValueError('Non-serving FR review packet required')
    if not aware(report['decision_at']) <= aware(report['created_at']) <= now:
        raise ValueError('Invalid packet timing')
    rows = report['matrix']
    if (len(rows) != report['candidate_count'] or not rows
            or len({row['symbol'] for row in rows}) != len(rows)
            or any(row.get('servable') is not False for row in rows)):
        raise ValueError('Inconsistent diagnostic population')
    if report['model_lineage'].get('model_executed') is not False or report['model_lineage'].get('release_approved') is not False:
        raise ValueError('Model must remain unreleased')

    proofs = [{'path': report['confirmation_report'], 'sha256': report['confirmation_sha256']},
              {'path': report['replay_report'], 'sha256': report['replay_report_sha256']}]
    proofs.extend(report['model_lineage']['evidence'])
    proofs.extend({'path': path, 'sha256': digest} for path, digest in report['actions_archive_proofs'].items())
    replay, _ = read_proof(scoped_path(report['replay_report'], root))
    proofs.extend(replay['files'])
    unique = {}
    for proof in proofs:
        path = scoped_path(proof['path'], root)
        if path in unique and unique[path] != proof['sha256']:
            raise ValueError('Conflicting evidence hashes')
        unique[path] = proof['sha256']
    for path, expected in unique.items():
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        if digest.hexdigest() != expected:
            raise ValueError('Evidence checksum mismatch: ' + str(path.relative_to(root)))

    review_status, review_result, review_hash = 'MISSING', None, None
    if review_path is not None:
        review, review_hash = read_proof(scoped_path(str(review_path), root))
        if review.get('packet_sha256') != packet_hash or review.get('market_code') != 'FR_EQ':
            raise ValueError('Review is not bound to this FR packet')
        if any(review.get(key) is not False for key in ('serving_allowed', 'orders_allowed')):
            raise ValueError('Review cannot grant execution')
        if review.get('decision') == 'PENDING':
            review_status = 'PENDING_NOT_ATTESTED'
        else:
            review_result = validate_review(review, packet_hash, now=now, packet_created_at=report['created_at'])
            review_status = 'ATTESTATION_ENVELOPE_VALID_NOT_RELEASE'

    return {'schema_version': 1, 'market_code': 'FR_EQ', 'checked_at': now.isoformat(),
        'status': 'HANDOFF_VERIFIED_NOT_RELEASED', 'packet_sha256': packet_hash,
        'review_sha256': review_hash, 'review_status': review_status, 'review_result': review_result,
        'evidence_files_verified': len(unique), 'candidate_count': len(rows),
        'symbols_requiring_pre_anchor_identity_proof': [r['symbol'] for r in rows
            if r['feature_identity_sessions_before_anchor']],
        'symbols_requiring_trading_currency_proof': [r['symbol'] for r in rows
            if r['trading_currency_interval_qualified'] is not True],
        'symbols_requiring_independent_action_proof': [r['symbol'] for r in rows
            if r['actions']['actions_independently_qualified'] is not True],
        'release_gates_from_packet': report['remaining_gates'],
        'independence_verified_by_software': False,
        'serving_allowed': False, 'orders_allowed': False, 'sql_writes': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    allowed = (ROOT / 'artifacts/fr/research/release_review_16g3').resolve()
    if output == allowed or not output.is_relative_to(allowed) or output.exists():
        parser.error('New isolated FR release-review output folder required')
    result = check(args.packet, args.review)
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'report.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({key: result[key] for key in ('status', 'review_status',
        'evidence_files_verified', 'candidate_count', 'serving_allowed')}))


if __name__ == '__main__':
    main()
