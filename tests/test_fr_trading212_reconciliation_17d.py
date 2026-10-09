from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal as D

import pytest

from service.fr.broker_contract_17a import FrenchTestIntent
from service.fr.trading212_reconciliation_17d import SyntheticOrderJournal


def intent(key='one'):
    return FrenchTestIntent(key, 1, 'FR0000120321', 'XPAR', 10, D('100'))


def journal():
    j = SyntheticOrderJournal(D('2000'))
    j.register(intent())
    j.begin_dispatch('one')
    return j


def observe(j, status='NEW', filled='0', sequence=0, broker_id='synthetic-1'):
    return j.observe('one', broker_id=broker_id, status=status, filled=D(filled), sequence=sequence)


def test_timeout_never_resends_and_can_reconcile():
    j = journal()
    assert j.submission_timeout('one')['status'] == 'UNKNOWN_SUBMISSION'
    with pytest.raises(ValueError, match='resend'):
        j.begin_dispatch('one')
    assert observe(j)['status'] == 'NEW'


def test_cancel_request_can_race_with_fill():
    j = journal()
    observe(j)
    j.request_cancel('one')
    partial = observe(j, 'PARTIALLY_FILLED', '3', 1)
    assert partial['filled_quantity'] == '3' and partial['remaining_quantity'] == '7'
    cancelled = observe(j, 'CANCELLED', '3', 2)
    assert cancelled['status'] == 'CANCELLED' and cancelled['filled_quantity'] == '3'


def test_fill_can_win_cancel_race():
    j = journal()
    j.request_cancel('one')
    assert observe(j, 'FILLED', '10')['status'] == 'FILLED'


def test_exact_duplicate_receipt_is_idempotent():
    j = journal()
    assert observe(j) == observe(j)


@pytest.mark.parametrize('status,filled', [('FUTURE_UNKNOWN', '0'), ('FILLED', '3'),
    ('PARTIALLY_FILLED', '0'), ('PARTIALLY_FILLED', '10'), ('NEW', '2'),
    ('REJECTED', '1'), ('FILLED', 'NaN'), ('FILLED', 'Infinity'), ('FILLED', '11')])
def test_invalid_receipt_quarantines_without_mutating_fills(status, filled):
    j = journal()
    with pytest.raises(ValueError):
        observe(j, status, filled)
    state = j.snapshot('one')
    assert state['quarantined'] and state['filled_quantity'] == '0'


def test_cumulative_fill_regression_and_old_receipt_require_review():
    for sequence, filled in [(2, '2'), (0, '3')]:
        j = journal()
        observe(j, 'PARTIALLY_FILLED', '3', 1)
        with pytest.raises(ValueError):
            observe(j, 'PARTIALLY_FILLED', filled, sequence)
        assert j.snapshot('one')['filled_quantity'] == '3'


def test_broker_identity_not_rebound():
    j = journal()
    observe(j)
    with pytest.raises(ValueError):
        observe(j, sequence=1, broker_id='other')


def test_one_broker_id_cannot_own_two_intentions():
    j = journal()
    observe(j)
    j.register(intent('two'))
    j.begin_dispatch('two')
    with pytest.raises(ValueError):
        j.observe('two', broker_id='synthetic-1', status='NEW', filled=D('0'), sequence=0)


def test_kill_is_not_cancellation_confirmation_or_position_close():
    j = journal()
    observe(j, 'PARTIALLY_FILLED', '3')
    state = j.kill()[0]
    assert state['status'] == 'PARTIALLY_FILLED'
    assert state['filled_quantity'] == '3' and state['cancel_requested']
    with pytest.raises(ValueError):
        j.register(intent('two'))


def test_terminal_state_change_requires_manual_review():
    j = journal()
    observe(j, 'CANCELLED')
    with pytest.raises(ValueError):
        observe(j, 'FILLED', '10', 1)
    assert j.snapshot('one')['status'] == 'CANCELLED'


def test_concurrent_duplicate_registration_only_one_acceptance():
    j = SyntheticOrderJournal(D('2000'))
    def register(_):
        try:
            j.register(intent())
            return 1
        except ValueError:
            return 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(register, range(8))) == 1


@pytest.mark.parametrize('change', [{'market_code': 'US_EQ'}, {'currency': 'USD'},
                                  {'account_id': 'live'}, {'side': 'sell'}])
def test_cross_market_or_real_account_denied(change):
    j = SyntheticOrderJournal(D('2000'))
    with pytest.raises(ValueError):
        j.register(replace(intent(), **change))


def test_snapshot_mutation_does_not_mutate_journal():
    j = journal()
    state = j.snapshot('one')
    state['filled_quantity'] = '99'
    assert j.snapshot('one')['filled_quantity'] == '0'
