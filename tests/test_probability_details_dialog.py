"""Exact archived issuer, graph period changes and no approval when inspecting."""
from datetime import date
import json
from types import SimpleNamespace

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from tests.test_q051_human_selection import proposal
from ihm.components import probability_details_dialog as details,local_symbol_bars_dialog as chart


def packet():
    return dict(symbol='B',trade_date='2026-11-19',llm_run_id='llm-example',provider='GPT',
        evidence_cutoff_utc='2026-11-19T22:00:00+00:00',
        assessment=dict(probability_up_without_stop=.9,evidence_quality='SUFFICIENT',
            probability_explanation='Explication archivée exacte du titre B.',
            evidence_explanation='Deux sources datées.',bull_case='Cas favorable B',bear_case='Cas défavorable B',
            consensus_analysis='Consensus manquant : recherche Web effectuée.',context_analysis='Contexte de B',
            risk_factors=['Risque exemple'],sources=[dict(url='https://example.org/issuer-b',published_at='2026-11-18')]))


def bars(symbol,end,months=12):
    start=(pd.Timestamp(end)-pd.DateOffset(months=months)).date()
    frame=pd.DataFrame([dict(date=pd.Timestamp(d),open=10.,high=12.,low=9.,close=11.,volume=1000,data_source='alpaca_sip')
                        for d in pd.bdate_range(start,end)])
    return dict(bars=frame,stats=dict(excluded=0,missing_volume=0),start=start,end=date.fromisoformat(end))


def test_archived_details_require_exact_sealed_candidate_and_llm_receipt(proposal,monkeypatch):
    folder,report,_=proposal
    payload=packet()
    run=dict(input_sha256=report['llm_filter']['input_sha256'],batch_id=report['batch_id'],
        trade_date=report['trade_date'],input_json=json.dumps(dict(candidates=[dict(symbol='B',local_data_status={},
            evidence_cutoff_utc=payload['evidence_cutoff_utc'])])))
    item=dict(symbol='B',status='VALID',assessment_json=json.dumps(payload['assessment']))
    monkeypatch.setattr('service.llm_directional.repository.Repository',lambda engine:SimpleNamespace(get=lambda run_id:(run,[item])))
    result=details.load_analysis(None,report['run_id'],'B')
    assert result['assessment']['bull_case']=='Cas favorable B'
    with pytest.raises(ValueError,match='absent'):details.load_analysis(None,report['run_id'],'OTHER')
    run['input_sha256']='wrong'
    with pytest.raises(ValueError,match='différente'):details.load_analysis(None,report['run_id'],'B')


def test_inline_button_opens_details_periods_change_and_no_choice_is_published(proposal,monkeypatch):
    from ihm.components import probability_selection as selection
    from service.q051_paper.human_selection import approval_path
    from streamlit.components.v2.bidi_component.main import _make_trigger_id
    folder,report,frame=proposal
    monkeypatch.setattr(selection,'_test_proposal',proposal,raising=False)
    monkeypatch.setattr('ihm.services.db.get_engine',lambda:None)
    monkeypatch.setattr(details,'load_analysis',lambda *a:packet())
    loaded=[]
    def fetch(symbol,end,months=12):
        loaded.append((symbol,end,months));return bars(symbol,end,months)
    monkeypatch.setattr(chart,'_cached_local_symbol_bars',fetch)
    script='''
import streamlit as st
from ihm.components.probability_selection import render,_test_proposal
from ihm.components.prediction_review_table import _registered_table_component
_registered_table_component.clear()
@st.fragment(run_every='5s')
def panel():
    render(*_test_proposal)
panel()
from ihm.components.local_symbol_bars_dialog import render_pending_local_symbol_bars_dialog
render_pending_local_symbol_bars_dialog()
from streamlit.runtime.scriptrunner import get_script_run_ctx
st.session_state['test_parents']=dict(get_script_run_ctx().fragment_storage._parent_by_id)
'''
    app=AppTest.from_string(script).run(timeout=30)
    assert not app.exception and not loaded
    symbol='B'
    widget=app.get('bidi_component')[0]
    states=app._tree.get_widget_states()
    state=states.widgets.add();state.id=widget.proto.id
    state.json_value=json.dumps(dict(selected_symbols=[symbol]))
    trigger=states.widgets.add();trigger.id=_make_trigger_id(widget.proto.id,'events')
    trigger.json_trigger_value=json.dumps([dict(event='open_symbol',value=symbol)])
    app._run(states,timeout=30)
    assert not app.exception and len(app.get('plotly_chart'))==1
    assert loaded[-1][0]==symbol and loaded[-1][2]==12
    assert all(parent is None for parent in app.session_state['test_parents'].values())
    assert any('Analyse GPT / DeepSeek détaillée' in h.value for h in app.subheader)
    for label,months in [('6 mois',6),('1 mois',1)]:
        app.get('button_group')[0].set_value(label).run(timeout=30)
        assert not app.exception and loaded[-1][2]==months
        figure=json.loads(app.get('plotly_chart')[0].proto.spec)
        expected=(pd.Timestamp(loaded[-1][1])-pd.DateOffset(months=months)).date().isoformat()
        assert figure['layout']['xaxis']['range'][0]==expected
    assert not approval_path(folder).exists()
    app.button(key='probability-details-close-'+symbol).click().run(timeout=30)
    assert not app.exception and details.REQUEST_KEY not in app.session_state.filtered_state
    # AppTest can retain the last dialog fragment's delta tree after st.rerun;
    # the next complete page render must not reopen a dismissed context.
    app._run(None,timeout=30)  # no stale, already-unregistered dialog widget states.
    assert not app.exception and not app.get('plotly_chart')
    key='probability-choice-'+report['run_id']
    assert app.session_state[key+'-checked']==[symbol]
    assert not approval_path(folder).exists()


def test_analysis_is_readable_even_without_price_history(monkeypatch):
    monkeypatch.setattr(details,'load_analysis',lambda *a:packet())
    monkeypatch.setattr('ihm.services.db.get_engine',lambda:None)
    monkeypatch.setattr(chart,'_cached_local_symbol_bars',lambda *a:dict(
        bars=pd.DataFrame(),stats=dict(excluded=0,missing_volume=0),start=date(2025,11,19),end=date(2026,11,19)))
    app=AppTest.from_string('''
from ihm.components.probability_details_dialog import render_body
render_body(dict(symbol='B',trade_date='2026-11-19',run_id='example',demo=False))
''').run(timeout=30)
    assert not app.exception and not app.get('plotly_chart')
    assert any('Aucune barre' in i.value for i in app.info)
    assert any('Explication archivée exacte' in t.value for t in app.text)
