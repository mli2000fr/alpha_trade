"""Parser typé du bloc YAML ``market_regimes`` + ``risk_management.trailing_stop``.

Le parser est tolérant aux clés manquantes : valeurs par défaut conservatrices
qui maintiennent le comportement nominal historique du dépôt si la section
n'est pas définie dans `config.yaml`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class CalendarPatternConfig:
    enabled: bool = False
    start: str = "01-01"
    end: str = "01-01"
    risk_mult: float = 1.0
    screener_expansion_pct: float = 0.0
    sentiment_threshold_addon: float = 0.0
    block_new_entries: bool = False
    rule: str | None = None  # ex 3rd_friday
    mode: str | None = None  # ex sentiment_hardening | block_entries
    business_days_from_month_end: int | None = None


@dataclass(frozen=True, slots=True)
class VixConfig:
    enabled: bool = False
    symbol: str = "VIX"
    high_threshold: float = 25.0
    inverted_curve_mode: str = "capital_preservation"


@dataclass(frozen=True, slots=True)
class YieldsConfig:
    enabled: bool = False
    provider: str = "default"
    symbol_10y: str = "US10Y"
    fred_series_10y: str = "DGS10"
    lookback_days: int = 5
    relative_spike_threshold: float = 0.05
    block_sectors: tuple[str, ...] = ("Technology", "Tech", "Growth")
    block_high_beta: bool = True
    high_beta_threshold: float = 1.2
    risk_mult: float = 0.6
    soft_max_positions: int | None = None
    soft_max_position_weight: float | None = None
    soft_max_sector_weight: float | None = None
    soft_max_gross_exposure: float | None = None
    hard_relative_spike_threshold: float | None = None
    hard_block_sectors: tuple[str, ...] = ()
    hard_risk_mult: float | None = None
    hard_mode_live: str = "close_only"
    hard_mode_backtest: str = "cash_only"
    hard_requires_vix_high: bool = True
    hard_requires_sentiment_warning: bool = True
    hard_max_positions: int | None = None
    hard_max_position_weight: float | None = None
    hard_max_sector_weight: float | None = None
    hard_max_gross_exposure: float | None = None


@dataclass(frozen=True, slots=True)
class SentimentBreakerConfig:
    enabled: bool = False
    lookback_days: int = 7
    warning_threshold: float = -0.15
    critical_threshold: float = -0.30
    warning_max_positions: int = 2
    critical_mode_live: str = "close_only"
    critical_mode_backtest: str = "cash_only"


@dataclass(frozen=True, slots=True)
class SectorLimitsConfig:
    enabled: bool = False
    max_tickers_per_sector: int = 2


@dataclass(frozen=True, slots=True)
class EarningsShieldConfig:
    enabled: bool = False
    days_before: int = 2
    days_after: int = 2
    mode: str = "strict_block"  # strict_block | negative_score
    negative_score_value: float = -1.0


@dataclass(frozen=True, slots=True)
class BuybackBlackoutConfig:
    enabled: bool = False
    days_before_earnings: int = 14
    ml_score_multiplier: float = 0.70


@dataclass(frozen=True, slots=True)
class SentinelConfig:
    enabled: bool = True
    preflight_summary: bool = True


@dataclass(frozen=True, slots=True)
class MarketRegimesConfig:
    enabled: bool = False
    cache_ttl_seconds: int = 300
    enforce_min_notional: float = 155.0
    capital_preservation_max_gross_exposure: float | None = None
    allow_neutral_fallback_on_missing_macro_data: bool = True
    macro_pit_mode_backtest: str = "asof_inclusive"

    sentinel: SentinelConfig = field(default_factory=SentinelConfig)
    vix: VixConfig = field(default_factory=VixConfig)
    yields: YieldsConfig = field(default_factory=YieldsConfig)
    sentiment_circuit_breaker: SentimentBreakerConfig = field(default_factory=SentimentBreakerConfig)
    sector_limits: SectorLimitsConfig = field(default_factory=SectorLimitsConfig)
    earnings_shield: EarningsShieldConfig = field(default_factory=EarningsShieldConfig)
    buyback_blackout: BuybackBlackoutConfig = field(default_factory=BuybackBlackoutConfig)
    patterns: Mapping[str, CalendarPatternConfig] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TrailingStopYAMLConfig:
    enabled: bool = False
    mode: str = "fixed"  # fixed | dynamic_atr
    atr_period: int = 14
    atr_multiplier: float = 2.5
    fallback_fixed_pct: float = 5.0
    break_even_after_atr_multiple: float = 2.0
    eod_check_time_est: str = "15:50"
    apply_to_manual_orphan_buys: bool = True


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _to_pattern(name: str, raw: Mapping[str, Any] | None) -> CalendarPatternConfig:
    raw = raw or {}
    return CalendarPatternConfig(
        enabled=bool(raw.get("enabled", False)),
        start=str(raw.get("start", "01-01")),
        end=str(raw.get("end", "01-01")),
        risk_mult=float(raw.get("risk_mult", 1.0)),
        screener_expansion_pct=float(raw.get("screener_expansion_pct", 0.0)),
        sentiment_threshold_addon=float(raw.get("sentiment_threshold_addon", 0.0)),
        block_new_entries=bool(raw.get("block_new_entries", False)),
        rule=raw.get("rule"),
        mode=raw.get("mode"),
        business_days_from_month_end=raw.get("business_days_from_month_end"),
    )


def parse_market_regimes(raw: Mapping[str, Any] | None) -> MarketRegimesConfig:
    """Construit un ``MarketRegimesConfig`` à partir du dict YAML."""
    raw = raw or {}
    sentinel = raw.get("sentinel", {}) or {}
    vix = raw.get("vix", {}) or {}
    yields = raw.get("yields", {}) or {}
    breaker = raw.get("sentiment_circuit_breaker", {}) or {}
    sector_limits = raw.get("sector_limits", {}) or {}
    earnings = raw.get("earnings_shield", {}) or {}
    buyback = raw.get("buyback_blackout", {}) or {}
    patterns_raw = raw.get("patterns", {}) or {}
    patterns = {name: _to_pattern(name, val) for name, val in patterns_raw.items()}

    return MarketRegimesConfig(
        enabled=bool(raw.get("enabled", False)),
        cache_ttl_seconds=int(raw.get("cache_ttl_seconds", 300)),
        enforce_min_notional=float(raw.get("enforce_min_notional", 155.0)),
        capital_preservation_max_gross_exposure=(
            float(raw["capital_preservation_max_gross_exposure"])
            if raw.get("capital_preservation_max_gross_exposure") not in {None, ""}
            else None
        ),
        allow_neutral_fallback_on_missing_macro_data=bool(
            raw.get("allow_neutral_fallback_on_missing_macro_data", True)
        ),
        macro_pit_mode_backtest=str(raw.get("macro_pit_mode_backtest", "asof_inclusive") or "asof_inclusive"),
        sentinel=SentinelConfig(
            enabled=bool(sentinel.get("enabled", True)),
            preflight_summary=bool(sentinel.get("preflight_summary", True)),
        ),
        vix=VixConfig(
            enabled=bool(vix.get("enabled", False)),
            symbol=str(vix.get("symbol", "VIX")),
            high_threshold=float(vix.get("high_threshold", 25.0)),
            inverted_curve_mode=str(vix.get("inverted_curve_mode", "capital_preservation")),
        ),
        yields=YieldsConfig(
            enabled=bool(yields.get("enabled", False)),
            provider=str(yields.get("provider", "default")),
            symbol_10y=str(yields.get("symbol_10y", "US10Y")),
            fred_series_10y=str(yields.get("fred_series_10y", "DGS10")),
            lookback_days=int(yields.get("lookback_days", 5)),
            relative_spike_threshold=float(yields.get("relative_spike_threshold", 0.05)),
            block_sectors=tuple(yields.get("block_sectors", ["Technology", "Tech", "Growth"])),
            block_high_beta=bool(yields.get("block_high_beta", True)),
            high_beta_threshold=float(yields.get("high_beta_threshold", 1.2)),
            risk_mult=float(yields.get("risk_mult", 0.6)),
            soft_max_positions=(
                int(yields["soft_max_positions"])
                if yields.get("soft_max_positions") not in {None, ""}
                else None
            ),
            soft_max_position_weight=(
                float(yields["soft_max_position_weight"])
                if yields.get("soft_max_position_weight") not in {None, ""}
                else None
            ),
            soft_max_sector_weight=(
                float(yields["soft_max_sector_weight"])
                if yields.get("soft_max_sector_weight") not in {None, ""}
                else None
            ),
            soft_max_gross_exposure=(
                float(yields["soft_max_gross_exposure"])
                if yields.get("soft_max_gross_exposure") not in {None, ""}
                else None
            ),
            hard_relative_spike_threshold=(
                float(yields["hard_relative_spike_threshold"])
                if yields.get("hard_relative_spike_threshold") not in {None, ""}
                else None
            ),
            hard_block_sectors=tuple(yields.get("hard_block_sectors", [])),
            hard_risk_mult=(
                float(yields["hard_risk_mult"])
                if yields.get("hard_risk_mult") not in {None, ""}
                else None
            ),
            hard_mode_live=str(yields.get("hard_mode_live", "close_only")),
            hard_mode_backtest=str(yields.get("hard_mode_backtest", "cash_only")),
            hard_requires_vix_high=bool(yields.get("hard_requires_vix_high", True)),
            hard_requires_sentiment_warning=bool(yields.get("hard_requires_sentiment_warning", True)),
            hard_max_positions=(
                int(yields["hard_max_positions"])
                if yields.get("hard_max_positions") not in {None, ""}
                else None
            ),
            hard_max_position_weight=(
                float(yields["hard_max_position_weight"])
                if yields.get("hard_max_position_weight") not in {None, ""}
                else None
            ),
            hard_max_sector_weight=(
                float(yields["hard_max_sector_weight"])
                if yields.get("hard_max_sector_weight") not in {None, ""}
                else None
            ),
            hard_max_gross_exposure=(
                float(yields["hard_max_gross_exposure"])
                if yields.get("hard_max_gross_exposure") not in {None, ""}
                else None
            ),
        ),
        sentiment_circuit_breaker=SentimentBreakerConfig(
            enabled=bool(breaker.get("enabled", False)),
            lookback_days=int(breaker.get("lookback_days", 7)),
            warning_threshold=float(breaker.get("warning_threshold", -0.15)),
            critical_threshold=float(breaker.get("critical_threshold", -0.30)),
            warning_max_positions=int(breaker.get("warning_max_positions", 2)),
            critical_mode_live=str(breaker.get("critical_mode_live", "close_only")),
            critical_mode_backtest=str(breaker.get("critical_mode_backtest", "cash_only")),
        ),
        sector_limits=SectorLimitsConfig(
            enabled=bool(sector_limits.get("enabled", False)),
            max_tickers_per_sector=int(sector_limits.get("max_tickers_per_sector", 2)),
        ),
        earnings_shield=EarningsShieldConfig(
            enabled=bool(earnings.get("enabled", False)),
            days_before=int(earnings.get("days_before", 2)),
            days_after=int(earnings.get("days_after", 2)),
            mode=str(earnings.get("mode", "strict_block")),
            negative_score_value=float(earnings.get("negative_score_value", -1.0)),
        ),
        buyback_blackout=BuybackBlackoutConfig(
            enabled=bool(buyback.get("enabled", False)),
            days_before_earnings=int(buyback.get("days_before_earnings", 14)),
            ml_score_multiplier=float(buyback.get("ml_score_multiplier", 0.70)),
        ),
        patterns=patterns,
    )


def parse_trailing_stop(raw: Mapping[str, Any] | None) -> TrailingStopYAMLConfig:
    raw = raw or {}
    return TrailingStopYAMLConfig(
        enabled=bool(raw.get("enabled", False)),
        mode=str(raw.get("mode", "fixed")),
        atr_period=int(raw.get("atr_period", 14)),
        atr_multiplier=float(raw.get("atr_multiplier", 2.5)),
        fallback_fixed_pct=float(raw.get("fallback_fixed_pct", 5.0)),
        break_even_after_atr_multiple=float(raw.get("break_even_after_atr_multiple", 2.0)),
        eod_check_time_est=str(raw.get("eod_check_time_est", "15:50")),
        apply_to_manual_orphan_buys=bool(raw.get("apply_to_manual_orphan_buys", True)),
    )


__all__ = [
    "CalendarPatternConfig",
    "VixConfig",
    "YieldsConfig",
    "SentimentBreakerConfig",
    "SectorLimitsConfig",
    "EarningsShieldConfig",
    "BuybackBlackoutConfig",
    "SentinelConfig",
    "MarketRegimesConfig",
    "TrailingStopYAMLConfig",
    "parse_market_regimes",
    "parse_trailing_stop",
]

