"""Independent UI buttons: exact local provenance, no API/SQL/order."""
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command
from ihm.services import llm_manual_handoff as handoff


@pytest.fixture(autouse=True)
def signal_day(monkeypatch):
    monkeypatch.setattr(handoff, 'resolve_us_signal_date',
                        lambda day: SimpleNamespace(isoformat=lambda: '2026-10-16'))


def options(**overrides):
    return replace(PipelineLaunchOptions(llm_filter_enabled=True, account_id='default',
        execution_mode='paper', trade_date='2026-10-17', ml_predict_batch_id='oracle-test',
        ml_predict_symbol_source='universe-file:test.txt'), **overrides)


def source(**overrides):
    return dict(dict(run_id='20261017_202916_test', step_key='ml_predict', account_id='default',
        executed_at='2026-10-17T20:29:16', finished_at='2026-10-17T20:36:13',
        status='completed', returncode=0,
        command=['python', '-u', '-m', 'service.llm_directional.pipeline', '--phase', 'predict',
                 '--run-id', 'auto', '--trade-date', '2026-10-16', '--batch-id', 'oracle-test',
                 '--symbol-source', 'universe-file:test.txt'],
        run_summary={'run_id': 'llm-exact-test', 'status': 'completed', 'selected': ['FMC']}), **overrides)


def test_auto_id_and_paris_completion_message_without_mutating_options():
    original = options()
    bound, info = handoff.bind_manual_handoff('risk_management', original, [source()])
    assert bound.llm_filter_run_id == 'llm-exact-test'
    assert bound.trade_date == '2026-10-16'
    assert original.llm_filter_run_id is None and original.trade_date == '2026-10-17'
    assert info.finished_at_paris == '17/10/2026 à 20:36:13 CEST'
    assert info.source_step == '10' and info.source_run_id == source()['run_id']


def test_new_completed_step10_refreshes_the_prefill():
    original = options()
    previous, _ = handoff.bind_manual_handoff('risk_management', original, [source()])
    latest = source(run_id='new-source', executed_at='2026-10-17T21:00:00',
        finished_at='2026-10-17T21:04:00',
        run_summary={'run_id': 'llm-new', 'status': 'completed', 'selected': []})
    bound, info = handoff.bind_manual_handoff('risk_management', original, [source(), latest])
    assert previous.llm_filter_run_id == 'llm-exact-test'
    assert bound.llm_filter_run_id == 'llm-new'
    assert info.source_run_id == 'new-source' and '21:04:00' in info.finished_at_paris


def test_latest_attempt_not_older_success_and_unordered_history():
    old = source(executed_at='2026-10-17T19:00:00')
    latest = source(run_id='new', status='failed')
    for records in ([old, latest], [latest, old]):
        bound, info = handoff.bind_manual_handoff('risk_management', options(), records)
        assert bound.llm_filter_run_id is None
        assert 'ancienne analyse' in info.error


@pytest.mark.parametrize('status', ['starting', 'running', 'timeout', 'stopped', 'failed'])
def test_non_success_does_not_supply_id(status):
    _, info = handoff.bind_manual_handoff('risk_management', options(), [source(status=status)])
    assert info.error and info.run_id is None


def test_older_completion_does_not_supersede_a_newer_launch():
    old = source(executed_at='2026-10-17T19:00:00', finished_at='2026-10-17T23:00:00')
    latest = source(status='running')
    _, info = handoff.bind_manual_handoff('risk_management', options(), [old, latest])
    assert info.error


def test_other_account_is_not_picked():
    _, info = handoff.bind_manual_handoff('risk_management', options(), [source(account_id='other')])
    assert info.error and info.run_id is None


@pytest.mark.parametrize('field,new', [('--trade-date', '2026-10-15'),
    ('--batch-id', 'other-oracle'), ('--symbol-source', 'universe-file:other.txt'),
    ('--phase', 'execute'), ('--run-id', 'llm-wrong')])
