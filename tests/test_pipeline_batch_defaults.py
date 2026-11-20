"""Manual defaults use the scheduled configuration and its actual launcher."""
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from ihm.components import pipeline_batch_defaults as ui
from ihm.services import batch_management
from ihm.services.pipeline_runner import build_pipeline_command
from service.forward_pit import us_pipeline


@pytest.fixture
def default_view(monkeypatch):
    policy=dict(us_pipeline.load_pipeline_policy(),gpt_filter_enabled=False)
    monkeypatch.setattr(us_pipeline,'load_pipeline_policy',lambda:policy)
    # No broker/network access is required to construct the page's defaults.
    monkeypatch.setattr(us_pipeline, 'require_paper_account', lambda *a: None)
    monkeypatch.setattr('common.q051_paper.require_paper', lambda *a: None)
    monkeypatch.setattr(us_pipeline, 'additional_paper_accounts', lambda *a: ('test1', 'test2'))
    return ui.load_defaults(now=datetime(2026, 11, 19, 22, tzinfo=UTC))


def test_default_manual_route_matches_active_scheduled_b_profile(default_view):
    view = default_view
    opts = view.options
    policy = us_pipeline.load_pipeline_policy()
    from common.q051_paper import settings
    deployed = settings()
    assert view.skip_reason is None
    assert opts.execution_mode == policy['execution_mode'] == 'paper'
    assert opts.account_id == policy['account_id'] == 'default'
    assert view.other_accounts == ('test1', 'test2')
    assert [int(s.num) for s in view.steps] == policy['steps']
    assert opts.q051_paper_enabled
    assert opts.q051_profile_id == deployed['profile_id']
    assert opts.ml_predict_batch_id == opts.ml_live_predict_batch_id == deployed['model_batch_id']
    assert not opts.llm_filter_enabled and not opts.options_filter_enabled
    assert not opts.ml_predict_use_historical_range
    assert not opts.force_trade_date_to_latest_snapshot
    source = 'universe-file:' + view.spec.symbols_file
    for name in ['ml_predict_symbol_source', 'sentiment_pipeline_symbol_source',
                 'data_integrity_quotes_symbol_source', 'data_integrity_earnings_symbol_source']:
        assert getattr(opts, name) == source
    assert opts.data_integrity_quotes_mode == 'historical'
    assert opts.data_integrity_quotes_from_date == '2026-11-12'
    assert opts.data_integrity_quotes_to_date == '2026-11-19'
    assert opts.data_integrity_earnings_to_date == '2026-12-19'
    assert opts.eodhd_import_target_date == '2026-11-19'
    for stage in ['ml_predict', 'risk_management', 'execution']:
        command = build_pipeline_command(stage, opts)
        assert command[3] == 'service.q051_paper.pipeline'
        assert command[command.index('--profile-id') + 1] == deployed['profile_id']
        assert command[command.index('--batch-id') + 1] == deployed['model_batch_id']
        assert command[command.index('--run-id') + 1] == opts.q051_run_id


def test_friday_choice_and_preclose_guard_remain_scheduled(monkeypatch):
    monkeypatch.setattr(us_pipeline, 'load_pipeline_policy', lambda: dict(
        steps=[1, 2], steps_friday=[1], execution_mode='simulate', run_other_paper_accounts=False))
    view = ui.load_defaults(now=datetime(2026, 11, 20, 18, tzinfo=UTC))
    assert view.skip_reason == 'SESSION_NOT_CLOSED'
    assert view.steps_source == 'steps_friday' and [s.num for s in view.steps] == ['1']
    assert view.options.trade_date == '2026-11-20'
    assert view.options.execution_mode == 'simulate'
    assert not view.options.q051_paper_enabled


def test_no_implicit_live_route_in_manual_defaults(monkeypatch):
    monkeypatch.setattr(us_pipeline, 'load_pipeline_policy', lambda: dict(
        steps=[1], execution_mode='live', run_other_paper_accounts=False))
    with pytest.raises(ValueError, match='paper'):
        ui.load_defaults(now=datetime(2026, 11, 19, 22, tzinfo=UTC))


