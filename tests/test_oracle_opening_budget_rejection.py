from dataclasses import replace

import pytest

from tests.test_oracle_portfolio_ledger import setup, decide, D1, D2


def opening_order(*, reject):
    ledger, session = setup()
    ledger.config.reject_constrained_replay_entries = reject
    ledger.begin_day(D1)
    orders = [e for e in decide(ledger, session, D1) if e.approved_shares > 0]
    ledger.finish_day()
    ledger.begin_day(D2)
    return ledger, orders


def test_default_strict_contract_still_errors_on_unaffordable_quantity():
    ledger, orders = opening_order(reject=False)
    ledger.state.settled_cash = 1.
    with pytest.raises(ValueError, match='Replay quantity clipped'):
        ledger.execute_approved(orders, execution_config=ledger.config.exec_config)
    assert ledger.failed
    assert not ledger.state.positions


def test_whole_order_rejection_keeps_cash_and_never_creates_protection_or_fill():
    ledger, orders = opening_order(reject=True)
    ledger.state.settled_cash = 1.
    phase4, opened = ledger.execute_approved(orders, execution_config=ledger.config.exec_config)
    assert not opened and phase4.signals_df.empty
    assert not ledger.state.positions and not ledger.protections
    assert ledger.state.settled_cash == 1.
    assert not ledger.failed
    audit = ledger.execution_audits[-1]
    assert audit['hypothetical_fills_not_committed'] == []
    assert audit['phase3_attempts_rejected_at_portfolio_commit'] == ['FIXTURE']
    rejection = audit['explicit_entry_rejections'][0]
    assert rejection['rejection_reason'] == 'approved_quantity_exceeds_opening_constraints'
    assert rejection['policy'] == 'reject_whole_order_no_resize'
    ledger.mark_close()
    assert ledger.snapshot().positions == [] or len(ledger.snapshot().positions) == 0


def test_rejection_does_not_prevent_later_affordable_order_or_resize_it():
    ledger, orders = opening_order(reject=True)
    ledger.state.settled_cash = 200.
    for frame in (ledger.opens, ledger.close, ledger.high, ledger.low, ledger.volume, ledger.adv):
        frame['SMALL'] = frame['FIXTURE']
    ledger.sectors['SMALL'] = 'Technology'
    large = replace(orders[0], approved_shares=100.)
    small = replace(orders[0], symbol='SMALL', approved_shares=1.)
    _, opened = ledger.execute_approved([large, small], execution_config=ledger.config.exec_config)
    assert opened == ['SMALL']
    assert ledger.state.positions['SMALL'].quantity == 1.
    assert 0 < ledger.state.settled_cash < 100.
    assert ledger.protections['SMALL'].signals_df.filled_qty.iloc[0] == 1.
    assert len(ledger.execution_audits[-1]['explicit_entry_rejections']) == 1


def test_costs_alone_can_make_an_order_unaffordable():
    ledger, orders = opening_order(reject=True)
    ledger.state.settled_cash = 100.
    _, opened = ledger.execute_approved([replace(orders[0], approved_shares=1.)],
        execution_config=ledger.config.exec_config)
    assert not opened
    assert ledger.state.settled_cash == 100.
    assert ledger.execution_audits[-1]['explicit_entry_rejections'][0]['effective_unit_cost'] > 100.
