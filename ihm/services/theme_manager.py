"""Sprint S20 — Toggle thème (light/dark) et injection CSS associée.

Streamlit limite l'altération du chrome après ``set_page_config``. On
applique donc :

* un toggle ``st.session_state["ihm_theme"]`` partagé entre pages ;
* une injection CSS étendue (palette + tabular-nums sur les KPI +
  background, sidebar, headers) via ``st.markdown(unsafe_allow_html=True)``.

Fix anomalie #2 — l'ancienne implémentation ne ciblait que les
``stMetric*`` : le background restait blanc en mode dark. La fonction
:func:`apply_theme_chrome` injecte désormais des règles ciblées sur
``stAppViewContainer``, ``stMain``, ``stSidebar`` et ``stHeader``.
"""
from __future__ import annotations

from typing import Literal

from ihm.theme import get_palette
from ihm.theme.typography import FONT_MONO

ThemeName = Literal["light", "dark"]
SESSION_KEY = "ihm_theme"


def get_current_theme(state: dict | None = None) -> ThemeName:
    """Retourne le thème actif. ``state`` est ``st.session_state`` (ou dict-like)."""
    if state is None:
        return "light"
    value = state.get(SESSION_KEY, "light")
    return "dark" if value == "dark" else "light"


def set_theme(state: dict, theme: ThemeName) -> None:
    state[SESSION_KEY] = "dark" if theme == "dark" else "light"


def build_css(theme: ThemeName) -> str:
    """Retourne le bloc ``<style>`` à injecter pour appliquer le thème.

    Couvre :
    * Conteneur principal (background, texte) ;
    * Sidebar (background, séparateurs) ;
    * Header Streamlit (visibilité réduite en dark) ;
    * KPI (police mono + couleurs) ;
    * Badges harmonisés (success/warning/danger/info).
    """
    p = get_palette(theme)
    nav_active_bg = "#CBD5E1" if theme == "light" else "#64748B"
    nav_active_hover_bg = "#BFCAD8" if theme == "light" else "#75859A"
    nav_active_text = p["text"]
    return (
        "<style>"
        # === Conteneur principal ===
        f"[data-testid='stAppViewContainer'] {{ "
        f"  background-color: {p['bg']} !important; "
        f"  color: {p['text']} !important; "
        f"}}"
        f"[data-testid='stMain'] {{ "
        f"  background-color: {p['bg']} !important; "
        f"}}"
        f".main, .stApp {{ "
        f"  background-color: {p['bg']} !important; "
        f"  color: {p['text']} !important; "
        f"}}"
        # === Header (barre supérieure) ===
        f"[data-testid='stHeader'] {{ "
        f"  background-color: {p['bg']} !important; "
        f"  border-bottom: 1px solid {p['border']} !important; "
        f"}}"
        # === Sidebar ===
        f"[data-testid='stSidebar'] {{ "
        f"  background-color: {p['surface']} !important; "
        f"  border-right: 1px solid {p['border']} !important; "
        f"  --primary-color: {nav_active_bg} !important; "
        f"  accent-color: {nav_active_bg} !important; "
        f"}}"
        f"[data-testid='stSidebar'] * {{ "
        f"  color: {p['text']} !important; "
        f"}}"
        f"[data-testid='stSidebar'] .stMarkdown, "
        f"[data-testid='stSidebar'] [data-testid='stCaptionContainer'] {{ "
        f"  color: {p['text_muted']} !important; "
        f"}}"
        # === Texte général ===
        f"h1, h2, h3, h4, h5, h6, p, span, label, div {{ "
        f"  color: {p['text']}; "
        f"}}"
        # === KPI / metrics ===
        f"[data-testid='stMetricValue'] {{ "
        f"  font-family: {FONT_MONO}; "
        f"  font-variant-numeric: tabular-nums; "
        f"  color: {p['text']} !important; "
        f"}}"
        f"[data-testid='stMetricLabel'] {{ "
        f"  color: {p['text_muted']} !important; "
        f"}}"
        f"[data-testid='stMetricDelta'] {{ "
        f"  color: {p['text_muted']} !important; "
        f"}}"
        # === Cartes KPI custom ===
        f"div.alpha-kpi-card {{ "
        f"  background: {p['surface']}; "
        f"  border: 1px solid {p['border']}; "
        f"  border-radius: 8px; "
        f"  padding: 0.75rem 1rem; "
        f"}}"
        # === Badges statut ===
        f"span.alpha-badge-ok {{ color: {p['success']}; font-weight: 600; }}"
        f"span.alpha-badge-warning {{ color: {p['warning']}; font-weight: 600; }}"
        f"span.alpha-badge-danger {{ color: {p['danger']}; font-weight: 600; }}"
        f"span.alpha-badge-info {{ color: {p['info']}; font-weight: 600; }}"
        # === Tableaux / dataframes ===
        f"[data-testid='stDataFrame'] {{ "
        f"  background-color: {p['surface']} !important; "
        f"}}"
        # === Inputs / selects (en mode dark, fond sombre) ===
        f"[data-baseweb='select'] > div, "
        f"[data-baseweb='input'] > div {{ "
        f"  background-color: {p['surface']} !important; "
        f"  color: {p['text']} !important; "
        f"  border-color: {p['border']} !important; "
        f"}}"
        # === Expanders ===
        f"[data-testid='stExpander'] {{ "
        f"  background-color: {p['surface']}; "
        f"  border: 1px solid {p['border']}; "
        f"  border-radius: 6px; "
        f"}}"
        # === Navigation active (sidebar) ===
        # Streamlit peut rendre un bouton primaire avec plusieurs variantes
        # de markup selon la version (`kind='primary'`, `data-testid`,
        # wrapper `.stButton`, etc.). On cible volontairement large pour
        # écraser toute couleur primaire résiduelle (ici rouge côté user).
        f"[data-testid='stSidebar'] .stButton > button[kind='primary'], "
        f"[data-testid='stSidebar'] button[kind='primary'], "
        f"[data-testid='stSidebar'] button[data-testid='baseButton-primary'] {{ "
        f"  background: {nav_active_bg} !important; "
        f"  background-color: {nav_active_bg} !important; "
        f"  border: 1px solid {nav_active_bg} !important; "
        f"  border-color: {nav_active_bg} !important; "
        f"  color: {nav_active_text} !important; "
        f"  box-shadow: none !important; "
        f"}}"
        f"[data-testid='stSidebar'] .stButton > button[kind='primary']:hover, "
        f"[data-testid='stSidebar'] button[kind='primary']:hover, "
        f"[data-testid='stSidebar'] button[data-testid='baseButton-primary']:hover, "
        f"[data-testid='stSidebar'] .stButton > button[kind='primary']:focus, "
        f"[data-testid='stSidebar'] button[kind='primary']:focus, "
        f"[data-testid='stSidebar'] button[data-testid='baseButton-primary']:focus {{ "
        f"  background: {nav_active_hover_bg} !important; "
        f"  background-color: {nav_active_hover_bg} !important; "
        f"  border-color: {nav_active_hover_bg} !important; "
        f"  color: {nav_active_text} !important; "
        f"  box-shadow: none !important; "
        f"}}"
        # === Liens ===
        f"a {{ color: {p['primary']} !important; }}"
        "</style>"
    )


