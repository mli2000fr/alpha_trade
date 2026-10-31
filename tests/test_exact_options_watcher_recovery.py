"""Operator recovery never accepts an ambiguous or nonzero-effect attempt."""
import pytest

from scripts.operations import recover_options_watcher_attempt_20261028 as recovery


def evidence():
    claim = dict(attempt_id=recovery.ATTEMPT,
        binding_sha256='63cddaf8e56ffc8f7980db87a65df384a05a90dc16b831daf7d8969c8dbbe50d',
        report_sha256='0c3d09442157ff5716f64274aa67debcbc333d26c79761f0eed2a25569438af2',
        risk_run_id=recovery.RISK, run_id=recovery.RUN, started_at='2026-10-28T11:02:43.593167+00:00')
    result = dict(attempt_id=recovery.ATTEMPT, claim_sha256=recovery.CLAIM_HASH,
        risk_run_id=recovery.RISK, run_id=recovery.RUN, status='CHILD_COMPLETED')
    effects = dict(attempt_id=recovery.ATTEMPT, claim_sha256=recovery.CLAIM_HASH, risk_run_id=recovery.RISK)
    rows = [dict(exec_run_id=recovery.EXEC, risk_run_id=recovery.RISK, status='FAILED', error_message=recovery.ERROR,
        total_submitted=0, total_filled=0, account_id='default', broker_mode='paper')]
    sql = dict(order_requests=0, winner_campaigns=0, active_account_locks=0, active_execution_runs=0)
    broker = dict(positions=0, open_orders=0, orders_today=0, fills_today=0)
    return [claim, result, effects, rows, sql, broker]


def test_accepts_only_known_failed_zero_effect_attempt():
    recovery.validate_proof(*evidence())


@pytest.mark.parametrize('field', ['order_requests', 'winner_campaigns', 'active_account_locks', 'active_execution_runs'])
def test_sql_effect_or_active_process_blocks(field):
    items = evidence()
    items[4][field] = 1
    with pytest.raises(ValueError):
        recovery.validate_proof(*items)


@pytest.mark.parametrize('field', ['positions', 'open_orders', 'orders_today', 'fills_today'])
def test_broker_evidence_blocks_even_when_sql_empty(field):
    items = evidence()
    items[5][field] = 1
    with pytest.raises(ValueError):
        recovery.validate_proof(*items)


@pytest.mark.parametrize('patch', [dict(status='RUNNING'), dict(status='COMPLETED'),
    dict(total_submitted=1), dict(total_filled=1), dict(broker_mode='live'),
    dict(error_message='Broker timeout'), dict(exec_run_id='another'), dict(account_id='test1')])
def test_different_sql_outcome_blocks(patch):
    items = evidence()
    items[3][0].update(patch)
    with pytest.raises(ValueError):
        recovery.validate_proof(*items)


def test_missing_or_extra_execution_run_blocks():
    for rows in ([], evidence()[3]*2):
        items = evidence()
        items[3] = rows
        with pytest.raises(ValueError):
            recovery.validate_proof(*items)


@pytest.mark.parametrize('index,field', [(0, 'attempt_id'), (1, 'claim_sha256'), (2, 'risk_run_id')])
def test_different_artifact_binding_blocks(index, field):
    items = evidence()
    items[index][field] = 'changed'
    with pytest.raises(ValueError):
        recovery.validate_proof(*items)
