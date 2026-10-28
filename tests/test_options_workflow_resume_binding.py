"""An 11/12-only workflow must reuse a qualified analysis, never invent its ID."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from ihm.services import process_registry
from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command
from service.options_directional import store
from tests.test_options_directional_orchestration import env, RUN


def options(**kwargs):
    return replace(PipelineLaunchOptions(options_filter_enabled=True,
        execution_mode='paper', account_id='default', risk_enable_kelly=False,
        trade_date='2026-10-16', ml_predict_batch_id='model-test',
        ml_predict_symbol_source='universe-file:test.txt', capital_preset_key='capital_2001_5000'), **kwargs)


def steps(*keys):
    return tuple(SimpleNamespace(key=key) for key in keys)


@pytest.mark.parametrize('keys', [('risk_management',), ('execution',), ('risk_management','execution')])
@pytest.mark.parametrize('run_id', [None, 'auto', RUN])
def test_resume_pins_existing_exact_report_once(env, keys, run_id):
    original = options(options_filter_run_id=run_id)
    bound = process_registry._bind_options_workflow_run(original, steps(*keys))
    assert bound.options_filter_run_id == RUN
    assert bound.trade_date == '2026-10-16'
    assert bound.force_trade_date_to_latest_snapshot is False
    assert original.options_filter_run_id == run_id  # no mutation
    for key in keys:
        command = build_pipeline_command(key, bound)
        assert command[command.index('--run-id')+1] == RUN


def test_new_prediction_is_only_case_that_generates_new_id(env, monkeypatch):
    monkeypatch.setattr(store, 'latest_matching', lambda **kw: pytest.fail('lookup during new prediction'))
    monkeypatch.setattr(store, 'qualified', lambda *a, **kw: pytest.fail('lookup during new prediction'))
    bound = process_registry._bind_options_workflow_run(options(), steps('ml_predict','risk_management','execution'))
    assert bound.options_filter_run_id.startswith('opt-') and bound.options_filter_run_id != RUN


def test_explicit_new_prediction_id_is_preserved(env):
    explicit = 'opt-'+'a'*32
    bound = process_registry._bind_options_workflow_run(options(options_filter_run_id=explicit), steps('ml_predict'))
    assert bound.options_filter_run_id == explicit


def test_unknown_explicit_id_never_falls_back_to_another_analysis(env):
    with pytest.raises(FileNotFoundError):
        process_registry._bind_options_workflow_run(options(options_filter_run_id='opt-'+'c'*32), steps('risk_management'))


@pytest.mark.parametrize('change', [dict(ml_predict_batch_id='other-model'),
    dict(ml_predict_symbol_source='universe-file:other.txt')])
def test_other_context_never_reuses_report(env, change):
    with pytest.raises(ValueError, match='Aucun filtre options'):
        process_registry._bind_options_workflow_run(options(**change), steps('risk_management','execution'))


@pytest.mark.parametrize('account', ['default','test1','test2'])
def test_shared_selection_keeps_archived_universe_for_other_account_presets(env, account):
    bound=process_registry._bind_options_workflow_run(
        options(account_id=account,capital_preset_key='capital_0_2000'),steps('risk_management','execution'))
    assert bound.options_filter_run_id==RUN
    assert bound.account_id==account


def test_tampered_latest_analysis_blocks_before_launch(env):
    (store.directory(RUN)/'inputs.json').write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='altérée'):
        process_registry._bind_options_workflow_run(options(), steps('risk_management'))


def test_collection_only_does_not_create_or_lookup_analysis(env, monkeypatch):
    monkeypatch.setattr(store, 'latest_matching', lambda **kw: pytest.fail('collection lookup'))
    bound = process_registry._bind_options_workflow_run(options(), steps('import_alpaca_bar'))
    assert bound.options_filter_run_id is None
