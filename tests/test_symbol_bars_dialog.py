"""Broker history follows its provider/account; SIP never falls back silently."""
from datetime import date
from contextlib import nullcontext

import pandas as pd
import pytest

from ihm.components import symbol_bars_dialog as ui


@pytest.fixture(autouse=True)
def clear_cache():
    ui._cached_symbol_bars.clear()
    yield
    ui._cached_symbol_bars.clear()


def test_sip_loader_normalizes_daily_dates_prices_and_selected_account(monkeypatch):
    calls=[]
    monkeypatch.setattr('common.verified_http.verified_session',lambda:nullcontext('verified-session'))
    def fetch(*args,**kwargs):
        calls.append((args,kwargs))
        return [dict(t='2026-11-19T05:00:00Z',o=10,h=12,l=9,c=11,v=500),
                dict(t='2026-11-18T05:00:00Z',o=9,h=10,l=8,c=9.5,v=400),
                dict(t='2026-11-17T05:00:00Z',o=0,h=12,l=9,c=11,v=500),
                dict(t='2026-10-01T04:00:00Z',o=10,h=12,l=9,c=11,v=500)]
    monkeypatch.setattr('service.alpaca.clientAlpaca.fetch_bars',fetch)
    frame=ui._fetch_bars_alpaca('FLEX',start=date(2026,11,1),end=date(2026,11,19),account_id='test1')
    assert frame.date.dt.date.tolist()==[date(2026,11,18),date(2026,11,19)]
    assert frame.close.tolist()==[9.5,11.] and frame.attrs['provider']=='alpaca_sip'
    assert calls==[(('FLEX','1Day'),dict(start_date='2026-11-01T00:00:00+00:00',account_id='test1',session='verified-session',feed='sip'))]


def test_real_shared_client_accepts_aware_boundary_and_keeps_first_daily_bar(monkeypatch):
    from types import SimpleNamespace
    from service.alpaca import clientAlpaca as client
    params=[]
    monkeypatch.setattr('common.verified_http.verified_session',lambda:nullcontext('verified-session'))
    monkeypatch.setattr(client,'_build_headers',lambda account:{})
    monkeypatch.setattr(client.time,'sleep',lambda *a:None)
    def request(*args,**kwargs):
        params.append(dict(kwargs['params']))
        return SimpleNamespace(json=lambda:dict(bars=[dict(t='2026-11-19T05:00:00Z',o=10,h=12,l=9,c=11,v=500)]))
    monkeypatch.setattr(client,'request_with_retry',request)
    frame=ui._fetch_bars_alpaca('FLEX',start=date(2026,11,19),end=date(2026,11,20),account_id='test2')
    assert len(frame)==1 and frame.iloc[0].date.date()==date(2026,11,19)
    assert params[0]['feed']=='sip' and params[0]['timeframe']=='1Day'
    assert params[0]['start']=='2026-11-19'


def test_configured_provider_and_account_are_part_of_cache_key(monkeypatch):
    provider=['alpaca'];calls=[]
    monkeypatch.setattr('ihm.services.market_data_provider.get_bars_provider',lambda:provider[0])
    monkeypatch.setattr(ui,'_fetch_bars_alpaca',lambda symbol,**kwargs:calls.append(('alpaca',symbol,kwargs['account_id'])) or pd.DataFrame(dict(close=[11.])))
    monkeypatch.setattr(ui,'_fetch_bars_eodhd',lambda symbol,**kwargs:calls.append(('eodhd',symbol,None)) or pd.DataFrame(dict(close=[10.])))
    monkeypatch.setattr(ui,'_fetch_bars_stooq',lambda *a,**k:pytest.fail('No unnecessary fallback'))
    assert ui.load_symbol_bars(' flex ',account_id='test1').close.iloc[0]==11.
    ui.load_symbol_bars('FLEX',account_id='test1')
    ui.load_symbol_bars('FLEX',account_id='test2')
    provider[0]='eodhd'
    assert ui.load_symbol_bars('FLEX',account_id='test1').close.iloc[0]==10.
    assert calls==[('alpaca','FLEX','test1'),('alpaca','FLEX','test2'),('eodhd','FLEX',None)]


def test_sip_failure_does_not_contact_eodhd_or_stooq(monkeypatch):
    monkeypatch.setattr('ihm.services.market_data_provider.get_bars_provider',lambda:'alpaca')
    monkeypatch.setattr('service.alpaca.clientAlpaca.fetch_bars',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('HTTP403')))
    monkeypatch.setattr('common.verified_http.verified_session',lambda:nullcontext('verified-session'))
    monkeypatch.setattr(ui,'_fetch_bars_eodhd',lambda *a,**k:pytest.fail('Unexpected EODHD request'))
    monkeypatch.setattr(ui,'_fetch_bars_stooq',lambda *a,**k:pytest.fail('Unexpected Stooq request'))
    assert ui.load_symbol_bars('FLEX',account_id='test1').empty


def test_dialog_uses_selected_account_and_period_and_correct_error_message(monkeypatch):
    from streamlit.testing.v1 import AppTest
    loaded=[]
    monkeypatch.setattr('ihm.services.market_data_provider.get_bars_provider',lambda:'alpaca')
    monkeypatch.setattr(ui,'load_symbol_bars',lambda symbol,lookback_days,account_id:loaded.append((symbol,lookback_days,account_id)) or pd.DataFrame())
    app=AppTest.from_string('''
from ihm.components.symbol_bars_dialog import _render_dialog_body
_render_dialog_body('FLEX',365,account_id='test1')
''').run(timeout=20)
    assert not app.exception and loaded[-1]==('FLEX',365,'test1')
    assert any('Alpaca SIP' in m.value for m in app.warning)
    assert all('EODHD' not in m.value for m in app.warning)
    app.selectbox[0].set_value('1 mois').run(timeout=20)
    assert not app.exception and loaded[-1]==('FLEX',31,'test1')


def test_symbol_table_forwards_the_account_to_the_dialog(monkeypatch):
    from ihm.components import symbol_table as table
    from types import SimpleNamespace
    opened=[]
    monkeypatch.setattr(table.st,'columns',lambda n:[SimpleNamespace(button=lambda *a,**k:True)])
    monkeypatch.setattr(table,'show_symbol_bars_dialog',lambda *a,**kw:opened.append((a,kw)))
    table._render_action_bar(df=pd.DataFrame(dict(symbol=['FLEX'])),row_index=0,symbol='FLEX',
        table_key='accounts',extra_actions=[],bars_lookback_days=365,bars_account_id='test2')
    assert opened==[(('FLEX',),dict(lookback_days=365,account_id='test2'))]
