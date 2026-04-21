from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class StrictFilterProfile:
    """Profil de seuils partagé entre scanner live, backfill PIT et reruns backtest."""

    name: str
    min_close: float
    min_avg_dollar_volume_20d: float
    max_volatility_ratio: float

    def __post_init__(self) -> None:
        if self.min_close <= 0:
            raise ValueError("min_close doit être strictement positif.")
        if self.min_avg_dollar_volume_20d <= 0:
            raise ValueError("min_avg_dollar_volume_20d doit être strictement positif.")
        if self.max_volatility_ratio <= 0:
            raise ValueError("max_volatility_ratio doit être strictement positif.")

    def to_backtest_filter_dict(self) -> dict[str, float]:
        return {
            "min_close": self.min_close,
            "min_avg_dollar_volume_20d": self.min_avg_dollar_volume_20d,
            "max_volatility_ratio": self.max_volatility_ratio,
        }

    def to_scanner_config_kwargs(self) -> dict[str, float]:
        return {
            "min_close": self.min_close,
            "liquidity_threshold": self.min_avg_dollar_volume_20d,
            "max_volatility_ratio": self.max_volatility_ratio,
        }

    def apply_to_frame(
        self,
        frame: pd.DataFrame,
        *,
        close_col: str = "latest_close",
        adv_col: str = "avg_dollar_volume_20d",
        volatility_ratio_col: str = "volatility_ratio",
    ) -> pd.DataFrame:
        if frame.empty:
            return frame.copy()

        required = {close_col, adv_col, volatility_ratio_col}
        missing = sorted(required.difference(frame.columns))
        if missing:
            raise ValueError(f"Colonnes manquantes pour appliquer le profil {self.name}: {missing}")

        filtered = frame[
            (frame[close_col] >= self.min_close)
            & (frame[adv_col] >= self.min_avg_dollar_volume_20d)
            & frame[volatility_ratio_col].notna()
            & (frame[volatility_ratio_col] <= self.max_volatility_ratio)
        ]
        return filtered.copy()


STRICT_SWING_CASH_FILTERS = StrictFilterProfile(
    name="strict_swing_cash",
    min_close=10.0,
    min_avg_dollar_volume_20d=30_000_000.0,
    max_volatility_ratio=0.9,
)

