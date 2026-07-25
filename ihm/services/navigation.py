"""Configuration centralisée de la navigation IHM Streamlit.

Sprint S19.5 — Refonte hiérarchique en **5 sections** logiques (cf.
``prompt/tod/plan_ihm.md`` §2.2). Compatibilité ascendante préservée :
les helpers historiques ``get_navigation_pages`` / ``_labels`` /
``_mapping`` / ``_imports`` continuent à exposer une vue à plat.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

NavigationGroup = Literal[
    "pipeline",
    "support",
    "home",
    "trading",
    "research",
    "config",
    "workflow",
    "compliance",
]


@dataclass(frozen=True, slots=True)
class NavigationPage:
    """Définition d'une page affichée dans la sidebar."""

    label: str
    key: str
    module_name: str
    group: NavigationGroup


@dataclass(frozen=True, slots=True)
class NavigationSection:
    """Section logique regroupant plusieurs pages (S19.5)."""

    key: str
    label: str
    icon: str
    pages: tuple[NavigationPage, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Pages — compat ascendante (groupes "pipeline" / "support" historiques)
# ---------------------------------------------------------------------------

PIPELINE_NAVIGATION_PAGES: tuple[NavigationPage, ...] = (
    NavigationPage("🏠 Vue d'ensemble", "overview", "ihm.pages.overview", "pipeline"),
    NavigationPage("🔄 Pipeline", "pipeline", "ihm.pages.pipeline", "pipeline"),
    NavigationPage("📊 Screening", "screening", "ihm.pages.screening", "pipeline"),
    NavigationPage("🤖 ML / Prédictions", "ml", "ihm.pages.ml", "pipeline"),
    NavigationPage("⚖️ Risk", "risk", "ihm.pages.risk", "pipeline"),
    NavigationPage("📊 Régime Marché", "market_regime", "ihm.pages.market_regime", "pipeline"),
    NavigationPage("🚀 Execution", "execution", "ihm.pages.execution", "pipeline"),
    NavigationPage("🏦 Comptes Alpaca", "alpaca_accounts", "ihm.pages.alpaca_accounts", "pipeline"),
    NavigationPage("📑 Corporate Actions", "corporate_actions", "ihm.pages.corporate_actions", "pipeline"),
)


SUPPORT_NAVIGATION_PAGES: tuple[NavigationPage, ...] = (
    NavigationPage("🛟 Supervision Ops", "supervision_ops", "ihm.pages.supervision_ops", "support"),
    NavigationPage("🔧 Infra & Backups", "ops_infra", "ihm.pages.ops_infra", "support"),
    NavigationPage("🧪 Backtesting", "backtesting", "ihm.pages.backtesting", "support"),
    NavigationPage("🧮 Calibrations poids", "weights_calibration_runs", "ihm.pages.weights_calibration_runs", "support"),
    NavigationPage("🔀 Parité Backtest ↔ Live", "parity", "ihm.pages.parity", "support"),
    NavigationPage("🩺 Diagnostic ML", "ml_diagnostics", "ihm.pages.ml_diagnostics", "support"),
    NavigationPage("📊 Fondamentaux", "fundamentals", "ihm.pages.fundamentals", "support"),
    NavigationPage("🗃️ Administration DB", "db_admin", "ihm.pages.db_admin", "support"),
    NavigationPage("⚙️ Paramètres / Santé", "settings", "ihm.pages.settings", "support"),
    # Sprint S19.4 / S19.5 — nouvelles pages institutionnelles
    NavigationPage("💰 Tax Compliance", "tax_compliance", "ihm.pages.tax_compliance", "support"),
    NavigationPage("📜 Compliance & Audit", "compliance_audit", "ihm.pages.compliance_audit", "support"),
    # Sprint S24.2 — Phase G : sandbox health 30 j
    NavigationPage("🟢 Sandbox health", "sandbox_health", "ihm.pages.sandbox_health", "support"),
    NavigationPage("📚 Glossaire", "glossary", "ihm.pages.glossary", "support"),
)


NAVIGATION_PAGES: tuple[NavigationPage, ...] = (
    PIPELINE_NAVIGATION_PAGES + SUPPORT_NAVIGATION_PAGES
)


# ---------------------------------------------------------------------------
# Sections hiérarchiques cible (Sprint S19.5)
# ---------------------------------------------------------------------------


def _get_page(key: str) -> NavigationPage:
    for page in NAVIGATION_PAGES:
        if page.key == key:
            return page
    raise KeyError(f"Page navigation inconnue : {key}")


def get_navigation_sections() -> tuple[NavigationSection, ...]:
    """Retourne les sections logiques de la sidebar (Sprint S19.5 + S20.6).

    Évolution S20.6 — anomalie utilisateur (d) : la page **Pipeline**
    (utilisée quotidiennement) a été promue dans une section dédiée
    *Workflow & Orchestration* en tête, et n'apparaît plus dans
    *Configuration* (qui ne devait recevoir que les réglages durables).
    """
    return (
        NavigationSection(
            key="home",
            label="Accueil",
            icon="🏠",
            pages=(_get_page("overview"),),
        ),
        NavigationSection(
            key="workflow",
            label="Workflow & Orchestration",
            icon="🔄",
            pages=(
                _get_page("pipeline"),
                _get_page("supervision_ops"),
                _get_page("ops_infra"),
            ),
        ),
        NavigationSection(
            key="trading",
            label="Trading",
            icon="📈",
            pages=(
                _get_page("execution"),
                _get_page("risk"),
                _get_page("market_regime"),
                _get_page("alpaca_accounts"),
            ),
        ),
        NavigationSection(
            key="research",
            label="Analyse & Recherche",
            icon="🔬",
            pages=(
                _get_page("screening"),
                _get_page("backtesting"),
                _get_page("weights_calibration_runs"),
                _get_page("parity"),
                _get_page("ml"),
                _get_page("ml_diagnostics"),
                _get_page("fundamentals"),
            ),
        ),
        NavigationSection(
            key="config",
            label="Configuration",
            icon="⚙️",
            pages=(
                _get_page("settings"),
            ),
        ),
        NavigationSection(
            key="compliance",
            label="Conformité & Admin",
            icon="🛡️",
            pages=(
                _get_page("compliance_audit"),
                _get_page("tax_compliance"),
                _get_page("sandbox_health"),
                _get_page("corporate_actions"),
                _get_page("db_admin"),
                _get_page("glossary"),
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Helpers historiques (rétro-compat — ne pas casser app.py / tests)
# ---------------------------------------------------------------------------


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
        "Vue d'ensemble → Pipeline → Screening → ML / Prédictions → Risk → Execution → Comptes Alpaca → Corporate Actions"
    )


def build_support_navigation_caption() -> str:
    return (
        "Pages hors workflow quotidien : Supervision Ops → Backtesting → "
        "Calibrations poids → Parité Backtest ↔ Live → Administration DB → Paramètres / Santé → "
        "Tax Compliance → Compliance & Audit → Glossaire"
    )


def build_section_navigation_caption() -> str:
    """Sprint S19.5 — caption pour la nouvelle vue par sections."""
    sections = get_navigation_sections()
    return " · ".join(f"{s.icon} {s.label}" for s in sections)
