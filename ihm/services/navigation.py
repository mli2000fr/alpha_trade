"""Configuration centralisée de la navigation IHM Streamlit."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


NavigationGroup = Literal["pipeline", "support"]


@dataclass(frozen=True, slots=True)
class NavigationPage:
    """Définition d'une page affichée dans la sidebar."""

    label: str
    key: str
    module_name: str
    group: NavigationGroup


PIPELINE_NAVIGATION_PAGES: tuple[NavigationPage, ...] = (
    NavigationPage("🏠 Vue d'ensemble", "overview", "ihm.pages.overview", "pipeline"),
    NavigationPage("🔄 Pipeline", "pipeline", "ihm.pages.pipeline", "pipeline"),
    NavigationPage("📊 Screening", "screening", "ihm.pages.screening", "pipeline"),
    NavigationPage("🤖 ML / Prédictions", "ml", "ihm.pages.ml", "pipeline"),
    NavigationPage("⚖️ Risk", "risk", "ihm.pages.risk", "pipeline"),
    NavigationPage("🚀 Execution", "execution", "ihm.pages.execution", "pipeline"),
    NavigationPage("📑 Corporate Actions", "corporate_actions", "ihm.pages.corporate_actions", "pipeline"),
)


SUPPORT_NAVIGATION_PAGES: tuple[NavigationPage, ...] = (
    NavigationPage("🧪 Backtesting", "backtesting", "ihm.pages.backtesting", "support"),
    NavigationPage("🗃️ Administration DB", "db_admin", "ihm.pages.db_admin", "support"),
    NavigationPage("⚙️ Paramètres / Santé", "settings", "ihm.pages.settings", "support"),
)


NAVIGATION_PAGES: tuple[NavigationPage, ...] = PIPELINE_NAVIGATION_PAGES + SUPPORT_NAVIGATION_PAGES


def get_navigation_pages() -> tuple[NavigationPage, ...]:
    return NAVIGATION_PAGES


def get_navigation_page_labels() -> list[str]:
    return [page.label for page in NAVIGATION_PAGES]


def get_navigation_page_mapping() -> dict[str, str]:
    return {page.label: page.key for page in NAVIGATION_PAGES}


def get_navigation_page_imports() -> dict[str, str]:
    return {page.key: page.module_name for page in NAVIGATION_PAGES}


def build_primary_navigation_caption() -> str:
    return (
        "Flux quotidien du haut vers le bas : "
        "Vue d'ensemble → Pipeline → Screening → ML / Prédictions → Risk → Execution → Corporate Actions"
    )


def build_support_navigation_caption() -> str:
    return "Pages hors workflow quotidien : Backtesting → Administration DB → Paramètres / Santé"
