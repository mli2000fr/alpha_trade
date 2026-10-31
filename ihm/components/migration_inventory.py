"""Visible asynchronous file inventory, with only public environment metadata."""
from pathlib import Path

import streamlit as st

from ihm.services import migration_runner as jobs
from .migration_progress import amount,duration,elapsed


@st.fragment(run_every=2)
def render_inventory_result(job):
    state=jobs.job_state(job);tracking=state.get('tracking') or {};worker=state.get('progress') or {}
    result=state.get('result') or {};active=worker.get('status') in ('STARTING','STARTED')
    st.markdown('**Inventaire des fichiers et des variables**')
    percent=max(0.,min(100.,float(tracking.get('percent',0))))
    st.progress(percent/100,text=tracking.get('label') or 'Démarrage de l’inventaire…')
    if state.get('worker_ended_without_result'):
        active=False;st.error('Le processus d’inventaire s’est arrêté sans résultat final. Consulter son journal dans « Suivi et packages ».')
    if worker.get('status')=='FAILED':st.error(worker.get('message') or 'Inventaire en échec ; consulter son journal.')
    if worker.get('status')=='CANCELED':st.info('Inventaire interrompu.')
    if active:
        left,middle,right=st.columns(3)
        left.metric('Fichiers parcourus',f"{tracking.get('inventory_files',tracking.get('files_done',0)):,}")
        middle.metric('Taille recensée',amount(tracking.get('inventory_bytes',tracking.get('processed_bytes'))))
        right.metric('Temps écoulé',duration(elapsed(tracking,True)))
        if tracking.get('item'):st.caption('En cours : '+tracking['item'])
        if tracking.get('phase')=='INVENTORY_SCAN':
            st.caption('Parcours des dossiers en cours : le nombre total de fichiers n’est pas encore connu. Aucune lecture du contenu des résultats de backtest pour rechercher les variables.')
        elif tracking.get('phase')=='ENVIRONMENT_INVENTORY':
            st.caption(f"{tracking.get('completed',0):,} / {tracking.get('total',0):,} fichiers de code/configuration analysés.")
        st.caption('Actualisation automatique toutes les 2 secondes. La sauvegarde n’est pas lancée par cet inventaire.')
        if st.button('Arrêter cet inventaire',key='t56_inventory_cancel'):
            (Path(job)/'cancel.request').touch();st.info('Arrêt demandé à l’inventaire.')
    if result.get('status')=='INVENTORIED':
        st.success('Inventaire terminé.')
        st.dataframe(result['packages'],hide_index=True)
        with st.expander('Variables : noms, présence et origine (aucune valeur affichée)'):
            st.dataframe(result['variables'],hide_index=True)
