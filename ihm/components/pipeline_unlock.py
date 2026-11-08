"""Confirmation UI, rendered only while a relevant durable lock exists."""
import streamlit as st

from ihm.services.pipeline_unlock import list_locked_scopes, inspect_unlock, confirm_unlock


def render_pipeline_unlock(engine, options, records):
    from ihm.services.watcher_runtime import list_alpaca_account_ids
    run_id=options.options_filter_run_id
    if not run_id or run_id=='auto':
        predictions=[r for r in records if r.get('step_key')=='ml_predict' and not r.get('history_deleted')]
        latest=max(predictions,key=lambda r:str(r.get('actual_started_at') or r.get('executed_at') or ''),default={})
        run_id=(latest.get('run_summary') or {}).get('options_filter_run_id')
    try:
        if callable(engine):
            engine=engine()
        candidates=list_locked_scopes(engine,list_alpaca_account_ids(),run_id)
    except Exception:
        return  # An unreadable state never authorizes recovery.
    notice=st.session_state.pop('pipeline_unlock_notice',None)
    if notice:
        st.success(notice)
    if not candidates:
        return
    with st.expander('🔓 Déverrouiller une reprise — étapes 11/12 et watchers'):
        st.caption('Comptes PAPER. Reprise des étapes 11/12 de la sélection options affichée et des watchers arrêtés. '
                   'Les processus actifs, les ordres déjà engagés et les situations incertaines restent protégés.')
        by_id={f"{c['account_id']}:{c['kind']}:{c['run_id'] or ''}":c for c in candidates}
        if st.session_state.get('pipeline_unlock_scope') not in by_id:
            preferred=next((key for key,c in by_id.items()
                if c['account_id']==(getattr(options,'account_id',None) or 'default') and c['kind']=='execute'),next(iter(by_id)))
            st.session_state['pipeline_unlock_scope']=preferred
        selected=st.selectbox('Verrou à vérifier',options=list(by_id),
            format_func=lambda key:by_id[key]['label'],key='pipeline_unlock_scope')
        candidate=by_id[selected]
        if candidate['kind']=='risk':
            st.warning('Réinitialiser 11 archive son résultat : il faudra obligatoirement relancer 11 puis 12. '
                       'Pour réessayer seulement 12, choisir « Reprendre 12 (conserver le risque) » lorsqu’il est proposé.')
        if st.button('Vérifier avant déverrouillage',key='pipeline_unlock_verify'):
            st.session_state.pop('pipeline_unlock_preview',None)
            try:
                with st.spinner('Vérification des processus, tentatives et ordres…'):
                    st.session_state['pipeline_unlock_preview']=inspect_unlock(engine,candidate)
            except (ValueError,RuntimeError,OSError) as exc:
                st.error(str(exc))
            except Exception:
                st.error('Vérification impossible : une source nécessaire est indisponible. Verrou conservé.')
        preview=st.session_state.get('pipeline_unlock_preview')
        if not preview or preview['candidate']!=candidate:
            return
        st.warning(f"Compte {candidate['account_id']} — {preview['message']}")
        confirmed=st.checkbox('Je confirme le déverrouillage de cette tentative uniquement.',
            key='pipeline_unlock_confirm_'+preview['fingerprint'])
        if st.button('🔓 Confirmer le déverrouillage',key='pipeline_unlock_apply',disabled=not confirmed):
            try:
                with st.spinner('Nouvelle vérification et libération du verrou…'):
                    message=confirm_unlock(engine,preview)
            except (ValueError,RuntimeError,OSError) as exc:
                st.error(str(exc))
                st.session_state.pop('pipeline_unlock_preview',None)
            except Exception:
                st.error('Déverrouillage non confirmé : vérifier à nouveau. Aucun ordre envoyé par ce bouton.')
                st.session_state.pop('pipeline_unlock_preview',None)
            else:
                st.session_state.pop('pipeline_unlock_preview',None)
                st.session_state['pipeline_unlock_notice']=message
                st.rerun()
