import hashlib
import json
from datetime import datetime, timezone

import pytest

from service.fr import mifir_options_daily as daily
from service.fr import mifir_options_poc as poc
from test_fr_mifir_options_poc import reference, trade, zipped


def setup(monkeypatch):
    monkeypatch.setattr(daily, 'reference_scope', lambda path:
        (2, {'OTHER.PA': ({'isin': 'FR0000120321'}, []),
             'BN.PA': ({'isin': 'FR0000120644'}, [])}, []))
    result = {'persisted_count': 0, 'failed_count': 0}
    return result


def fake_fetch(calls, rows=None, docs=None):
    def fetch(url, limit):
        calls.append(url)
        if url == poc.TRADES_PAGE:
            raw = b'EQUITY_INDEX_DERIVATIVES PREVIOUS_TRADING_DAY value="PAR"'
        elif url == poc.TRADES_URL:
            raw = zipped(rows if rows is not None else [trade()])
        else:
            records = docs if docs is not None else [reference()]
            raw = json.dumps({'response': {'numFound': len(records), 'docs': records}}).encode()
        return raw, {'url': url, 'received_at': '2026-10-06T07:00:00Z',
                     'sha256': hashlib.sha256(raw).hexdigest()}
    return fetch


def collect(tmp_path, result, calls, **kwargs):
    return daily.collect({}, result, root=tmp_path/'collection', identities=tmp_path/'identities',
        clock=datetime(2026, 10, 6, 8, tzinfo=timezone.utc), fetch=fake_fetch(calls, **kwargs))


def test_full_configured_scope_not_pilot_and_idempotence(tmp_path, monkeypatch):
    result = setup(monkeypatch)
    calls = []
    collect(tmp_path, result, calls)
    assert result['requested_count'] == 2
    assert result['received_count'] == result['persisted_count'] == 1
    assert result['coverage']['OTHER.PA']['accepted_trade_rows'] == 1
    assert result['symbols_without_accepted_trade'] == ['BN.PA']
    snapshot = json.loads(__import__('pathlib').Path(result['snapshot_path']).read_text())
    assert snapshot['ml_eligible'] is False
    again = {'persisted_count': 0, 'failed_count': 0}
    collect(tmp_path, again, calls)
    assert again['already_archived'] and again['persisted_count'] == 0
    assert len(list((tmp_path/'collection/snapshots').glob('*.json'))) == 1
    assert len([url for url in calls if url.startswith(poc.REFERENCE_URL)]) == 1


def test_dry_run_no_network_no_writes(tmp_path, monkeypatch):
    result = setup(monkeypatch)
    daily.collect({}, result, root=tmp_path/'absent', identities=tmp_path/'ids', dry_run=True,
                  fetch=lambda *a: pytest.fail('network forbidden'))
    assert result['requested_count'] == 2
    assert not (tmp_path/'absent').exists()


def test_cancelled_trade_is_archived_but_not_counted(tmp_path, monkeypatch):
    result = setup(monkeypatch)
    collect(tmp_path, result, [], rows=[trade(), trade(MmtModificationIndicator='CANC')])
    assert result['received_count'] == 0
    assert result['exclusion_counts']['CANCELLED_ID'] == 2


def test_partial_reference_failure_preserves_raw(tmp_path, monkeypatch):
    result = setup(monkeypatch)
    with pytest.raises(ValueError, match='Incomplete'):
        collect(tmp_path, result, [], docs=[])
    assert list((tmp_path/'collection/objects').iterdir())
    assert list((tmp_path/'collection/attempts').glob('*.json'))


def test_same_day_source_rejected(tmp_path, monkeypatch):
    result = setup(monkeypatch)
    with pytest.raises(ValueError, match='same-day'):
        collect(tmp_path, result, [], rows=[trade(TradingDateTime='2026-10-06T01:00:00Z')])


def test_corrupt_resume_checkpoint_is_blocking(tmp_path, monkeypatch):
    result = setup(monkeypatch)
    collect(tmp_path, result, [])
    checkpoint = next((tmp_path/'collection/checkpoints').rglob('*.json'))
    entry = json.loads(checkpoint.read_text())
    (tmp_path/'collection/objects'/entry['sha256']).write_bytes(b'corruption')
    with pytest.raises(ValueError, match='Corrupted'):
        collect(tmp_path, result, [])


def test_batch_visible_with_common_launcher():
    from pathlib import Path
    from ihm.services.batch_management import load_batch_specs
    specs = load_batch_specs(Path('batch_fr.yaml'))
    spec = next(s for s in specs if s.name == 'fr_options_mifir_trade_sync')
    assert spec.raw_config['status'] == 'ACTIVE_RESEARCH'
    assert spec.provider == 'euronext_mifir_esma_firds'


def test_runner_preserves_failure_counts_and_emits_failed_status(tmp_path, monkeypatch):
    from service.fr import operational_batch_15a as runner
    monkeypatch.setattr(runner, 'OPS', tmp_path/'operations')
    monkeypatch.setattr(runner, 'load_section', lambda *a: {
        'enabled': True, 'status': 'ACTIVE_RESEARCH', 'provider': 'test'})
    def failing(name, cfg, result, **kw):
        result.update(requested_count=294, received_count=12, persisted_count=12)
        raise ValueError('FIRDS incomplete')
    monkeypatch.setattr(runner, '_handle', failing)
    result = runner.run('fr_options_mifir_trade_sync')
    assert result['status'] == 'FAILED'
    assert result['requested_count'] == 294
    assert result['received_count'] == result['persisted_count'] == 12
    assert result['failed_count'] == 1
    assert 'FIRDS' in result['error_message']


def test_archive_checks_receipt_integrity(tmp_path):
    with pytest.raises(ValueError, match='checksum'):
        daily._archive(tmp_path, b'raw', {'sha256': 'wrong'})