def apply_theme_chrome(st_module, theme: ThemeName) -> None:
    """Injecte le CSS du thème au niveau ``st`` (chrome global).

    À appeler **une seule fois** près du début de ``app.py`` (après
    ``set_page_config`` mais avant tout autre rendu) pour garantir une
    palette cohérente sur l'ensemble de la page (background inclus).
    """
    st_module.markdown(build_css(theme), unsafe_allow_html=True)


def render_theme_toggle(st_module) -> ThemeName:
    """Affiche le toggle dans la sidebar et retourne le thème courant.

    Si l'utilisateur change le thème, on applique immédiatement le CSS
    associé puis on déclenche un ``st.rerun()`` afin que toutes les
    règles ``!important`` soient ré-injectées en haut de page (sans
    quoi seuls les blocs rendus *après* le toggle reçoivent le nouveau
    chrome — c'est ce qui produisait l'anomalie #2).

    ``st_module`` est passé en paramètre pour garder ce service
    *Streamlit-agnostique* aux fins de tests unitaires.
    """
    previous = get_current_theme(st_module.session_state)
    # Fix anomalie (a) — utiliser ``st_module.toggle`` (pas
    # ``st_module.sidebar.toggle``) afin que le widget se rende dans le
    # *context manager* courant (typiquement un ``st.sidebar.expander``
    # créé par l'appelant). Sinon le toggle s'affiche en haut de la
    # sidebar et l'expander « 🎨 Thème » apparaît vide.
    is_dark = st_module.toggle(
        "🌙 Thème sombre",
        value=(previous == "dark"),
        key="ihm_theme_toggle",
        help="Bascule la palette IHM en mode sombre (haute densité, lecture nocturne).",
    )
    new_theme: ThemeName = "dark" if is_dark else "light"
    if new_theme != previous:
        set_theme(st_module.session_state, new_theme)
        # Re-run pour que ``apply_theme_chrome`` (en haut de app.py)
        # ré-injecte le CSS correspondant au nouveau thème.
        try:
            st_module.rerun()
        except Exception:
            # st.rerun introduit en Streamlit 1.27 ; fallback no-op.
            pass
    apply_theme_chrome(st_module, new_theme)
    return new_theme
