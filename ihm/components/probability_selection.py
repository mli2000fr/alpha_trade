"""Explicit per-run human choice; no provider call and no broker order in UI."""
from datetime import UTC, datetime

import streamlit as st


def render(folder,report,frame):
    from service.q051_paper.human_selection import read,check_expiry,approve,approval_path
    receipt=report['llm_filter']
    st.markdown('#### TOP Oracle — avis GPT / DeepSeek')
    candidates=frame[frame.selected_before_llm].sort_values(
        ['llm_probability_up_without_stop','oracle_rank'],ascending=[False,True],na_position='last')
    contract=receipt['contract']
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
            display=candidates.assign(Retenu=candidates.symbol.isin(value['selected_symbols']))
            st.dataframe(display[['Retenu','symbol','llm_probability_up_without_stop','llm_explanation']],
                         hide_index=True,use_container_width=True)
        except (OSError,ValueError,KeyError) as exc:
            st.warning(f'Validation archivée indisponible ou expirée : {exc}')
        return
    try:
        check_expiry(report)
    except ValueError as exc:
        st.warning(str(exc));return
    st.warning('Le batch attend votre choix avant l’étape11. Cochez les titres à transmettre au risque, '
               'puis validez. Valider sans titre annule tous les achats de cette sélection.')
    import pandas as pd
    rows=pd.DataFrame(dict(Retenir=False,Symbole=candidates.symbol,
        Probabilite=candidates.llm_probability_up_without_stop*100,
        Preuves=candidates.llm_evidence_quality,Analyse=candidates.llm_explanation,
        Motifs=candidates.llm_blockers,Eligible=candidates.selected))
    key='probability-choice-'+report['run_id']
    with st.form(key):
        edited=st.data_editor(rows,hide_index=True,num_rows='fixed',use_container_width=True,
            disabled=[c for c in rows.columns if c!='Retenir'],
            column_config={'Retenir':st.column_config.CheckboxColumn('Retenir'),
                           'Probabilite':st.column_config.NumberColumn('Probabilité estimée (%)',format='%.1f'),
                           'Eligible':st.column_config.CheckboxColumn('Preuves qualifiées')},key=key+'-table')
        confirmed=st.form_submit_button('Valider la sélection',type='primary')
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
