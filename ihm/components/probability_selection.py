"""Explicit per-run human choice; no provider call and no broker order in UI."""
from datetime import UTC, datetime

import streamlit as st


def _choice_table(candidates,key,*,details=None,read_only=False):
    """Shared presentation only; persistence belongs to the caller."""
    import pandas as pd
    rows=pd.DataFrame(dict(Retenir=False,Symbole=candidates.symbol,
        Probabilite=candidates.llm_probability_up_without_stop*100,
        ToucheSL=candidates.get('llm_probability_stop_touch',pd.Series(index=candidates.index,dtype=float))*100,
        HausseFinale=candidates.get('llm_probability_positive_exit',pd.Series(index=candidates.index,dtype=float))*100,
        Preuves=candidates.llm_evidence_quality,Analyse=candidates.llm_explanation,
        Motifs=candidates.llm_blockers,Eligible=candidates.selected))
    from ihm.components.prediction_review_table import table_payload,_table_component
    payload=table_payload(rows)
    checked_key=key+'-checked'
    checked=st.session_state.get(checked_key,[])
    for column in payload['columns']:
        if column['key']=='Retenir':column['checkbox']=True
        if column['action']:
            column.update(label='Courbe et analyse',title='Afficher la courbe et l’analyse GPT détaillée')
        labels={'Probabilite':'Hausse sans SL (%)','ToucheSL':'Touche du SL (%)','HausseFinale':'Hausse à la sortie (%)'}
        if column['key'] in labels:column['label']=labels[column['key']]
        if column['key']=='Eligible':column['label']='Preuves qualifiées'
    for row in payload['rows']:
        for column,cell in zip(payload['columns'],row['cells']):
            if column['key'] in labels and cell['sort'] is not None:
                cell['text']=f'{cell["sort"]:.1f} %'
    payload.update(selected_symbols=checked,read_only=read_only)
    result=_table_component(key=key+'-details-v1',data=payload,
        default={'selected_symbols':checked},on_selected_symbols_change=lambda:None,
        on_open_symbol_change=lambda:None,height='content',width='stretch')
    chosen=getattr(result,'selected_symbols',checked)
    if not isinstance(chosen,list) or any(not isinstance(s,str) for s in chosen):chosen=[]
    st.session_state[checked_key]=chosen
    symbol=getattr(result,'open_symbol',None)
    if details is not None and isinstance(symbol,str) and symbol in set(candidates.symbol):
        from ihm.components.probability_details_dialog import request
        context=dict(details)
        request(symbol,context)
    rows['Retenir']=rows.Symbole.isin(chosen)
    confirmed=st.button('Valider la sélection',type='primary',key=key+'-confirm') if not read_only else False
    return rows,confirmed


