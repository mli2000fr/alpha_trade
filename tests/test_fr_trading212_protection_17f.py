from dataclasses import replace
from decimal import Decimal as D
import pytest

from service.fr.trading212_protection_17f import ExitLeg, audit_protection, replacement_preflight, readiness


def leg(kind='STOP', requested='10', filled='0', status='NEW', broker_id='stop', **kw):
    return ExitLeg(broker_id, kind, D(requested), D(filled), status, **kw)


def audit(legs, held='10', entry='10', **kw):
    return audit_protection(entry_filled=D(entry), position_quantity=D(held), legs=legs,
        position_reconciled=kw.get('position_reconciled', True), entry_terminal=kw.get('entry_terminal', True))


def test_single_stop_consistency_does_not_qualify_broker_or_price():
    result = audit([leg()])
    assert result['status'] == 'CONSISTENT_SYNTHETIC_ONLY'
    assert not result['orders_allowed'] and not result['stop_price_guaranteed']
    assert not result['broker_protection_qualified']


def test_two_full_independent_exits_are_not_oco():
    result = audit([leg(), leg('LIMIT_TP', broker_id='tp')])
    assert 'INDEPENDENT_EXITS_NOT_ATOMIC_OCO' in result['reasons']
    assert 'POTENTIAL_EXIT_QUANTITY_EXCEEDS_POSITION' in result['reasons']


def test_splitting_quantity_does_not_create_full_stop_coverage():
    result = audit([leg(requested='5'), leg('LIMIT_TP', requested='5', broker_id='tp')])
    assert 'STOP_MARKET_COVERAGE_INCOMPLETE' in result['reasons']
    assert 'INDEPENDENT_EXITS_NOT_ATOMIC_OCO' in result['reasons']


@pytest.mark.parametrize('cancel_requested', [False, True])
def test_tp_fill_before_stop_cancel_still_exposes_remaining_position(cancel_requested):
    result = audit([leg(cancel_requested=cancel_requested),
                    leg('LIMIT_TP', filled='4', status='PARTIALLY_FILLED', broker_id='tp')], held='6')
    assert result['potential_exit_quantity'] == '16'
    assert 'POTENTIAL_EXIT_QUANTITY_EXCEEDS_POSITION' in result['reasons']


def test_stop_and_tp_both_filled_detects_oversell():
    result = audit([leg(filled='10', status='FILLED'),
                    leg('LIMIT_TP', filled='10', status='FILLED', broker_id='tp')], held='0')
    assert 'OVERSOLD_SYNTHETIC_POSITION' in result['reasons']


def test_confirmed_cancel_retains_partial_fills():
    result = audit([leg(filled='3', status='CANCELLED')], held='7')
    assert result['exit_filled'] == '3'
    assert result['potential_exit_quantity'] == '0'
    assert 'STOP_MARKET_COVERAGE_INCOMPLETE' in result['reasons']


@pytest.mark.parametrize('status', ['CANCELLING', 'UNKNOWN_SUBMISSION', 'NEW'])
def test_no_replace_before_confirmed_cancel(status):
    result = replacement_preflight(entry_filled=D('10'), position_quantity=D('10'),
        legs=[leg(status=status, cancel_requested=True)], old_broker_id='stop',
        position_reconciled=True, entry_terminal=True)
    assert result['replacement_quantity'] is None
    assert 'OLD_STOP_NOT_CONFIRMED_CANCELLED' in result['reasons']


def test_replacement_uses_residual_after_cancel_race_not_original_quantity():
    result = replacement_preflight(entry_filled=D('10'), position_quantity=D('7'),
        legs=[leg(status='CANCELLED', filled='3')], old_broker_id='stop',
        position_reconciled=True, entry_terminal=True)
    assert result['replacement_quantity'] == '7'
    assert result['unprotected_gap'] and not result['atomic_replace_qualified']
    assert not result['orders_allowed']


@pytest.mark.parametrize('flag', ['position_reconciled', 'entry_terminal'])
def test_unreconciled_position_or_pending_entry_blocks(flag):
    assert audit([leg()], **{flag: False})['status'] == 'BLOCKED_SYNTHETIC_REVIEW'


def test_replacement_blocked_if_tp_still_active():
    result = replacement_preflight(entry_filled=D('10'), position_quantity=D('10'),
        legs=[leg(status='CANCELLED'), leg('LIMIT_TP', broker_id='tp')], old_broker_id='stop',
        position_reconciled=True, entry_terminal=True)
    assert 'OTHER_EXIT_MAY_EXECUTE' in result['reasons']


def test_stop_limit_not_substituted_for_guaranteed_stop_market():
    result = audit([leg('STOP_LIMIT')])
    assert 'STOP_LIMIT_EXECUTION_NOT_GUARANTEED' in result['reasons']


def test_closed_position_with_active_stop_is_blocked():
    result = audit([leg(), leg('LIMIT_TP', filled='10', status='FILLED', broker_id='tp')], held='0')
    assert 'POTENTIAL_EXIT_QUANTITY_EXCEEDS_POSITION' in result['reasons']


def test_repeated_identity_not_double_counted():
    with pytest.raises(ValueError, match='Duplicate'):
        audit([leg(), leg()])


@pytest.mark.parametrize('change', [{'filled': D('NaN')}, {'requested': D('-1')},
    {'status': 'ALIEN'}, {'status': 'FILLED'}, {'filled': D('1')}, {'kind': 'NATIVE_OCO'}])
def test_invalid_leg_rejected(change):
    with pytest.raises(ValueError):
        audit([replace(leg(), **change)])


def test_no_position_never_creates_replacement():
    result = replacement_preflight(entry_filled=D('10'), position_quantity=D('0'),
        legs=[leg(status='CANCELLED', filled='10')], old_broker_id='stop',
        position_reconciled=True, entry_terminal=True)
    assert 'NO_RESIDUAL_LONG_POSITION' in result['reasons']


def test_readiness_never_promotes_api_documentation_to_behavior_proof():
    result = readiness()
    assert result['stop_endpoint_documented']
    assert not result['demo_behavior_tested'] and not result['orders_allowed']


@pytest.mark.parametrize('status', ['REPLACING', 'REPLACED'])
def test_replacement_chain_never_assumed_complete(status):
    assert 'REPLACEMENT_CHAIN_NOT_QUALIFIED' in audit([leg(status=status)])['reasons']
