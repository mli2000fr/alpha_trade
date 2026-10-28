"""No orders: only a proven pre-effects child failure permits an exact retry."""
import json
import subprocess

import pytest

from service.options_directional import store
from service.options_directional.execution_attempts import (
    execution_attempt, execution_child_guard, mark_execution_effects_possible,
)
from service.options_directional.risk_attempts import risk_lock
from tests.test_options_directional_orchestration import env, RUN


def prepare(env):
    invoke, calls, engine, report = env
    invoke('risk', ['python', '-u', '-m', 'risk_management'])
    folder = store.directory(RUN)
    binding = json.loads((folder/'risk_binding.json').read_text())
    return folder, report, binding


def child(attempt):
    return execution_child_guard(RUN, attempt['attempt_id'], risk_run_id='risk-exact',
        mode='paper', account_id='default', trade_date='2026-10-16')


def test_proven_pre_effect_failure_can_retry_but_completed_execution_cannot(env):
    folder, report, binding = prepare(env)
    with pytest.raises(ImportError):
        with execution_attempt(folder, report, binding) as first:
            with child(first):
                raise ImportError('pre-submission dependency missing')
    old = json.loads((folder/'execution.claim.json').read_text())
    assert (folder/f'execution.pre_effect_failure.{first["attempt_id"]}.json').exists()
    with execution_attempt(folder, report, binding) as second:
        with child(second):
            mark_execution_effects_possible(risk_run_id='risk-exact', mode='paper', account_id='default')
    assert second['attempt_id'] != first['attempt_id']
    archived = folder/'execution_attempts'/first['attempt_id']/'execution.claim.json'
    assert json.loads(archived.read_text()) == old
    with pytest.raises(FileExistsError, match='terminée'):
        with execution_attempt(folder, report, binding):
            pytest.fail('duplicate execution')


def test_error_after_financial_checkpoint_never_auto_retries(env):
    folder, report, binding = prepare(env)
    with pytest.raises(TimeoutError):
        with execution_attempt(folder, report, binding) as attempt:
            with child(attempt):
                mark_execution_effects_possible(risk_run_id='risk-exact', mode='paper', account_id='default')
                raise TimeoutError('unknown broker outcome')
    assert not (folder/f'execution.pre_effect_failure.{attempt["attempt_id"]}.json').exists()
    with pytest.raises(FileExistsError, match='ambiguë'):
        with execution_attempt(folder, report, binding):
            pytest.fail('ambiguous retry')


def test_unobserved_subprocess_failure_never_auto_retries(env):
    folder, report, binding = prepare(env)
    with pytest.raises(subprocess.CalledProcessError):
        with execution_attempt(folder, report, binding):
            raise subprocess.CalledProcessError(1, ['fake'])
    with pytest.raises(FileExistsError, match='ambiguë'):
        with execution_attempt(folder, report, binding):
            pytest.fail('no child proof')


@pytest.mark.parametrize('field,value', [('claim_sha256', 'altered'), ('phase', 'after_orders'),
    ('retryable', False), ('binding_sha256', 'altered'), ('risk_run_id', 'other')])
def test_bad_receipt_never_authorizes_retry(env, field, value):
    folder, report, binding = prepare(env)
    with pytest.raises(ValueError):
        with execution_attempt(folder, report, binding) as attempt:
            with child(attempt):
                raise ValueError('preflight failure')
    path = folder/f'execution.pre_effect_failure.{attempt["attempt_id"]}.json'
    proof = json.loads(path.read_text()); proof[field] = value
    path.write_text(json.dumps(proof))
    with pytest.raises(ValueError, match='altérée'):
        with execution_attempt(folder, report, binding):
            pytest.fail('tampered proof accepted')


def test_legacy_claim_and_parallel_execution_are_not_deleted(env):
    folder, report, binding = prepare(env)
    with risk_lock(folder, lock_name='execution.lock'):
        with pytest.raises(OSError):
            with execution_attempt(folder, report, binding):
                pytest.fail('parallel attempt')
    store.write_new(folder/'execution.claim.json', {'started_at': 'legacy'})
    with pytest.raises(FileExistsError, match='Ancienne tentative'):
        with execution_attempt(folder, report, binding):
            pytest.fail('legacy claim silently removed')


@pytest.mark.parametrize('mode,account,risk', [('live', 'default', 'risk-exact'),
    ('paper', 'other', 'risk-exact'), ('paper', 'default', 'other')])
def test_child_cannot_change_routing(env, mode, account, risk):
    folder, report, binding = prepare(env)
    with pytest.raises(ValueError, match='incompatible'):
        with execution_attempt(folder, report, binding) as attempt:
            with execution_child_guard(RUN, attempt['attempt_id'], risk_run_id=risk,
                mode=mode, account_id=account, trade_date='2026-10-16'):
                pytest.fail('routing changed')


def test_durable_marker_precedes_transition_orders_and_executor():
    from pathlib import Path
    source = Path('run_execution.py').read_text(encoding='utf-8')
    run = source.split('def run(', 1)[1].split('def build_parser()', 1)[0]
    marker = run.index('mark_execution_effects_possible(risk_run_id=')
    assert marker < run.index('_execute_transition_plan(')
    assert marker < run.index('executor.execute_run(')


@pytest.mark.parametrize('effects_possible', [False, True])
def test_actual_child_cli_records_only_pre_effect_failure(env, monkeypatch, effects_possible):
    import sys
    import run_execution
    folder, report, binding = prepare(env)
    monkeypatch.setattr(run_execution, '_apply_feature_flags', lambda args: None)
    monkeypatch.setattr(run_execution, 'abort_missing_env', lambda **kwargs: None)
    def fail(*args, **kwargs):
        if effects_possible:
            mark_execution_effects_possible(risk_run_id='risk-exact', mode='paper', account_id='default')
        raise RuntimeError('simulated child failure')
    monkeypatch.setattr(run_execution, 'run', fail)
    with pytest.raises(RuntimeError):
        with execution_attempt(folder, report, binding) as attempt:
            monkeypatch.setattr(sys, 'argv', ['run_execution.py', 'paper', '--run-id', 'risk-exact',
                '--date', '2026-10-16', '--account', 'default', '--options-filter-run-id', RUN,
                '--options-execution-attempt-id', attempt['attempt_id']])
            run_execution.main()
    proof = folder/f'execution.pre_effect_failure.{attempt["attempt_id"]}.json'
    assert proof.exists() is (not effects_possible)
