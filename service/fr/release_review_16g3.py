"""Offline release-review packet; records technical evidence, never grants serving."""
from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
import hashlib
import json
from pathlib import Path

from service.fr.daily_feature_adapter_16b import action_checks, observed_payloads
from service.fr.prediction_contract_16a import ROOT, aware, prepare_manifest, scoped_path
from service.fr.qualification_dossier_16g import build, read_proof

REVIEW_CHECKS = ('full_fragments_and_official_checksums', 'post_full_delta_coverage',
                'candidate_isin_mic_comparisons', 'no_historical_backdating',
                'remaining_release_reserves_acknowledged')


def effective_events(payloads, symbol, sessions):
    """Provider declarations after superseding corrections, not certified absence."""
    issues = action_checks(payloads, symbol, sessions)
    result = {}
    for kind in ('div', 'splits'):
        events, support = {}, []
        selected = [p for p in payloads if p['raw']['symbol'] == symbol and p['raw']['kind'] == kind]
        for payload in sorted(selected, key=lambda p: (p['time'], p['path'])):
            raw = payload['raw']
            start, end = map(date.fromisoformat, raw['window'])
            if end < min(sessions) or start > max(sessions):
                continue
            events = {day: rows for day, rows in events.items() if not start <= day <= end}
            for event in raw['rows']:
                day = date.fromisoformat(event['date'])
                events.setdefault(day, []).append(event)
            support.append({'path': payload['path'], 'raw_sha256': payload['observation']['raw_sha256'],
                'observed_at': payload['observed'].isoformat(), 'available_at': payload['time'].isoformat(),
                'window': raw['window']})
        result[kind] = {'provider_events_in_window': [event for day, rows in sorted(events.items())
                                                    if day in sessions for event in rows],
                        'supporting_observations': support, 'absence_independently_proved': False}
    return {'provider_check_issues': issues, 'types': result, 'actions_independently_qualified': False}


def validate_review(review, packet_hash, *, now=None, packet_created_at=None):
    """Validate an attestation envelope, not the truth or independence of its author."""
    now = now or datetime.now(UTC)
    if review.get('market_code') != 'FR_EQ' or review.get('packet_sha256') != packet_hash:
        raise ValueError('Review market or packet hash mismatch')
    if review.get('serving_allowed') is not False or review.get('orders_allowed') is not False:
        raise ValueError('Review cannot enable serving or orders')
    if (review.get('review_kind') != 'INDEPENDENT_HUMAN_ATTESTATION'
            or review.get('independence_declared') is not True
            or not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip()):
        raise ValueError('Named independent reviewer attestation required')
    reviewed = aware(review['reviewed_at'])
    if reviewed > now:
        raise ValueError('Future review not accepted')
    if packet_created_at is not None and reviewed < aware(packet_created_at):
        raise ValueError('Review predates its packet')
    if review.get('decision') != 'ACCEPT_ANCHOR_FOR_PROSPECTIVE_CONTRACT_ONLY':
        raise ValueError('Anchor review acceptance missing')
    if set(review.get('checks', {})) != set(REVIEW_CHECKS) or any(
            review['checks'][key] is not True for key in REVIEW_CHECKS):
        raise ValueError('Review checklist incomplete')
    return {'status': 'ATTESTATION_ENVELOPE_VALID_NOT_RELEASE',
            'reviewed_at': reviewed.isoformat(), 'identity_and_independence_verified_by_software': False,
            'serving_allowed': False, 'orders_allowed': False}


