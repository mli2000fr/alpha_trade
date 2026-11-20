"""Batch GPT switch and its UI default share one source; no API calls."""
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from ihm.components import pipeline_batch_defaults as ui
from ihm.services import batch_management
from ihm.services.pipeline_runner import build_pipeline_command
from service.forward_pit import us_pipeline
from service.llm_directional.config import FilterConfig


@pytest.fixture
def view(monkeypatch):
    monkeypatch.setattr(us_pipeline,'require_paper_account',lambda *a:None)
    monkeypatch.setattr('common.q051_paper.require_paper',lambda *a:None)
    monkeypatch.setattr(us_pipeline,'additional_paper_accounts',lambda *a:('test1','test2'))
    return ui.load_defaults(now=datetime(2026,11,19,22,tzinfo=UTC))


def test_gpt_switch_is_first_batch_parameter_and_preserves_disabled_default():
    import yaml
    values=yaml.safe_load(Path('config.yaml').read_text(encoding='utf-8'))['us_pipeline']
    assert next(iter(values))=='gpt_filter_enabled'
    assert type(values['gpt_filter_enabled']) is bool


@pytest.mark.parametrize('enabled',[False,True])
def test_scheduled_batch_and_ui_options_follow_same_switch(view,monkeypatch,enabled):
    policy=dict(us_pipeline.load_pipeline_policy(),gpt_filter_enabled=enabled)
    monkeypatch.setattr(us_pipeline,'load_pipeline_policy',lambda:policy)
    current=ui.load_defaults(now=datetime(2026,11,19,22,tzinfo=UTC))
    scheduled=us_pipeline.fresh_pipeline_options(dict(view.spec.raw_config),policy,date(2026,11,19),view.steps)
    for opts in [scheduled,current.options]:
        assert opts.llm_filter_enabled is enabled
        assert opts.q051_paper_enabled and not opts.options_filter_enabled
        assert opts.q051_profile_id==view.options.q051_profile_id
        assert ('--llm-filter' in build_pipeline_command('ml_predict',opts)) is enabled
        assert '--llm-filter' not in build_pipeline_command('risk_management',opts)
        assert '--llm-filter' not in build_pipeline_command('execution',opts)


@pytest.mark.parametrize('invalid',['false','true',0,1,None])
def test_batch_parameter_rejects_non_booleans(invalid):
    with pytest.raises(ValueError,match='booléen'):
        us_pipeline.gpt_filter_enabled({'gpt_filter_enabled':invalid})


def test_manual_false_overrides_enabled_batch_without_mutating_policy(view):
    policy=dict(us_pipeline.load_pipeline_policy(),gpt_filter_enabled=True)
    before=deepcopy(policy)
    options=us_pipeline.fresh_pipeline_options(dict(view.spec.raw_config,_manual_q051_llm_filter=False),
        policy,date(2026,11,19),view.steps)
    assert not options.llm_filter_enabled and options.q051_paper_enabled
    assert policy==before
    command=batch_management.build_run_command(view.spec,q051_llm_filter=False)
    assert command==batch_management.build_run_command(view.spec)+['-NoQ051LlmFilter']
    with pytest.raises(ValueError,match='reprise'):
        batch_management.build_run_command(view.spec,q051_llm_filter=False,recovery_date='2026-11-18')


def test_false_override_passes_through_runner_as_false(monkeypatch):
    from service.forward_pit import batch
    original={'us_pipeline':dict(enabled=True,market_code='US_EQ')}
    seen=[]
    monkeypatch.setattr(batch,'load_batch_config',lambda *a:original)
    monkeypatch.setattr(batch,'get_sqlalchemy_engine',lambda:SimpleNamespace(url=SimpleNamespace(database='alpha_trade')))
    monkeypatch.setitem(batch.HANDLERS,'us_pipeline',lambda engine,cfg,*a:seen.append(cfg) or batch.Outcome())
    batch.execute('us_pipeline',dry_run=True,us_pipeline_llm_filter=False)
    assert seen[0]['_manual_q051_llm_filter'] is False
    assert '_manual_q051_llm_filter' not in original['us_pipeline']
    seen.clear();batch.execute('us_pipeline',dry_run=True)
    assert '_manual_q051_llm_filter' not in seen[0]


