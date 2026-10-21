"""Step 4 must never request SIP real-time by default (no production I/O)."""
from datetime import datetime

import pytest

from ihm.services.pipeline_quote_scope import quote_defaults, resolve_quote_scope, DEFAULT_SOURCE
from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command


@pytest.mark.parametrize('now,expected', [
    ('2026-10-20T08:02:00+02:00','2026-10-19'),
    ('2026-10-19T20:00:00+02:00','2026-10-16'),
    ('2026-10-19T22:19:00+02:00','2026-10-16'),
    ('2026-10-19T22:20:00+02:00','2026-10-19'),
    ('2026-10-20T00:02:00+02:00','2026-10-19'),
    ('2026-10-18T08:00:00+02:00','2026-10-16'),
    ('2026-07-06T08:00:00+02:00','2026-07-02'),
    ('2026-11-04T22:19:00+01:00','2026-11-03'),
    ('2026-11-04T22:20:00+01:00','2026-11-04'),
    ('2026-11-27T19:20:00+01:00','2026-11-27'),
])
def test_latest_closed_session_morning_weekend_holiday_dst_and_halfday(now,expected):
    options=PipelineLaunchOptions()
    result=resolve_quote_scope(options,now=datetime.fromisoformat(now),config={})
    assert result.data_integrity_quotes_mode=='historical'
    assert result.data_integrity_quotes_to_date==expected
    assert result.data_integrity_quotes_symbol_source==DEFAULT_SOURCE
    assert result.trade_date is None and options.data_integrity_quotes_to_date is None


def test_date_upper_bound_does_not_advance_a_previous_workflow_session():
    options=PipelineLaunchOptions(trade_date='2026-10-16')
    result=resolve_quote_scope(options,now=datetime.fromisoformat('2026-10-20T08:00:00+02:00'),config={})
    assert result.data_integrity_quotes_from_date=='2026-10-09'
    assert result.data_integrity_quotes_to_date==options.trade_date


def test_explicit_history_dates_source_and_limits_are_preserved():
    options=PipelineLaunchOptions(data_integrity_quotes_from_date='2026-04-01',
        data_integrity_quotes_to_date='2026-04-30',data_integrity_quotes_symbol_source='stock_bars_daily',
        data_integrity_quotes_limit=12)
    result=resolve_quote_scope(options,config={'market_data':{'pipeline_quotes':{'mode':'latest'}}})
    assert result.data_integrity_quotes_mode=='historical'
    assert result.data_integrity_quotes_from_date=='2026-04-01'
    assert result.data_integrity_quotes_to_date=='2026-04-30'
    assert result.data_integrity_quotes_symbol_source=='stock_bars_daily'
    assert result.data_integrity_quotes_limit==12


def test_latest_remains_explicit_and_has_no_synthetic_dates():
    result=resolve_quote_scope(PipelineLaunchOptions(data_integrity_quotes_mode='latest'),config={})
    assert result.data_integrity_quotes_mode=='latest'
    assert result.data_integrity_quotes_from_date is result.data_integrity_quotes_to_date is None
    command=build_pipeline_command('sync_latest_quotes',result)
    assert '--from-date' not in command and '--to-date' not in command
    assert command[command.index('--feed')+1]=='sip'


@pytest.mark.parametrize('policy',[{'mode':'iex'}, {'lookback_days':-1}, {'lookback_days':True},
    {'lookback_days':1.5},{'symbol_source':''},{'symbol_source':'unexpected'}])
def test_invalid_policy_blocks_not_broadens_scope(policy):
    with pytest.raises(ValueError):
        quote_defaults({'market_data':{'pipeline_quotes':policy}})


def test_no_iex_or_conflicting_modes_and_no_weekday_calendar_fallback(monkeypatch):
    with pytest.raises(ValueError,match='SIP'):
        quote_defaults({'market_data':{'quotes_historical_feed':'iex'}})
    with pytest.raises(ValueError,match='incompatible'):
        resolve_quote_scope(PipelineLaunchOptions(data_integrity_quotes_mode='latest',
            data_integrity_quotes_to_date='2026-10-19'),config={})
    with pytest.raises(ValueError):
        resolve_quote_scope(PipelineLaunchOptions(data_integrity_quotes_from_date='bad'),config={})
    import ihm.services.pipeline_quote_scope as module
    def unavailable(code,**kwargs):
        assert code=='US_EQ' and kwargs=={'allow_us_weekday_fallback':False}
        raise RuntimeError('calendar missing')
    monkeypatch.setattr(module,'get_market_calendar',unavailable)
    with pytest.raises(RuntimeError,match='missing'):
        resolve_quote_scope(PipelineLaunchOptions(),config={})


def test_effective_historical_command_cannot_fall_back_to_latest():
    options=resolve_quote_scope(PipelineLaunchOptions(),config={},
        now=datetime.fromisoformat('2026-10-20T08:02:00+02:00'))
    command=build_pipeline_command('sync_latest_quotes',options)
    assert command[command.index('--from-date')+1]=='2026-10-12'
    assert command[command.index('--to-date')+1]=='2026-10-19'
    assert command[command.index('--symbol-source')+1]==DEFAULT_SOURCE
    assert 'active-tradable' not in command


