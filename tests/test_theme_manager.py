"""Sprint S20 — Tests du gestionnaire de thème (light/dark)."""
from __future__ import annotations

from ihm.services import theme_manager
from ihm.theme import get_palette


def test_default_theme_is_light() -> None:
    state: dict = {}
    assert theme_manager.get_current_theme(state) == "light"


def test_set_theme_dark_persists_in_state() -> None:
    state: dict = {}
    theme_manager.set_theme(state, "dark")
    assert state[theme_manager.SESSION_KEY] == "dark"
    assert theme_manager.get_current_theme(state) == "dark"


def test_set_theme_unknown_falls_back_to_light() -> None:
    state: dict = {theme_manager.SESSION_KEY: "fluorescent"}
    assert theme_manager.get_current_theme(state) == "light"


def test_build_css_includes_palette_colors_for_light() -> None:
    css = theme_manager.build_css("light")
    palette = get_palette("light")
    # Au moins surface et border doivent être présents.
    assert palette["surface"] in css
    assert palette["border"] in css


def test_build_css_includes_palette_colors_for_dark() -> None:
    css = theme_manager.build_css("dark")
    palette = get_palette("dark")
    assert palette["surface"] in css
    assert palette["border"] in css


def test_palette_keys_are_consistent_across_themes() -> None:
    light = get_palette("light")
    dark = get_palette("dark")
    assert set(light.keys()) == set(dark.keys())


# ---------------------------------------------------------------------------
# Anomalie #2 — le CSS doit cibler le chrome global (pas seulement stMetric)
# ---------------------------------------------------------------------------

CHROME_SELECTORS = (
    "stAppViewContainer",
    "stMain",
    "stHeader",
    "stSidebar",
)


def test_build_css_targets_full_chrome_for_dark_mode() -> None:
    """Le mode sombre doit changer le background global, pas seulement
    les KPI (régression historique de l'anomalie #2)."""
    css = theme_manager.build_css("dark")
    for selector in CHROME_SELECTORS:
        assert selector in css, (
            f"CSS dark ne cible pas {selector!r} — le background "
            "resterait clair en mode sombre."
        )
    palette = get_palette("dark")
    # Le background sombre doit apparaître au moins une fois dans le CSS.
    assert palette["bg"] in css


def test_build_css_targets_full_chrome_for_light_mode() -> None:
    css = theme_manager.build_css("light")
    for selector in CHROME_SELECTORS:
        assert selector in css


def test_build_css_uses_important_to_override_streamlit_defaults() -> None:
    """Sans ``!important``, Streamlit gagne la cascade et ré-applique
    son fond blanc par-dessus notre thème."""
    css = theme_manager.build_css("dark")
    assert "!important" in css


