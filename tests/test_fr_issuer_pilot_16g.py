import hashlib
import json

import pytest

from service.fr.issuer_pilot_16g import PILOT, checked, metadata_inventory, select_candidates
from service.fr.prediction_contract_16a import aware


def test_exact_population():
    packet = {'market_code': 'FR_EQ', 'matrix': [
        {'symbol': s, 'isin': i, 'mic': 'XPAR'} for s, i in PILOT.items()]}
    assert len(select_candidates(packet)) == 3
    packet['matrix'][0]['isin'] = 'WRONG'
    with pytest.raises(ValueError):
        select_candidates(packet)


def test_missing_population():
    with pytest.raises(ValueError):
        select_candidates({'market_code': 'FR_EQ', 'matrix': []})


def test_hash_tamper(tmp_path):
    path = tmp_path / 'proof.json'
    path.write_text('{}')
    with pytest.raises(ValueError):
        checked(path, '0' * 64)


def fixture_archive(folder, available):
    (folder / 'raw').mkdir(exist_ok=True)
    (folder / 'observations').mkdir(exist_ok=True)
    row = {'identificationsociete_iso_cd_isi': PILOT['AIR.PA'], 'uin_idt_uin': '1',
           'uin_dat_amf': '2026-10-01T10:00:00+00:00'}
    raw = json.dumps({'query_window': ['2026-09-09', '2026-10-07'], 'records': [row]})
    digest = hashlib.sha256(raw.encode()).hexdigest()
    (folder / 'raw' / f'{digest}.json').write_text(raw)
    obs = {'raw_sha256': digest, 'observed_at': available, 'available_at': available,
           'window': ['2026-09-09', '2026-10-07']}
    (folder / 'observations' / 'a.json').write_text(json.dumps(obs))


def inventory(folder):
    return metadata_inventory(folder, cutoff=aware('2026-10-08T07:00:00+00:00'),
                              start='2026-09-09', end='2026-10-07')[0]


def test_post_decision_excluded(tmp_path):
    fixture_archive(tmp_path, '2026-10-08T08:00:00+00:00')
    assert inventory(tmp_path) == []


def test_metadata_never_certifies_document(tmp_path):
    fixture_archive(tmp_path, '2026-10-07T20:00:00+00:00')
    (tmp_path / 'latest.json').write_text('not trusted')
    records = inventory(tmp_path)
    assert len(records) == 1
    assert records[0]['document_read'] is False
    assert records[0]['effective_event_qualified'] is False


def test_repeated_observation_not_duplicate(tmp_path):
    fixture_archive(tmp_path, '2026-10-07T20:00:00+00:00')
    obs = (tmp_path / 'observations' / 'a.json').read_text()
    (tmp_path / 'observations' / 'b.json').write_text(obs)
    assert len(inventory(tmp_path)) == 1
