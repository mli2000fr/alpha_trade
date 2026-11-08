"""Read-only review of the batch's archived per-symbol ranking."""
import streamlit as st


def render(options):
    from modelFactory.oracle_path.directional import requested,read_predictions
    from modelFactory.oracle_path.predict import load_contract
    from common.us_signal_date import resolve_us_signal_date
    from ihm.services.db import safe_query,get_engine
    batch=options.ml_live_predict_batch_id or options.ml_predict_batch_id
    if not batch or not requested(options.ml_artifacts_dir,batch):return False
    st.markdown('#### TOP Oracle → classement LONG par titre')
    st.caption('Les deux branches sont entraînées. Seul LONG est utilisé pour la sélection ; '
               'le score SHORT est affiché pour information. Aucun filtre options/GPT ne remplace ce classement.')
    try:
        root,protocol,_,_=load_contract(options.ml_artifacts_dir,batch)
        day=resolve_us_signal_date(options.trade_date or None)
        frame=safe_query('SELECT prediction_date AS date,symbol,proba_extreme FROM oracle_extreme_predictions '
            'WHERE batch_id=:batch AND prediction_date=:day',dict(batch=batch,day=day))
        if frame.empty:
            st.info(f'Aucune prédiction enregistrée pour ce batch et la séance {day}. Lancer l’étape 10.')
            return True
        ranked=read_predictions(get_engine(),root,frame,batch)
        ranked=ranked[ranked.oracle_rank.le(protocol['directional_contract']['oracle_top_n'])].sort_values('oracle_rank')
        names={'symbol':'Symbole','oracle_rank':'Rang Oracle','proba_extreme':'Score amplitude',
               'long_probability':'Probabilité gain LONG','short_probability':'Probabilité gain SHORT — non utilisée',
               'long_rank':'Rang LONG','selected':'Retenu LONG','reason':'Motif'}
        st.caption(f'Séance {day} · batch {batch} · Oracle et modèles par titre H{protocol["directional_contract"]["horizon_sessions"]} · '
                   f'TOP{protocol["directional_contract"]["selected_n"]} LONG au maximum. '
                   'Le risque peut ensuite refuser une entrée ; un titre déjà détenu n’est pas remplacé.')
        st.dataframe(ranked[list(names)].rename(columns=names),hide_index=True,use_container_width=True)
    except (OSError,ValueError,KeyError) as exc:
        st.warning(f'Classement de ce batch indisponible ou non qualifié : {exc}')
    return True
