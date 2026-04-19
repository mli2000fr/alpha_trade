"""
ihm/app.py — Point d'entrée Streamlit pour l'IHM opérateur Alpha Trade.

Lancement :
    python -m streamlit run ihm/app.py
"""
from __future__ import annotations

import streamlit as st

from ihm.components.db_controls import render_db_connection_form

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

with st.sidebar.expander("🗄️ Connexion DB", expanded=False):
    render_db_connection_form("sidebar_db_connection_form", show_host_fields=True)

# --- Sélecteur multi-comptes ---
try:
    from service.alpaca.accounts import AccountRegistry
    _accounts = AccountRegistry.get().list_accounts()
    if len(_accounts) > 1:
        _acct_options = {f"{a.label} ({a.account_id}, {a.mode})": a.account_id for a in _accounts}
        _acct_label = st.sidebar.selectbox("🏦 Compte Alpaca", list(_acct_options.keys()))
        st.session_state["selected_account_id"] = _acct_options[_acct_label]
    elif _accounts:
        st.session_state["selected_account_id"] = _accounts[0].account_id
    else:
        st.session_state.setdefault("selected_account_id", "default")
except Exception:
    st.session_state.setdefault("selected_account_id", "default")

selection = st.sidebar.radio("Navigation", list(PAGES.keys()), label_visibility="collapsed")

page_key = PAGES[selection]

# ---------------------------------------------------------------------------
# Routage vers la page sélectionnée
# ---------------------------------------------------------------------------
PAGE_IMPORTS = {
    "overview": "ihm.pages.overview",
    "pipeline": "ihm.pages.pipeline",
    "screening": "ihm.pages.screening",
    "risk": "ihm.pages.risk",
    "execution": "ihm.pages.execution",
    "corporate_actions": "ihm.pages.corporate_actions",
    "ml": "ihm.pages.ml",
    "settings": "ihm.pages.settings",
}

render = None
module_name = PAGE_IMPORTS.get(page_key)
if module_name:
    module = __import__(module_name, fromlist=["render"])
    render = getattr(module, "render", None)

if render is None:
    def render() -> None:
        st.error("Page inconnue ou module de rendu introuvable.")

try:
    render()
except Exception as exc:
    st.error(f"Erreur lors du rendu de la page : {exc}")