def render(folder,report,frame):
    from service.q051_paper.human_selection import read,check_expiry,approve,approval_path,selection_policy,selectable_symbols
    receipt=report['llm_filter']
    st.markdown('#### TOP Oracle — avis GPT / DeepSeek')
    candidates=frame[frame.selected_before_llm].sort_values(
        ['llm_probability_up_without_stop','oracle_rank'],ascending=[False,True],na_position='last')
    contract=receipt['contract']
    details=dict(run_id=report['run_id'],trade_date=report['trade_date'])
    st.caption(f'Probabilité estimée : sortie open{contract["exit_session"]} au-dessus du prix d’entrée, '
               f'sans toucher SL {contract["stop_loss_pct"]:.0%} durant H{contract["horizon_sessions"]}. '
               'Estimation GPT/DeepSeek non calibrée, pas une fréquence de réussite démontrée. '
               'Le prix d’entrée réel n’est pas encore connu.')
    st.caption('« Touche du SL » : au moins une touche avant la sortie. « Hausse à la sortie » : '
               'cours final supérieur à l’entrée, même si le SL aurait été touché auparavant. '
               'Les trois probabilités ne s’additionnent pas à 100 %. Le tri conserve la hausse sans SL. '
               '— : estimation absente, notamment dans les anciennes analyses.')
    expires=datetime.fromisoformat(receipt['approval_expires_at'])
    from zoneinfo import ZoneInfo
    st.caption('Validation possible jusqu’au '+expires.astimezone(ZoneInfo('Europe/Paris')).strftime('%d/%m/%Y %H:%M:%S %Z')
               +'. Après expiration, lancer un nouveau batch ou pipeline pour obtenir de nouveaux résultats.')
    if candidates.empty:
        st.info('Aucun candidat LONG à analyser ; aucun achat proposé.')
        return
    if approval_path(folder).is_file():
        try:
            value=read(folder,report,frame)
            st.success(f'Sélection validée : {", ".join(value["selected_symbols"]) or "aucun titre"}. '
                       'Le batch peut reprendre le risque puis l’exécution.')
            key='probability-approved-'+report['run_id']
            st.session_state.setdefault(key+'-checked',value['selected_symbols'])
            _choice_table(candidates,key,details=details,read_only=True)
        except (OSError,ValueError,KeyError) as exc:
            st.warning(f'Validation archivée indisponible ou expirée : {exc}')
            _choice_table(candidates,'probability-history-'+report['run_id'],details=details,read_only=True)
        return
    try:
        check_expiry(report)
    except ValueError as exc:
        st.warning(str(exc))
        _choice_table(candidates,'probability-expired-'+report['run_id'],details=details,read_only=True)
        return
    policy=selection_policy()
    st.warning('Le batch attend votre choix avant l’étape11. Cochez les titres à transmettre au risque, '
               'puis validez. Valider sans titre annule tous les achats de cette sélection.')
    if policy['require_qualified_evidence'] and not candidates.selected.any():
        st.info('Aucun titre ne dispose actuellement de preuves qualifiées. Les cases « Retenir » '
                'ne permettent pas de contourner ce contrôle ; vous pouvez valider sans titre pour terminer sans achat.')
    key='probability-choice-'+report['run_id']
    selectable=selectable_symbols(candidates,policy)
    if not policy['require_qualified_evidence']:
        st.info('Qualification des preuves facultative pour votre choix manuel. Vous pouvez retenir une estimation '
                'valide malgré des preuves partielles ; leur qualité reste affichée. '
                'Identité, validité des réponses, expiration et contrôles de risque restent obligatoires.')
    # Old refusals based on the previous policy must not survive its explicit change.
    policy_key=key+'-validation-policy'
    error_key=key+'-validation-error'
    if st.session_state.get(policy_key)!=policy:
        st.session_state.pop(error_key,None)
        st.session_state[policy_key]=policy
    previous_error=st.session_state.get(error_key)
    if previous_error:
        st.error(previous_error)
    edited,confirmed=_choice_table(candidates,key,details=details)
    if confirmed:
        chosen=edited.loc[edited.Retenir,'Symbole'].tolist()
        invalid=sorted(set(chosen)-selectable)
        if invalid:
            reason='preuves non qualifiées' if policy['require_qualified_evidence'] else 'estimation absente ou contrôle obligatoire non satisfait'
            message=('Sélection refusée : '+reason+' pour '+', '.join(invalid)+'. '
                     'Aucune validation enregistrée ; les étapes 11/12 restent en attente. '
                     'Décochez ces titres. Vous pouvez valider une sélection vide pour terminer sans achat.')
            st.session_state[error_key]=message
            st.error(message)
            return
        try:
            from ihm.services.db import get_engine
            with st.spinner('Vérification de la sélection et des preuves archivées…'):
                value=approve(get_engine(),report['run_id'],chosen)
        except Exception as exc:
            message=f'Sélection non validée : {exc}'
            st.session_state[error_key]=message
            st.error(message)
        else:
            st.session_state.pop(error_key,None)
            st.success(f'{len(value["selected_symbols"])} titre(s) validé(s). Un batch en attente peut reprendre les étapes suivantes.')
            st.rerun()
