"""Macro signals : VIX (high / inverted curve) + VXN (Nasdaq vol) + VIX3M
(term structure) + MOVE (bond vol) + RVX (Small Caps vol) + 10Y US Treasury.

Les sources externes sont **injectables** via le `Protocol` ``MacroDataProvider``.
Si aucun provider n'est branché, l'évaluation retourne un résultat neutre — ce
qui garantit que l'absence de donnée macro **ne bloque jamais** le pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


class MacroDataProvider(Protocol):
    """Interface minimale pour récupérer les niveaux macro nécessaires.

    Implémenter les méthodes en best-effort : retourner ``None`` quand la donnée
    n'est pas disponible. Aucune méthode n'est obligatoire de réussir.
    """

    # --- VIX family (S&P 500) ---
    def get_vix_close(self, trade_date: date) -> float | None: ...
    def get_vix_short_term_close(self, trade_date: date) -> float | None: ...  # ex VIX9D

    # --- VXN (Nasdaq-100 volatility) ---
    def get_vxn_close(self, trade_date: date) -> float | None: ...

    # --- VIX3M (3-month volatility, term structure) ---
    def get_vix3m_close(self, trade_date: date) -> float | None: ...

    # --- MOVE (ICE BofA Bond volatility) ---
    def get_move_close(self, trade_date: date) -> float | None: ...

    # --- RVX (Russell 2000 volatility, Small Caps) ---
    def get_rvx_close(self, trade_date: date) -> float | None: ...

    # --- US 10Y Treasury yield ---
    def get_us10y_history(self, trade_date: date, lookback_days: int) -> list[float] | None: ...


@dataclass(frozen=True, slots=True)
class MacroEvaluation:
    vix_value: float | None = None
    vix_curve_inverted: bool = False
    yield_10y_5d_pct: float | None = None
    vix_high: bool = False
    yield_spike: bool = False
    reasons: tuple[str, ...] = ()
    data_quality: dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.data_quality is None:
            object.__setattr__(self, "data_quality", {})


@dataclass(frozen=True, slots=True)
class VixTermStructure:
    """Résultat de l'évaluation de la structure à terme VIX/VIX3M."""

    vix_value: float | None = None
    vix3m_value: float | None = None
    ratio: float | None = None  # VIX / VIX3M ; > 1 = backwardation
    backwardation: bool = False
    data_quality: dict[str, str] = field(default_factory=dict)


def evaluate_vix(
    provider: MacroDataProvider | None,
    trade_date: date,
    *,
    high_threshold: float,
    inverted_curve_min_spread: float = 0.0,
    inverted_curve_min_ratio: float = 1.0,
) -> tuple[float | None, bool, bool, dict[str, str]]:
    """Retourne (vix_value, is_high, curve_inverted, data_quality)."""
    if provider is None:
        return None, False, False, {"vix": "no_provider"}
    try:
        v = provider.get_vix_close(trade_date)
    except Exception:
        return None, False, False, {"vix": "provider_error"}
    if v is None:
        return None, False, False, {"vix": "missing"}
    inverted = False
    try:
        short = provider.get_vix_short_term_close(trade_date)
        min_spread = max(0.0, float(inverted_curve_min_spread))
        min_ratio = max(1.0, float(inverted_curve_min_ratio))
        if (
            short is not None
            and v is not None
            and short > v
            and (short - v) >= min_spread
            and (short / v) >= min_ratio
        ):
            inverted = True
    except Exception:
        pass
    return v, v >= high_threshold, inverted, {"vix": "ok"}


def evaluate_vxn(
    provider: MacroDataProvider | None,
    trade_date: date,
    *,
    high_threshold: float,
) -> tuple[float | None, bool, dict[str, str]]:
    """Retourne (vxn_value, is_high, data_quality) — miroir Nasdaq de ``evaluate_vix``."""
    if provider is None:
        return None, False, {"vxn": "no_provider"}
    try:
        v = provider.get_vxn_close(trade_date)
    except Exception:
        return None, False, {"vxn": "provider_error"}
    if v is None:
        return None, False, {"vxn": "missing"}
    return v, v >= high_threshold, {"vxn": "ok"}


def evaluate_vix_term_structure(
    provider: MacroDataProvider | None,
    trade_date: date,
    *,
    backwardation_threshold: float = 1.0,
) -> VixTermStructure:
    """Évalue la structure à terme VIX/VIX3M (contango vs backwardation).

    - ``ratio > 1`` : le marché anticipe plus de stress à court terme qu'à 3 mois
      (backwardation) — signal de panique immédiate.
    - ``ratio < 1`` : contango normal, la volatilité future est plus chère.
    """
    if provider is None:
        return VixTermStructure(data_quality={"vix_term_structure": "no_provider"})
    dq: dict[str, str] = {}
    vix_value: float | None = None
    vix3m_value: float | None = None
    try:
        vix_value = provider.get_vix_close(trade_date)
    except Exception:
        dq["vix"] = "provider_error"
    try:
        vix3m_value = provider.get_vix3m_close(trade_date)
    except Exception:
        dq["vix3m"] = "provider_error"
    if vix_value is None:
        dq.setdefault("vix", "missing")
    if vix3m_value is None:
        dq.setdefault("vix3m", "missing")
    if not dq:
        dq["vix_term_structure"] = "ok"
    if vix_value is None or vix3m_value is None or vix3m_value <= 0:
        return VixTermStructure(
            vix_value=vix_value,
            vix3m_value=vix3m_value,
            backwardation=False,
            data_quality=dq,
        )
    ratio = vix_value / vix3m_value
    backwardation = ratio > backwardation_threshold
    return VixTermStructure(
        vix_value=vix_value,
        vix3m_value=vix3m_value,
        ratio=ratio,
        backwardation=backwardation,
        data_quality=dq,
    )


def evaluate_yield_10y(
    provider: MacroDataProvider | None,
    trade_date: date,
    *,
    lookback_days: int,
    relative_spike_threshold: float,
) -> tuple[float | None, bool, dict[str, str]]:
    """Retourne (relative_change, is_spike, data_quality)."""
    if provider is None:
        return None, False, {"yield_10y": "no_provider"}
    try:
        history = provider.get_us10y_history(trade_date, lookback_days)
    except Exception:
        return None, False, {"yield_10y": "provider_error"}
    if not history or len(history) < 2:
        return None, False, {"yield_10y": "missing"}
    start = history[0]
    end = history[-1]
    if start is None or end is None or start <= 0:
        return None, False, {"yield_10y": "invalid"}
    rel = (end - start) / start
    return rel, rel >= relative_spike_threshold, {"yield_10y": "ok"}


__all__ = [
    "MacroDataProvider",
    "MacroEvaluation",
    "VixTermStructure",
    "evaluate_vix",
    "evaluate_vxn",
    "evaluate_vix_term_structure",
    "evaluate_yield_10y",
]

