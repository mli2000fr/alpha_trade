from datetime import date
import json
from pathlib import Path

import pytest

from service.fr import anchor_replay_16g2 as module
from service.fr.qualification_dossier_16g import read_proof


def record(name='ABC', event='Full'):
    return dict(isin='FR_ABC', mic='XPAR', event=event, currency='EUR', cfi='ESXXXX',
                name=name, first_trade_reported='2000-01-01', termination_reported=None,
                publication_from_reported='2026-09-26')


def version(name='ABC', event='Full'):
    return dict(record(name, event), asof_from='2026-09-26', asof_to=None)


def test_semantic_payload_matches_despite_reset_full_provenance():
    history = {('FR_ABC', 'XPAR'): [version()]}
    master = {'symbols': [{'isin': 'FR_ABC', 'market_reference': [
        {'mic': 'XPAR', 'versions': [dict(version(event='ModfdRcrd'), asof_from='2020-01-01')]}]}]}
    rows = module.compare(history, master, [{'isin': 'FR_ABC', 'mic': 'XPAR', 'symbol': 'ABC.PA'}], date(2026, 9, 28))
    assert rows[0]['matches_current_payload']
    assert not rows[0]['servable']


@pytest.fixture
def replay_case(tmp_path, monkeypatch):
    root = tmp_path
    full = root / 'artifacts/fr/full'
    historical = root / 'artifacts/fr/history'
    daily = root / 'artifacts/fr/operations/master'
    for p in (full, historical, daily / 'versions'):
        p.mkdir(parents=True)
    def write(path, value):
        path.write_text(json.dumps(value), encoding='utf-8')
    full_file = dict(file='FULINS_E_20260926_01of01.zip', date='2026-09-26', type='FULINS_E', md5='md5')
    write(full / 'index.json', {'files': [full_file]})
    deltas = [dict(file=f'DLTINS_202609{day}_01of01.zip', date=f'2026-09-{day}', type='DLTINS',
        md5='md5', url=f'https://firds.esma.europa.eu/firds/DLTINS_202609{day}_01of01.zip') for day in (27, 28)]
    write(historical / 'index.json', {'files': deltas[:1]})
    current = {'market_code': 'FR_EQ', 'files': deltas[1:], 'historical_missing_days': ['2018-01-09'],
        'symbols': [{'isin': 'FR_ABC', 'market_reference': [{'mic': 'XPAR', 'versions': [version()]}]}]}
    master_path = daily / 'versions/state.json'
    write(master_path, current)
    digest = read_proof(master_path)[1]
    dossier = {'reference_coverage_end': '2026-09-28', 'reference_observed_at': '2026-09-29T05:00:00+00:00',
        'decision_at': '2026-09-29T07:00:00+00:00', 'source_sha256': 'confirmation_hash',
        'master_proofs': [{'path': str(master_path.relative_to(root)), 'end': '2026-09-28',
            'observed_at': '2026-09-29T05:00:00+00:00', 'sha256': digest}],
        'matrix': [{'symbol': 'ABC.PA', 'isin': 'FR_ABC', 'mic': 'XPAR',
                    'local_checks_without_continuity_passed': True}]}
    monkeypatch.setattr(module, 'build', lambda *args, **kwargs: dossier)
    monkeypatch.setattr(module, 'inspect_anchor', lambda *args, **kwargs: {'full_date': '2026-09-26'})
    monkeypatch.setattr(module, '_check', lambda *args, **kwargs: {'sha256': 'archive', 'official_md5_available': True})
    monkeypatch.setattr(module, 'archive_records', lambda path, *args:
                        [record()] if path.name.startswith('FULINS') else [])
    return root, full, historical, dossier, current, master_path


def run_case(case):
    root, full, historical, *_ = case
    return module.replay(root / 'artifacts/fr/confirmation.json', full, historical, root=root)