def test_custom_file_preview_never_expands_to_active_tradable(monkeypatch):
    from ihm.pages import pipeline
    seen=[]
    monkeypatch.setattr(pipeline,'list_symbols_for_source',lambda source,**kw:seen.append(source) or ['AAPL'])
    # Bypass caching, which is unrelated to the scope contract.
    preview=pipeline._resolve_data_integrity_scope_preview.__wrapped__(DEFAULT_SOURCE)
    assert preview['symbol_count']==1 and seen==[DEFAULT_SOURCE]
    with pytest.raises(ValueError,match='inconnu'):
        pipeline._resolve_data_integrity_scope_preview.__wrapped__('invalid-source')


def test_schedule_forces_historical_even_if_page_config_is_latest(monkeypatch):
    from datetime import date
    from service.forward_pit.us_pipeline import collection_options
    import ihm.services.pipeline_quote_scope as module
    monkeypatch.setattr(module,'load_config',lambda:{'market_data':{'pipeline_quotes':{'mode':'latest'}}})
    options=collection_options(PipelineLaunchOptions(data_integrity_quotes_mode='latest'),
        {'symbols_file':'config/univers_batch/univers_filtred_tradable.txt',
         'quotes_collection':{'lookback_days':7,'batch_size':200}},date(2026,10,19))
    command=build_pipeline_command('sync_latest_quotes',options)
    assert options.data_integrity_quotes_mode=='historical'
    assert command[command.index('--to-date')+1]=='2026-10-19'


def test_mode_widget_defaults_historical_and_can_explicitly_select_latest(monkeypatch,tmp_path):
    import tempfile
    monkeypatch.setattr(tempfile,'tempdir',str(tmp_path))
    from streamlit.testing.v1 import AppTest
    from streamlit.testing.v1 import app_test
    from types import SimpleNamespace
    monkeypatch.setattr(app_test,'TMP_DIR',SimpleNamespace(name=str(tmp_path)))
    import ihm.services.pipeline_quote_scope as module
    monkeypatch.setattr(module,'load_config',lambda:{})
    app=AppTest.from_string('''import streamlit as st
from ihm.pages._execution_center import _render_data_integrity_block
result=_render_data_integrity_block()
st.write('MODE='+str(result['data_integrity_quotes_mode']))
''').run(timeout=20)
    assert not app.exception
    assert app.selectbox(key='pipeline_data_integrity_quotes_mode_v2').value=='historical'
    app.selectbox(key='pipeline_data_integrity_quotes_mode_v2').select('latest').run()
    assert not app.exception
    assert any('MODE=latest' in item.value for item in app.markdown)


def test_history_panel_offers_configured_batch_file_without_broadening(monkeypatch,tmp_path):
    from types import SimpleNamespace
    from streamlit.testing.v1 import AppTest, app_test
    from ihm.pages import pipeline
    monkeypatch.setattr(app_test,'TMP_DIR',SimpleNamespace(name=str(tmp_path)))
    monkeypatch.setattr(pipeline,'_resolve_data_integrity_scope_preview',
        lambda *a,**kw:{'symbol_count':1,'sample_symbols':['AAPL']})
    monkeypatch.setattr(pipeline,'estimate_sync_latest_quotes_cost',lambda **kw:{'warning_required':False})
    launches=[]
    monkeypatch.setattr(pipeline,'_launch_pipeline_step',lambda step,label,options,*a:launches.append(options))
    app=AppTest.from_string('''from ihm.pages.pipeline import _render_period_sync_block, PipelineLaunchOptions
_render_period_sync_block('sync_latest_quotes',PipelineLaunchOptions(),workflow_active=False,
    active_for_step=[],db_config={},all_runs=[])
''').run()
    assert not app.exception
    assert app.selectbox(key=pipeline.QUOTE_HISTORY_SYMBOL_SOURCE_KEY).value==DEFAULT_SOURCE
    app.button(key='sync_latest_quotes_historical_period_launch').click().run()
    assert not app.exception and len(launches)==1
    assert launches[0].data_integrity_quotes_symbol_source==DEFAULT_SOURCE
    assert launches[0].data_integrity_quotes_mode=='historical'


def test_scope_failure_disables_only_quotes_panel(monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace
    from ihm.pages import pipeline
    import ihm.services.pipeline_quote_scope as scope
    def unavailable(*a,**kw):
        raise RuntimeError('calendar unavailable')
    monkeypatch.setattr(scope,'resolve_quote_scope',unavailable)
    errors=[];buttons=[]
    monkeypatch.setattr(pipeline,'st',SimpleNamespace(expander=lambda *a,**kw:nullcontext(),
        error=errors.append,button=lambda *a,**kw:buttons.append(kw)))
    monkeypatch.setattr(pipeline,'_render_step_result',lambda *a:None)
    step=next(s for s in pipeline.get_pipeline_steps() if s.key=='sync_latest_quotes')
    pipeline._render_launchable_step_panel(step,PipelineLaunchOptions(),False,{},
        workflow_active=False,active_by_step={},all_runs=[],latest_by_step={},
        dependency_diagnostic=None,live_guard={})
    assert buttons[0]['disabled'] and 'calendar unavailable' in errors[0]
