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
