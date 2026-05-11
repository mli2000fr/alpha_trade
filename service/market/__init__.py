"""Couche centralisée de régime marché (Axe A du plan ``prompt/parttern/plan.md``).

Exporte :

* :class:`MarketRegimeSnapshot` — contexte immutable consommé par tous les
  modules (risk, execution, backtest, selector).
* :func:`build_snapshot` — orchestrateur principal.
* :func:`neutral_snapshot` — snapshot fallback (régime désactivé).
* Sous-modules :py:mod:`config`, :py:mod:`calendar_patterns`,
  :py:mod:`macro_signals`, :py:mod:`sentiment_regime`,
  :py:mod:`earnings_shield`, :py:mod:`volatility`.
"""
from service.market.config import (
    MarketRegimesConfig,
    TrailingStopYAMLConfig,
    parse_market_regimes,
    parse_trailing_stop,
)
from service.market.models import (
    EarningsShieldMode,
    MarketRegimeSnapshot,
    RegimeMode,
    neutral_snapshot,
)
from service.market.regime_manager import build_snapshot, reset_cache
from service.market.macro_providers import (
    CompositeMacroProvider,
    EodhdMacroProvider,
    StooqMacroProvider,
    build_default_macro_provider,
)

__all__ = [
    "MarketRegimeSnapshot",
    "MarketRegimesConfig",
    "TrailingStopYAMLConfig",
    "RegimeMode",
    "EarningsShieldMode",
    "build_snapshot",
    "neutral_snapshot",
    "reset_cache",
    "parse_market_regimes",
    "parse_trailing_stop",
    "StooqMacroProvider",
    "EodhdMacroProvider",
    "CompositeMacroProvider",
    "build_default_macro_provider",
]

