"""
ihm/app.py — Point d'entrée Streamlit pour l'IHM opérateur Alpha Trade.

Lancement :
    python -m streamlit run ihm/app.py
"""
from __future__ import annotations

import logging

import streamlit as st

from ihm.services.navigation import (
    get_navigation_page_imports,
    get_navigation_page_labels,
    get_navigation_page_mapping,
    get_navigation_sections,
)
from ihm.services.security import render_auth_gate, render_security_banner
from ihm.services.theme_manager import (
    apply_theme_chrome,
    get_current_theme,
)

logger = logging.getLogger(__name__)

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


def _select_page(label: str) -> None:
    """Callback bouton de navigation : fixe la page active.

    Fix anomalies (b) + (c) — l'ancien ``st.radio`` n'émettait
    ``on_change`` **que si la valeur changeait**, donc cliquer sur la
    page déjà sélectionnée (cas typique : « Vue d'ensemble » dans la
    section *Accueil* qui ne contient qu'une seule page) n'avait aucun
    effet. Avec ``st.button`` + ce callback, *chaque* clic positionne
    explicitement la sélection canonique.
    """
    if label in PAGE_LABELS:
        st.session_state[NAVIGATION_RADIO_KEY] = label


st.sidebar.title("📈 Alpha Trade")
st.sidebar.caption("Cockpit opérateur — supervision et suivi")

# Phase 6.2 — bannière sécurité (auth/exposition réseau).
render_security_banner()


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
# Sprint S20.6 / fix anomalies (b)+(c) — Navigation par **boutons**.
#
# Pourquoi des boutons et plus des radios :
#   * un ``st.radio`` n'émet ``on_change`` que si la valeur change ⇒
#     cliquer sur la page déjà active (typique de la section *Accueil*
#     mono-page) ne déclenche aucun rerun ;
#   * visuellement, une liste de radios fait « formulaire », pas
#     « menu de navigation institutionnel ».
#
# Convention :
#   * un bouton par page, libellé = label métier ;
#   * la page active est rendue en ``type="primary"`` ;
#   * ``use_container_width=True`` aligne tous les boutons à la largeur
#     de la sidebar pour un rendu menu propre ;
#   * la section contenant la page active est expandée par défaut.
# ---------------------------------------------------------------------------
sections = get_navigation_sections()
st.sidebar.markdown("### 🧭 Navigation")
for section in sections:
    section_pages = section.pages
    if not section_pages:
        continue
    section_labels = [p.label for p in section_pages]
    is_active_section = current_label in section_labels
    with st.sidebar.expander(
        f"{section.icon} {section.label}", expanded=is_active_section
    ):
        for page in section_pages:
            is_active = (page.label == current_label)
            st.button(
                page.label,
                key=f"ihm_nav_btn_{section.key}_{page.key}",
                type=("primary" if is_active else "secondary"),
                use_container_width=True,
                on_click=_select_page,
                args=(page.label,),
                help=f"Aller à la page : {page.label}",
            )

# La sélection effective est lue APRÈS l'éventuelle propagation des
# callbacks. NB : les callbacks Streamlit ont déjà tourné à ce stade.
selection: str = st.session_state.get(NAVIGATION_RADIO_KEY, PAGE_LABELS[0])
if selection not in PAGES:
    selection = PAGE_LABELS[0]
page_key = PAGES[selection]

# ---------------------------------------------------------------------------
# Sprint S27.7 / A14 — « Mode avancé » : réintroduit les 3 expanders
# historiques de la sidebar (Aperçu navigation, Thème, Connexion DB)
# précédemment masqués (régression de découvrabilité). L'opérateur garde
# le contrôle via un toggle dans la sidebar (persisté en session_state).
# ---------------------------------------------------------------------------
ADVANCED_MODE_KEY = "ihm_sidebar_advanced_mode"
st.session_state.setdefault(ADVANCED_MODE_KEY, False)

st.sidebar.markdown("---")
st.sidebar.toggle(
    "🛠️ Mode avancé",
    key=ADVANCED_MODE_KEY,
    help=(
        "Affiche les expanders avancés de la sidebar : aperçu de la "
        "navigation, sélecteur de thème, paramètres de connexion DB. "
        "Désactivé par défaut pour garder la sidebar épurée."
    ),
)

if st.session_state[ADVANCED_MODE_KEY]:
    with st.sidebar.expander("🧭 Aperçu navigation", expanded=False):
        try:
            from ihm.services.navigation import build_section_navigation_caption
            st.caption(build_section_navigation_caption())
        except Exception as exc:  # pragma: no cover — affichage défensif
            st.caption(f"Aperçu indisponible : {exc}")

    with st.sidebar.expander("🎨 Thème", expanded=False):
        try:
            from ihm.services.theme_manager import render_theme_toggle
            render_theme_toggle(st)
        except Exception as exc:  # pragma: no cover
            st.caption(f"Thème indisponible : {exc}")

    with st.sidebar.expander("🗄️ Connexion DB", expanded=False):
        try:
            from database.connection import get_sqlalchemy_engine
            engine = get_sqlalchemy_engine()
            url = getattr(engine, "url", None)
            st.caption(f"DSN : `{url}`" if url else "DSN indisponible.")
        except Exception as exc:  # pragma: no cover
            st.caption(f"Connexion indisponible : {exc}")

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
except Exception as exc:  # noqa: BLE001 — on veut TOUT capturer pour l'opérateur
    logger.exception("Erreur lors du rendu de la page %s", page_key)
    st.error(f"Erreur lors du rendu de la page : {exc}")
    st.exception(exc)
