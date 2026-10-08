from datetime import UTC, datetime
import hashlib
import json

import pytest

from service.fr.release_review_check_16g import check
from service.fr.release_review_16g3 import REVIEW_CHECKS

NOW = datetime(2026, 10, 8, 20, tzinfo=UTC)


def write(path, value):
    raw = json.dumps(value).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def handoff(tmp_path):
    folder = tmp_path / 'artifacts/fr'
    folder.mkdir(parents=True)
    confirmation_hash = write(folder / 'confirmation.json', {})
    replay_hash = write(folder / 'replay.json', {'files': []})
    model_hash = write(folder / 'model.joblib', {'never': 'deserialized'})
    packet = {'market_code': 'FR_EQ', 'status': 'RELEASE_REVIEW_PENDING_NOT_RELEASED',
        'serving_allowed': False, 'orders_allowed': False, 'sql_writes': False,
        'decision_at': '2026-10-08T07:00:00+00:00', 'created_at': '2026-10-08T17:00:00+00:00',
        'candidate_count': 1, 'matrix': [{'symbol': 'ABC.PA', 'servable': False,
            'feature_identity_sessions_before_anchor': ['2026-09-25'],
            'trading_currency_interval_qualified': False,
            'actions': {'actions_independently_qualified': False}}],
        'model_lineage': {'model_executed': False, 'release_approved': False,
            'evidence': [{'path': 'artifacts/fr/model.joblib', 'sha256': model_hash}]},
        'confirmation_report': 'artifacts/fr/confirmation.json', 'confirmation_sha256': confirmation_hash,
        'replay_report': 'artifacts/fr/replay.json', 'replay_report_sha256': replay_hash,
        'actions_archive_proofs': {}, 'remaining_gates': ['INDEPENDENT_ANCHOR_REVIEW']}
    packet_path = folder / 'packet.json'
    digest = write(packet_path, packet)
    review = {'market_code': 'FR_EQ', 'packet_sha256': digest, 'decision': 'PENDING',
        'serving_allowed': False, 'orders_allowed': False}
    return tmp_path, folder, packet_path, packet, review


def run(handoff, review=None):
    root, folder, path, packet, _ = handoff
    write(path, packet)
    review_path = None
    if review is not None:
        review_path = folder / 'review.json'
        write(review_path, review)
    return check(path, review_path, root=root, now=NOW)


def test_missing_review_and_proofs_are_explicit(handoff):
    result = run(handoff)
    assert result['review_status'] == 'MISSING'
    assert result['evidence_files_verified'] == 3
    assert result['symbols_requiring_trading_currency_proof'] == ['ABC.PA']
    assert result['symbols_requiring_independent_action_proof'] == ['ABC.PA']
    assert result['symbols_requiring_pre_anchor_identity_proof'] == ['ABC.PA']
    assert not result['serving_allowed'] and not result['orders_allowed']


def test_blank_template_is_pending_not_invalid_or_approved(handoff):
    assert run(handoff, handoff[4])['review_status'] == 'PENDING_NOT_ATTESTED'


def test_valid_attestation_never_promotes_other_gates(handoff):
    review = handoff[4]
    review.update(decision='ACCEPT_ANCHOR_FOR_PROSPECTIVE_CONTRACT_ONLY',
        reviewer='Reviewer', reviewed_at='2026-10-08T18:00:00+00:00',
        independence_declared=True, review_kind='INDEPENDENT_HUMAN_ATTESTATION',
        checks={key: True for key in REVIEW_CHECKS})
    result = run(handoff, review)
    assert result['review_status'] == 'ATTESTATION_ENVELOPE_VALID_NOT_RELEASE'
    assert result['symbols_requiring_pre_anchor_identity_proof'] == ['ABC.PA']
    assert not result['serving_allowed'] and not result['independence_verified_by_software']


@pytest.mark.parametrize('mutation', ['packet', 'review_hash', 'early_review', 'model', 'escape', 'duplicate'])
def test_tamper_and_inconsistent_handoff_rejected(handoff, mutation):
    review = handoff[4]
    if mutation == 'packet': handoff[3]['orders_allowed'] = True
    if mutation == 'review_hash': review['packet_sha256'] = 'other'
    if mutation == 'early_review':
        review.update(decision='ACCEPT_ANCHOR_FOR_PROSPECTIVE_CONTRACT_ONLY', reviewer='Person',
            reviewed_at='2026-10-08T16:00:00+00:00', independence_declared=True,
            review_kind='INDEPENDENT_HUMAN_ATTESTATION', checks={k: True for k in REVIEW_CHECKS})
    if mutation == 'model': (handoff[1] / 'model.joblib').write_bytes(b'tampered')
    if mutation == 'escape': handoff[3]['confirmation_report'] = '../outside.json'
    if mutation == 'duplicate': handoff[3]['matrix'] *= 2
    with pytest.raises(ValueError):
        run(handoff, review)
