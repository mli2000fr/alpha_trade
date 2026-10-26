"""Global LLM-off must override a previously checked Pipeline widget (no API)."""
from dataclasses import replace

import pytest

from ihm.pages import _execution_center as page
from service.llm_directional.config import FilterConfig, load_filter_config


@pytest.mark.parametrize('previous', [None, True, False])
def test_global_off_unchecks_and_disables_widget(monkeypatch, previous):
    state = {} if previous is None else {'pipeline_llm_filter_enabled': previous}
    monkeypatch.setattr(page.st, 'session_state', state)
    captured = {}

    def checkbox(label, **kwargs):
        captured.update(kwargs)
        return kwargs['value']

    monkeypatch.setattr(page.st, 'checkbox', checkbox)
    monkeypatch.setattr(page.st, 'caption', lambda *a: None)
    assert page._render_llm_filter_toggle(FilterConfig(enabled=False)) is False
    assert state['pipeline_llm_filter_enabled'] is False
    assert captured['value'] is False
    assert captured['disabled'] is True


def test_enabled_config_keeps_manual_opt_out(monkeypatch):
    monkeypatch.setattr(page.st, 'session_state', {'pipeline_llm_filter_enabled': False})
    monkeypatch.setattr(page.st, 'checkbox', lambda label, **kwargs: kwargs['value'])
    assert page._render_llm_filter_toggle(FilterConfig(enabled=True)) is False


def test_deployed_pipeline_configuration_disables_both_providers():
    config = load_filter_config()
    assert config.enabled is False
    for provider in ('openai', 'deepseek'):
        assert replace(config, provider=provider).enabled is False
