"""Explicit per-run human choice; no provider call and no broker order in UI."""
from datetime import UTC, datetime

import streamlit as st


def _choice_table(candidates,key,*,details=None,read_only=False):
    """Shared presentation only; persistence belongs to the caller."""
    import pandas as pd
    rows=pd.DataFrame(dict(Retenir=False,Symbole=candidates.symbol,
        Probabilite=candidates.llm_probability_up_without_stop*100,
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
        if column['key']=='Probabilite':column['label']='Probabilité estimée (%)'
        if column['key']=='Eligible':column['label']='Preuves qualifiées'
    for row in payload['rows']:
        for column,cell in zip(payload['columns'],row['cells']):
            if column['key']=='Probabilite' and cell['sort'] is not None:
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
        if context.get('demo'):
            source=candidates[candidates.symbol==symbol].iloc[0]
            context['assessment']=dict(probability_up_without_stop=None if pd.isna(source.llm_probability_up_without_stop)
                else float(source.llm_probability_up_without_stop),evidence_quality=source.llm_evidence_quality,
                probability_explanation=source.llm_explanation,
                evidence_explanation='Exemple fictif ; aucune recherche Web effectuée.',
                bull_case='Exemple fictif : un élément favorable serait une amélioration des perspectives confirmée par des sources datées.',
                bear_case='Exemple fictif : une annonce décevante ou un retournement du marché pourrait invalider le scénario.',
                consensus_analysis='Aucun consensus réel utilisé dans cette démonstration.',
                context_analysis='Exemple de lecture du contexte ; aucune donnée financière fictive n’est présentée comme réelle.',
                risk_factors=['Exemple fictif : risque de gap et de toucher le SL.'],
                selection_blockers=source.llm_blockers.split(', ') if source.llm_blockers else [])
        request(symbol,context)
    rows['Retenir']=rows.Symbole.isin(chosen)
    confirmed=st.button('Valider la sélection',type='primary',key=key+'-confirm') if not read_only else False
    return rows,confirmed


def render_demo(*,key='pipeline-gpt-probability-demo'):
    """In-memory illustrative responses, entirely outside the trading path."""
    import pandas as pd
    with st.expander('Aperçu simulé — 3 réponses GPT fictives',expanded=True):
        st.markdown('#### TOP Oracle — avis GPT / DeepSeek')
        st.warning('DÉMONSTRATION : symboles et pourcentages illustratifs, aucun avis GPT réel. '
                   'Les cases et le bouton ci-dessous ne transmettent rien au risque ou au broker.')
        st.caption('Exemple H10 / SL5 % / sortie open11 : finir au-dessus du prix d’entrée sans toucher le stop. '
                   'Tri par probabilité décroissante ; indéterminable en fin de tableau.')
        candidates=pd.DataFrame(dict(symbol=['AAPL','MSFT','NVDA'],
            llm_probability_up_without_stop=[.72,.58,None],
            llm_evidence_quality=['SUFFICIENT','SUFFICIENT','INSUFFICIENT'],
            llm_explanation=[
                'Exemple fictif : plusieurs éléments concordants, avec un risque de recul restant significatif.',
                'Exemple fictif : éléments favorables et défavorables ; estimation plus incertaine.',
                'Exemple fictif : informations datées insuffisantes ; aucune probabilité défendable.'],
            llm_blockers=['','','probability_undeterminable, evidence_insufficient'],
            selected=[True,True,False]))
        from zoneinfo import ZoneInfo
        edited,confirmed=_choice_table(candidates,key,details=dict(demo=True,
            trade_date=datetime.now(ZoneInfo('Europe/Paris')).date().isoformat()))
        if confirmed:
            chosen=edited.loc[edited.Retenir & edited.Eligible,'Symbole'].tolist()
            refused=edited.loc[edited.Retenir & ~edited.Eligible,'Symbole'].tolist()
            if refused:st.warning('Exclus de la simulation faute de preuves : '+', '.join(refused))
            st.info('Simulation uniquement — choix : '+(', '.join(chosen) or 'aucun titre')
                    +'. Aucun choix réel enregistré, aucun workflow débloqué et aucun ordre envoyé.')


def render(folder,report,frame):
    from service.q051_paper.human_selection import read,check_expiry,approve,approval_path
    receipt=report['llm_filter']
    st.markdown('#### TOP Oracle — avis GPT / DeepSeek')
    candidates=frame[frame.selected_before_llm].sort_values(
        ['llm_probability_up_without_stop','oracle_rank'],ascending=[False,True],na_position='last')
    contract=receipt['contract']
    details=dict(demo=False,run_id=report['run_id'],trade_date=report['trade_date'])
    st.caption(f'Probabilité estimée : sortie open{contract["exit_session"]} au-dessus du prix d’entrée, '
               f'sans toucher SL {contract["stop_loss_pct"]:.0%} durant H{contract["horizon_sessions"]}. '
               'Estimation GPT/DeepSeek non calibrée, pas une fréquence de réussite démontrée. '
               'Le prix d’entrée réel n’est pas encore connu.')
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
    st.warning('Le batch attend votre choix avant l’étape11. Cochez les titres à transmettre au risque, '
               'puis validez. Valider sans titre annule tous les achats de cette sélection.')
    key='probability-choice-'+report['run_id']
    edited,confirmed=_choice_table(candidates,key,details=details)
    if confirmed:
        try:
            chosen=edited.loc[edited.Retenir,'Symbole'].tolist()
            from ihm.services.db import get_engine
            value=approve(get_engine(),report['run_id'],chosen)
        except Exception as exc:
            st.error(f'Sélection non validée : {exc}')
        else:
            st.success(f'{len(value["selected_symbols"])} titre(s) validé(s). Un batch en attente peut reprendre les étapes suivantes.')
            st.rerun()
