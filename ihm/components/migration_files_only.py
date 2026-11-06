"""Independent file-only restore controls; never request MySQL credentials."""
from datetime import datetime,timezone
from pathlib import Path

import streamlit as st

from ihm.services import migration_runner as jobs


def render_files_only_restore(folder,target,password,launch):
    st.markdown('**Restauration des fichiers uniquement — bases conservées**')
    st.caption('Restaure le code, les modèles, la configuration et les archives. Aucune connexion MySQL, '
        'aucun import SQL, aucune purge des bases. Les variables système, les fichiers .env à la racine '
        'et le .venv existant sont conservés. Les anciens dossiers remplacés sont mis de côté pour retour arrière.')
    context=dict(folder=folder,target=target)
    if context!=st.session_state.get('t56_files_context'):
        st.session_state.pop('t56_files_plan',None)
        st.session_state.pop('t56_files_job',None)
        st.session_state['t56_files_confirm']=False
        st.session_state['t56_files_context']=context
    missing=not folder.strip() or not target.strip() or len(password)<12
    if st.button('Prévisualiser les fichiers uniquement',key='t56_plan_files_only',disabled=missing):
        st.session_state.pop('t56_files_plan',None)
        st.session_state['t56_files_confirm']=False
        launch(dict(action='plan_files_only',folder=folder,target=target,password=password))
    job=st.session_state.get('t56_files_job')
    state=jobs.job_state(job) if job else {}
    plan=state.get('result') or st.session_state.get('t56_files_plan')
    if isinstance(plan,dict) and plan.get('mode')=='FILES_ONLY' and 'fingerprint' in plan:
        st.session_state['t56_files_plan']=plan
        st.json(plan)
        st.warning('Les dossiers indiqués sur le PC cible seront remplacés. Les tâches actives de ce projet '
            'doivent se terminer ; aucune tâche du PC source ne sera arrêtée.')
        ready=st.checkbox('Je confirme le remplacement des fichiers du projet cible uniquement',key='t56_files_confirm')
        if st.button('Restaurer uniquement les fichiers et modèles',key='t56_restore_files_only',disabled=missing or not ready):
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            report=Path(folder).resolve()/'journaux'/('fichiers-seuls-'+stamp)
            launch(dict(action='restore_files_only',folder=folder,target=target,password=password,
                approved_plan=plan['fingerprint'],report_dir=str(report)),
                parent=Path(folder).resolve()/'journaux'/'jobs')
