from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal as D
import os
import subprocess
import sys

import pytest

from service.fr.broker_contract_17a import FrenchTestIntent
from service.fr.trading212_durable_17e import DurableSyntheticJournal, FakeTransport, JournalBlocked


def intent(key='one'):
    return FrenchTestIntent(key, 1, 'FR0000120321', 'XPAR', 10, D('100'))


def open_journal(root, limit='2000'):
    return DurableSyntheticJournal(root=root, directory='artifacts/fr/synthetic',
                                   max_intent_notional_eur=D(limit))


def test_restart_preserves_fill_and_duplicate_rejection(tmp_path):
    with open_journal(tmp_path) as j:
        j.register(intent())
        j.submit_fake('one', FakeTransport())
        j.observe('one', broker_id='fake-one', status='PARTIALLY_FILLED', filled='3', sequence=1)
    with open_journal(tmp_path) as j:
        assert j.snapshot('one')['filled_quantity'] == '3'
        with pytest.raises(ValueError):
            j.register(intent())
        transport = FakeTransport()
        with pytest.raises(ValueError):
            j.submit_fake('one', transport)
        assert transport.calls == 0


@pytest.mark.parametrize('outcome', ['crash', 'timeout'])
def test_uncertain_dispatch_never_resent_after_restart(tmp_path, outcome):
    with open_journal(tmp_path) as j:
        j.register(intent())
        if outcome == 'crash':
            with pytest.raises(SystemExit):
                j.submit_fake('one', FakeTransport(outcome))
        else:
            j.submit_fake('one', FakeTransport(outcome))
    with open_journal(tmp_path) as j:
        assert j.snapshot('one')['status'] == 'UNKNOWN_SUBMISSION'
        with pytest.raises(ValueError):
            j.submit_fake('one', FakeTransport())
        j.observe('one', broker_id='fake-one', status='NEW', filled='0', sequence=0)


def test_kill_and_quarantine_survive_restart(tmp_path):
    with open_journal(tmp_path) as j:
        j.register(intent())
        j.submit_fake('one', FakeTransport())
        with pytest.raises(ValueError):
            j.observe('one', broker_id='fake-one', status='ALIEN', filled='0', sequence=1)
        j.kill()
    with open_journal(tmp_path) as j:
        assert j.snapshot('one')['quarantined']
        assert j.snapshot('one')['cancel_requested']
        with pytest.raises(ValueError):
            j.register(intent('two'))


def test_single_writer_lock_and_release(tmp_path):
    with open_journal(tmp_path):
        with pytest.raises(JournalBlocked, match='writer'):
            open_journal(tmp_path)
    with open_journal(tmp_path):
        pass


@pytest.mark.parametrize('corruption', ['partial', 'altered', 'empty'])
def test_corrupt_journal_fails_closed_without_repair(tmp_path, corruption):
    with open_journal(tmp_path) as j:
        j.register(intent())
    path = tmp_path / 'artifacts/fr/synthetic/events.jsonl'
    raw = path.read_bytes()
    raw = raw[:-2] if corruption == 'partial' else (
        raw.replace(b'2000', b'2999') if corruption == 'altered' else b'')
    path.write_bytes(raw)
    with pytest.raises(JournalBlocked):
        open_journal(tmp_path)
    assert path.read_bytes() == raw


def test_configuration_cannot_change_on_restart(tmp_path):
    with open_journal(tmp_path):
        pass
    with pytest.raises(JournalBlocked, match='context'):
        open_journal(tmp_path, '3000')


def test_persistence_failure_prevents_transport_call(tmp_path, monkeypatch):
    with open_journal(tmp_path) as j:
        j.register(intent())
        def fail(_):
            raise OSError('Synthetic disk failure')
        monkeypatch.setattr(os, 'fsync', fail)
        transport = FakeTransport()
        with pytest.raises(JournalBlocked, match='persistence'):
            j.submit_fake('one', transport)
        assert transport.calls == 0
        with pytest.raises(JournalBlocked):
            j.snapshot('one')


def test_no_arbitrary_transport_or_real_route(tmp_path):
    class Dangerous(FakeTransport):
        def submit(self, _):
            raise AssertionError('Must not be invoked')
    with open_journal(tmp_path) as j:
        j.register(intent())
        with pytest.raises(JournalBlocked, match='FakeTransport'):
            j.submit_fake('one', Dangerous())
        assert not j.snapshot('one')['dispatch_attempted_synthetic']


def test_concurrent_registration_persists_once(tmp_path):
    with open_journal(tmp_path) as j:
        def register(_):
            try:
                j.register(intent())
                return 1
            except ValueError:
                return 0
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert sum(pool.map(register, range(8))) == 1
    with open_journal(tmp_path) as j:
        assert j.snapshot('one')['requested_quantity'] == '10'


def test_real_process_death_releases_lock_and_blocks_resend(tmp_path):
    # Child exits without finally/close after the durable pre-dispatch record.
    code = '''
import os,sys
from pathlib import Path
from decimal import Decimal as D
from service.fr.trading212_durable_17e import DurableSyntheticJournal
from service.fr.broker_contract_17a import FrenchTestIntent
j=DurableSyntheticJournal(root=Path(sys.argv[1]),directory='artifacts/fr/synthetic',max_intent_notional_eur=D('2000'))
j.register(FrenchTestIntent('one',1,'FR0000120321','XPAR',10,D('100')))
j._change({'op':'begin_dispatch','intent_id':'one'})
os._exit(17)
'''
    child = subprocess.run([sys.executable, '-c', code, str(tmp_path)], capture_output=True, timeout=30)
    assert child.returncode == 17, child.stderr.decode(errors='replace')
    with open_journal(tmp_path) as j:
        assert j.snapshot('one')['status'] == 'UNKNOWN_SUBMISSION'
        with pytest.raises(ValueError):
            j.submit_fake('one', FakeTransport())


def test_scope_outside_fr_denied(tmp_path):
    with pytest.raises(ValueError, match='outside'):
        DurableSyntheticJournal(root=tmp_path, directory='artifacts/us/journal',
                                max_intent_notional_eur=D('2000'))
