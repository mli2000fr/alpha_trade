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


# ---------------------------------------------------------------------------
# Anomalie (a) — le toggle doit se rendre dans le contexte courant,
# pas via ``st.sidebar.toggle`` (sinon l'expander « 🎨 Thème » est vide).
# ---------------------------------------------------------------------------

class _FakeSidebar:
    def __init__(self) -> None:
        self.toggle_calls: list[tuple[tuple, dict]] = []

    def toggle(self, *args, **kwargs) -> bool:  # pragma: no cover - garde-fou
        self.toggle_calls.append((args, kwargs))
        return False


class _FakeStreamlit:
    """Capture les appels critiques pour vérifier le rendu *contextuel*."""

    def __init__(self) -> None:
        self.session_state: dict = {}
        self.sidebar = _FakeSidebar()
        self.toggle_calls: list[tuple[tuple, dict]] = []
        self.markdown_calls: list[str] = []

    def toggle(self, *args, **kwargs) -> bool:
        self.toggle_calls.append((args, kwargs))
        return False  # par défaut : reste en light

    def markdown(self, html: str, unsafe_allow_html: bool = False) -> None:
        self.markdown_calls.append(html)

    def rerun(self) -> None:  # pragma: no cover - non sollicité ici
        pass


def test_render_theme_toggle_uses_context_toggle_not_sidebar() -> None:
    """Anti-régression anomalie (a) : ``render_theme_toggle`` doit
    appeler ``st.toggle(...)`` (rendu dans le ``with expander``) et
    NON ``st.sidebar.toggle(...)`` (rendu en haut de la sidebar
    ⇒ expander vide visible par l'utilisateur)."""
    fake = _FakeStreamlit()
    theme_manager.render_theme_toggle(fake)
    assert fake.toggle_calls, "Le toggle thème doit être créé via st.toggle()"
    assert not fake.sidebar.toggle_calls, (
        "Régression : le toggle est encore attaché à st.sidebar, ce qui "
        "vide l'expander '🎨 Thème' (anomalie a)."
    )


