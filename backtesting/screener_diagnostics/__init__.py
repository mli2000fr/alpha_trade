"""
backtesting.screener_diagnostics — package des diagnostics screener.
Refactor Phase G.2 : le module historique (~2100 LOC) est éclaté en
sous-modules thématiques (`scenarios`, `analyze`, `regime`, `recommend`,
`holdout`). L'implémentation source reste centralisée dans `_impl` ;
chaque sous-module en réexporte uniquement la portion fonctionnelle qui le
concerne. Tous les symboles publics historiques restent disponibles depuis
``backtesting.screener_diagnostics`` afin de préserver la compatibilité
ascendante (tests + CLI).
"""
from __future__ import annotations
from backtesting.screener_diagnostics._impl import (
    # Datatypes
    ScreenerDiagnosticsResult,
    ScreenerDiagnosticsScenario,
    ScreenerDiagnosticsService,
    # Scenarios
    build_screener_grid_scenarios,
    build_screener_oat_scenarios,
    # Analyze
    summarize_screener_diagnostics,
    export_screener_diagnostics,
    # Regime
    classify_market_regimes,
    summarize_screener_diagnostics_by_regime,
    # Recommend
    build_cross_regime_recommendations,
    recommend_screener_scenarios,
    recommend_screener_scenarios_by_objective,
    recommend_screener_scenarios_by_regime,
    export_screener_objective_recommendations,
    export_screener_recommendations,
    export_screener_regime_recommendations,
    # Holdout
    export_holdout_validation,
    validate_recommendations_holdout,
    # Réexport pour compat tests : permet
    # `monkeypatch.setattr("backtesting.screener_diagnostics.get_required_bars_source_filter", ...)`
    get_required_bars_source_filter,
)
__all__ = [
    "ScreenerDiagnosticsResult",
    "ScreenerDiagnosticsScenario",
    "ScreenerDiagnosticsService",
    "get_required_bars_source_filter",
    "build_screener_grid_scenarios",
    "build_screener_oat_scenarios",
    "summarize_screener_diagnostics",
    "export_screener_diagnostics",
    "classify_market_regimes",
    "summarize_screener_diagnostics_by_regime",
    "build_cross_regime_recommendations",
    "recommend_screener_scenarios",
    "recommend_screener_scenarios_by_objective",
    "recommend_screener_scenarios_by_regime",
    "export_screener_objective_recommendations",
    "export_screener_recommendations",
    "export_screener_regime_recommendations",
    "export_holdout_validation",
    "validate_recommendations_holdout",
    "get_required_bars_source_filter",
]
