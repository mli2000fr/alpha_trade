"""
ihm/app.py — Point d'entrée Streamlit pour l'IHM opérateur Alpha Trade.

Lancement :
    python -m streamlit run ihm/app.py
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Alpha Trade — Cockpit Opérateur",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Navigation sidebar
# ---------------------------------------------------------------------------
PAGES = {
    "🏠 Vue d'ensemble": "overview",
    "🔄 Pipeline": "pipeline",
    "📊 Screening": "screening",
    "⚖️ Risk": "risk",
    "🚀 Execution": "execution",
    "📑 Corporate Actions": "corporate_actions",
    "🤖 ML / Prédictions": "ml",
    "⚙️ Paramètres / Santé": "settings",
}

st.sidebar.title("📈 Alpha Trade")
st.sidebar.caption("Cockpit opérateur — lecture seule")
selection = st.sidebar.radio("Navigation", list(PAGES.keys()), label_visibility="collapsed")

page_key = PAGES[selection]

# ---------------------------------------------------------------------------
# Routage vers la page sélectionnée
# ---------------------------------------------------------------------------
if page_key == "overview":
    from ihm.pages.overview import render
elif page_key == "pipeline":
    from ihm.pages.pipeline import render
elif page_key == "screening":
    from ihm.pages.screening import render
elif page_key == "risk":
    from ihm.pages.risk import render
elif page_key == "execution":
    from ihm.pages.execution import render
elif page_key == "corporate_actions":
    from ihm.pages.corporate_actions import render
elif page_key == "ml":
    from ihm.pages.ml import render
elif page_key == "settings":
    from ihm.pages.settings import render
else:
    def render() -> None:
        st.error("Page inconnue.")

try:
    render()
except Exception as exc:
    st.error(f"Erreur lors du rendu de la page : {exc}")

