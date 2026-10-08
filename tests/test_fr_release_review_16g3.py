import copy
from datetime import UTC, date, datetime
import hashlib
import json

import pytest

from service.fr import release_review_16g3 as module


SESSIONS = [date(2026, 10, 5), date(2026, 10, 6)]
NOW = datetime(2026, 10, 8, 18, tzinfo=UTC)


def payload(kind, rows=(), *, stamp='2026-10-07T10:00:00+00:00', window=None):
    return {'raw': {'symbol': 'ABC.PA', 'kind': kind, 'rows': list(rows),
                    'window': window or ['2026-10-05', '2026-10-06']},
            'time': datetime.fromisoformat(stamp), 'observed': datetime.fromisoformat(stamp),
            'path': kind + stamp, 'observation': {'raw_sha256': 'hash'}}


def test_empty_provider_declarations_never_certify_independent_absence():
    result = module.effective_events([payload('div'), payload('splits')], 'ABC.PA', SESSIONS)
    assert result['provider_check_issues'] == []
    assert not result['actions_independently_qualified']
    assert all(not item['absence_independently_proved'] for item in result['types'].values())
    assert all(item['supporting_observations'] for item in result['types'].values())


def test_newer_provider_correction_replaces_prior_event():
    event = {'date': '2026-10-05', 'value': 1.0}
    items = [payload('div', [event]), payload('splits'),
             payload('div', stamp='2026-10-07T11:00:00+00:00')]
    result = module.effective_events(items, 'ABC.PA', SESSIONS)
    assert result['types']['div']['provider_events_in_window'] == []
    assert len(result['types']['div']['supporting_observations']) == 2
    assert result['provider_check_issues'] == []


def test_effective_event_and_missing_coverage_remain_reserved():
    event = {'date': '2026-10-05', 'value': 1.0}
    result = module.effective_events([payload('div', [event])], 'ABC.PA', SESSIONS)
    assert result['types']['div']['provider_events_in_window'] == [event]
    assert set(result['provider_check_issues']) == {
        'UNQUALIFIED_DIV_IN_FEATURE_WINDOW', 'INCOMPLETE_SPLITS_OBSERVED_COVERAGE'}


def test_ambiguous_provider_corrections_fail_closed():
    with pytest.raises(ValueError, match='ambiguous'):
        module.effective_events([payload('div'), payload('div', [{'date': '2026-10-05'}])],
                                'ABC.PA', SESSIONS)


def review():
    return {'market_code': 'FR_EQ', 'packet_sha256': 'packet', 'serving_allowed': False,
            'orders_allowed': False, 'review_kind': 'INDEPENDENT_HUMAN_ATTESTATION',
            'independence_declared': True, 'reviewer': 'Independent reviewer',
            'reviewed_at': '2026-10-08T17:00:00+00:00',
            'decision': 'ACCEPT_ANCHOR_FOR_PROSPECTIVE_CONTRACT_ONLY',
            'checks': {key: True for key in module.REVIEW_CHECKS}}


def test_valid_attestation_does_not_grant_release_or_verify_person():
    result = module.validate_review(review(), 'packet', now=NOW)
    assert result['status'] == 'ATTESTATION_ENVELOPE_VALID_NOT_RELEASE'
    assert not result['serving_allowed'] and not result['orders_allowed']
    assert not result['identity_and_independence_verified_by_software']


@pytest.mark.parametrize('field,value', [
    ('market_code', 'US_EQ'), ('packet_sha256', 'other'), ('serving_allowed', True),
    ('orders_allowed', True), ('review_kind', 'AUTOMATIC'), ('reviewer', ' '),
    ('independence_declared', False), ('decision', 'PENDING'),
    ('reviewed_at', '2026-10-09T17:00:00+00:00'), ('reviewed_at', '2026-10-08T17:00:00'),
    ('checks', {}),
])
def test_invalid_attestation_rejected(field, value):
    item = review()
    item[field] = value
    with pytest.raises(ValueError):
        module.validate_review(item, 'packet', now=NOW)


