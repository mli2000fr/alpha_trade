"""Sprint S7 — `AlphaScannerConfig` + constantes module ``selector``.

Extrait de ``selector.alpha_scanner`` (Phase 3.3.a → S7) pour découpler
la configuration de l'orchestration. Tout est ré-exporté par le shim
``selector.alpha_scanner`` afin de préserver l'API historique.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.filter_profiles import STRICT_SWING_CASH_FILTERS, StrictFilterProfile

RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
PRICE_COLUMNS = ["symbol", "date", "close", "volume", "high", "low"]


@dataclass(frozen=True, slots=True)
class AlphaScannerConfig:
    price_table: str = "stock_bars_daily"
    score_table: str = "stock_scores"
    chunk_size: int = 500
    selection_size: int = 100
    min_history_days: int = 252
    liquidity_threshold: float = 20_000_000.0
    min_close: float = 5.0
    max_volatility_ratio: float | None = None
    min_relative_strength_index: float | None = None
    min_high_52w_proximity: float | None = None
    min_weekly_trend_score: float | None = None
    min_atr_pct_20: float | None = None
    max_atr_pct_20: float | None = None
    min_market_cap: float | None = None
    min_beta_126: float | None = None
    max_spread_bps: float | None = None
    # Phase 3.3.c — extensions IEX : relâchement contrôlé du filtre spread.
    max_spread_bps_iex: float | None = None
    min_quote_size: float | None = None
    # Phase 3.3.d — TTL appliqué au filtre ``min_market_cap``.
    market_cap_max_age_days: int | None = None
    earnings_blackout_days: int | None = None
    require_above_ma200: bool = False
    max_anomaly_count: int = 20
    max_missing_days_count: int = 10
    sector_cap_ratio: float = 0.30
    volatility_short_window: int = 10
    volatility_long_window: int = 60
    vcp_ratio_threshold: float = 0.60
    ma_short_window: int = 50
    ma_mid_window: int = 150
    ma_long_window: int = 200
    trailing_range_window: int = 252
    liquidity_lookback_days: int = 20
    update_batch_size: int = 500
    max_workers: int | None = None

    # Composition multi-facteurs : poids configurables.
    weight_trend_vcp: float = 0.50
    weight_total_score: float = 0.30
    weight_rsi: float = 0.20

    # Winsorisation (anti-outliers).
    winsor_lower_pct: float = 0.01
    winsor_upper_pct: float = 0.99

    # Neutralisation cross-sectorielle (P0).
    neutralize_by_sector: bool = True

    @classmethod
    def from_filter_profile(
        cls,
        profile: StrictFilterProfile,
        **overrides: object,
    ) -> "AlphaScannerConfig":
        merged_kwargs: dict[str, object] = dict(profile.to_scanner_config_kwargs())
        # Phase 3.3.c/d — merger les extensions IEX/TTL.
        for key, value in profile.iex_extensions().items():
            if value is not None:
                merged_kwargs[key] = value
        for key, value in overrides.items():
            merged_kwargs[key] = value
        return cls(**merged_kwargs)

    @classmethod
    def strict_swing_cash(cls, **overrides: object) -> "AlphaScannerConfig":
        return cls.from_filter_profile(STRICT_SWING_CASH_FILTERS, **overrides)

    def __post_init__(self) -> None:
        if self.chunk_size < 1:
            raise ValueError("chunk_size doit être supérieur ou égal à 1.")
        if self.selection_size < 1:
            raise ValueError("selection_size doit être supérieur ou égal à 1.")
        if self.min_history_days < self.trailing_range_window:
            raise ValueError("min_history_days doit être supérieur ou égal à trailing_range_window.")
        if self.liquidity_threshold <= 0:
            raise ValueError("liquidity_threshold doit être strictement positif.")
        if self.min_close <= 0:
            raise ValueError("min_close doit être strictement positif.")
        if self.max_volatility_ratio is not None and self.max_volatility_ratio <= 0:
            raise ValueError("max_volatility_ratio doit être strictement positif lorsqu'il est renseigné.")
        if self.min_relative_strength_index is not None and self.min_relative_strength_index <= 0:
            raise ValueError("min_relative_strength_index doit être strictement positif lorsqu'il est renseigné.")
        if self.min_high_52w_proximity is not None and not 0 < self.min_high_52w_proximity <= 1:
            raise ValueError("min_high_52w_proximity doit être compris dans ]0, 1] lorsqu'il est renseigné.")
        if self.min_weekly_trend_score is not None and not 0 <= self.min_weekly_trend_score <= 1:
            raise ValueError("min_weekly_trend_score doit être compris dans [0, 1] lorsqu'il est renseigné.")
        if self.min_atr_pct_20 is not None and self.min_atr_pct_20 <= 0:
            raise ValueError("min_atr_pct_20 doit être strictement positif lorsqu'il est renseigné.")
        if self.max_atr_pct_20 is not None and self.max_atr_pct_20 <= 0:
            raise ValueError("max_atr_pct_20 doit être strictement positif lorsqu'il est renseigné.")
        if self.min_market_cap is not None and self.min_market_cap <= 0:
            raise ValueError("min_market_cap doit être strictement positif lorsqu'il est renseigné.")
        if self.min_beta_126 is not None and self.min_beta_126 <= 0:
            raise ValueError("min_beta_126 doit être strictement positif lorsqu'il est renseigné.")
        if self.max_spread_bps is not None and self.max_spread_bps <= 0:
            raise ValueError("max_spread_bps doit être strictement positif lorsqu'il est renseigné.")
        if self.max_spread_bps_iex is not None and self.max_spread_bps_iex <= 0:
            raise ValueError("max_spread_bps_iex doit être strictement positif lorsqu'il est renseigné.")
        if (
            self.max_spread_bps is not None
            and self.max_spread_bps_iex is not None
            and self.max_spread_bps_iex < self.max_spread_bps
        ):
            raise ValueError(
                "max_spread_bps_iex doit être >= max_spread_bps (relâchement IEX, pas durcissement)."
            )
        if self.min_quote_size is not None and self.min_quote_size < 0:
            raise ValueError("min_quote_size doit être positif ou nul lorsqu'il est renseigné.")
        if self.market_cap_max_age_days is not None and self.market_cap_max_age_days < 0:
            raise ValueError("market_cap_max_age_days doit être positif ou nul lorsqu'il est renseigné.")
        if self.earnings_blackout_days is not None and self.earnings_blackout_days < 0:
            raise ValueError("earnings_blackout_days doit être positif ou nul lorsqu'il est renseigné.")
        if (
            self.min_atr_pct_20 is not None
            and self.max_atr_pct_20 is not None
            and self.min_atr_pct_20 > self.max_atr_pct_20
        ):
            raise ValueError("min_atr_pct_20 ne peut pas être supérieur à max_atr_pct_20.")
        if not 0 < self.sector_cap_ratio <= 1:
            raise ValueError("sector_cap_ratio doit être compris entre 0 exclus et 1 inclus.")
        if self.volatility_short_window < 2 or self.volatility_long_window <= self.volatility_short_window:
            raise ValueError("Les fenêtres de volatilité sont invalides.")
        if self.vcp_ratio_threshold <= 0:
            raise ValueError("vcp_ratio_threshold doit être strictement positif.")
        if self.update_batch_size < 1:
            raise ValueError("update_batch_size doit être supérieur ou égal à 1.")
        if self.max_workers is not None and self.max_workers < 1:
            raise ValueError("max_workers doit être supérieur ou égal à 1.")
        total_weight = self.weight_trend_vcp + self.weight_total_score + self.weight_rsi
        if not np.isclose(total_weight, 1.0, atol=1e-6):
            raise ValueError(
                f"La somme des poids facteurs doit être égale à 1.0 "
                f"(weight_trend_vcp + weight_total_score + weight_rsi = {total_weight:.6f})."
            )
        if not 0.0 <= self.winsor_lower_pct < self.winsor_upper_pct <= 1.0:
            raise ValueError("winsor_lower_pct et winsor_upper_pct doivent respecter 0 ≤ lower < upper ≤ 1.")


__all__ = ["AlphaScannerConfig", "PRICE_COLUMNS", "RUN_SUMMARY_PREFIX"]