def test_complete_chain_matches_without_enabling_release(replay_case):
    result = run_case(replay_case)
    assert result['status'] == 'ANCHORED_REFERENCE_MATCHED_NOT_RELEASED'
    assert result['archive_count'] == 3 and result['delta_archive_count'] == 2
    assert result['matched_count'] == 1
    assert result['inherited_historical_missing_days'] == ['2018-01-09']
    assert result['post_full_chain_technically_complete']
    assert not result['historical_continuity_confirmed']
    assert not result['serving_allowed'] and not result['orders_allowed']
    assert result['prospective_contract_draft']['status'] == 'DRAFT_NOT_APPROVED'


def test_missing_delta_day_fails_closed(replay_case):
    path = replay_case[2] / 'index.json'
    path.write_text('{"files": []}', encoding='utf-8')
    with pytest.raises(ValueError, match='Missing Delta'):
        run_case(replay_case)


def test_changed_master_is_rejected(replay_case):
    replay_case[5].write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='changed'):
        run_case(replay_case)


def test_semantic_difference_keeps_replay_reserved(replay_case, monkeypatch):
    monkeypatch.setattr(module, 'archive_records', lambda path, *args:
                        [record(name='OTHER')] if path.name.startswith('FULINS') else [])
    result = run_case(replay_case)
    assert result['status'] == 'ANCHORED_REPLAY_RESERVED'
    assert result['mismatch_count'] == 1
    assert result['comparisons'][0]['differences'] == ['FIELD_DIFF:name']


def test_event_without_prior_is_not_qualified(replay_case, monkeypatch):
    monkeypatch.setattr(module, 'archive_records', lambda path, *args:
        [record(event='ModfdRcrd')] if path.name.startswith('DLTINS_20260927') else [])
    result = run_case(replay_case)
    assert result['status'] == 'ANCHORED_REPLAY_RESERVED'
    assert any(a['type'] == 'event_without_prior_record' for a in result['anomalies'])


def test_tampered_daily_archive_hash_rejected(replay_case):
    master = replay_case[4]
    master['files'][0]['sha256'] = 'wrong'
    replay_case[5].write_text(json.dumps(master), encoding='utf-8')
    replay_case[3]['master_proofs'][0]['sha256'] = read_proof(replay_case[5])[1]
    with pytest.raises(ValueError, match='SHA-256'):
        run_case(replay_case)


def test_incomplete_delta_fragment_rejected(replay_case):
    path = replay_case[2] / 'index.json'
    value = json.loads(path.read_bytes())
    value['files'][0]['file'] = 'DLTINS_20260927_01of02.zip'
    value['files'][0]['url'] = 'https://firds.esma.europa.eu/firds/DLTINS_20260927_01of02.zip'
    path.write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises(ValueError, match='Fragments'):
        run_case(replay_case)


def test_duplicate_current_pair_is_rejected(replay_case):
    master = replay_case[4]
    master['symbols'].append(master['symbols'][0])
    replay_case[5].write_text(json.dumps(master), encoding='utf-8')
    replay_case[3]['master_proofs'][0]['sha256'] = read_proof(replay_case[5])[1]
    with pytest.raises(ValueError, match='Duplicate current'):
        run_case(replay_case)


def test_terminal_event_cannot_match_as_active_candidate(replay_case, monkeypatch):
    monkeypatch.setattr(module, 'archive_records', lambda path, *args:
        [record()] if path.name.startswith('FULINS') else
        [record(event='TermntdRcrd')] if path.name.startswith('DLTINS_20260927') else [])
    result = run_case(replay_case)
    assert result['status'] == 'ANCHORED_REPLAY_RESERVED'
    assert 'TERMINAL_EVENT' in result['comparisons'][0]['differences']


def test_prospective_contract_remains_explicitly_draft_and_disabled():
    path = Path(__file__).parents[1] / 'config/research_fr/prospective_anchor_16g2_draft.json'
    value = json.loads(path.read_bytes())
    assert value['status'] == 'DRAFT_NOT_APPROVED'
    assert value['market_code'] == 'FR_EQ'
    assert value['old_historical_continuity_boolean_must_remain_false']
    assert not any(value[k] for k in ('serving_allowed', 'orders_allowed', 'sql_writes', 'model_refit_allowed'))
