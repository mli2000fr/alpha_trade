"""Local one-year popins: SQLite fixtures, no provider or trading calls."""
from contextlib import nullcontext
from datetime import date
from types import SimpleNamespace
import json

import pandas as pd
import pytest
from sqlalchemy import create_engine, event, text

from ihm.components import local_symbol_bars_dialog as chart

DAY = date(2026,10,16)


@pytest.fixture(autouse=True)
def no_consensus_database_calls(monkeypatch):
    # Consensus has its own SQLite/UI tests; these tests exercise bar windows.
    monkeypatch.setattr(chart,'render_symbol_consensus_panel',lambda *a:None)


@pytest.fixture
def engine():
    engine=create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.execute(text('''CREATE TABLE stock_bars_daily (symbol TEXT,date DATE,
            open FLOAT,high FLOAT,low FLOAT,close FLOAT,volume FLOAT,is_filled INTEGER,data_source TEXT)'''))
        for symbol,day in [('FUN','2025-10-15'),('FUN','2025-10-16'),('FUN','2026-10-16'),
                           ('FUN','2026-10-19'),('OTHER','2026-10-16')]:
            conn.execute(text('INSERT INTO stock_bars_daily VALUES (:symbol,:day,10,12,9,11,1000,0,\'alpaca_sip\')'),dict(symbol=symbol,day=day))
    return engine


def test_one_calendar_year_and_no_future_or_other_symbol(engine):
    statements=[]
    event.listen(engine,'before_cursor_execute',lambda c,cu,s,p,ctx,many:statements.append(s))
    result=chart.load_local_symbol_bars(engine,'FUN',DAY)
    assert result['start']==date(2025,10,16) and result['end']==DAY
    assert result['bars']['date'].dt.date.tolist()==[date(2025,10,16),DAY]
    assert len(statements)==1 and statements[0].lstrip().upper().startswith('SELECT')


def test_leap_day_window_is_calendar_year_not_365_days():
    assert chart.annual_window(date(2024,2,29))==(date(2023,2,28),date(2024,2,29))


def test_unknown_symbol_does_not_fallback_to_network(engine):
    result=chart.load_local_symbol_bars(engine,'UNKNOWN',DAY)
    assert result['bars'].empty and result['stats']['received']==0


def test_parameter_binding_does_not_interpolate_symbol(engine):
    assert chart.load_local_symbol_bars(engine,"FUN'",DAY)['bars'].empty


@pytest.mark.parametrize('symbol',['',None,'A'*33,'FUN OR OTHER'])
def test_invalid_symbol_refused_before_query(engine,symbol):
    with pytest.raises(ValueError,match='Symbole invalide'):
        chart.load_local_symbol_bars(engine,symbol,DAY)


def test_filled_and_invalid_ohlc_are_not_drawn_as_real_bars(engine):
    with engine.begin() as conn:
        conn.execute(text("UPDATE stock_bars_daily SET is_filled=1 WHERE date='2025-10-16'"))
        conn.execute(text("UPDATE stock_bars_daily SET high=5 WHERE date='2026-10-16'"))
    result=chart.load_local_symbol_bars(engine,'FUN',DAY)
    assert result['bars'].empty and result['stats']['excluded']==2
    assert result['stats']['filled_or_unknown']==1 and result['stats']['invalid_prices']==1


def test_missing_volume_stays_missing_not_zero(engine):
    with engine.begin() as conn:
        conn.execute(text("UPDATE stock_bars_daily SET volume=-1 WHERE date='2026-10-16'"))
    result=chart.load_local_symbol_bars(engine,'FUN',DAY)
    assert len(result['bars'])==2 and pd.isna(result['bars'].iloc[-1]['volume'])
    assert result['stats']['missing_volume']==1


