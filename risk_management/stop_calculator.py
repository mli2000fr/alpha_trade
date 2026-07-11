"""risk_management/stop_calculator.py — Calculateur de stops directionnels (Sprint Maître 12).

Calcule les niveaux de protection par side et régime :
- Stop initial (long sous l'entrée, short au-dessus)
- Take profit
- Trailing stop
- Break-even
- Time stop
- Recalcul après fill (quantité et prix réels)

Usage ::

    from risk_management.stop_calculator import (
        StopCalculator, StopLevels, compute_initial_stop_price,
    )
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# ── StopLevels ──────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class StopLevels:
    """Niveaux de protection calculés pour une position (Sprint Maître 12).

    Tous les prix sont directionnels :
    - Long : stop sous l'entrée, TP au-dessus
    - Short : stop au-dessus de l'entrée, TP en-dessous

    Attributes
    ----------
    symbol : str
    side : str
    entry_price : float
        Prix d'entrée attendu.
    stop_price : float
        Prix du stop initial.
    stop_distance_pct : float
        Distance du stop en % (toujours positive).
    take_profit_price : float | None
        Prix du take profit.
    tp_distance_pct : float | None
        Distance du TP en %.
    trailing_activation_price : float | None
        Prix d'activation du trailing stop.
    break_even_price : float | None
        Prix de break-even.
    atr : float | None
        ATR utilisé pour le calcul.
    risk_per_share : float
        Risque par titre en dollars (stop_distance × prix).
    risk_total : float | None
        Risque total en dollars (risk_per_share × quantity).
    time_stop_sessions : int | None
        Nombre de sessions max avant time stop.
    """

    symbol: str
    side: str
    entry_price: float = 0.0
    stop_price: float = 0.0
    stop_distance_pct: float = 0.0
    take_profit_price: float | None = None
    tp_distance_pct: float | None = None
    trailing_activation_price: float | None = None
    break_even_price: float | None = None
    atr: float | None = None
    risk_per_share: float = 0.0
    risk_total: float | None = None
    time_stop_sessions: int | None = None

    def __post_init__(self) -> None:
        if self.side not in ("long", "short"):
            raise ValueError(f"side invalide: {self.side!r}")

    @property
    def is_valid(self) -> bool:
        """True si le stop est du bon côté de l'entrée."""
        if self.side == "long":
            return self.stop_price < self.entry_price
        else:
            return self.stop_price > self.entry_price

    @property
    def is_tp_valid(self) -> bool | None:
        """True si le TP est du bon côté."""
        if self.take_profit_price is None:
            return None
        if self.side == "long":
            return self.take_profit_price > self.entry_price
        else:
            return self.take_profit_price < self.entry_price

    def recalculate_after_fill(
        self,
        fill_price: float,
        fill_quantity: float,
    ) -> "StopLevels":
        """Recalcule les stops après fill avec le prix et la quantité réels.

        Le stop initial est recentré sur le prix de fill réel.
        Le risque total est recalculé avec la quantité réelle.

        Parameters
        ----------
        fill_price : float
            Prix de fill réel.
        fill_quantity : float
            Quantité réellement filled.

        Returns
        -------
        StopLevels
        """
        stop_dist = self.stop_distance_pct
        atr = self.atr

        if self.side == "long":
            new_stop = fill_price * (1.0 - stop_dist)
            new_tp = fill_price * (1.0 + self.tp_distance_pct) if self.tp_distance_pct else None
        else:
            new_stop = fill_price * (1.0 + stop_dist)
            new_tp = fill_price * (1.0 - self.tp_distance_pct) if self.tp_distance_pct else None

        risk_per_share = abs(fill_price - new_stop)
        risk_total = risk_per_share * fill_quantity

        return StopLevels(
            symbol=self.symbol,
            side=self.side,
            entry_price=fill_price,
            stop_price=round(new_stop, 2),
            stop_distance_pct=stop_dist,
            take_profit_price=round(new_tp, 2) if new_tp else None,
            tp_distance_pct=self.tp_distance_pct,
            trailing_activation_price=(
                round(fill_price * (1.0 + self.stop_distance_pct * 1.5), 2)
                if self.side == "long" and self.trailing_activation_price is not None
                else round(fill_price * (1.0 - self.stop_distance_pct * 1.5), 2)
                if self.side == "short" and self.trailing_activation_price is not None
                else None
            ),
            break_even_price=round(fill_price, 2),
            atr=atr,
            risk_per_share=round(risk_per_share, 4),
            risk_total=round(risk_total, 2),
            time_stop_sessions=self.time_stop_sessions,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": round(self.entry_price, 2),
            "stop_price": round(self.stop_price, 2),
            "stop_distance_pct": round(self.stop_distance_pct, 4),
            "take_profit_price": round(self.take_profit_price, 2) if self.take_profit_price else None,
            "tp_distance_pct": round(self.tp_distance_pct, 4) if self.tp_distance_pct else None,
            "atr": round(self.atr, 4) if self.atr is not None else None,
            "risk_per_share": round(self.risk_per_share, 4),
            "risk_total": round(self.risk_total, 2) if self.risk_total else None,
            "time_stop_sessions": self.time_stop_sessions,
            "is_valid": self.is_valid,
        }


