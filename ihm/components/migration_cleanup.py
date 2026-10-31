"""Preview and explicitly confirm deletion of the scoped T5.6 archive history."""
import streamlit as st

from service.migration.cleanup import preview_cleanup,cleanup


def _apply(root):
    plan=st.session_state.get('t56_cleanup_plan')
    if not plan:return
    try:
        result=cleanup(root,approved_plan=plan['fingerprint'])
        st.session_state.pop('t56_cleanup_error',None)
        st.session_state['t56_cleanup_result']=result
        for key in ('t56_cleanup_plan','t56_cleanup_confirm','t56_job','t56_jobs','t56_follow',
                    't56_plan','t56_plan_context','t56_output','t56_inventory_job','t56_inventory_result'):
            st.session_state.pop(key,None)
    except (ValueError,OSError) as exc:st.session_state['t56_cleanup_error']=str(exc)


def render_migration_cleanup(root):
    with st.expander('Nettoyer les anciennes sauvegardes T5.6 et libérer le verrou'):
        st.caption('Périmètre : backups/migrations et backups/migration_jobs. Suppression des packages et journaux listés ci-dessous ; les sauvegardes DB/ML/FR/CN planifiées restent en dehors de ce nettoyage. Aucun processus n’est arrêté.')
        if st.button('Inventorier les sauvegardes à supprimer',key='t56_cleanup_preview'):
            try:
                st.session_state.pop('t56_cleanup_error',None)
                st.session_state['t56_cleanup_plan']=preview_cleanup(root)
            except (ValueError,OSError) as exc:st.error(str(exc))
        plan=st.session_state.get('t56_cleanup_plan')
        if plan:
            st.dataframe([{k:entry[k] for k in ('path','kind','status','files','bytes')} for entry in plan['entries']],hide_index=True)
            st.caption(f"{len(plan['entries'])} répertoires ; {plan['total_files']:,} fichiers ; {plan['total_bytes']/1024**3:.2f} Gio. Verrou orphelin : {'oui' if plan['stale_lock'] else 'non'}.")
            if plan['blocked']:st.warning('Éléments non reconnus conservés : '+', '.join(plan['blocked']))
            confirmed=st.checkbox('Je confirme la suppression définitive des anciens packages et journaux listés',key='t56_cleanup_confirm')
            st.button('Nettoyer les anciennes sauvegardes et déverrouiller',key='t56_cleanup_apply',
                disabled=not confirmed or not (plan['entries'] or plan['stale_lock']),on_click=_apply,args=(root,))
        if st.session_state.get('t56_cleanup_result'):
            result=st.session_state['t56_cleanup_result']
            if result['status']=='CLEANED':
                st.success(f"Nettoyage terminé : {len(result['deleted'])} répertoires supprimés ; verrou libéré : {'oui' if result['lock_released'] else 'aucun verrou à libérer'}.")
            else:st.warning('Nettoyage partiel : certains fichiers n’ont pas pu être supprimés.')
            with st.expander('Bilan du nettoyage'):st.json(result)
        if st.session_state.get('t56_cleanup_error'):st.error(st.session_state['t56_cleanup_error'])