def test_context_or_identity_mismatch_never_silently_reuses(field, new):
    row = source()
    command = row['command'][:]
    command[command.index(field)+1] = new
    _, info = handoff.bind_manual_handoff('risk_management', options(), [dict(row, command=command)])
    assert info.error and info.run_id is None


def test_no_llm_on_latest_step10_does_not_fall_back():
    latest = source(command=['python', '-u', '-m', 'modelFactory'])
    old = source(executed_at='2026-10-17T19:00:00')
    _, info = handoff.bind_manual_handoff('risk_management', options(), [old, latest])
    assert 'pas d’analyse LLM' in info.error


@pytest.mark.parametrize('summary', [{}, {'run_id': 'oracle-model'},
    {'run_id': 'llm-id', 'status': 'failed', 'selected': []},
    {'run_id': 'auto', 'status': 'completed', 'selected': []}])
def test_partial_or_wrong_summary_is_not_a_valid_handoff(summary):
    _, info = handoff.bind_manual_handoff('risk_management', options(), [source(run_summary=summary)])
    assert info.error


def test_empty_but_successful_selection_still_links_the_analysis():
    row = source(run_summary={'run_id': 'llm-abstain', 'status': 'completed', 'selected': []})
    bound, info = handoff.bind_manual_handoff('risk_management', options(), [row])
    assert bound.llm_filter_run_id == 'llm-abstain' and not info.error


def test_explicit_override_and_predict_workflow_unaffected():
    explicit = options(llm_filter_run_id='llm-manual')
    bound, info = handoff.bind_manual_handoff('risk_management', explicit, [source()])
    assert bound.llm_filter_run_id == 'llm-manual' and info.manual
    for step in ('ml_predict', 'ml_train', 'import_alpaca_bar'):
        bound, info = handoff.bind_manual_handoff(step, options(), [source()])
        assert info is None and bound.llm_filter_run_id is None
    bound, info = handoff.bind_manual_handoff('risk_management', options(llm_filter_enabled=False), [source()])
    assert info is None and bound.llm_filter_run_id is None


@pytest.mark.parametrize('bad_id', ['auto', '../run', 'a'*81])
def test_invalid_manual_id_rejected_before_button_launch(bad_id):
    _, info = handoff.bind_manual_handoff('risk_management', options(llm_filter_run_id=bad_id), [])
    assert info.error


def test_execution_reuses_exact_analysis_id_from_completed_risk_command():
    row = source(step_key='risk_management', run_summary={'run_id': 'risk-exact'})
    row['command'][row['command'].index('--phase')+1] = 'risk'
    row['command'][row['command'].index('--run-id')+1] = 'llm-bound-to-risk'
    bound, info = handoff.bind_manual_handoff('execution', options(), [row])
    assert bound.llm_filter_run_id == 'llm-bound-to-risk'
    assert info.source_step == '11'


def test_aware_timestamp_converted_to_paris():
    _, info = handoff.bind_manual_handoff('risk_management', options(),
        [source(finished_at='2026-10-17T18:36:13+00:00')])
    assert '20:36:13 CEST' in info.finished_at_paris


def test_legacy_summary_recovered_from_bounded_ansi_log(monkeypatch, tmp_path):
    from ihm.services import process_registry
    monkeypatch.setattr(process_registry, 'RUNS_DIR', tmp_path)
    log = tmp_path / 'ml_predict' / 'source' / 'stdout.log'
    log.parent.mkdir(parents=True)
    final = {'run_id': 'llm-old-exact', 'status': 'completed', 'selected': ['FMC']}
    log.write_text('x'*70000 + '\n\x1b[0m::alpha_trade_run_summary::' + json.dumps(final) + '\n', encoding='utf-8')
    row = source(run_summary={'run_id': 'oracle-only'}, stdout_path=str(log))
    bound, info = handoff.bind_manual_handoff('risk_management', options(), [row])
    assert bound.llm_filter_run_id == 'llm-old-exact' and not info.error