# ── StopCalculator ──────────────────────────────────────────────────────────


@dataclass
class StopCalculator:
    """Calcule les niveaux de protection par side et régime (Sprint Maître 12).

    Parameters
    ----------
    atr_stop_multiple : float
        Multiple d'ATR pour le stop initial (défaut 2.0).
    tp_atr_multiple : float | None
        Multiple d'ATR pour le take profit (None = pas de TP).
    trailing_activation_r_multiple : float
        Multiple de R pour activer le trailing (défaut 1.0 = 1R).
    break_even_r_multiple : float
        Multiple de R pour activer le break-even (défaut 0.5 = 0.5R).
    time_stop_sessions : int | None
        Sessions max avant time stop.
    min_stop_distance_pct : float
        Distance minimale du stop en % (évite stops trop serrés).
    max_stop_distance_pct : float
        Distance maximale du stop en % (évite stops trop larges).
    """

    atr_stop_multiple: float = 2.0
    tp_atr_multiple: float | None = 3.0
    trailing_activation_r_multiple: float = 1.0
    break_even_r_multiple: float = 0.5
    time_stop_sessions: int | None = None
    min_stop_distance_pct: float = 0.005  # 0.5%
    max_stop_distance_pct: float = 0.15   # 15%

    def compute(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        *,
        atr: float | None = None,
        quantity: float | None = None,
        is_defensive_regime: bool = False,
    ) -> StopLevels:
        """Calcule les niveaux de protection pour une position.

        Parameters
        ----------
        symbol : str
        side : str
        entry_price : float
        atr : float | None
        quantity : float | None
        is_defensive_regime : bool
            Si True, stops plus serrés, TP plus proches.

        Returns
        -------
        StopLevels
        """
        # ── Stop distance ──────────────────────────────────────────────
        if atr is not None and atr > 0 and entry_price > 0:
            stop_distance_pct = (atr * self.atr_stop_multiple) / entry_price
        else:
            stop_distance_pct = 0.03  # 3% par défaut sans ATR

        # Régime défensif → stops plus serrés
        if is_defensive_regime:
            stop_distance_pct *= 0.7
            if self.tp_atr_multiple is not None:
                self.tp_atr_multiple *= 0.7

        # Clamp
        stop_distance_pct = max(self.min_stop_distance_pct, min(stop_distance_pct, self.max_stop_distance_pct))

        # ── Stop price (directionnel) ──────────────────────────────────
        if side == "long":
            stop_price = entry_price * (1.0 - stop_distance_pct)
        else:
            stop_price = entry_price * (1.0 + stop_distance_pct)

        # ── Take profit ────────────────────────────────────────────────
        tp_price = None
        tp_distance_pct = None
        if self.tp_atr_multiple is not None and atr is not None and atr > 0:
            tp_distance_pct = (atr * self.tp_atr_multiple) / entry_price
            tp_distance_pct = min(tp_distance_pct, 0.30)  # Cap 30%
            if side == "long":
                tp_price = entry_price * (1.0 + tp_distance_pct)
            else:
                tp_price = entry_price * (1.0 - tp_distance_pct)

        # ── Trailing activation ────────────────────────────────────────
        trail_activation = None
        if atr is not None and atr > 0:
            r_distance = atr * self.atr_stop_multiple * self.trailing_activation_r_multiple
            if side == "long":
                trail_activation = entry_price + r_distance
            else:
                trail_activation = entry_price - r_distance

        # ── Break-even ─────────────────────────────────────────────────
        be_price = None
        if atr is not None and atr > 0:
            be_distance = atr * self.atr_stop_multiple * self.break_even_r_multiple
            if side == "long":
                be_price = entry_price + be_distance
            else:
                be_price = entry_price - be_distance

        # ── Risk ───────────────────────────────────────────────────────
        risk_per_share = abs(entry_price - stop_price)
        risk_total = risk_per_share * quantity if quantity is not None else None

        # ── Time stop ──────────────────────────────────────────────────
        time_stop = self.time_stop_sessions
        if is_defensive_regime and time_stop is not None:
            time_stop = max(1, int(time_stop * 0.5))  # Plus rapide en défensif

        return StopLevels(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            stop_price=round(stop_price, 2),
            stop_distance_pct=round(stop_distance_pct, 4),
            take_profit_price=round(tp_price, 2) if tp_price else None,
            tp_distance_pct=round(tp_distance_pct, 4) if tp_distance_pct else None,
            trailing_activation_price=round(trail_activation, 2) if trail_activation else None,
            break_even_price=round(be_price, 2) if be_price else None,
            atr=atr,
            risk_per_share=round(risk_per_share, 4),
            risk_total=round(risk_total, 2) if risk_total else None,
            time_stop_sessions=time_stop,
        )

    def compute_for_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        atr: float | None = None,
        quantity: float | None = None,
        *,
        is_defensive_regime: bool = False,
    ) -> StopLevels:
        """Alias de compute() pour usage direct."""
        return self.compute(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            atr=atr,
            quantity=quantity,
            is_defensive_regime=is_defensive_regime,
        )


