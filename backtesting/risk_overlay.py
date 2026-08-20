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

import numpy as np
import pandas as pd

# ── P2-1 : SizingConfig partagé avec le live (common/sizing.py) ──
from common.sizing import SizingConfig, SizingMode



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
class BullStrictConfig:
    """P2-3 — overlay no-trades en bull strict.

    Bull strict = ``SPY > SMA(sma_window)`` **ET** rendement SPY sur
    ``ret_window`` séances > ``ret_threshold``.

    - ``mode="no_shorts"`` : bloque uniquement les nouvelles entrées short.
    - ``mode="no_trades"`` : bloque toutes les nouvelles entrées (long+short).

    Post-hoc B25 : shorts bull strict = −11.8k sur 98 trades ; couper →
    +9.4% PnL, DD −4 pts ; couper tous trades → +10.7%, DD −10 pts.
    """

    enabled: bool = False
    mode: Literal["no_shorts", "no_trades"] = "no_shorts"
    sma_window: int = 200
    ret_window: int = 60
    ret_threshold: float = 0.03

    def is_bull_strict(self, benchmark_close: pd.Series | None, as_of: pd.Timestamp) -> bool:
        if not self.enabled or benchmark_close is None or benchmark_close.empty:
            return False
        try:
            hist = benchmark_close.loc[:as_of].dropna()
            if len(hist) < max(self.sma_window // 2, 40):
                return False
            sma = float(hist.tail(self.sma_window).mean())
            spot = float(hist.iloc[-1])
            if sma <= 0 or spot <= 0:
                return False
            above_sma = spot > sma
            ret = (spot / float(hist.iloc[-(self.ret_window + 1)]) - 1.0) if len(hist) > self.ret_window else 0.0
            return bool(above_sma and ret > self.ret_threshold)
        except Exception:
            return False

    def is_entry_allowed(
        self,
        side: str,
        benchmark_close: pd.Series | None,
        as_of: pd.Timestamp,
    ) -> bool:
        if not self.is_bull_strict(benchmark_close, as_of):
            return True
        if self.mode == "no_trades":
            return False
        # no_shorts : seuls les shorts sont bloqués
        return str(side or "").strip().lower() != "sell"


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
    """Coupe les nouvelles entrées si DD > max_dd_pct, avec ramp-up régimed.

    Quand le breaker est trippé, l'allocation dégradée de base
    (``degraded_entry_allocation_pct``) peut être progressivement augmentée
    si le régime de marché repasse en ``normal`` **et** que l'equity
    progresse par rapport à la veille. Le bonus quotidien est
    ``regime_ramp_up_pct_per_day``, plafonné à ``regime_ramp_up_max_pct``.

    Si le régime est normal mais que l'equity stagne ou baisse, le streak
    est gelé (pas d'incrément, pas de reset). Dès que le régime quitte
    ``normal``, le streak est remis à zéro.
    """

    enabled: bool = False
    max_dd_pct: float = 0.20
    recovery_pct: float = 0.92
    rolling_peak_window_days: int = 252
    degraded_entry_allocation_pct: float = 0.0
    # Ramp-up progressif quand le régime redevient normal ET l'equity monte
    regime_ramp_up_enabled: bool = False
    regime_ramp_up_pct_per_day: float = 0.025
    regime_ramp_up_max_pct: float = 0.40
    # Fenêtre glissante pour le « pic sur N jours » : le streak s'incrémente
    # dès que l'equity dépasse le max des N jours précédents (et pas seulement
    # la veille), ce qui rend le ramp-up résilient aux jours de stagnation.
    regime_ramp_up_peak_window_days: int = 5
    # Force-close : liquide toutes les positions quand le breaker trippe.
    force_close_on_breaker: bool = False
    force_close_pct: float = 0.50  # fraction liquidée (1.0 = tout)
    # E19 — coupe TOUS les symboles perdants (down en long, up en short) au
    # déclenchement, au lieu d'une fraction (force_close_pct) des pires PnL.
    force_close_losers_on_breaker: bool = False
    _tripped: bool = field(default=False, init=False)
    _was_tripped: bool = field(default=False, init=False)
    _equity_window: list[float] = field(default_factory=list, init=False)
    _normal_streak: int = field(default=0, init=False)
    _equity_prev: float = field(default=0.0, init=False)
    _equity_peak_window: list[float] = field(default_factory=list, init=False)

    def _reference_peak(self, peak_equity: float) -> float:
        if self.rolling_peak_window_days <= 0:
            return float(peak_equity)
        if not self._equity_window:
            return float(peak_equity)
        return float(max(self._equity_window))

    def allocation_scale(self, entry_mode: str | None = None, side: str | None = None) -> float:
        """Retourne l'échelle d'allocation courante.

        - 1.0 si le breaker n'est pas trippé.
        - ``degraded_entry_allocation_pct`` si trippé sans ramp-up.
        - valeur rampée si trippé + régime normal depuis N séances.

        Sprint 2 — ``side`` permet un scaling différent long/short (réservé).
        Pour l'instant, le même scale s'applique aux deux directions.
        """
        _ = side  # reserved for future per-side scaling
        if not self._tripped:
            return 1.0
        base = float(np.clip(self.degraded_entry_allocation_pct, 0.0, 1.0))
        if not self.regime_ramp_up_enabled or not entry_mode:
            return base
        if str(entry_mode).strip().lower() == "normal" and self._normal_streak > 0:
            ramp_bonus = float(self._normal_streak) * float(self.regime_ramp_up_pct_per_day)
            return float(np.clip(base + ramp_bonus, base, float(self.regime_ramp_up_max_pct)))
        return base

    def update_regime_streak(self, entry_mode: str | None, current_equity: float = 0.0) -> None:
        """Met à jour le compteur de jours de recovery.

        Doit être appelé une fois par jour de trading, après ``update()``.
        Le streak n'est incrémenté que si :
        - le breaker est trippé,
        - le régime est ``normal``,
        - l'equity du jour établit un nouveau pic sur la fenêtre glissante
          des N derniers jours (``regime_ramp_up_peak_window_days``).

        Cela rend le ramp-up résilient aux jours de stagnation : le streak
        progresse dès que l'equity dépasse le meilleur niveau récent, sans
        exiger une hausse quotidienne stricte.

        Si le régime est normal mais que l'equity ne fait pas de nouveau pic,
        le streak reste inchangé (gelé, pas de reset).
        Tout régime non-normal remet le compteur à zéro.
        """
        if not self.regime_ramp_up_enabled or not self._tripped:
            self._normal_streak = 0
            self._equity_peak_window.clear()
            return
        if entry_mode and str(entry_mode).strip().lower() == "normal":
            # Alimente la fenêtre glissante des N derniers jours
            if np.isfinite(current_equity) and current_equity > 0:
                self._equity_peak_window.append(float(current_equity))
                peak_window = int(self.regime_ramp_up_peak_window_days)
                if peak_window > 0 and len(self._equity_peak_window) > peak_window:
                    self._equity_peak_window = self._equity_peak_window[-peak_window:]
            # Incrémente le streak si l'equity du jour bat le pic des jours précédents
            if len(self._equity_peak_window) >= 2:
                previous_peak = max(self._equity_peak_window[:-1])
                if current_equity > previous_peak:
                    self._normal_streak += 1
            # else: streak gelé (normal mais equity ne fait pas de nouveau pic)
        else:
            self._normal_streak = 0
            self._equity_peak_window.clear()

    def update(self, equity: float, peak_equity: float) -> bool:
        if not self.enabled or peak_equity <= 0:
            return True
        # Calculer le pic de référence sur l'historique EXISTANT (avant aujourd'hui)
        reference_peak = self._reference_peak(peak_equity)
        # Enregistrer l'equity du jour pour les prochains appels
        if np.isfinite(equity) and equity > 0:
            self._equity_window.append(float(equity))
            if self.rolling_peak_window_days > 0 and len(self._equity_window) > self.rolling_peak_window_days:
                self._equity_window = self._equity_window[-self.rolling_peak_window_days :]
        if reference_peak <= 0:
            return True
        dd = (equity / reference_peak) - 1.0
        self._was_tripped = self._tripped
        if not self._tripped and dd <= -abs(self.max_dd_pct):
            self._tripped = True
        elif self._tripped and equity >= reference_peak * self.recovery_pct:
            self._tripped = False
            self._normal_streak = 0
            self._equity_peak_window.clear()
            self._normal_streak = 0
        return not self._tripped

    def just_tripped(self) -> bool:
        """Retourne True si le breaker vient de se déclencher CE JOUR."""
        return self._tripped and not self._was_tripped


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
    bull_strict: BullStrictConfig = field(default_factory=BullStrictConfig)
    sectoral_cap: SectoralCapConfig = field(default_factory=SectoralCapConfig)
    drawdown_breaker: DrawdownCircuitBreaker = field(default_factory=DrawdownCircuitBreaker)
    target_annual_vol: float | None = None

    def is_default(self) -> bool:
        return (
            self.sizing.mode == "equal_weight"
            and not self.regime_filter.enabled
            and not self.bull_strict.enabled
            and not self.sectoral_cap.enabled
            and not self.drawdown_breaker.enabled
            and self.target_annual_vol is None
        )


__all__ = [
    "BullStrictConfig",
    "DrawdownCircuitBreaker",
    "RegimeFilterConfig",
    "RiskOverlayConfig",
    "SectoralCapConfig",
    "SizingConfig",
    "SizingMode",
    "compute_portfolio_vol_scaler",
    "snapshot_sector_exposure",
]
