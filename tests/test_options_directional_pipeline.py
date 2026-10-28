from dataclasses import replace
from datetime import date
import json
from types import SimpleNamespace

import pytest

from ihm.services.pipeline_runner import build_pipeline_command, pipeline_page_default_options
from service.forward_pit import us_pipeline
from service.options_directional.config import OptionsFilterConfig


def options():
    return replace(pipeline_page_default_options(trade_date='2026-10-16'), execution_mode='paper',
                   account_id='default', ml_predict_symbol_source='universe-file:test.txt')


def test_batch_enabled_binds_all_commands_same_id_day_model(monkeypatch):
    monkeypatch.setattr(us_pipeline,'require_paper_account',lambda account:None)
    monkeypatch.setattr('common.us_signal_date.resolve_us_signal_date', lambda *a: date(2026,10,16))
    steps = us_pipeline.selected_steps([10,11,12])
    bound = us_pipeline.options_filter_options(options(), steps, config=OptionsFilterConfig(enabled=True))
    assert bound.options_filter_enabled and bound.options_filter_run_id.startswith('opt-')
    assert not bound.llm_filter_enabled
    for step, phase in zip(steps, ['predict','risk','execute']):
        command = build_pipeline_command(step.key, bound)
        assert command[3] == 'service.options_directional.pipeline'
        for flag,value in [('phase',phase),('run-id',bound.options_filter_run_id),('trade-date','2026-10-16'),
                           ('batch-id',bound.ml_predict_batch_id),('symbol-source','universe-file:test.txt')]:
            assert command[command.index('--'+flag)+1] == value
        inner = json.loads(command[command.index('--command-json')+1])
        assert 'service.llm_directional.pipeline' not in inner
        if phase=='predict':
            assert inner[inner.index('--batch-id')+1] == bound.ml_predict_batch_id


@pytest.mark.parametrize('account',['test1','test2'])
def test_secondary_paper_account_is_carried_by_all_wrapped_commands(monkeypatch,account):
    checked=[]
    monkeypatch.setattr(us_pipeline,'require_paper_account',lambda value:checked.append(value))
    monkeypatch.setattr('common.us_signal_date.resolve_us_signal_date',lambda *a:date(2026,10,16))
    steps=us_pipeline.selected_steps([10,11,12])
    bound=us_pipeline.options_filter_options(replace(options(),account_id=account),steps,
        config=OptionsFilterConfig(enabled=True))
    assert checked==[account]
    for step in steps:
        cmd=build_pipeline_command(step.key,bound)
        assert cmd[cmd.index('--account')+1]==account
        inner=json.loads(cmd[cmd.index('--command-json')+1])
        if step.num!='10':
            assert inner[inner.index('--account')+1]==account


@pytest.mark.parametrize('numbers', [[11], [12], [11,12]])
def test_no_missing_prediction_in_scheduled_batch(numbers):
    with pytest.raises(ValueError, match='inclure étape 10'):
        us_pipeline.options_filter_options(options(), us_pipeline.selected_steps(numbers),
                                          config=OptionsFilterConfig(enabled=True))


def test_disabled_and_collection_only_do_not_activate_filter():
    original = replace(options(), options_filter_enabled=True, options_filter_run_id='old')
    bound = us_pipeline.options_filter_options(original, us_pipeline.selected_steps([10]),
                                               config=OptionsFilterConfig(enabled=False))
    assert not bound.options_filter_enabled and bound.options_filter_run_id is None
    assert us_pipeline.options_filter_options(original, us_pipeline.selected_steps([1])) is original


@pytest.mark.parametrize('kwargs', [dict(execution_mode='live'), dict(execution_mode='simulate'),
                                    dict(llm_filter_enabled=True)])
def test_no_live_or_implicit_llm_combination(kwargs):
    with pytest.raises(ValueError):
        us_pipeline.options_filter_options(replace(options(), **kwargs), us_pipeline.selected_steps([10]),
                                          config=OptionsFilterConfig(enabled=True))


def test_checkbox_default_and_manual_opt_out(monkeypatch):
    from ihm.pages import _execution_center as page
    config = OptionsFilterConfig(enabled=True)
    for state, expected in [({},True), ({'pipeline_options_filter_enabled':False},False)]:
        monkeypatch.setattr(page.st,'session_state',state)
        monkeypatch.setattr(page.st,'checkbox',lambda label,**kwargs:kwargs['value'])
        monkeypatch.setattr(page.st,'caption',lambda *a:None)
        assert page._render_options_filter_toggle(config) is expected
        assert not page._render_options_filter_toggle(config,llm_enabled=True)
        assert not page._render_options_filter_toggle(config,paper_allowed=False)


def test_research_scope_bypasses_prospective_options_only_locally():
    from ihm.pages.pipeline import _ml_prediction_scope_options
    original = replace(options(), options_filter_enabled=True, ml_predict_use_historical_range=True)
    assert not _ml_prediction_scope_options(original).options_filter_enabled
    assert original.options_filter_enabled
