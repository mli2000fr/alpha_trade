"""The per-symbol B option is independent of Oracle amplitude inputs."""
import streamlit as st


def render_volatility_features(enabled):
    active=st.checkbox('Volatilité inhabituelle — per-symbol (B)',value=True,
        key='pipeline_ml_path_directional_volatility',disabled=not enabled,
        help='Ajoute aux 24 variables par titre la volatilité sur 60/120 séances et les écarts '
             'de volatilité 20/60/120 séances à leur niveau habituel : 29 variables LONG/SHORT. '
             'Concerne le bundle Oracle parcours ; les variables de l’Oracle restent inchangées.')
    if enabled:
        st.caption('Variables par titre : '+('29 — groupe B (24 existantes + 5 de volatilité).' if active
            else '24 — configuration compacte historique.'))
    return 'compact_volatility' if enabled and active else 'compact'


def render_anti_sl_features(bundle,feature_mode,horizon):
    eligible=bool(bundle and feature_mode=='compact_volatility' and horizon==10)
    key='pipeline_ml_path_anti_sl'
    eligibility_key=key+'_default_on_eligible'
    if not eligible:
        st.session_state[key]=False
    elif st.session_state.get(eligibility_key) is not True:
        st.session_state[key]=True
    st.session_state[eligibility_key]=eligible
    active=st.checkbox('Ajouter le filtre anti-SL — trajectoire dix séances',value=eligible,key=key,disabled=not eligible,
        help='Bundle H10/B29 : entraîne une tête commune à 44 variables pour le risque de SL durant la première séance. '
             'Le veto est appliqué automatiquement après le TOP LONG si le batch contient cette tête, sans remplacement.')
    if active and eligible:
        st.caption('Même batch : Oracle H10 + per-symbol B + anti-SL. Validation OOF causale ; seuil fixé sur la calibration. '
                   'Les dix séances décrivent les données passées, pas dix séances protégées contre les stops.')
    return bool(eligible and active)