def test_ui_config_changes_update_default_without_leaking_old_session():
    state={ui.GPT_KEY:True}
    ui.sync_gpt_default(state,False)
    assert state[ui.GPT_KEY] is False
    state[ui.GPT_KEY]=True
    ui.sync_gpt_default(state,False)
    assert state[ui.GPT_KEY] is True  # Explicit current edit survives ordinary reruns.
    ui.sync_gpt_default(state,True)
    assert state[ui.GPT_KEY] is True
    state[ui.GPT_KEY]=False
    ui.sync_gpt_default(state,False)
    assert state[ui.GPT_KEY] is False


def prepare_ui(view,monkeypatch,*,configured=True,recovery=None):
    from streamlit.testing.v1 import AppTest
    live=[replace(view,options=replace(view.options,llm_filter_enabled=configured))]
    calls=[]
    monkeypatch.setattr(ui,'load_defaults',lambda:live[0])
    monkeypatch.setattr(ui,'us_pipeline_recovery_state',lambda spec:recovery or {'visible':False})
    monkeypatch.setattr(ui,'render_selection',lambda view:None)
    monkeypatch.setattr(ui,'launch',lambda *a,**kw:calls.append(kw) or SimpleNamespace(run_id='fake'))
    app=AppTest.from_string('''
from ihm.components.pipeline_batch_defaults import render
render(db_config={'name':'alpha_trade'},active_runs=[])
''').run(timeout=30)
    assert not app.exception
    return app,live,calls


def test_configured_enabled_checkbox_is_checked_and_inherits_on_launch(view,monkeypatch):
    app,_,calls=prepare_ui(view,monkeypatch)
    assert app.checkbox(key=ui.GPT_KEY).value is True
    assert not calls
    app.button(key='pipeline_launch_us_batch_defaults').click().run(timeout=30)
    assert not app.exception
    assert calls==[dict(db_config={'name':'alpha_trade'})]


def test_ui_opt_out_of_configured_true_sends_explicit_false(view,monkeypatch):
    app,_,calls=prepare_ui(view,monkeypatch)
    app.checkbox(key=ui.GPT_KEY).uncheck().run(timeout=30)
    assert not calls
    app.button(key='pipeline_launch_us_batch_defaults').click().run(timeout=30)
    assert not app.exception
    assert calls==[dict(db_config={'name':'alpha_trade'},llm_filter_enabled=False)]


def test_changed_yaml_value_updates_existing_ui_session(view,monkeypatch):
    app,live,_=prepare_ui(view,monkeypatch,configured=False)
    assert not app.checkbox(key=ui.GPT_KEY).value
    live[0]=replace(live[0],options=replace(live[0].options,llm_filter_enabled=True))
    app.run(timeout=30)
    assert not app.exception and app.checkbox(key=ui.GPT_KEY).value
    live[0]=replace(live[0],options=replace(live[0].options,llm_filter_enabled=False))
    app.run(timeout=30)
    assert not app.exception and not app.checkbox(key=ui.GPT_KEY).value


def test_recovery_keeps_original_configuration_even_if_batch_default_is_now_true(view,monkeypatch):
    app,_,calls=prepare_ui(view,monkeypatch,recovery=dict(visible=True,eligible=True,trade_date='2026-11-18'))
    assert not app.button(key='pipeline_us_defaults_recovery').disabled
    app.button(key='pipeline_us_defaults_recovery').click().run(timeout=30)
    assert not app.exception
    assert calls==[dict(db_config={'name':'alpha_trade'},recovery_date='2026-11-18')]


def test_scheduled_permission_does_not_depend_on_manual_override_permission(view,monkeypatch):
    from service.q051_paper import llm_filter
    policy=dict(us_pipeline.load_pipeline_policy(),gpt_filter_enabled=True)
    monkeypatch.setattr(us_pipeline,'load_pipeline_policy',lambda:policy)
    monkeypatch.setattr('service.llm_directional.config.load_filter_config',lambda:FilterConfig(manual_opt_in_allowed=False))
    monkeypatch.setattr(llm_filter,'load_filter_config',lambda:FilterConfig(manual_opt_in_allowed=False))
    opts=us_pipeline.fresh_pipeline_options(dict(view.spec.raw_config),policy,date(2026,11,19),view.steps)
    assert opts.llm_filter_enabled
    assert llm_filter.manual_config(10,10).enabled