def test_figure_is_candles_and_volume_from_the_actual_rows(engine):
    bars=chart.load_local_symbol_bars(engine,'FUN',DAY)['bars']
    figure=chart.build_bars_figure(bars)
    assert [trace.type for trace in figure.data]==['candlestick','bar']
    assert list(figure.data[0].close)==[11,11] and list(figure.data[1].y)==[1000,1000]


@pytest.mark.parametrize('months,start',[(12,date(2025,10,16)),(6,date(2026,4,16)),(1,date(2026,9,16))])
def test_periods_bound_query_without_changing_cutoff(engine,months,start):
    result=chart.load_local_symbol_bars(engine,'FUN',DAY,months)
    assert result['start']==start and result['end']==DAY
    assert result['bars']['date'].max().date()==DAY


@pytest.fixture
def fake_dialog(monkeypatch):
    calls=dict(info=[],warning=[],plotly_chart=[],caption=[])
    monkeypatch.setattr(chart.st,'subheader',lambda *a,**kw:None)
    monkeypatch.setattr(chart.st,'spinner',lambda *a,**kw:nullcontext())
    monkeypatch.setattr(chart.st,'expander',lambda *a,**kw:nullcontext())
    monkeypatch.setattr(chart.st,'columns',lambda n:[SimpleNamespace(metric=lambda *a,**kw:None) for _ in range(n)])
    monkeypatch.setattr(chart.st,'dataframe',lambda *a,**kw:None)
    monkeypatch.setattr(chart.st,'button',lambda *a,**kw:False)
    monkeypatch.setattr(chart.st,'segmented_control',lambda *a,**kw:'1 an')
    for kind in calls:
        monkeypatch.setattr(chart.st,kind,lambda value,*a,_kind=kind,**kw:calls[_kind].append(value))
    return calls


def test_dialog_draws_local_figure_and_states_cutoff(engine,fake_dialog,monkeypatch):
    result=chart.load_local_symbol_bars(engine,'FUN',DAY)
    monkeypatch.setattr(chart,'_cached_local_symbol_bars',lambda *a:result)
    chart._render_local_bars_dialog_body('FUN',DAY,'Six Flags')
    assert len(fake_dialog['plotly_chart'])==1
    assert any('arrêtée à la séance de l’analyse' in s and 'aucun appel fournisseur' in s for s in fake_dialog['caption'])


def test_dialog_empty_is_not_a_silent_provider_download(engine,fake_dialog,monkeypatch):
    result=chart.load_local_symbol_bars(engine,'UNKNOWN',DAY)
    monkeypatch.setattr(chart,'_cached_local_symbol_bars',lambda *a:result)
    chart._render_local_bars_dialog_body('UNKNOWN',DAY)
    assert fake_dialog['info'] and not fake_dialog['plotly_chart']


def test_dialog_sql_failure_does_not_expose_credentials(fake_dialog,monkeypatch):
    def fail(*a):
        raise RuntimeError('secret connection token')
    monkeypatch.setattr(chart,'_cached_local_symbol_bars',fail)
    chart._render_local_bars_dialog_body('FUN',DAY)
    assert fake_dialog['warning'] and 'secret connection token' not in str(fake_dialog)


def test_real_streamlit_button_opens_native_dialog_and_chart(engine,monkeypatch,tmp_path):
    import tempfile
    monkeypatch.setattr(tempfile,'tempdir',str(tmp_path))
    from streamlit.testing.v1 import AppTest
    import streamlit.testing.v1.app_test as app_test_module
    monkeypatch.setattr(app_test_module,'TMP_DIR',SimpleNamespace(name=str(tmp_path)))
    results={m:chart.load_local_symbol_bars(engine,'FUN',DAY,m) for m in (12,6,1)}
    loaded=[]
    def fetch(symbol,end,months=12):
        loaded.append(months)
        return results[months]
    monkeypatch.setattr(chart,'_cached_local_symbol_bars',fetch)
    app=AppTest.from_string('''
import streamlit as st
from ihm.components.local_symbol_bars_dialog import (
    request_local_symbol_bars_dialog, render_pending_local_symbol_bars_dialog)
@st.fragment(run_every='2s')
def panel():
    if st.button('Voir',key='open_bars'):
        request_local_symbol_bars_dialog('FUN','2026-10-16','Six Flags')
panel()
render_pending_local_symbol_bars_dialog()
''').run(timeout=20)
    assert not app.exception
    app.button(key='open_bars').click().run(timeout=20)
    assert not app.exception and len(app.get('plotly_chart'))==1
    assert any('Barres journalières' in heading.value for heading in app.subheader)
    period=app.get('button_group')[0]
    assert period.options==['1 an','6 mois','1 mois']
    assert loaded[-1]==12
    app.button(key='local_bars_close_FUN_2026-10-16').click().run(timeout=20)
    assert not app.exception and len(app.get('plotly_chart'))==0