def packet(confirmation_report, replay_report, *, root=ROOT):
    root = root.resolve()
    dossier = build(confirmation_report, root=root)
    confirmation, _ = read_proof(scoped_path(str(confirmation_report), root))
    replay_path = scoped_path(str(replay_report), root)
    replay, replay_hash = read_proof(replay_path)
    if (replay.get('market_code') != 'FR_EQ'
            or replay.get('status') != 'ANCHORED_REFERENCE_MATCHED_NOT_RELEASED'
            or replay.get('source_confirmation_sha256') != dossier['source_sha256']
            or replay.get('decision_at') != dossier['decision_at']
            or replay.get('anomalies') or replay.get('mismatch_count') != 0
            or not replay.get('post_full_chain_technically_complete')
            or any(replay.get(k) is not False for k in ('serving_allowed', 'orders_allowed', 'sql_writes'))):
        raise ValueError('Matched non-serving replay bound to this confirmation required')
    if aware(replay['qualified_at']) > datetime.now(UTC):
        raise ValueError('Future technical qualification')
    candidates = [r for r in dossier['matrix'] if r['local_checks_without_continuity_passed']]
    compared = {r['symbol']: r for r in replay['comparisons']}
    if (len(compared) != len(replay['comparisons']) or set(compared) != {r['symbol'] for r in candidates}
            or replay['candidate_count'] != len(candidates) or replay['matched_count'] != len(candidates)):
        raise ValueError('Candidate populations inconsistent')
    for row in candidates:
        comparison = compared[row['symbol']]
        if (not comparison['matches_current_payload'] or comparison['differences']
                or (comparison['isin'], comparison['mic']) != (row['isin'], row['mic'])):
            raise ValueError('Candidate identity or comparison mismatch')
    # Stream hashes only: no costly XML reparse, no deserialization of model joblib.
    for proof in replay['files']:
        path = scoped_path(proof['path'], root)
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024*1024), b''):
                digest.update(block)
        if digest.hexdigest() != proof['sha256']:
            raise ValueError('Replayed archive changed before release review')
    cutoff = aware(dossier['decision_at'])
    bootstrap = scoped_path(confirmation['protocol']['bootstrap_dir'], root)
    proofs, payloads, errors = {}, [], []
    for folder in (root/'artifacts/fr/operations/fr_corporate_actions_sync', bootstrap/'corporate_actions'):
        selected, problems = observed_payloads(folder, cutoff, root, proofs)
        payloads.extend(selected)
        errors.extend(problems)
    if errors:
        raise ValueError('Actions archive integrity errors')
    sessions = [date.fromisoformat(d) for d in confirmation['daily_assembly']['required_sessions']]
    rows = []
    for identity in candidates:
        actions = effective_events(payloads, identity['symbol'], sessions)
        rows.append({'symbol': identity['symbol'], 'isin': identity['isin'], 'mic': identity['mic'],
            'nominal_currency': identity['nominal_currency'], 'trading_currency': None,
            'trading_currency_interval_qualified': False, 'actions': actions,
            'anchor_payload_matched': True, 'anchor_independent_review': 'PENDING',
            'feature_identity_sessions_before_anchor': [str(d) for d in sessions if str(d) < replay['full_date']],
            'servable': False})
    manifest = prepare_manifest(root=root)
    return {'schema_version': 1, 'market_code': 'FR_EQ', 'status': 'RELEASE_REVIEW_PENDING_NOT_RELEASED',
        'created_at': datetime.now(UTC).isoformat(), 'decision_at': dossier['decision_at'],
        'confirmation_report': str(scoped_path(str(confirmation_report), root).relative_to(root)).replace('\\', '/'),
        'replay_report': str(replay_path.relative_to(root)).replace('\\', '/'),
        'confirmation_sha256': dossier['source_sha256'], 'replay_report_sha256': replay_hash,
        'technical_replay_completed_at': replay['qualified_at'], 'candidate_count': len(rows),
        'provider_action_checks_passed_count': sum(not r['actions']['provider_check_issues'] for r in rows),
        'provider_declared_event_count': sum(len(t['provider_events_in_window']) for r in rows
                                             for t in r['actions']['types'].values()),
        'actions_independently_qualified_count': 0, 'trading_currency_qualified_count': 0,
        'actions_archive_proofs': proofs, 'matrix': rows,
        'model_lineage': {'evidence': manifest['evidence'], 'horizon': manifest['oracle_horizon'],
            'features': manifest['features'], 'transforms': manifest['transforms'],
            'manifest_lineage_readable': True, 'model_executed': False, 'release_approved': False},
        'remaining_gates': ['INDEPENDENT_ANCHOR_REVIEW', 'FULL_FEATURE_WINDOW_IDENTITY_COVERAGE',
            'INDEPENDENT_ACTION_COVERAGE_AND_TRADING_CURRENCY', 'MODEL_FEATURE_PARITY_AND_RELEASE_REVIEW',
            'SPRINT15_OPERATIONAL_RESERVES', 'FROZEN_SHADOW_PROTOCOL'],
        'serving_allowed': False, 'orders_allowed': False, 'sql_writes': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirmation-report', type=Path, required=True)
    parser.add_argument('--replay-report', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    allowed = (ROOT/'artifacts/fr/research/release_review_16g3').resolve()
    if output == allowed or not output.is_relative_to(allowed) or output.exists():
        parser.error('New isolated FR release_review_16g3 folder required')
    result = packet(args.confirmation_report, args.replay_report)
    raw = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
    packet_hash = hashlib.sha256(raw).hexdigest()
    review = {'schema_version': 1, 'market_code': 'FR_EQ', 'packet_sha256': packet_hash,
        'review_kind': 'INDEPENDENT_HUMAN_ATTESTATION', 'reviewer': None,
        'reviewed_at': None, 'independence_declared': False, 'decision': 'PENDING',
        'checks': {key: None for key in REVIEW_CHECKS}, 'reservations': [],
        'serving_allowed': False, 'orders_allowed': False}
    output.mkdir(parents=True, exist_ok=False)
    with (output/'report.json').open('xb') as stream:
        stream.write(raw)
    with (output/'independent_review_template.json').open('x', encoding='utf-8') as stream:
        json.dump(review, stream, ensure_ascii=False, indent=2)
    print(json.dumps({k: result[k] for k in ('status', 'candidate_count',
        'provider_action_checks_passed_count', 'provider_declared_event_count',
        'actions_independently_qualified_count', 'trading_currency_qualified_count')}))


if __name__ == '__main__':
    main()
