import hashlib
import json

import pytest

from service.inpi.files import atomic
from service.fr.consensus_revision_compare import compare


def observation(folder, stamp, avg=12, target=400):
    payload = {'info': {'targetMeanPrice': target}, 'tables': {'get_earnings_estimate': {'avg': {'0y': avg}}}}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    digest = hashlib.sha256(raw).hexdigest()
    obj = folder/'objects'/f'{digest}.json'
    atomic(obj, payload)
    atomic(folder/'observations/OR.PA/one.json', {'symbol': 'OR.PA', 'reference_identity': {'isin': 'FR0000120321'},
           'identity_review': {'isin': 'FR0000120321'}, 'identity_qualified': True,
           'object_path': str(obj), 'source_sha256': digest, 'observed_at': stamp, 'available_at': stamp})
    atomic(folder/'report.json', {'status': 'SUCCESS_RESEARCH_ONLY', 'persisted_count': 1})


def test_different_days_detect_delta_and_missing(tmp_path):
    a, b = tmp_path/'a', tmp_path/'b'
    observation(a, '2026-10-05T20:00:00+00:00')
    observation(b, '2026-10-06T20:00:00+00:00', avg=13, target=None)
    output = compare(a, b)
    rows = {r['field']: r for r in output['symbols']['OR.PA']['changes']}
    assert rows['/tables/get_earnings_estimate/avg/0y']['delta'] == 1
    assert rows['/info/targetMeanPrice']['kind'] == 'COVERAGE_CHANGE'
    assert output['ml_eligible'] is False


def test_same_paris_date_refused_even_different_utc_days(tmp_path):
    a, b = tmp_path/'a', tmp_path/'b'
    observation(a, '2026-10-05T23:00:00+00:00')
    observation(b, '2026-10-06T01:00:00+00:00')
    with pytest.raises(ValueError, match='dates Paris'):
        compare(a, b)


def test_identical_values_are_not_revision(tmp_path):
    a, b = tmp_path/'a', tmp_path/'b'
    observation(a, '2026-10-05T20:00:00+00:00')
    observation(b, '2026-10-06T20:00:00+00:00')
    assert compare(a, b)['symbols']['OR.PA']['changed_fields'] == 0


def test_corrupt_object_refused(tmp_path):
    a, b = tmp_path/'a', tmp_path/'b'
    observation(a, '2026-10-05T20:00:00+00:00')
    observation(b, '2026-10-06T20:00:00+00:00')
    atomic(next((b/'objects').glob('*.json')), {'tampered': True})
    with pytest.raises(ValueError, match='corrompu'):
        compare(a, b)
