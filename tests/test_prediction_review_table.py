"""Native inline graph action: payload, event routing, client-side sorting."""
import json
import shutil
import subprocess
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from ihm.components import prediction_review_table as table


def frame():
    return pd.DataFrame([{'Rang Oracle':1,'Symbole':'FUN','Nom de l’entreprise':'Six Flags',
        'Score Oracle':.9,'Dernier prix ($)':8.11,'Date du prix':date(2026,10,16),'Retenu':False},
        {'Rang Oracle':2,'Symbole':'FMC','Nom de l’entreprise':'FMC Corp',
        'Score Oracle':.8,'Dernier prix ($)':5.66,'Date du prix':date(2026,10,16),'Retenu':True}])


def test_button_column_is_in_table_after_symbol_not_a_period_label():
    payload=table.table_payload(frame())
    assert [c['label'] for c in payload['columns']][:4]==['Rang Oracle','Symbole','Graphique','Nom de l’entreprise']
    assert payload['columns'][2]['action']
    assert payload['rows'][0]['cells'][4]['text']=='0.900000'
    assert payload['rows'][0]['cells'][5]['text']=='8.1100 $'
    assert payload['rows'][0]['cells'][6]['text']=='16/10/2026'
    assert payload['rows'][0]['cells'][7]['text']=='Non'


