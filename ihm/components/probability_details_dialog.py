"""Archived probability analysis and local charts. Read only, no cloud calls."""
import json

import streamlit as st

REQUEST_KEY='_pipeline_probability_details_request'


def request(symbol,context):
    from ihm.components.local_symbol_bars_dialog import _DIALOG_REQUEST_KEY
    st.session_state.pop(_DIALOG_REQUEST_KEY,None)
    st.session_state[REQUEST_KEY]=dict(context,symbol=symbol)
    st.rerun(scope='app')


def render_pending():
    context=st.session_state.get(REQUEST_KEY)
    if context is not None:
        show(context)


def load_analysis(engine,run_id,symbol):
    """Bind the displayed assessment to this sealed proposal and exact issuer."""
    import pandas as pd
    from service.q051_paper.pipeline import directory,digest
    from service.llm_directional.repository import Repository
    folder=directory(run_id)
    report=json.loads((folder/'selection.json').read_text(encoding='utf-8'))
    seal=json.loads((folder/'seal.json').read_text(encoding='utf-8'))
    if (report['run_id']!=run_id or seal['report_sha256']!=digest(folder/'selection.json')
            or report['selection_sha256']!=digest(folder/'selection.parquet')):
        raise ValueError('Proposition archivée incompatible')
    frame=pd.read_parquet(folder/'selection.parquet')
    if symbol not in set(frame.loc[frame.selected_before_llm,'symbol']):
        raise ValueError('Titre absent des candidats de cette analyse')
    receipt=report['llm_filter']
    run,items=Repository(engine).get(receipt['run_id'])
    if (run['input_sha256']!=receipt['input_sha256'] or run['batch_id']!=report['batch_id']
            or str(run['trade_date'])!=report['trade_date']):
        raise ValueError('Analyse LLM différente de la proposition')
    item=next((i for i in items if i['symbol']==symbol),None)
    if item is None:raise ValueError('Réponse de ce titre absente')
    context=next((c for c in json.loads(run['input_json'])['candidates'] if c['symbol']==symbol),{})
    return dict(symbol=symbol,trade_date=report['trade_date'],contract=receipt['contract'],
        run_id=run_id,llm_run_id=receipt['run_id'],provider=receipt.get('provider'),
        assessment=json.loads(item['assessment_json'] or '{}'),
        local_data_status=context.get('local_data_status',{}),
        evidence_cutoff_utc=context.get('evidence_cutoff_utc'),status=item['status'])


def render_analysis(packet):
    value=packet['assessment']
    st.subheader('Analyse GPT / DeepSeek détaillée')
    for field,label in [('probability_up_without_stop','Hausse sans toucher le SL'),
                        ('probability_stop_touch','Toucher le SL avant la sortie'),
                        ('probability_positive_exit','Hausse à la sortie, même après une touche du SL')]:
        p=value.get(field)
        st.metric(label,'Non disponible' if p is None else f'{p:.1%}')
    st.caption('Ces probabilités se recouvrent et ne totalisent pas 100 %. La hausse finale est '
               'hypothétique si le stop aurait déjà fermé la position.')
    st.caption('Estimation non calibrée · preuves : '+str(value.get('evidence_quality','indisponibles')))
    for field,label in [('probability_explanation','Explication de la probabilité'),
                        ('stop_touch_explanation','Explication du risque de toucher le SL'),
                        ('positive_exit_explanation','Explication de la hausse finale hypothétique'),
                        ('evidence_explanation','Qualité et limites des preuves'),
                        ('bull_case','Éléments favorables'),('bear_case','Éléments défavorables'),
                        ('consensus_analysis','Consensus et attentes du marché'),
                        ('context_analysis','Contexte prix, annonces et fondamentaux')]:
        if value.get(field):
            st.markdown('**'+label+'**');st.text(str(value[field]))
    for field,label in [('catalysts','Catalyseurs'),('risk_factors','Risques'),
                        ('selection_blockers','Motifs empêchant la sélection')]:
        if value.get(field):
            st.markdown('**'+label+'**')
            st.json(value[field],expanded=True)
    for field,label in [('sources','Sources Web citées'),('source_qualifications','Qualification des sources Web'),
                        ('local_evidence','Extraits locaux cités'),('excluded_sources','Sources écartées')]:
        if value.get(field):
            with st.expander(label,expanded=field=='sources'):
                st.json(value[field])
    if packet.get('local_data_status'):
        with st.expander('Données locales disponibles et manquantes'):
            st.json(packet['local_data_status'])
    if packet.get('llm_run_id'):
        st.caption(f'Analyse archivée : {packet["llm_run_id"]} · fournisseur : {packet.get("provider")} · '
                   f'cutoff : {packet.get("evidence_cutoff_utc")}. Aucun nouvel appel LLM.')
    with st.expander('Réponse analysée complète'):
        st.json(value)


def render_body(context):
    symbol=context['symbol']
    st.subheader(symbol+' — courbe et analyse')
    try:
        from ihm.services.db import get_engine
        packet=load_analysis(get_engine(),context['run_id'],symbol)
    except Exception:
        packet=None
        st.warning('Analyse archivée indisponible ou incompatible ; aucune ancienne réponse substituée.')
    from ihm.components.local_symbol_bars_dialog import _render_local_bars_section
    _render_local_bars_section(symbol,packet['trade_date'] if packet else context['trade_date'])
    if packet:render_analysis(packet)
    if st.button('Fermer',key='probability-details-close-'+symbol):
        dismiss();st.rerun()


def dismiss():
    st.session_state.pop(REQUEST_KEY,None)


@st.dialog('Courbe et analyse GPT / DeepSeek',width='large',on_dismiss=dismiss)
def show(context):
    render_body(context)
