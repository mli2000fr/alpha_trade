from datetime import date

import pytest

from execution_engine.winner_reconciliation import defer_unsubmitted_campaign_targets
from risk_management.daily_reconciliation import DailyReconciliation


def evidence():
    target = dict(symbol='P', quantity=1., side='long')
    state = dict(exec_run_id='exec', risk_run_id='risk', account_id='default', broker_mode='paper',
        symbol='P', status='PENDING', admission='STEP11_APPROVED_RECHECK_REQUIRED',
        lots=[], operations=[], parents={}, initial_attempted=False, first_fill_at=None)
    return target, state


def run(target, state):
    return defer_unsubmitted_campaign_targets([target], [{'state': state}], exec_run_id='exec',
        risk_run_id='risk', account_id='default', broker_mode='paper')


def test_pending_plan_without_order_is_not_a_missing_holding():
    target, state = evidence()
    expected, pending = run(target, state)
    assert expected == [] and pending == [target]
    report = DailyReconciliation().reconcile(date(2026, 10, 27), target_positions=expected, actual_positions=[])
    assert report.categories['positions'] == 'matched'
    assert not report.requires_operator_action  # Unknown cash/PnL remain pending, not invented.


def test_unexpected_broker_holding_is_still_detected():
    expected, _ = run(*evidence())
    report = DailyReconciliation().reconcile(date(2026, 10, 27), target_positions=expected,
        actual_positions=[dict(symbol='P', quantity=1., side='long')])
    assert not report.is_clean
    assert report.items[0].delta == 'extra_position'


@pytest.mark.parametrize('patch', [dict(exec_run_id='other'), dict(risk_run_id='other'),
    dict(account_id='test1'), dict(broker_mode='live'), dict(status='CLOSED'), dict(lots=[{}]),
    dict(operations=[dict(status='RESERVED')]), dict(operations=[dict(status='SUBMITTED')]),
    dict(parents={'order': {}}), dict(initial_attempted=True), dict(first_fill_at='2026-10-27')])
def test_possible_effect_or_wrong_lineage_preserves_position_check(patch):
    target, state = evidence()
    state.update(patch)
    expected, pending = run(target, state)
    assert expected == [target] and pending == []
