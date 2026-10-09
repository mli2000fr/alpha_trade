import json
from pathlib import Path

import pytest

from service.fr.issuer_pilot_16g import PILOT
from service.fr.pilot_documents_16g import MAX_BYTES, collect, official_url


@pytest.mark.parametrize('url', [
    'http://echanges.dila.gouv.fr/OPENDATA/AMF/MKW/2026/10/FCMKW116486_20261006.pdf',
    'https://evil.example/OPENDATA/AMF/MKW/2026/10/FCMKW116486_20261006.pdf',
    'https://echanges.dila.gouv.fr/OPENDATA/AMF/../secret.pdf',
    'https://user@echanges.dila.gouv.fr/OPENDATA/AMF/MKW/2026/10/FCMKW116486_20261006.pdf',
    'https://echanges.dila.gouv.fr/OPENDATA/AMF/MKW/2026/10/FCMKW116486_20261006.pdf?x=1',
])
def test_reject_unapproved_url(url):
    with pytest.raises(ValueError):
        official_url(url)


def test_exact_mirror():
    url = 'https://fr.ftp.opendatasoft.com/datadila/INFOFI/MKW/2026/10/FCMKW116486_20261006.pdf'
    assert official_url(url) == 'https://echanges.dila.gouv.fr/OPENDATA/AMF/MKW/2026/10/FCMKW116486_20261006.pdf'


def fixture_inventory(root):
    root = root / 'artifacts/fr'
    root.mkdir(parents=True)
    rows = [{'symbol': s, 'isin': i, 'mic': 'XPAR', 'metadata': []} for s, i in PILOT.items()]
    rows[1]['metadata'] = [{'id': '116486_20261006', 'isin': PILOT['OR.PA'],
        'available_at': '2026-10-06T19:30:00+00:00',
        'document_url': 'https://fr.ftp.opendatasoft.com/datadila/INFOFI/MKW/2026/10/FCMKW116486_20261006.pdf'}]
    path = root / 'inventory.json'
    path.write_text(json.dumps({'market_code': 'FR_EQ', 'status': 'PILOT_INVENTORY_NOT_RELEASED',
        'decision_at': '2026-10-08T07:00:00+00:00', 'matrix': rows}), encoding='utf-8')
    return path


def test_receipt_not_backdated_or_released(tmp_path):
    path = fixture_inventory(tmp_path)
    result = collect(path, tmp_path/'artifacts/fr/out', root=tmp_path,
                     fetcher=lambda u: (b'%PDF-fake', {'http_status': 200}))
    assert result['archived'] == 1
    assert not result['serving_allowed'] and not result['actions_independently_qualified']
    doc = result['documents'][0]
    assert doc['document_observed_at'] != doc['available_at']
    assert not doc['document_read'] and not doc['effective_event_qualified']
    assert Path(doc['pdf_path']).read_bytes() == b'%PDF-fake'
    with pytest.raises(ValueError):
        collect(path, tmp_path/'artifacts/fr/out', root=tmp_path)


@pytest.mark.parametrize('raw', [b'<html>error', b'%PDF-' + b'a' * MAX_BYTES], ids=['html', 'oversized'])
def test_invalid_payload_keeps_failure(tmp_path, raw):
    result = collect(fixture_inventory(tmp_path), tmp_path/'artifacts/fr/out', root=tmp_path,
                     fetcher=lambda u: (raw, {}))
    assert result['failed'] == 1 and result['archived'] == 0
    assert result['status'] == 'PARTIAL_DOCUMENT_DOWNLOAD_FAILURE'


def test_identity_mismatch_fails_before_network(tmp_path):
    path = fixture_inventory(tmp_path)
    data = json.loads(path.read_text())
    data['matrix'][1]['metadata'][0]['isin'] = PILOT['SAN.PA']
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        collect(path, tmp_path/'artifacts/fr/out', root=tmp_path,
                fetcher=lambda _: pytest.fail('Network must not be reached'))
