"""Scheduled LLM handoff: local plans/fake workflow only, no SQL/API/orders."""
from dataclasses import replace
from datetime import date
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ihm.services import process_registry
from ihm.services.pipeline_runner import build_pipeline_command, pipeline_page_default_options
from service.forward_pit import us_pipeline
from service.llm_directional.config import FilterConfig


@pytest.fixture
def config():
    return FilterConfig(enabled=True, provider='openai',
        default_oracle_batch_id='model-factory-test-oracle', oracle_top_n=10, max_selected=3,
        protections=dict(enabled=True, stop_loss_pct=.07, trailing_stop_pct=.15, exit_session=21))


@pytest.fixture(autouse=True)
def isolate_optional_options_gate(monkeypatch):
    from service.options_directional.config import OptionsFilterConfig
    monkeypatch.setattr('service.options_directional.config.load_options_filter_config',
                        lambda: OptionsFilterConfig(enabled=False))


def options():
    return replace(pipeline_page_default_options(trade_date='2026-10-16'),
        execution_mode='paper', account_id='default',
        ml_predict_symbol_source='universe-file:config/univers_batch/univers_filtred_tradable.txt')


@pytest.mark.parametrize('provider', ['openai', 'deepseek'])
def test_explicit_batch_common_universe_and_unique_run(config, provider):
    config = replace(config, provider=provider)
    steps = us_pipeline.selected_steps([10, 11, 12])
    result = us_pipeline.llm_options(options(), steps, config=config)
    assert result.llm_filter_enabled
    assert result.ml_predict_batch_id == result.ml_live_predict_batch_id == config.default_oracle_batch_id
    assert result.ml_predict_symbol_source == options().ml_predict_symbol_source
    assert result.llm_specific_protections is True
    assert result.llm_filter_run_id.startswith('llm-')
    assert result.llm_filter_run_id != us_pipeline.llm_options(options(), steps, config=config).llm_filter_run_id


def test_all_three_commands_share_id_date_and_model(monkeypatch, config):
    monkeypatch.setattr('service.llm_directional.config.load_filter_config', lambda: config)
    monkeypatch.setattr('common.us_signal_date.resolve_us_signal_date', lambda *a: date(2026, 10, 16))
    steps = us_pipeline.selected_steps([10, 11, 12])
    bound = us_pipeline.llm_options(options(), steps, config=config)
    for step, phase in zip(steps, ['predict', 'risk', 'execute']):
        command = build_pipeline_command(step.key, bound)
        assert command[command.index('-m')+1] == 'service.llm_directional.pipeline'
        for name, value in [('phase', phase), ('run-id', bound.llm_filter_run_id),
                            ('trade-date', '2026-10-16'), ('batch-id', config.default_oracle_batch_id),
                            ('symbol-source', bound.ml_predict_symbol_source)]:
            assert command[command.index('--'+name)+1] == value
        assert '--specific-protections' in command
        inner = json.loads(command[command.index('--command-json')+1])
        if phase == 'predict':
            assert inner[inner.index('--batch-id')+1] == config.default_oracle_batch_id
            assert inner[inner.index('--artifacts-dir')+1].endswith(config.default_oracle_batch_id)
        elif phase == 'execute':
            assert inner[3] == 'paper'


def test_collection_only_does_not_load_llm(monkeypatch):
    monkeypatch.setattr(us_pipeline, 'load_filter_config', lambda: pytest.fail('LLM settings loaded'))
    original = options()
    assert us_pipeline.llm_options(original, us_pipeline.selected_steps([1, 9])) is original


def test_disabled_preserves_old_route(config):
    original = options()
    assert us_pipeline.llm_options(original, us_pipeline.selected_steps([10, 11, 12]),
                                   config=replace(config, enabled=False)) == replace(
                                       original, llm_specific_protections=False)


def test_disabled_clears_stale_llm_options_without_changing_oracle(monkeypatch, config):
    monkeypatch.setattr('common.us_signal_date.resolve_us_signal_date', lambda *a: date(2026, 10, 16))
    original = replace(options(), llm_filter_enabled=True, llm_filter_run_id='llm-old',
                       llm_specific_protections=True, ml_predict_batch_id='model-factory-kept',
                       ml_live_predict_batch_id='model-factory-kept')
    steps = us_pipeline.selected_steps([10, 11, 12])
    result = us_pipeline.llm_options(original, steps, config=replace(config, enabled=False))
    assert not result.llm_filter_enabled
    assert result.llm_filter_run_id is None
    assert not result.llm_specific_protections
    assert result.ml_predict_batch_id == result.ml_live_predict_batch_id == 'model-factory-kept'
    for step in steps:
        command = build_pipeline_command(step.key, result)
        assert 'service.llm_directional.pipeline' not in command
        assert '--llm-filter-run-id' not in command