def test_review_cannot_predate_packet():
    with pytest.raises(ValueError, match='predates'):
        module.validate_review(review(), 'packet', now=NOW,
                               packet_created_at='2026-10-08T17:30:00+00:00')


@pytest.fixture
def source(tmp_path, monkeypatch):
    folder = tmp_path / 'artifacts/fr'
    folder.mkdir(parents=True)
    confirmation = folder / 'confirmation.json'
    confirmation.write_text(json.dumps({'protocol': {'bootstrap_dir': 'artifacts/fr/bootstrap'},
        'daily_assembly': {'required_sessions': [str(day) for day in SESSIONS]}}), encoding='utf-8')
    archive = folder / 'archive.zip'
    archive.write_bytes(b'archive')
    replay = {'market_code': 'FR_EQ', 'status': 'ANCHORED_REFERENCE_MATCHED_NOT_RELEASED',
        'source_confirmation_sha256': 'confirmation_hash', 'decision_at': '2026-10-08T07:00:00+00:00',
        'anomalies': [], 'mismatch_count': 0, 'post_full_chain_technically_complete': True,
        'serving_allowed': False, 'orders_allowed': False, 'sql_writes': False,
        'qualified_at': '2026-10-07T17:00:00+00:00', 'full_date': '2026-09-26',
        'candidate_count': 1, 'matched_count': 1,
        'comparisons': [{'symbol': 'ABC.PA', 'isin': 'FR000ABC', 'mic': 'XPAR',
                         'matches_current_payload': True, 'differences': {}}],
        'files': [{'path': 'artifacts/fr/archive.zip', 'sha256': hashlib.sha256(b'archive').hexdigest()}]}
    replay_path = folder / 'replay.json'
    dossier = {'source_sha256': 'confirmation_hash', 'decision_at': replay['decision_at'],
        'matrix': [{'symbol': 'ABC.PA', 'isin': 'FR000ABC', 'mic': 'XPAR',
                    'nominal_currency': 'EUR', 'local_checks_without_continuity_passed': True}]}
    monkeypatch.setattr(module, 'build', lambda *a, **kw: copy.deepcopy(dossier))
    monkeypatch.setattr(module, 'observed_payloads', lambda *a: ([], []))
    monkeypatch.setattr(module, 'prepare_manifest', lambda **kw: {
        'evidence': {'artifact': 'sha'}, 'oracle_horizon': 5, 'features': ['f'], 'transforms': []})
    return tmp_path, confirmation, replay_path, replay, archive


def calculate(source):
    root, confirmation, path, replay, _ = source
    path.write_text(json.dumps(replay), encoding='utf-8')
    return module.packet(confirmation, path, root=root)


def test_packet_keeps_unknown_currency_and_model_unexecuted(source):
    result = calculate(source)
    assert result['matrix'][0]['trading_currency'] is None
    assert not result['matrix'][0]['servable']
    assert not result['model_lineage']['model_executed']
    assert result['actions_independently_qualified_count'] == 0
    assert all(result[key] is False for key in ('sql_writes', 'orders_allowed', 'serving_allowed'))


@pytest.mark.parametrize('mutation', ['source', 'population', 'identity', 'sql', 'archive'])
def test_packet_rejects_inconsistent_evidence(source, mutation):
    replay = source[3]
    if mutation == 'source': replay['source_confirmation_sha256'] = 'other'
    if mutation == 'population': replay['candidate_count'] = 2
    if mutation == 'identity': replay['comparisons'][0]['isin'] = 'OTHER'
    if mutation == 'sql': replay['sql_writes'] = True
    if mutation == 'archive': source[4].write_bytes(b'tampered')
    with pytest.raises(ValueError):
        calculate(source)


def test_packet_rejects_action_archive_errors(source, monkeypatch):
    monkeypatch.setattr(module, 'observed_payloads', lambda *a: ([], ['hash mismatch']))
    with pytest.raises(ValueError, match='Actions archive'):
        calculate(source)
