"""
ihm/app.py — Point d'entrée Streamlit pour l'IHM opérateur Alpha Trade.

Lancement :
    python -m streamlit run ihm/app.py
"""
from __future__ import annotations

import streamlit as st

from ihm.components.db_controls import render_db_connection_form
from ihm.services.navigation import (
    build_section_navigation_caption,
    get_navigation_page_imports,
    get_navigation_page_labels,
    get_navigation_page_mapping,
    get_navigation_sections,
)
from ihm.services.security import render_auth_gate, render_security_banner
from ihm.services.theme_manager import (
    apply_theme_chrome,
    get_current_theme,
    render_theme_toggle,
)

st.set_page_config(
    page_title="Alpha Trade — Cockpit Opérateur",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sprint S19.5 / fix anomalie #1 — Streamlit auto-détecte ``ihm/pages/``
# comme un dossier multipage et ajoute une navigation native dans la
# sidebar (``[data-testid="stSidebarNav"]``). Cette navigation fait
# doublon avec la navigation hiérarchique métier construite ci-dessous :
# on la masque via CSS dès le 1er rendu.
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    [data-testid="stSidebarNav"] { display: none !important; }
    [data-testid="stSidebarNavItems"] { display: none !important; }
    [data-testid="stSidebarNavSeparator"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Sprint S20 / fix anomalie #2 — applique le thème (palette + chrome)
# **avant** tout autre rendu pour que background, sidebar et widgets
# soient cohérents dès le 1er paint.
apply_theme_chrome(st, get_current_theme(st.session_state))

# Phase 6.2 — gate d'authentification optionnelle (IHM_AUTH_TOKEN).
if not render_auth_gate():
    st.stop()

# ---------------------------------------------------------------------------
# Navigation sidebar — clés et constantes
# ---------------------------------------------------------------------------
PAGES = get_navigation_page_mapping()
PAGE_LABELS = get_navigation_page_labels()
PAGE_IMPORTS = get_navigation_page_imports()

# Clé canonique : label de la page active (single source of truth).
NAVIGATION_RADIO_KEY = "ihm_sidebar_navigation"
NAVIGATION_TARGET_PAGE_KEY = "ihm_navigation_target_page"


def _on_section_radio_change(section_key: str) -> None:
    """Callback : propage la sélection d'une section à la clé canonique.

    Streamlit appelle ce callback **avant** la phase de rendu suivante,
    permettant d'écrire dans ``st.session_state[NAVIGATION_RADIO_KEY]``
    sans conflit avec un widget portant cette clé (lequel n'existe
    plus depuis la suppression du radio « vue à plat »).
    """
    new_label = st.session_state.get(f"ihm_nav_section_{section_key}")
    if new_label and new_label in PAGE_LABELS:
        st.session_state[NAVIGATION_RADIO_KEY] = new_label


st.sidebar.title("📈 Alpha Trade")
st.sidebar.caption("Cockpit opérateur — supervision et suivi")

# Phase 6.2 — bannière sécurité (auth/exposition réseau).
render_security_banner()

with st.sidebar.expander("🧭 Aperçu navigation", expanded=False):
    st.caption(build_section_navigation_caption())

with st.sidebar.expander("🎨 Thème", expanded=False):
    try:
        render_theme_toggle(st)
    except Exception:
        pass

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

# Page demandée par redirection programmatique (boutons cross-page).
requested_page_key = st.session_state.pop(NAVIGATION_TARGET_PAGE_KEY, None)
if requested_page_key in PAGES.values():
    for label, key in PAGES.items():
        if key == requested_page_key:
            st.session_state[NAVIGATION_RADIO_KEY] = label
            break

# Initialise la sélection courante (1ère visite ⇒ Vue d'ensemble).
if NAVIGATION_RADIO_KEY not in st.session_state:
    st.session_state[NAVIGATION_RADIO_KEY] = PAGE_LABELS[0]

current_label: str = st.session_state[NAVIGATION_RADIO_KEY]

# ---------------------------------------------------------------------------
# Sprint S19.5 / fix anomalie #3 — Navigation hiérarchique en 5 sections.
# Une SEULE radio par section (pas de doublon « vue à plat »). Chaque
# radio a son propre key + un callback qui pousse la sélection vers
# ``NAVIGATION_RADIO_KEY``. La section contenant la page active est
# expandée par défaut ; les autres sont collapsées.
# ---------------------------------------------------------------------------
sections = get_navigation_sections()
st.sidebar.markdown("### 🧭 Navigation")
for section in sections:
    section_labels = [p.label for p in section.pages]
    if not section_labels:
        continue
    is_active_section = current_label in section_labels
    with st.sidebar.expander(
        f"{section.icon} {section.label}", expanded=is_active_section
    ):
        # ``index=`` pointe sur la page active si elle est dans la
        # section ; sinon, on n'impose pas de sélection visuelle.
        default_index = (
            section_labels.index(current_label) if is_active_section else 0
        )
        st.radio(
            label=f"Pages {section.label}",
            options=section_labels,
            index=default_index,
            label_visibility="collapsed",
            key=f"ihm_nav_section_{section.key}",
            on_change=_on_section_radio_change,
            args=(section.key,),
        )

# La sélection effective est lue APRÈS l'éventuelle propagation des
# callbacks. NB : les callbacks Streamlit ont déjà tourné à ce stade.
selection: str = st.session_state.get(NAVIGATION_RADIO_KEY, PAGE_LABELS[0])
if selection not in PAGES:
    selection = PAGE_LABELS[0]
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
