"""Phase G.2 — validation hors-échantillon (holdout) des recommandations."""
from __future__ import annotations
from backtesting.screener_diagnostics._impl import (
    export_holdout_validation,
    validate_recommendations_holdout,
)
__all__ = [
    "export_holdout_validation",
    "validate_recommendations_holdout",
]
