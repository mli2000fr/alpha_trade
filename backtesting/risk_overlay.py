"""
backtesting/risk_overlay.py
============================
Phase C — surcouches risk management appliquées par le simulateur :
- C1. Sizing pondéré par conviction.
- C2. Volatility targeting portefeuille.
- C3. Filtre régime à l'entrée.
- C4. Sectoral cap (max % equity par secteur).
- C5. Circuit breaker drawdown portefeuille.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd


SizingMode = Literal["equal_weight", "conviction_weighted"]


@dataclass(slots=True, frozen=True)
class SizingConfig:
    """Sizing config (equal_weight | conviction_weighted)."""

    mode: SizingMode = "equal_weight"
    min_weight_pct: float = 0.005
    max_weight_pct: float = 0.20

    def compute_weights(self, candidates: pd.DataFrame, max_positions: int) -> pd.Series:
        if candidates.empty:
            return pd.Series(dtype=float)
        if self.mode == "equal_weight" or "conviction" not in candidates.columns:
            base = 1.0 / max(max_positions, 1)
            return pd.Series(base, index=candidates.index, dtype=float)
        conv = candidates["conviction"].fillna(0.0).clip(lower=0.0)
        total = float(conv.sum())
        if total <= 0:
            base = 1.0 / max(max_positions, 1)
            return pd.Series(base, index=candidates.index, dtype=float)
        weights = conv / total
        weights = weights.clip(lower=self.min_weight_pct, upper=self.max_weight_pct)
        weights = weights / max(weights.sum(), 1e-9)
        return weights


@dataclass(slots=True, frozen=True)
class RegimeFilterConfig:
    """Filtre simple : interdit nouvelles entrées en régime bear (vs SMA)."""

    enabled: bool = False
    sma_window: int = 200
    bear_threshold: float = -0.02

    def is_entry_allowed(self, benchmark_close: pd.Series | None, as_of: pd.Timestamp) -> bool:
        if not self.enabled or benchmark_close is None or benchmark_close.empty:
            return True
        try:
            window = benchmark_close.loc[:as_of].tail(self.sma_window)
            if len(window) < self.sma_window // 2:
                return True
            sma = float(window.mean())
            spot = float(window.iloc[-1])
            if sma <= 0:
                return True
            distance = (spot / sma) - 1.0
            return distance > self.bear_threshold
        except Exception:
            return True


@dataclass(slots=True, frozen=True)
class SectoralCapConfig:
    """Cap d'exposition par secteur (en % equity)."""

    enabled: bool = False
    max_sector_exposure_pct: float = 0.40

    def is_entry_allowed(
        self,
        sector: str | None,
        sector_exposure_pct: float,
        candidate_weight_pct: float,
    ) -> bool:
        if not self.enabled or not sector or sector == "Unknown":
            return True
        return (sector_exposure_pct + candidate_weight_pct) <= self.max_sector_exposure_pct


@dataclass(slots=True)
class DrawdownCircuitBreaker:
    """Coupe les nouvelles entrées si DD > max_dd_pct."""

    enabled: bool = False
    max_dd_pct: float = 0.20
    recovery_pct: float = 0.95
    _tripped: bool = field(default=False, init=False)

    def update(self, equity: float, peak_equity: float) -> bool:
        if not self.enabled or peak_equity <= 0:
            return True
        dd = (equity / peak_equity) - 1.0
        if not self._tripped and dd <= -abs(self.max_dd_pct):
            self._tripped = True
        elif self._tripped and equity >= peak_equity * self.recovery_pct:
            self._tripped = False
        return not self._tripped


def compute_portfolio_vol_scaler(
    daily_returns: pd.Series,
    *,
    target_annual_vol: float,
    lookback: int = 60,
    floor: float = 0.25,
    cap: float = 1.5,
) -> float:
    """Scaler ∈ [floor, cap] qui ramène la vol réalisée à la cible."""
    if daily_returns.empty:
        return 1.0
    window = daily_returns.tail(lookback).dropna()
    if len(window) < max(20, lookback // 3):
        return 1.0
    realized = float(window.std(ddof=0)) * np.sqrt(252.0)
    if realized <= 0:
        return 1.0
    scaler = float(target_annual_vol) / realized
    return float(np.clip(scaler, floor, cap))


def snapshot_sector_exposure(
    positions: dict,
    close: pd.DataFrame,
    trade_day: pd.Timestamp,
    sector_map: dict,
    current_equity: float,
) -> dict:
    """Phase E.3.b — calcule l'exposition courante par secteur (en % equity).

    Extrait de ``simulator._try_open_entries`` pour rendre la logique
    testable sans construire un ``BacktestEngine`` complet. Tolérant aux
    symboles absents de ``close.columns`` : retombe sur ``entry_price``.

    Parameters
    ----------
    positions : dict[str, position-like]
        Doit exposer ``symbol``, ``quantity``, ``entry_price``, ``sector``.
    close : pd.DataFrame
        Pivot OHLCV ``close`` indexé par date, colonnes = symboles.
    trade_day : pd.Timestamp
        Jour de référence pour le mark-to-market.
    sector_map : dict[str, str]
        Fallback secteur si la position n'en porte pas.
    current_equity : float
        Equity courante (cash + positions). 0 → snapshot vide.

    Returns
    -------
    dict[str, float] : exposition par secteur (fraction equity).
    """
    from collections import defaultdict

    exposure: dict[str, float] = defaultdict(float)
    if current_equity <= 0:
        return exposure
    for pos in positions.values():
        symbol = getattr(pos, "symbol", None)
        if symbol is None:
            continue
        try:
            px = float(close.at[trade_day, symbol]) if symbol in close.columns else float(pos.entry_price)
        except (KeyError, ValueError):
            px = float(getattr(pos, "entry_price", 0.0))
        sector = getattr(pos, "sector", None) or sector_map.get(symbol, "Unknown")
        exposure[sector] += (float(pos.quantity) * px) / current_equity
    return exposure


@dataclass(slots=True)
class RiskOverlayConfig:
    """Bundle des surcouches risk Phase C."""

    sizing: SizingConfig = field(default_factory=SizingConfig)
    regime_filter: RegimeFilterConfig = field(default_factory=RegimeFilterConfig)
    sectoral_cap: SectoralCapConfig = field(default_factory=SectoralCapConfig)
    drawdown_breaker: DrawdownCircuitBreaker = field(default_factory=DrawdownCircuitBreaker)
    target_annual_vol: float | None = None

    def is_default(self) -> bool:
        return (
            self.sizing.mode == "equal_weight"
            and not self.regime_filter.enabled
            and not self.sectoral_cap.enabled
            and not self.drawdown_breaker.enabled
            and self.target_annual_vol is None
        )


__all__ = [
    "DrawdownCircuitBreaker",
    "RegimeFilterConfig",
    "RiskOverlayConfig",
    "SectoralCapConfig",
    "SizingConfig",
    "SizingMode",
    "compute_portfolio_vol_scaler",
    "snapshot_sector_exposure",
]

