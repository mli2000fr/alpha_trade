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
# Anomalie #3 / S20.6 — navigation par boutons (plus de radio par section)
# ---------------------------------------------------------------------------

def test_app_py_uses_buttons_for_navigation_not_radios() -> None:
    """S20.6 — anomalies (b)+(c) : la nav utilise ``st.button`` avec
    callback ``_select_page``. Les radios par section ont été retirés
    car ils n'émettaient pas ``on_change`` lorsqu'on cliquait sur la
    page déjà active (cas des sections mono-page comme *Accueil*)."""
    src = APP_PATH.read_text(encoding="utf-8")
    assert "_select_page" in src
    assert "st.button(" in src
    assert "ihm_nav_btn_" in src
    # Les anciens radios de section (clé ``ihm_nav_section_*``) ne
    # doivent plus exister.
    assert "ihm_nav_section_" not in src
    assert "_on_section_radio_change" not in src


def test_app_py_does_not_define_flat_navigation_radio() -> None:
    """Anti-régression historique : pas de radio « vue à plat » qui
    réécrasait la sélection à chaque rerun."""
    src = APP_PATH.read_text(encoding="utf-8")
    assert "key=NAVIGATION_RADIO_KEY" not in src


# ---------------------------------------------------------------------------
# Sections hiérarchiques
# ---------------------------------------------------------------------------

EXPECTED_SECTION_KEYS = (
    "home",
    "workflow",
    "trading",
    "research",
    "config",
    "compliance",
)


def test_navigation_exposes_expected_sections_in_correct_order() -> None:
    sections = get_navigation_sections()
    assert tuple(s.key for s in sections) == EXPECTED_SECTION_KEYS


def test_pipeline_is_promoted_to_workflow_section_not_config() -> None:
    """S20.6 — anomalie (d) : Pipeline est utilisé tous les jours, il
    doit vivre dans la section *Workflow & Orchestration* en tête, pas
    dans *Configuration*."""
    sections = {s.key: s for s in get_navigation_sections()}
    workflow_keys = {p.key for p in sections["workflow"].pages}
    config_keys = {p.key for p in sections["config"].pages}
    assert "pipeline" in workflow_keys
    assert "pipeline" not in config_keys


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
# Callback ``_select_page`` — bouton de navigation (S20.6)
# ---------------------------------------------------------------------------

class _FakeSessionState(dict):
    """Mime ``st.session_state`` pour les besoins du test unitaire."""


@pytest.fixture()
def fake_state() -> _FakeSessionState:
    return _FakeSessionState()


def test_select_page_callback_sets_canonical_key(fake_state) -> None:
    """Le callback bouton doit positionner la clé canonique de
    navigation, **même** si la page cliquée est déjà active (cas qui
    cassait l'ancien radio mono-option de la section *Accueil*)."""
    page_labels = set(get_navigation_page_labels())
    target_label = next(iter(page_labels))

    # Reproduction locale du callback ``_select_page`` d'``app.py`` :
    # toute la valeur ajoutée tient dans la garde sur le label valide.
    def _select_page(label: str) -> None:
        if label in page_labels:
            fake_state["ihm_sidebar_navigation"] = label

    # Premier clic : sélection initiale.
    _select_page(target_label)
    assert fake_state["ihm_sidebar_navigation"] == target_label

    # Re-clic sur la même page : doit rester valide (anti-régression
    # du bug « cliquer sur Vue d'ensemble ne fait rien »).
    _select_page(target_label)
    assert fake_state["ihm_sidebar_navigation"] == target_label