# ── Helpers ─────────────────────────────────────────────────────────────────


def compute_initial_stop_price(
    side: str,
    entry_price: float,
    atr: float | None = None,
    *,
    atr_stop_multiple: float = 2.0,
    min_stop_pct: float = 0.005,
    max_stop_pct: float = 0.15,
) -> float:
    """Calcule le prix du stop initial (fonction pure).

    Parameters
    ----------
    side : str
        "long" ou "short".
    entry_price : float
    atr : float | None
    atr_stop_multiple : float
    min_stop_pct : float
    max_stop_pct : float

    Returns
    -------
    float
        Prix du stop.
    """
    if atr is not None and atr > 0 and entry_price > 0:
        stop_pct = (atr * atr_stop_multiple) / entry_price
    else:
        stop_pct = 0.03

    stop_pct = max(min_stop_pct, min(stop_pct, max_stop_pct))

    if side == "long":
        return round(entry_price * (1.0 - stop_pct), 2)
    else:
        return round(entry_price * (1.0 + stop_pct), 2)


def compute_stop_distance_pct(
    atr: float,
    entry_price: float,
    atr_stop_multiple: float = 2.0,
) -> float:
    """Calcule la distance du stop en %."""
    if entry_price <= 0 or atr <= 0:
        return 0.03
    return (atr * atr_stop_multiple) / entry_price


def is_stop_valid(side: str, entry_price: float, stop_price: float) -> bool:
    """Vérifie que le stop est du bon côté de l'entrée."""
    if side == "long":
        return stop_price < entry_price
    elif side == "short":
        return stop_price > entry_price
    return False
