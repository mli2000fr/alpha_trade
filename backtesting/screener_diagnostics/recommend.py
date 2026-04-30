"""Phase G.2 — moteurs de recommandation de scénarios screener."""
from __future__ import annotations
from backtesting.screener_diagnostics._impl import (
    build_cross_regime_recommendations,
    export_screener_objective_recommendations,
    export_screener_recommendations,
    export_screener_regime_recommendations,
    recommend_screener_scenarios,
    recommend_screener_scenarios_by_objective,
    recommend_screener_scenarios_by_regime,
)
__all__ = [
    "build_cross_regime_recommendations",
    "export_screener_objective_recommendations",
    "export_screener_recommendations",
    "export_screener_regime_recommendations",
    "recommend_screener_scenarios",
    "recommend_screener_scenarios_by_objective",
    "recommend_screener_scenarios_by_regime",
]
