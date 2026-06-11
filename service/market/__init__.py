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
    RegimeHysteresisConfig,
    TrailingStopYAMLConfig,
    parse_market_regimes,
    parse_trailing_stop,
)
from service.market.models import (
    EarningsShieldMode,
    MarketRegimeState,
    MarketRegimeSnapshot,
    RegimeMode,
    neutral_snapshot,
)
from service.market.regime_manager import MacroDataUnavailableError, build_snapshot, reset_cache
from service.market.state_store import load_regime_state, save_regime_state
from service.market.macro_providers import (
    CompositeMacroProvider,
    EodhdMacroProvider,
    FredMacroProvider,
    MACRO_PIT_MODE_ASOF_INCLUSIVE,
    MACRO_PIT_MODE_J_MINUS_1_STRICT,
    StooqMacroProvider,
    TableFirstMacroProvider,
    build_default_macro_provider,
    normalize_macro_pit_mode,
    populate_macro_indicators_table,
    resolve_macro_pit_mode,
)
from service.market.sentiment_provider import (
    DbSentimentScoreProvider,
    MarketSentimentReading,
    load_market_sentiment_reading,
)

__all__ = [
    "MarketRegimeSnapshot",
    "MarketRegimeState",
    "MarketRegimesConfig",
    "RegimeHysteresisConfig",
    "TrailingStopYAMLConfig",
    "RegimeMode",
    "EarningsShieldMode",
    "build_snapshot",
    "MacroDataUnavailableError",
    "neutral_snapshot",
    "reset_cache",
    "parse_market_regimes",
    "parse_trailing_stop",
    "load_regime_state",
    "save_regime_state",
    "StooqMacroProvider",
    "EodhdMacroProvider",
    "FredMacroProvider",
    "MACRO_PIT_MODE_ASOF_INCLUSIVE",
    "MACRO_PIT_MODE_J_MINUS_1_STRICT",
    "TableFirstMacroProvider",
    "CompositeMacroProvider",
    "build_default_macro_provider",
    "normalize_macro_pit_mode",
    "resolve_macro_pit_mode",
    "populate_macro_indicators_table",
    "DbSentimentScoreProvider",
    "MarketSentimentReading",
    "load_market_sentiment_reading",
]

