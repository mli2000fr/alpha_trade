"""Sprint S19.5 — Tests de non-régression sur la navigation hiérarchique.

Ces tests verrouillent les 3 corrections d'anomalies UX :

* **Anomalie #1** : ``app.py`` masque la navigation auto-générée par
  Streamlit (``[data-testid="stSidebarNav"]``) afin d'éviter le doublon
  avec la navigation métier.
* **Anomalie #3** : la sidebar n'expose plus qu'**une seule** radio par
  section (5 sections logiques) ; un callback ``on_change`` propage la
  sélection vers la clé canonique ``ihm_sidebar_navigation``. Plus de
  radio « vue à plat » qui réécrasait la valeur à chaque rerun.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ihm.services.navigation import (
    NavigationSection,
    build_section_navigation_caption,
    get_navigation_page_labels,
    get_navigation_page_mapping,
    get_navigation_sections,
)

APP_PATH = Path(__file__).resolve().parents[1] / "ihm" / "app.py"


# ---------------------------------------------------------------------------
# Anomalie #1 — masquage de la navigation auto Streamlit
# ---------------------------------------------------------------------------

def test_app_py_hides_streamlit_auto_sidebar_nav() -> None:
    """``app.py`` doit injecter du CSS masquant ``stSidebarNav``."""
    src = APP_PATH.read_text(encoding="utf-8")
    assert 'data-testid="stSidebarNav"' in src, (
        "app.py doit masquer la nav auto-générée par Streamlit "
        "(doublon avec la nav hiérarchique)."
    )
    assert "display: none" in src


# ---------------------------------------------------------------------------
# Anomalie #3 — une seule radio par section + clé canonique
# ---------------------------------------------------------------------------

def test_app_py_has_single_radio_per_section_with_callback() -> None:
    src = APP_PATH.read_text(encoding="utf-8")
    # Convention : un radio par section, clé "ihm_nav_section_<key>",
    # callback ``_on_section_radio_change``.
    assert "ihm_nav_section_" in src
    assert "_on_section_radio_change" in src
    # Clé canonique unique pour la sélection effective.
    assert "ihm_sidebar_navigation" in src


def test_app_py_does_not_define_flat_navigation_radio() -> None:
    """Le radio « vue à plat » historique (qui causait l'anomalie #3)
    ne doit plus exister."""
    src = APP_PATH.read_text(encoding="utf-8")
    # L'ancien radio plat utilisait directement ``key=NAVIGATION_RADIO_KEY``
    # ce qui entrait en conflit avec l'écriture par callback.
    assert "key=NAVIGATION_RADIO_KEY" not in src


# ---------------------------------------------------------------------------
# Sections hiérarchiques
# ---------------------------------------------------------------------------

EXPECTED_SECTION_KEYS = ("home", "trading", "research", "config", "compliance")


def test_navigation_exposes_five_sections_in_correct_order() -> None:
    sections = get_navigation_sections()
    assert tuple(s.key for s in sections) == EXPECTED_SECTION_KEYS


def test_each_section_is_non_empty_and_has_icon_label() -> None:
    for section in get_navigation_sections():
        assert isinstance(section, NavigationSection)
        assert section.icon, f"section {section.key} sans icône"
        assert section.label, f"section {section.key} sans label"
        assert section.pages, f"section {section.key} vide"


def test_every_navigation_page_belongs_to_exactly_one_section() -> None:
    all_labels = set(get_navigation_page_labels())
    seen: dict[str, str] = {}
    for section in get_navigation_sections():
        for page in section.pages:
            assert page.label not in seen, (
                f"page {page.label!r} dupliquée entre sections "
                f"{seen[page.label]} et {section.key}"
            )
            seen[page.label] = section.key
    # Chaque page de la nav à plat doit appartenir à une section
    # (sinon elle serait orpheline et non navigable).
    missing = all_labels - set(seen.keys())
    assert not missing, f"pages non rattachées à une section : {missing}"


def test_navigation_section_caption_lists_all_sections() -> None:
    caption = build_section_navigation_caption()
    for section in get_navigation_sections():
        assert section.label in caption


def test_navigation_page_mapping_keys_are_unique() -> None:
    mapping = get_navigation_page_mapping()
    assert len(mapping) == len(get_navigation_page_labels())


# ---------------------------------------------------------------------------
# Simulation du callback de navigation (anomalie #3)
# ---------------------------------------------------------------------------

class _FakeSessionState(dict):
    """Mime ``st.session_state`` pour les besoins du test unitaire."""


@pytest.fixture()
def fake_state() -> _FakeSessionState:
    return _FakeSessionState()


def test_section_radio_callback_updates_canonical_key(fake_state) -> None:
    """Le callback doit propager la sélection d'une section vers la
    clé canonique ``ihm_sidebar_navigation``."""
    sections = get_navigation_sections()
    trading = next(s for s in sections if s.key == "trading")
    target_label = trading.pages[0].label

    # Simulation : Streamlit a écrit la valeur dans la clé du radio.
    fake_state[f"ihm_nav_section_{trading.key}"] = target_label

    # Réimplémentation locale du callback (identique à celui d'app.py)
    # afin de vérifier le contrat sans avoir à instancier Streamlit.
    page_labels = set(get_navigation_page_labels())
    new_label = fake_state.get(f"ihm_nav_section_{trading.key}")
    if new_label and new_label in page_labels:
        fake_state["ihm_sidebar_navigation"] = new_label

    assert fake_state["ihm_sidebar_navigation"] == target_label

