"""Phase G.2 — classification des régimes de marché et résumés associés."""
from __future__ import annotations
from backtesting.screener_diagnostics._impl import (
    classify_market_regimes,
    summarize_screener_diagnostics_by_regime,
)
__all__ = [
    "classify_market_regimes",
    "summarize_screener_diagnostics_by_regime",
]