def test_no_fallback_read_outside_pipeline_storage(monkeypatch, tmp_path):
    from ihm.services import process_registry
    monkeypatch.setattr(process_registry, 'RUNS_DIR', tmp_path / 'allowed')
    log = tmp_path / 'stdout.log'
    log.write_text('::alpha_trade_run_summary::' + json.dumps(source()['run_summary']), encoding='utf-8')
    _, info = handoff.bind_manual_handoff('risk_management', options(),
        [source(run_summary={}, stdout_path=str(log))])
    assert info.error


@pytest.mark.parametrize('prefix,suffix', [('', ''), ('\x1b[0m', ''),
    ('\x1b[32m', '\x1b[0m'), ('\x1b[0m\x1b[2K', '')])
def test_registry_extracts_final_llm_summary_with_ansi(prefix, suffix):
    from ihm.services.process_registry import _extract_run_summary
    summary = source()['run_summary']
    assert _extract_run_summary(prefix + '::alpha_trade_run_summary::' + json.dumps(summary) + suffix) == summary


def test_automatic_id_reaches_exact_risk_command(monkeypatch):
    monkeypatch.setattr('common.us_signal_date.resolve_us_signal_date',
                        lambda day: SimpleNamespace(isoformat=lambda: '2026-10-16'))
    bound, _ = handoff.bind_manual_handoff('risk_management', options(), [source()])
    command = build_pipeline_command('risk_management', bound)
    assert command[command.index('--run-id')+1] == 'llm-exact-test'
    assert command[command.index('--trade-date')+1] == '2026-10-16'


@pytest.mark.parametrize('completed', [True, False])
def test_step11_panel_uses_prefill_for_preview_and_launch(monkeypatch, completed):
    from ihm.pages import pipeline
    class Block:
        def __enter__(self): return self
        def __exit__(self, *args): return False
    notices, launches, previews = [], [], []
    monkeypatch.setattr(pipeline.st, 'expander', lambda *a, **kw: Block())
    monkeypatch.setattr(pipeline.st, 'columns', lambda *a: [Block(), Block()])
    monkeypatch.setattr(pipeline.st, 'info', lambda text: notices.append(text))
    for method in ('markdown', 'caption', 'code', 'warning', 'error'):
        monkeypatch.setattr(pipeline.st, method, lambda *a, **kw: None)
    monkeypatch.setattr(pipeline.st, 'button', lambda *a, **kw: not kw.get('disabled', False))
    monkeypatch.setattr(pipeline.st, 'number_input', lambda *a, **kw: 4)
    monkeypatch.setattr(pipeline.st, 'session_state', {})
    monkeypatch.setattr(pipeline, '_render_step_result', lambda *a: None)
    monkeypatch.setattr(pipeline, '_launch_pipeline_step', lambda key, label, opts, *a: launches.append(opts))
    def preview(key, opts):
        previews.append(opts)
        return ['python', '--trade-date', '2026-10-16']
    monkeypatch.setattr(pipeline, 'build_pipeline_command', preview)
    import ihm.services.queries
    import pandas as pd
    monkeypatch.setattr(ihm.services.queries, 'safe_query', lambda *a, **kw: pd.DataFrame())
    step = next(step for step in pipeline.get_pipeline_steps() if step.key == 'risk_management')
    previous = source(status='completed' if completed else 'failed')
    pipeline._render_launchable_step_panel(step, options(), False, {}, workflow_active=False,
        active_by_step={}, all_runs=[previous], latest_by_step={'ml_predict': previous},
        dependency_diagnostic=None, live_guard={})
    if completed:
        assert any('17/10/2026 à 20:36:13' in notice and 'llm-exact-test' in notice for notice in notices)
        assert launches and launches[0].llm_filter_run_id == 'llm-exact-test'
        assert all(preview.llm_filter_run_id == 'llm-exact-test' for preview in previews)
    else:
        assert not launches