@pytest.mark.parametrize('symbol,expected',[('FUN','FUN'),('FMC','FMC'),('UNKNOWN',None),(None,None),([],None)])
def test_trigger_resolves_exact_symbol_not_visible_row_position(monkeypatch,symbol,expected):
    calls,opened=[],[]
    def mount(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(open_symbol=symbol)
    monkeypatch.setattr(table,'_table_component',mount)
    monkeypatch.setattr(table,'request_local_symbol_bars_dialog',lambda *a:opened.append(a))
    table.render_prediction_review_table(frame(),key='step_10_run',trade_date='2026-10-16')
    assert calls[0]['key']=='step_10_run_graph_v2'
    assert 'open_symbol' not in calls[0].get('default',{})
    assert opened==([(expected,'2026-10-16','Six Flags' if expected=='FUN' else 'FMC Corp')] if expected else [])


def test_no_graph_query_or_dialog_on_plain_table_render(monkeypatch):
    monkeypatch.setattr(table,'_table_component',lambda **kw:SimpleNamespace(open_symbol=None))
    monkeypatch.setattr(table,'request_local_symbol_bars_dialog',lambda *a:pytest.fail('only open on click'))
    table.render_prediction_review_table(frame(),key='step_11_run',trade_date='2026-10-16')


def test_empty_table_does_not_mount_and_duplicate_symbols_are_rejected(monkeypatch):
    monkeypatch.setattr(table,'_table_component',lambda **kw:pytest.fail('no empty component'))
    table.render_prediction_review_table(pd.DataFrame(),key='empty',trade_date='2026-10-16')
    with pytest.raises(ValueError,match='unique'):
        table.table_payload(pd.concat([frame(),frame()]))


def test_client_button_remains_bound_to_symbol_after_sorting_and_escapes_text():
    node=shutil.which('node')
    if not node:
        pytest.skip('Node requis pour vérifier le code client du composant')
    data=frame()
    data.loc[0,'Nom de l’entreprise']='<img src=x onerror=alert(1)>'
    payload=table.table_payload(data)
    script='''
import assert from 'node:assert/strict';
const {default:render}=await import('data:text/javascript;base64,'+Buffer.from(SOURCE).toString('base64'));
class Element {
 constructor(tag) {this.tag=tag;this.children=[];this.scrollLeft=0;this.scrollTop=0;this.textContent='';}
 appendChild(child){this.children.push(child);return child;}
 replaceChildren(){this.children=[];}
 setAttribute(key,value){this[key]=value;}
}
globalThis.document={createElement:(tag)=>new Element(tag)};
const root=new Element('div'),events=[];
render({data:PAYLOAD,parentElement:{querySelector:()=>root},setTriggerValue:(name,value)=>events.push([name,value])});
const body=()=>root.children[0].children[1];
const head=()=>root.children[0].children[0].children[0];
const graph=(index)=>body().children[index].children[2].children[0];
assert.equal(graph(0).tag,'button'); assert.equal(graph(0).textContent,'📈 Voir');
assert.equal(body().children[0].children[3].textContent,'<img src=x onerror=alert(1)>');
assert.equal(body().children[0].children[3].children.length,0);
graph(0).onclick(); assert.deepEqual(events.pop(),['open_symbol','FUN']);
// Ascending score reorders the rows, without changing the action's identity.
head().children[4].children[0].onclick();
assert.equal(body().children[0].children[1].textContent,'FMC');
graph(0).onclick(); assert.deepEqual(events.pop(),['open_symbol','FMC']);
head().children[4].children[0].onclick();
assert.equal(body().children[0].children[1].textContent,'FUN');
graph(0).onclick(); assert.deepEqual(events.pop(),['open_symbol','FUN']);
'''.replace('SOURCE',json.dumps(table.JS)).replace('PAYLOAD',json.dumps(payload,ensure_ascii=True))
    result=subprocess.run([node,'--input-type=module','-'],input=script,text=True,encoding='utf-8',
        capture_output=True,timeout=20)
    assert result.returncode==0,result.stderr


def test_real_streamlit_component_mounts_without_extra_buttons(monkeypatch,tmp_path):
    import tempfile
    monkeypatch.setattr(tempfile,'tempdir',str(tmp_path))
    from streamlit.testing.v1 import AppTest
    import streamlit.testing.v1.app_test as app_test_module
    monkeypatch.setattr(app_test_module,'TMP_DIR',SimpleNamespace(name=str(tmp_path)))
    app=AppTest.from_string('''
import pandas as pd
from ihm.components.prediction_review_table import render_prediction_review_table
render_prediction_review_table(pd.DataFrame([{'Rang Oracle':1,'Symbole':'FUN','Score Oracle':.9}]),
    key='inline_table',trade_date='2026-10-16')
''').run(timeout=20)
    assert not app.exception and len(app.button)==0
    assert len(app.get('bidi_component'))==1


@pytest.mark.parametrize('step',[10,11])
def test_real_component_trigger_opens_dialog_and_can_reopen_after_close(monkeypatch,tmp_path,step):
    """Send the frontend's actual trigger protocol, not a mocked ComponentResult."""
    import tempfile
    monkeypatch.setattr(tempfile,'tempdir',str(tmp_path))
    from streamlit.testing.v1 import AppTest
    import streamlit.testing.v1.app_test as app_test_module
    from streamlit.components.v2.bidi_component.main import _make_trigger_id
    from ihm.components import local_symbol_bars_dialog as chart
    monkeypatch.setattr(app_test_module,'TMP_DIR',SimpleNamespace(name=str(tmp_path)))
    loaded=[]
    def fetch(symbol,end,months=12):
        loaded.append((symbol,end,months))
        return dict(bars=pd.DataFrame([dict(date=pd.Timestamp('2026-10-16'),
            open=10,high=12,low=9,close=11,volume=1000,data_source='alpaca_sip')]),
            stats=dict(excluded=0,missing_volume=0),start=date(2025,10,16),end=date(2026,10,16))
    monkeypatch.setattr(chart,'_cached_local_symbol_bars',fetch)
    monkeypatch.setattr(chart,'render_symbol_consensus_panel',lambda *a:None)
    app=AppTest.from_string(f'''
import pandas as pd
import streamlit as st
from ihm.components.prediction_review_table import render_prediction_review_table
# AppTest replaces its runtime/registry on each run, unlike the live server.
from ihm.components.prediction_review_table import _registered_table_component
_registered_table_component.clear()
@st.fragment(run_every='2s')
def panel():
    render_prediction_review_table(pd.DataFrame([{{'Rang Oracle':1,'Symbole':'FUN',
        'Nom de l’entreprise':'Six Flags','Score Oracle':.9}}]),
        key='pipeline_{step}_table_exact_run',trade_date='2026-10-16')
panel()
from ihm.components.local_symbol_bars_dialog import render_pending_local_symbol_bars_dialog
render_pending_local_symbol_bars_dialog()
from streamlit.runtime.scriptrunner import get_script_run_ctx
st.session_state['test_fragment_parents']=dict(get_script_run_ctx().fragment_storage._parent_by_id)
''').run(timeout=20)
    assert not app.exception and not loaded

    def click(symbol):
        # Bidi events use an internal aggregator separate from persistent state.
        widget_states=app._tree.get_widget_states()
        event=widget_states.widgets.add()
        event.id=_make_trigger_id(app.get('bidi_component')[0].proto.id,'events')
        event.json_trigger_value=json.dumps([dict(event='open_symbol',value=symbol)])
        app._run(widget_states,timeout=20)

    click('FUN')
    assert not app.exception and len(app.get('plotly_chart'))==1
    assert loaded[-1]==('FUN','2026-10-16',12)
    # Polling must not own the dialog, or its next tick unregisters controls.
    assert len(app.session_state['test_fragment_parents'])==2
    assert all(parent is None for parent in app.session_state['test_fragment_parents'].values())
    assert any('Six Flags' in caption.value for caption in app.caption)
    app.button(key='local_bars_close_FUN_2026-10-16').click().run(timeout=20)
    assert not app.exception and len(app.get('plotly_chart'))==0
    click('FUN')
    assert not app.exception and len(app.get('plotly_chart'))==1
    app.button(key='local_bars_close_FUN_2026-10-16').click().run(timeout=20)
    count=len(loaded)
    click('UNKNOWN')
    assert not app.exception and len(app.get('plotly_chart'))==0 and len(loaded)==count
