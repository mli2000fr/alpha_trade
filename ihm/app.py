"""
ihm/app.py — Point d'entrée Streamlit pour l'IHM opérateur Alpha Trade.

Lancement :
    python -m streamlit run ihm/app.py
"""
from __future__ import annotations

import streamlit as st

from ihm.components.db_controls import render_db_connection_form
from ihm.services.navigation import (
    build_primary_navigation_caption,
    build_support_navigation_caption,
    get_navigation_page_imports,
    get_navigation_page_labels,
    get_navigation_page_mapping,
)

st.set_page_config(
    page_title="Alpha Trade — Cockpit Opérateur",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Navigation sidebar
# ---------------------------------------------------------------------------
PAGES = get_navigation_page_mapping()
PAGE_LABELS = get_navigation_page_labels()
PAGE_IMPORTS = get_navigation_page_imports()
NAVIGATION_RADIO_KEY = "ihm_sidebar_navigation"
NAVIGATION_TARGET_PAGE_KEY = "ihm_navigation_target_page"

st.sidebar.title("📈 Alpha Trade")
st.sidebar.caption("Cockpit opérateur — supervision et suivi")
st.sidebar.caption("Navigation ordonnée pour suivre le pipeline métier du haut vers le bas.")

with st.sidebar.expander("🧭 Ordre des pages", expanded=False):
    st.caption(build_primary_navigation_caption())
    st.caption(build_support_navigation_caption())

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

requested_page_key = st.session_state.pop(NAVIGATION_TARGET_PAGE_KEY, None)
if requested_page_key in PAGES.values():
    for label, key in PAGES.items():
        if key == requested_page_key:
            st.session_state[NAVIGATION_RADIO_KEY] = label
            break

selection = st.sidebar.radio("Navigation", PAGE_LABELS, label_visibility="collapsed", key=NAVIGATION_RADIO_KEY)

page_key = PAGES[selection]

# ---------------------------------------------------------------------------
# Routage vers la page sélectionnée
# ---------------------------------------------------------------------------

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