def test_manual_launch_delegates_to_exact_batch_launcher(default_view, monkeypatch):
    captured = {}
    def fake_start(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(run_id='not-executed-test')
    monkeypatch.setattr(batch_management, 'start_managed_run', fake_start)
    record = ui.launch(default_view, db_config={'name': 'alpha_trade'})
    assert record.run_id == 'not-executed-test'
    assert captured['command'] == batch_management.build_run_command(default_view.spec)
    assert captured['step_key'] == 'batch:us_pipeline'
    assert captured['db_config'] == {'name': 'alpha_trade'}
    assert captured['notify_on_finish'] is False  # Native batch notification, no duplicate.


def test_manual_catchup_keeps_existing_recovery_guard(default_view, monkeypatch):
    calls=[]
    monkeypatch.setattr(ui, 'start_batch', lambda spec, **kwargs: calls.append((spec, kwargs)))
    ui.launch(default_view, db_config={'name':'alpha_trade'}, recovery_date='2026-11-18')
    assert calls == [(default_view.spec, dict(db_config={'name':'alpha_trade'}, recovery_date='2026-11-18'))]


def test_page_ignores_old_custom_settings_when_shared_defaults_selected(monkeypatch):
    from ihm.pages import pipeline
    seen=[]
    monkeypatch.setattr(pipeline,'select_market',lambda *a:'US_EQ')
    monkeypatch.setattr(pipeline.st,'header',lambda *a,**k:None)
    monkeypatch.setattr(pipeline.st,'caption',lambda *a,**k:None)
    def checkbox(*a,**kwargs):
        assert kwargs['value'] is True and kwargs['key']==ui.MODE_KEY
        return True
    monkeypatch.setattr(pipeline.st,'checkbox',checkbox)
    monkeypatch.setattr(pipeline,'_merge_runs',lambda:([],[]))
    monkeypatch.setattr(pipeline,'get_runtime_db_config',lambda:{'name':'alpha_trade'})
    monkeypatch.setattr(ui,'render',lambda **kwargs:seen.append(kwargs))
    monkeypatch.setattr(pipeline,'_render_runtime_center',lambda:seen.append('runtime'))
    monkeypatch.setattr(pipeline,'render_pending_local_symbol_bars_dialog',lambda:None)
    monkeypatch.setattr(pipeline,'_build_launch_options',lambda:pytest.fail('Old custom defaults used'))
    monkeypatch.setattr(pipeline,'_render_workflow_launcher',lambda *a:pytest.fail('Custom launcher used'))
    pipeline.render()
    assert seen==[dict(db_config={'name':'alpha_trade'},active_runs=[]),'runtime']


def test_render_does_not_launch_until_clicked(default_view, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(ui, 'load_defaults', lambda: default_view)
    monkeypatch.setattr(ui, 'us_pipeline_recovery_state', lambda spec: {'visible':False})
    monkeypatch.setattr(ui, 'render_selection', lambda view: None)
    calls=[]
    monkeypatch.setattr(ui, 'launch', lambda *a, **kwargs: calls.append(kwargs) or SimpleNamespace(run_id='fake'))
    app=AppTest.from_string('''
import streamlit as st
from ihm.components.pipeline_batch_defaults import MODE_KEY,render
if st.checkbox('Utiliser la configuration du batch us_pipeline',value=True,key=MODE_KEY):
    render(db_config={'name':'alpha_trade'},active_runs=[])
''').run(timeout=30)
    assert not app.exception
    assert app.checkbox[0].value is True
    assert not calls
    app.button(key='pipeline_launch_us_batch_defaults').click().run(timeout=30)
    assert not app.exception
    assert calls == [{'db_config':{'name':'alpha_trade'}}]


@pytest.mark.parametrize('reason', ['SESSION_NOT_CLOSED', 'NON_TRADING_DAY'])
def test_page_cannot_silently_bypass_session_guard(default_view, monkeypatch, reason):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(ui,'load_defaults',lambda:replace(default_view,skip_reason=reason))
    monkeypatch.setattr(ui,'us_pipeline_recovery_state',lambda spec:{'visible':False})
    monkeypatch.setattr(ui,'render_selection',lambda view:None)
    app=AppTest.from_string('''
from ihm.components.pipeline_batch_defaults import render
render(db_config={'name':'alpha_trade'},active_runs=[])
''').run(timeout=30)
    assert not app.exception
    assert app.button(key='pipeline_launch_us_batch_defaults').disabled


def test_daily_selection_display_requires_matching_seals(default_view, monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest
    import json
    import pandas as pd
    from service.q051_paper import pipeline
    monkeypatch.setattr(pipeline, 'ARTIFACTS', tmp_path)
    folder=tmp_path/('q051-'+'a'*32);folder.mkdir()
    frame=pd.DataFrame([dict(symbol='EXAMPLE',proba_extreme=.9,long_probability=.8,long_auc=.65,selected=True)])
    frame.to_parquet(folder/'selection.parquet')
    report=dict(status='COMPLETED',trade_date=default_view.options.trade_date,
                batch_id=default_view.options.ml_predict_batch_id,
                strategy_profile=default_view.options.q051_profile_id,run_id=folder.name,
                cutoff='2026-11-19T22:00:00+00:00',selection_sha256=pipeline.digest(folder/'selection.parquet'))
    (folder/'selection.json').write_text(json.dumps(report))
    (folder/'seal.json').write_text(json.dumps(dict(report_sha256=pipeline.digest(folder/'selection.json'))))
    account_folder=folder/'accounts'/'default';account_folder.mkdir(parents=True)
    risk=dict(risk_run_id='risk-example',q051_run_id=folder.name,account_id='default',equity=4000.,
              trade_date=report['trade_date'],
              selection_sha256=pipeline.digest(folder/'selection.json'),approved_count=1,rejected_count=0,
              decisions=[dict(symbol='EXAMPLE',decision='APPROVED',approved_shares=4,entry_price=100.,target_notional=400.)])
    (account_folder/'risk.json').write_text(json.dumps(risk))
    (account_folder/'risk.seal.json').write_text(json.dumps(dict(risk_sha256=pipeline.digest(account_folder/'risk.json'))))
    monkeypatch.setattr(ui,'load_defaults',lambda:default_view)
    source='''
from ihm.components.pipeline_batch_defaults import render_selection,load_defaults
from ihm.components.prediction_review_table import _registered_table_component
_registered_table_component.clear()
render_selection(load_defaults())
'''
    app=AppTest.from_string(source).run(timeout=30)
    assert not app.exception
    demo=json.loads(app.get('bidi_component')[0].proto.json)
    assert [r['symbol'] for r in demo['rows']]==['AAPL','MSFT','NVDA']
    assert app.dataframe[0].value.iloc[0]['Symbole']=='EXAMPLE'
    assert app.dataframe[0].value.iloc[0]['Score Oracle']==.9
    assert app.dataframe[1].value.iloc[0]['Quantité']==4
    frame.assign(long_probability=.99).to_parquet(folder/'selection.parquet')
    app.run(timeout=30)
    assert not app.exception and not app.dataframe  # demo component remains; altered real selection is hidden.
    assert any('Empreinte' in w.value for w in app.warning)