@pytest.mark.parametrize('numbers', [[11], [12], [11, 12]])
def test_no_implicit_old_selection(config, numbers):
    with pytest.raises(ValueError, match='inclure étape 10'):
        us_pipeline.llm_options(options(), us_pipeline.selected_steps(numbers), config=config)


@pytest.mark.parametrize('overrides', [dict(execution_mode='simulate'),
                                     dict(execution_mode='live'), dict(account_id='test1')])
def test_llm_requires_main_paper_account(config, overrides):
    with pytest.raises(ValueError, match='default PAPER'):
        us_pipeline.llm_options(replace(options(), **overrides),
                               us_pipeline.selected_steps([10, 11, 12]), config=config)


def test_dedicated_protections_can_be_disabled(config):
    result = us_pipeline.llm_options(options(), us_pipeline.selected_steps([10]),
                                    config=replace(config, protections=None))
    assert result.llm_filter_enabled and result.llm_specific_protections is False


@pytest.mark.parametrize('dry_run', [True, False])
def test_scheduler_wires_llm_before_plan_and_workflow(monkeypatch, tmp_path, config, dry_run):
    monkeypatch.setattr(us_pipeline, 'ROOT', tmp_path)
    monkeypatch.setattr(us_pipeline, 'session_plan', lambda now: (date(2026, 10, 16), None))
    monkeypatch.setattr(us_pipeline, 'load_pipeline_policy', lambda: dict(
        steps=[1], steps_friday=[10, 11, 12], execution_mode='paper', account_id='default',
        run_other_paper_accounts=False))
    monkeypatch.setattr(us_pipeline, 'load_filter_config', lambda: config)
    monkeypatch.setattr('service.llm_directional.config.load_filter_config', lambda: config)
    monkeypatch.setattr('common.us_signal_date.resolve_us_signal_date', lambda *a: date(2026, 10, 16))
    monkeypatch.setattr(us_pipeline, 'require_paper_account', lambda account: None)
    start = Mock(return_value=SimpleNamespace(run_id='fake-workflow'))
    monkeypatch.setattr(process_registry, 'start_pipeline_workflow', start)
    monkeypatch.setattr(process_registry, 'poll_pipeline_run', lambda run: dict(
        status='completed', workflow_completed_steps=3))
    result = us_pipeline.execute_pipeline(SimpleNamespace(url=SimpleNamespace(database='alpha_trade')),
        dict(market_code='US_EQ', symbols_file='config/univers_batch/univers_filtred_tradable.txt'),
        'test', dry_run)
    planned = result.details['options']
    assert planned['llm_filter_enabled']
    assert planned['ml_predict_batch_id'] == config.default_oracle_batch_id
    assert planned['ml_predict_symbol_source'] == options().ml_predict_symbol_source
    assert result.details['selected_step_numbers'] == [10, 11, 12]
    for entry in result.details['steps']:
        command = entry['command']
        assert command[command.index('--run-id')+1] == planned['llm_filter_run_id']
    if dry_run:
        start.assert_not_called()
        assert not (tmp_path/'artifacts').exists()
    else:
        assert start.call_args.args[0].llm_filter_run_id == planned['llm_filter_run_id']
        assert start.call_args.kwargs['selected_step_keys'] == ('ml_predict', 'risk_management', 'execution')


def test_missing_predict_blocks_before_workflow(monkeypatch, tmp_path, config):
    monkeypatch.setattr(us_pipeline, 'ROOT', tmp_path)
    monkeypatch.setattr(us_pipeline, 'session_plan', lambda now: (date(2026, 10, 16), None))
    monkeypatch.setattr(us_pipeline, 'load_pipeline_policy', lambda: dict(
        steps_friday=[11, 12], execution_mode='paper'))
    monkeypatch.setattr(us_pipeline, 'load_filter_config', lambda: config)
    monkeypatch.setattr(us_pipeline, 'require_paper_account', lambda account: None)
    monkeypatch.setattr(process_registry, 'start_pipeline_workflow', lambda *a, **k: pytest.fail('started'))
    with pytest.raises(ValueError, match='inclure étape 10'):
        us_pipeline.execute_pipeline(SimpleNamespace(url=SimpleNamespace(database='alpha_trade')),
            dict(market_code='US_EQ'), 'bad', False)
    assert not (tmp_path/'artifacts').exists()