def test_real_period_controls_reload_matching_window(engine,monkeypatch,tmp_path):
    import tempfile
    monkeypatch.setattr(tempfile,'tempdir',str(tmp_path))
    from streamlit.testing.v1 import AppTest
    import streamlit.testing.v1.app_test as app_test_module
    monkeypatch.setattr(app_test_module,'TMP_DIR',SimpleNamespace(name=str(tmp_path)))
    results={m:chart.load_local_symbol_bars(engine,'FUN',DAY,m) for m in (12,6,1)}
    loaded=[]
    def fetch(symbol,end,months=12):
        loaded.append(months)
        return results[months]
    monkeypatch.setattr(chart,'_cached_local_symbol_bars',fetch)
    app=AppTest.from_string('''
from ihm.components.local_symbol_bars_dialog import _render_local_bars_dialog_body
_render_local_bars_dialog_body('FUN','2026-10-16','Six Flags')
''').run(timeout=20)
    assert not app.exception and loaded[-1]==12
    app.get('button_group')[0].set_value('6 mois').run(timeout=20)
    assert not app.exception and loaded[-1]==6 and len(app.get('plotly_chart'))==1
    assert any('16/04/2026' in caption.value for caption in app.caption)
    figure=json.loads(app.get('plotly_chart')[0].proto.spec)
    assert figure['layout']['xaxis']['range']==['2026-04-16','2026-10-16']
    app.get('button_group')[0].set_value('1 mois').run(timeout=20)
    assert not app.exception and loaded[-1]==1 and len(app.get('plotly_chart'))==1
    assert any('16/09/2026' in caption.value for caption in app.caption)
    figure=json.loads(app.get('plotly_chart')[0].proto.spec)
    assert figure['layout']['xaxis']['range']==['2026-09-16','2026-10-16']


def test_dialog_request_defers_opening_until_page_scope(monkeypatch):
    state, opened, reruns = {}, [], []
    monkeypatch.setattr(chart.st,'session_state',state)
    monkeypatch.setattr(chart.st,'rerun',lambda **kw:reruns.append(kw))
    monkeypatch.setattr(chart,'show_local_symbol_bars_dialog',lambda *a:opened.append(a))
    chart.request_local_symbol_bars_dialog('FUN',DAY,'Six Flags')
    assert not opened and reruns==[{'scope':'app'}]
    chart.render_pending_local_symbol_bars_dialog()
    assert opened==[('FUN',DAY,'Six Flags')] and not state
    chart.render_pending_local_symbol_bars_dialog()
    assert len(opened)==1  # no reopening on an unrelated rerun


def test_consensus_is_shown_even_without_bars(engine,fake_dialog,monkeypatch):
    calls=[]
    monkeypatch.setattr(chart,'_cached_local_symbol_bars',lambda *a:chart.load_local_symbol_bars(engine,'UNKNOWN',DAY))
    monkeypatch.setattr(chart,'render_symbol_consensus_panel',lambda *a:calls.append(a))
    chart._render_local_bars_dialog_body('UNKNOWN',DAY)
    assert calls==[('UNKNOWN',DAY)] and fake_dialog['info']
