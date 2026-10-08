import copy
from datetime import datetime, UTC
import hashlib
import json

import pytest

from service.fr.qualification_dossier_16g import build, inspect_anchor


@pytest.fixture
def dossier_source(tmp_path):
    archive = tmp_path / 'artifacts/fr'
    archive.mkdir(parents=True)
    state = {'market_code': 'FR_EQ', 'end': '2026-10-07',
             'last_observed_at': '2026-10-08T05:01:00+00:00',
             'historical_continuity_confirmed': False,
             'delta_publication_continuity_confirmed': True,
             'historical_missing_days': ['2026-09-09']}
    raw = json.dumps(state).encode()
    digest = hashlib.sha256(raw).hexdigest()
    master = archive / f'{digest}.json'
    master.write_bytes(raw)
    decision = '2026-10-08T07:00:00+00:00'
    report = {'market_code': 'FR_EQ', 'phase': 'confirm', 'decision_at': decision,
        'audit_at': '2026-10-08T16:00:00+00:00', 'serving_allowed': False,
        'orders_allowed': False, 'sql_writes': False,
        'daily_assembly': {'decision_at': decision, 'universe_count': 2,
            'archive_errors': {'bars': [], 'master': [], 'actions': []},
            'diagnostics': [dict(symbol=s, research_uid=s, features_computed=True,
                missing_sessions=[], reasons=['MASTER_CONTINUITY_UNQUALIFIED'] + reasons)
                for s, reasons in [('ABC.PA', []), ('XYZ.PA', ['UNQUALIFIED_DIV_IN_FEATURE_WINDOW'])]]},
        'reference': {'decision_at': decision, 'selected_coverage_end': '2026-10-07',
            'selected_observed_at': state['last_observed_at'],
            'proofs_sha256': {'artifacts/fr/' + master.name: digest},
            'identities': [dict(symbol=s, research_uid=s, isin='FR_'+s, mic='XPAR',
                nominal_currency='EUR', source_file='DLTINS_test.zip') for s in ['ABC.PA', 'XYZ.PA']]},
        'evidence': {'records': []}}
    path = archive / 'confirmation.json'
    path.write_text(json.dumps(report), encoding='utf-8')
    return tmp_path, path, report, master


def audit(source):
    root, path, _, _ = source
    return build(path, root=root, now=datetime(2026, 10, 8, 18, tzinfo=UTC))


def test_matrix_keeps_local_and_global_qualification_distinct(dossier_source):
    before = dossier_source[1].read_bytes()
    result = audit(dossier_source)
    assert result['universe_count'] == 2
    assert result['local_checks_passed_count'] == 1
    assert result['features_computed_count'] == 2
    assert result['servable_count'] == 0
    assert not result['serving_allowed'] and not result['sql_writes']
    assert all(not r['servable'] and r['global_release_gates'] for r in result['matrix'])
    assert result['matrix'][1]['local_blockers'] == ['UNQUALIFIED_DIV_IN_FEATURE_WINDOW']
    assert result['master_proofs'][0]['historical_missing_days'] == ['2026-09-09']
    assert dossier_source[1].read_bytes() == before


@pytest.mark.parametrize('mutation', ['market', 'serving', 'future', 'cutoff', 'duplicate', 'integrity', 'population'])
def test_invalid_frozen_report_fails_closed(dossier_source, mutation):
    _, path, original, _ = dossier_source
    report = copy.deepcopy(original)
    if mutation == 'market': report['market_code'] = 'US_EQ'
    if mutation == 'serving': report['serving_allowed'] = True
    if mutation == 'future': report['audit_at'] = '2026-10-09T16:00:00+00:00'
    if mutation == 'cutoff': report['reference']['decision_at'] = '2026-10-08T17:00:00+00:00'
    if mutation == 'duplicate': report['daily_assembly']['diagnostics'][1]['symbol'] = 'ABC.PA'
    if mutation == 'integrity': report['daily_assembly']['archive_errors']['bars'] = ['bad_hash']
    if mutation == 'population': report['reference']['identities'].pop()
    path.write_text(json.dumps(report), encoding='utf-8')
    with pytest.raises(ValueError): audit(dossier_source)


def test_tampered_master_proof_rejected(dossier_source):
    dossier_source[3].write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='hash'):
        audit(dossier_source)


@pytest.fixture
def anchor_source(dossier_source, monkeypatch):
    import service.fr.esma_firds_download as download
    import service.fr.esma_firds_history as history
    root = dossier_source[0]
    folder = root / 'artifacts/fr/anchor'
    folder.mkdir()
    names = [f'FULINS_E_20260926_0{i}of02.zip' for i in (1, 2)]
    files = [{'file': name, 'type': 'FULINS_E', 'date': '2026-09-26', 'md5': 'md5'} for name in names]
    (folder / 'index.json').write_text(json.dumps({'full_date': '2026-09-26', 'files': files}), encoding='utf-8')
    (folder / 'download_state.json').write_text(json.dumps({'complete': True, 'failed': [],
        'files': [{'file': n, 'sha256': 'proof'} for n in names]}), encoding='utf-8')
    monkeypatch.setattr(download, '_check', lambda path, md5: {'sha256': 'proof'})
    record = {'event': 'Full', 'isin': 'FR_ABC.PA', 'mic': 'XPAR', 'currency': 'EUR',
              'cfi': 'ESXXXX', 'termination_reported': None}
    monkeypatch.setattr(history, 'archive_records', lambda path, isins, mics:
                        [record] if path.name == names[0] else [])
    return folder, audit(dossier_source), root


def test_full_presence_never_promotes_qualification(anchor_source):
    folder, dossier, root = anchor_source
    result = inspect_anchor(dossier, folder, root=root)
    assert result['unique_pairs_count'] == 1
    assert result['local_candidates_with_unique_pair_count'] == 1
    assert not result['serving_allowed']
    assert all(not row['anchor_qualified'] for row in result['matrix'])


def test_incomplete_full_fragments_rejected(anchor_source):
    folder, dossier, root = anchor_source
    for name in ('index.json', 'download_state.json'):
        value = json.loads((folder / name).read_bytes())
        value['files'].pop()
        (folder / name).write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises(ValueError, match='fragments'):
        inspect_anchor(dossier, folder, root=root)


def test_full_receipt_hash_mismatch_rejected(anchor_source):
    folder, dossier, root = anchor_source
    value = json.loads((folder / 'download_state.json').read_bytes())
    value['files'][0]['sha256'] = 'changed'
    (folder / 'download_state.json').write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises(ValueError, match='hash'):
        inspect_anchor(dossier, folder, root=root)
